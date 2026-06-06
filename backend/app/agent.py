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
    max_agent_steps = 8

    # Do not use a while (true) and max the number of attempts at 8
    for _step in range(max_agent_steps):
        resp = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            tools=tools,
        )

        # Dump the response from OpenAI if you wish to debug
        # print(json.dumps(resp.model_dump(), indent=2))

        msg = resp.choices[0].message
        messages.append({"role": msg.role, "content": msg.content, "tool_calls": msg.tool_calls})

        # If there are no tool calls to be made, return the natural language output
        if not getattr(msg, "tool_calls", None):
            return msg.content or "", guardrails, tool_records

        # If the maximum number of tool calls are executed, proceed with the best possible response without the tools
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

            # Add the tool output to the messages so that it can be added to the final response
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
    reason = f"Reached maximum number of agent steps. {max_agent_steps}"
    record_guardrail(name, "execution", "warn", reason)
    guardrails.append(GuardrailResult(name=name, stage="execution", action="warn", reason=reason))
    return "I generated a partial plan. Please refine your request.", guardrails, tool_records