import sys
sys.path.append("./app")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace

from guardrails import run_input_guardrails, run_output_guardrails
from config import settings
from observability import init_openlit, current_trace_id
from models import TripPlanRequest, TripPlanResponse
from agent import run_agent

app = FastAPI(title=settings.TITLE, version=settings.VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_openlit(
        service_name=settings.SERVICE_NAME,
        environment=settings.ENV,
        otlp_endpoint=settings.OTLP_ENDPOINT,
        otlp_headers=settings.OTLP_HEADERS,
    )

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/plan", response_model=TripPlanResponse)
def plan(req: TripPlanRequest):
    tracer = trace.get_tracer("trip-planner.api")
    with tracer.start_as_current_span("trip_planner.plan"):
        user_prompt = (".join(["
                       f"Origin: {req.origin}",
                       f"Destination: {req.destination}",
                       f"Dates: {req.start_date} to {req.end_date}",
                       f"Travelers: {req.travelers}",
                       f"Budget: {req.budget or 'unspecified'}",
                       f"Preferences: {', '.join(req.preferences if req.preferences else 'none')}",
                       f"Additional Notes: {req.prompt or 'none'}",
                       "])")
        safe_prompt, g_in, blocked = run_input_guardrails(user_prompt)
        if blocked:
            raise HTTPException(status_code=400,
                                detail={"message": "Blocked by guardrails", "guardrails": [g.model_dump() for g in g_in]})

        plan_md, g_exec, tool_calls = run_agent(safe_prompt)
        g_out, out_blocked, plan_md2 = run_output_guardrails(plan_md)

        guardrails = g_in + g_exec + g_out
        if out_blocked:
            raise HTTPException(status_code=400,
                                detail={"message": "Output blocked by guardrails", "guardrails": [g.model_dump() for g in guardrails]})


        return TripPlanResponse(
            plan_markdown=plan_md2,
            guardrails=guardrails,
            tool_calls=tool_calls,
            trace_id=current_trace_id(),
        )