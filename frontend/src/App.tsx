import { useMemo, useState } from 'react'

type TripPlanRequest = {
  origin: string
  destination: string
  start_date: string
  end_date: string
  travelers: number
  budget?: string
  preferences: string[]
  prompt?: string
}

type GuardrailResult = {
  name: string
  stage: 'input'|'execution'|'output'|'tool'
  action: string
  reason: string
  meta: Record<string,string>
}

type ToolCallRecord = {
  tool_name: string
  status: string
  duration_ms: number
  args: Record<string, any>
  output_preview: string
}

type TripPlanResponse = {
  plan_markdown: string
  guardrails: GuardrailResult[]
  tool_calls: ToolCallRecord[]
  trace_id: string
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000'

export default function App(){
  const [form, setForm] = useState({
    origin: 'Bangalore',
    destination: 'Singapore',
    start_date: '2026-06-10',
    end_date: '2026-06-14',
    travelers: 2,
    budget: 'Mid-range',
    preferences: 'food,museums',
    prompt: 'Prefer public transport, avoid long walks.'
  })
  const [loading, setLoading] = useState(false)
  const [resp, setResp] = useState<TripPlanResponse|null>(null)
  const [err, setErr] = useState<any>(null)

  const payload: TripPlanRequest = useMemo(() => ({
    origin: form.origin,
    destination: form.destination,
    start_date: form.start_date,
    end_date: form.end_date,
    travelers: Number(form.travelers),
    budget: form.budget,
    preferences: form.preferences.split(',').map(s=>s.trim()).filter(Boolean),
    prompt: form.prompt
  }), [form])

  async function submit(){
    setLoading(true)
    setErr(null)
    setResp(null)
    try{
      const r = await fetch(`${API_BASE}/api/plan`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      })
      const data = await r.json()
      if(!r.ok) throw data
      setResp(data)
    } catch(e:any){
      setErr(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className='topbar'>
        <div className='topbar-inner'>
          <div className='brand'>
            <div className='logo'>I</div>
            <div>
              <h1>Trip Planner Agent</h1>
              <span>Agentic guardrails • Tool-level observability • OpenTelemetry</span>
            </div>
          </div>
          <div className='pill'>OTEL Trace ID shown after each run</div>
        </div>
      </div>

      <div className='container'>
        <div className='grid'>
          <div className='card'>
            <div style={{height:12}} />

            {[
              ['Origin','origin'],
              ['Destination','destination'],
              ['Start date','start_date'],
              ['End date','end_date'],
              ['Travelers','travelers'],
              ['Budget','budget'],
              ['Preferences (comma-separated)','preferences'],
            ].map(([label,key]) => (
              <div key={key as string} style={{marginBottom:12}}>
                <div className='label'>{label}</div>
                <input className='input' value={(form as any)[key]} onChange={e=>setForm({...form,[key]:e.target.value})} />
              </div>
            ))}

            <div style={{marginBottom:12}}>
              <div className='label'>Extra notes</div>
              <textarea className='textarea' value={form.prompt} onChange={e=>setForm({...form,prompt:e.target.value})} />
            </div>

            <button className='btn' onClick={submit} disabled={loading}>
              {loading ? 'Planning…' : 'Generate itinerary'}
            </button>
            <div style={{height:10}} />
            <div className='small'>Backend: {API_BASE}</div>
          </div>

          <div className='card'>
            {!resp && !err && <div className='small'>Run a plan to see results (plan, guardrails, tool calls, trace_id).</div>}

            {err && (
              <>
                <h3>Blocked / Error</h3>
                <pre>{JSON.stringify(err, null, 2)}</pre>
              </>
            )}

            {resp && (
              <>
                <h3>Trace ID</h3>
                <pre>{resp.trace_id}</pre>
                <div className='small'>Use Grafana Explore → Tempo and paste trace_id to see tool spans + guardrail events.</div>

                <h3>Itinerary</h3>
                <pre>{resp.plan_markdown}</pre>

                <h3>Guardrails</h3>
                <pre>{JSON.stringify(resp.guardrails, null, 2)}</pre>

                <h3>Tool calls</h3>
                <pre>{JSON.stringify(resp.tool_calls, null, 2)}</pre>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}