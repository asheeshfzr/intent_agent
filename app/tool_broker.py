# app/tool_broker.py
import httpx
import time
import asyncio
from typing import Any, Dict
from app.config import settings
from app.tools.registry import ToolMeta

def execute_http_tool(url: str, params: Dict[str,Any], tool_meta: ToolMeta):
    timeout = httpx.Timeout(settings.HTTP_TIMEOUT_SECONDS)
    client = httpx.Client(timeout=timeout)
    attempts = tool_meta.retries or settings.HTTP_RETRIES
    backoff = settings.HTTP_BACKOFF_BASE

    for attempt in range(attempts + 1):
        try:
            r = client.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            if attempt >= attempts:
                raise
            wait = backoff * (2 ** attempt)
            # use time.sleep for sync context
            time.sleep(wait)
    raise RuntimeError("unreachable")
