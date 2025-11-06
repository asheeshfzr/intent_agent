"""
Schemas
-------
Pydantic models for API input/output, tracing, and agent responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Query Input
# ---------------------------------------------------------
class QueryRequest(BaseModel):
    """Incoming query schema for agent workflow."""
    session_id: Optional[str] = Field(None, description="Unique session identifier")
    query: str = Field(..., description="User input or instruction to the agent")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context or metadata")


# ---------------------------------------------------------
# Trace Item
# ---------------------------------------------------------
class TraceItem(BaseModel):
    """A single trace event in the agent's execution flow."""
    timestamp: str = Field(..., description="UTC timestamp of this event")
    step: str = Field(..., description="Workflow step name")
    data: Dict[str, Any] = Field(default_factory=dict, description="Step-specific data or reasoning output")


# ---------------------------------------------------------
# Query Response
# ---------------------------------------------------------
class QueryResponse(BaseModel):
    session_id: Optional[str] = None
    response: Optional[str] = None
    status: str
    summary: Optional[str] = None
    data: dict = {}
    trace: list = []

    class Config:
        alias_generator = lambda s: ''.join(
            word.capitalize() if i else word for i, word in enumerate(s.split('_'))
        )
        populate_by_name = True


# ---------------------------------------------------------
# Error Schema (optional but useful)
# ---------------------------------------------------------
class ErrorResponse(BaseModel):
    """Standard error format for API responses."""
    error: str
    details: Optional[Dict[str, Any]] = None
