# This module wires up LangChain using our LocalLLM wrapper.
# It defines a LangChain-compatible LLM class and Tools for metrics/vector/sql.
from langchain.llms.base import LLM
from langchain.tools import Tool
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from .llm_local import LocalLLM
from .config import cfg
from .tools.metrics_client import call_metrics
from .tools.vector_tool import call_vector
from .tools.util_tool import run_sql, calc
import asyncio, json, httpx, time

class LocalLangChain(LLM):
    model: LocalLLM = LocalLLM()
    def _call(self, prompt: str, stop: Optional[List[str]] = None) -> str:
        # Keep agent steps short to encourage Action/Observation cycles
        return self.model.generate(prompt, max_tokens=cfg.AGENT_MAX_TOKENS, temperature=0.0)
    @property
    def _identifying_params(self):
        return {"name": "local-llm"}
    @property
    def _llm_type(self) -> str:
        # Required by LangChain's abstract LLM base to identify the implementation
        return "local-llm"

def make_langchain_tools():
    # metrics tool (sync HTTP to avoid asyncio event loop issues in AnyIO worker thread)
    def metrics_tool_fn(input_str: str) -> str:
        # parse input like "service=payments;window=5m"
        parts = {}
        for p in input_str.split(';'):
            if '=' in p:
                k, v = p.split('=', 1)
                parts[k.strip()] = v.strip()
        svc = parts.get('service', 'payments')
        window = parts.get('window', '5m')
        try:
            url = f"{cfg.METRICS_BASE_URL}/metrics"
            with httpx.Client(timeout=cfg.HTTP_TIMEOUT_SECONDS) as client:
                r = client.get(url, params={'service': svc, 'window': window})
                if r.status_code == 200:
                    payload = {
                        'tool': 'metrics',
                        'success': True,
                        'data': r.json(),
                        'score': 0.9,
                        'reason': 'mock',
                        'ts': time.time(),
                    }
                else:
                    payload = {
                        'tool': 'metrics',
                        'success': False,
                        'data': {'error': r.text},
                        'score': 0.0,
                        'ts': time.time(),
                    }
            return json.dumps(payload)
        except Exception as e:
            return json.dumps({
                'tool': 'metrics',
                'success': False,
                'data': {'error': str(e)},
                'score': 0.0,
                'ts': time.time(),
            })
    def vector_tool_fn(q: str) -> str:
        res = call_vector(q)
        return json.dumps(res.dict())
    def sql_tool_fn(q: str) -> str:
        if 'select' in q.lower():
            res = run_sql(q)
        else:
            res = calc(q)
        return json.dumps(res.dict())
    tools = [
        Tool(
            func=metrics_tool_fn,
            name='metrics_tool',
            description='Use this to fetch latency metrics. Input must be a string in the form "service=<name>;window=<duration>", e.g., "service=payments;window=5m".'
        ),
        Tool(
            func=vector_tool_fn,
            name='vector_tool',
            description='Use this to search knowledge base documents for guidance. Input is the raw user question.'
        ),
        Tool(
            func=sql_tool_fn,
            name='util_sql',
            description='Use this to either run SQL (input contains SELECT) or perform simple calculations. Input is the user request text.'
        )
    ]
    # Annotate capabilities for capability-based selection
    for t in tools:
        if t.name == 'metrics_tool':
            setattr(t, 'capabilities', ['metrics'])
        elif t.name == 'vector_tool':
            setattr(t, 'capabilities', ['knowledge'])
        elif t.name == 'util_sql':
            setattr(t, 'capabilities', ['calc','sql'])
    return tools
