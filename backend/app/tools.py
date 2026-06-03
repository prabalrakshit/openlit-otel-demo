import time
import json
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field, ValidationError
from opentelemetry import trace

from models import GuardrailResult, ToolCallRecord
from observability import record_guardrail, record_tool_call

tracer = trace.get_tracer("trip-planner.tools")

class WeatherArgs(BaseModel):
    location: str = Field(..., description="City Name")

class FlightSearchArgs(BaseModel):
    origin: str
    destination: str
    date: str
    travelers: int = Field(1, ge=1, le=20)

class BookingArgs(BaseModel):
    vendor: str
    item_id: str
    price_limit: float = Field(..., ge=0)

# Mock Tool Implementation
def get_weather(location: str) -> Dict[str, Any]:
    return {
        "location": location,
        "forecast": "Partly Cloudy",
        "temp_c": 29,
        "Humidity": 65
    }

def search_flights(origin: str, destination: str, date: str, travelers: int) -> Dict[str, Any]:
    return {
        "origin": origin,
        "destination": destination,
        "date": date,
        "travelers": travelers,
        "options": [
            {"id": "F123", "airline": "Mock Air", "price": 320.0,"duration": "4h 15m"},
            {"id": "F456", "airline": "Mock Jet", "price": 410.0,"duration": "3h 55m"},
        ]
    }

def book_item(vendor: str, item_id: str, price_limit: float) -> Dict[str, Any]:
    return {
        "requires_user_confirmation": True,
        "vendor": vendor,
        "item_id": item_id,
        "price": price_limit,
        "message": "Booking not executed. Please confirm in the portal to proceed"
    }

TOOL_REGISTRY = {
    "get_weather": {"schema": WeatherArgs, "fn": lambda args: get_weather(**args.model_dump()), "safe": True},
    "search_flights": {"schema": FlightSearchArgs, "fn": lambda args: search_flights(**args.model_dump()), "safe": True},
    "book_items": {"schema": BookingArgs, "fn": lambda args: search_flights(**args.model_dump()), "safe": True},
}

def openai_tools_schema() -> List[Dict[str, Any]]:
    def model_to_schema(model_cls: type[BaseModel]) -> Dict[str, Any]:
        s = model_cls.model_json_schema()
        s.setdefault("additionalProperties", False)
        return s

    tools: List[Dict[str, Any]] = []
    for name, spec in TOOL_REGISTRY.items():
        tools.append({
         "type": "function",
         "function": {
             "name": name,
             "description": f"Tool: {name}",
             "parameters": model_to_schema(spec["schema"]),
             "strict": True
         }
        })
    return tools

def execute_tool(tool_name: str, raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], List[GuardrailResult], ToolCallRecord]:
    guardrails: List[GuardrailResult] = []
    start = time.time()
    status = "ok"
    output:Dict[str, Any] = {}

    with tracer.start_as_current_span("tool.call") as span:
        span.set_attribute("tool_name", tool_name)

        if tool_name not in TOOL_REGISTRY:
            action = "blocked"
            reason = "Tool not allowed"
            record_guardrail("tool.allowlist", "tool", action, reason, tool=tool_name)
            guardrails.append(GuardrailResult(name="tool.allowlist", stage="tool", action=action, reason=reason, meta=("tool", tool_name)))
            output = {"error": reason}
        else:
            spec = TOOL_REGISTRY[tool_name]
            try:
                args_obj = spec["schema"](**raw_args)
            except ValidationError as ve:
                action = "blocked"
                reason = "Tool arguments failed validation"
                record_guardrail("tool.arg_validation", "tool", action, reason, tool=tool_name)
                guardrails.append(GuardrailResult(name="tool.arg_validation", stage="tool", action=action, reason=reason, meta=("tool", tool_name)))
                output = {"error": reason, "details": ve.errors}
            else:
                if not spec.get("safe", True):
                    action = "requires_user_confirmation"
                    reason = "Tool requires user confirmation"
                    record_guardrail("tool.safe_mode", "tool", action, reason, tool=tool_name)
                    guardrails.append(
                        GuardrailResult(name="tool.safe_mode", stage="tool", action=action, reason=reason,
                                        meta=("tool", tool_name)))
                    output = spec["fn"](args_obj)
                else:
                    try:
                        output = spec["fn"](args_obj)
                    except Exception as e:
                        action = "warn"
                        reason = "Tool execution failed"
                        record_guardrail("tool.exec_error", "tool", action, reason, tool=tool_name)
                        guardrails.append(
                            GuardrailResult(name="tool.exec_error", stage="tool", action=action, reason=reason,
                                            meta=("tool", tool_name)))
                        output = {"error", reason, "exception", str(e)}
            duration_ms = (time.time() - start) * 1000
            span.set_attribute("tool.status", status)
            span.set_attribute("tool.duration_ms", duration_ms)

        record_tool_call(tool_name, status, duration_ms)

        preview = json.dumps(output, ensure_ascii=False)
        if len(preview) > 400:
            preview = preview[:400] + "..."

        record = ToolCallRecord(
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            args=raw_args,
            output_preview=preview,
        )
        return output, guardrails, record



