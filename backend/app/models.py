from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

class TripPlanRequest(BaseModel):
    origin: str
    destination: str
    start_date: str
    end_date: str
    travelers: int = Field(1, ge=1, le=20)
    budget: Optional[str] = None
    preferences: List[str] = Field(default_factory=list)
    prompt: Optional[str] = None

class GuardrailResult(BaseModel):
    name: str
    stage: Literal["input", "execution", "output", "tool"]
    action: Literal["allow", "block", "redact", "warn", "limit", "require_confirmation"]
    reason: str
    meta: Dict[str, str] = Field(default_factory=dict)

class ToolCallRecord(BaseModel):
    tool_name: str
    status: Literal["ok", "error", "blocked", "requires_user_confirmation"]
    duration_ms: float
    args: Dict[str, Any]
    output_preview: str

class TripPlanResponse(BaseModel):
    plan_markdown: str
    guardrails: List[GuardrailResult]
    tool_calls: List[ToolCallRecord]
    trace_id: str

