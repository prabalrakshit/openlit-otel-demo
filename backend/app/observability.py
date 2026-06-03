import openlit
from opentelemetry import trace, metrics

tracer = trace.get_tracer("trip-planner")
meter = metrics.get_meter("trip-planner")

_guardrail_decisions = meter.create_counter(
    name="guardrail_decisions_total",
    description="Count of guardrail decisions by name/ stage/ action",
    unit="1"
)

_tool_calls = meter.create_counter(
    name="tool_calls_total",
    description="Count of tool calls by tool and status",
    unit="1"
)

_tool_latency = meter.create_histogram(
    name="tool_latency_ms",
    description="Tool call latency distribution (ms)",
    unit="1"
)

def init_openlit(service_name: str, environment: str, otlp_endpoint: str, otlp_headers: str):
    openlit.init(
        service_name=service_name,
        environment=environment,
        otlp_endpoint=otlp_endpoint,
        otlp_headers=otlp_headers or None,
        capture_message_content=False,
    )

def record_guardrail(name: str, stage:str, action:str, reason: str, **meta):
    span = trace.get_current_span()
    if span and span.is_recording():
        span.event(
            "guardrail_decision",
            attributes={
                "guardrail.name": name,
                "guardrail.stage": stage,
                "guardrail.action": action,
                "guardrail.reason": reason,
                **{f"guardrail.meta.{k}": str(v) for k, v in meta.items()}
            }
        )
        span.set_attribute("guardrail.last.name", name)
        span.set_attribute("guardrail.last.action", action)

    _guardrail_decisions.add(
        1,
        attributes={
            "guardrail.name": name,
            "guardrail.stage": stage,
            "guardrail.action": action,
        },
    )

def record_tool_call(tool_name: str, status: str, duration_ms: float):
    _tool_calls.add(1, attributes={"tool.name": tool_name, "tool.status": status})
    _tool_latency.record(duration_ms, attributes={"tool.name": tool_name, "tool.status": status})

def current_trace_id() -> str:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if not ctx or not ctx.is_valid:
        return ""
    return format(ctx.trace_id, "032x")
