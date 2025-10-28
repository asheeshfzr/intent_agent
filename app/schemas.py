from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class TraceItem(BaseModel):
    ts: float
    node_id: str
    node_type: str
    tool: str
    decision_rule: str
    confidence: float

class QueryResponse(BaseModel):
    status: str = Field(..., description="done|clarify|error")
    summary: str = Field(..., description="Human-readable short answer")
    data: Dict[str, Any] = Field(default_factory=dict)
    trace: List[TraceItem] = Field(default_factory=list)

class MetricsAnswer(BaseModel):
    service: str
    window: str
    p95: Optional[float]
    threshold_ms: Optional[int]
    verdict: Optional[str]  # above|ok|unknown
    reasoning: Optional[str]

class KnowledgeCitations(BaseModel):
    title: str
    snippet: str
    score: Optional[float] = None

class KnowledgeAnswer(BaseModel):
    query: str
    top: Optional[KnowledgeCitations] = None
    confidence: Optional[float] = None

class CalcCompareAnswer(BaseModel):
    targets: List[str] = []
    p95s: Dict[str, float] = {}
    diff_ms: Optional[int] = None
    live_p95s: Dict[str, float] = {}
