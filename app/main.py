from fastapi import FastAPI
from pydantic import BaseModel
from .agent import handle_query
from .trace import get_trace, clear_trace
from .schemas import QueryResponse

app = FastAPI(title='Intent Agent POC LangChain')

@app.get("/health")
async def health_check():
    """Simple readiness probe for Agent service."""
    return {"status": "ok", "service": "agent"}

class QueryIn(BaseModel):
    query: str
    user_id: str = 'anonymous'

@app.post('/query', response_model=QueryResponse)
def query_endpoint(p: QueryIn):
    return handle_query(p.query, p.user_id)

@app.post('/v1/query', response_model=QueryResponse)
def query_v1(p: QueryIn):
    return handle_query(p.query, p.user_id)

@app.get('/trace')
def trace():
    return get_trace()

@app.post('/clear_trace')
def clear():
    clear_trace(); return {'status':'ok'}
