# Trip Planner Agent (Production Full-Stack)

This solution upgrades the agentic prototype into a **production-ready FastAPI backend** + **React UI** and includes **Grafana dashboards JSON**.

## What you get
- FastAPI backend with tool-using agent loop + agentic guardrails
- OpenLIT OpenTelemetry-native instrumentation exporting via OTLP
- Tool-level observability (spans + metrics)
- Guardrail observability (events + metrics)
- React UI with Infosys-branded styling (placeholder logo)
- Grafana dashboards auto-provisioned

## Branding
The UI ships with a placeholder logo and Infosys-inspired colors. Replace the logo with the official Infosys asset from your internal marketing store portal (mplus). citeturn10search128

## Run locally

```bash
export OPENAI_API_KEY="YOUR_KEY"
cd deploy
docker compose up --build
```

Open:
- UI: http://localhost:3001
- API: http://localhost:8000/health
- Grafana: http://localhost:3000

## Dashboards
- Trip Planner - Guardrails & Tools
- Trip Planner - Traces (Tempo)

## Trace lookup
Every response returns a `trace_id`. Use Grafana Explore → Tempo and paste the trace_id.

 

