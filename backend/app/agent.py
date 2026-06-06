import json
from typing import Any, Dict, List, Tuple
from openai import OpenAI

from config import settings
from tools import openai_tools_schema, execute_tool
from models import GuardrailResult, ToolCallRecord
from observability import record_guardrail

client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_POLICY = """You are a travel planning assistant
Rules:
- Only help with travel planning (itinerary, logistics, suggestions).
- Use tools when helpful (weather, flights).
- Never provide illegal or unsafe guidance
- Do not execute bookings without explicit user confirmation.
- If you mention visa/ entry requirements, advise verifying official sources.
Return a markdown itinerary with a day-by-day plan.
"""

def run_agent(user_prompt: str) -> Tuple[str, List[GuardrailResult], List[ToolCallRecord]]:
    tools = openai_tools_schema()
    # The incoming text is a tuple, since it is a JSON from the front end. Join this to make a string
    regex_safe_user_prompt = ' '.join(user_prompt)

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_POLICY},
        {"role": "user", "content": regex_safe_user_prompt},
    ]

    guardrails: List[GuardrailResult] = []
    tool_records: List[ToolCallRecord] = []
    tool_calls_used = 0

    for _step in range(8):
        resp = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            tools=tools,
        )

        msg = resp.choices[0].message
        messages.append({"role": msg.role, "content": msg.content, "tool_calls": msg.tool_calls})

        if not getattr(msg, "tool_calls", None):
            return msg.content or "", guardrails, tool_records
        if tool_calls_used + len(msg.tool_calls) > settings.MAX_TOOL_CALLS:
            name = "tool.budget"
            reason = f"Exceeded max tool calls ({settings.MAX_TOOL_CALLS})"
            record_guardrail(name, "execution", "limit", reason, max=settings.MAX_TOOL_CALLS)
            guardrails.append(GuardrailResult(name=name, stage="execution", action="limit", reason=reason))
            messages.append({"role": "user", "content": "Proceed without any more tool calls. Provide the best itinerary with current context."})
            continue

        for tc in msg.tool_calls:
            tool_calls_used += 1
            tool_name = tc.function.name
            raw_args = json.loads(tc.function.arguments or "{}")

            tool_output, g_tool, record = execute_tool(tool_name, raw_args)
            guardrails.extend(g_tool)
            tool_records.append(record)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tool_name,
                "content": json.dumps(tool_output),
            })

            if record.status == "requires_user_confirmation":
                messages.append({
                    "role": "user",
                    "content": "The booking requires user confirmation. Do NOT proceed. Provide alternatives and ask user for confirmation",
                })

        name = "agent.max_steps"
        reason = "Reached max agent steps"
        record_guardrail(name, "execution", "warn", reason)
        guardrails.append(GuardrailResult(name=name, stage="execution", action="warn", reason=reason))
        return "I generated a partial plan. Please refine your request.", guardrails, tool_records
    return None