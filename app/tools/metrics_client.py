import httpx, time, asyncio
from .mcp import MCPOutput
from ..config import cfg

async def call_metrics(service: str, window: str = '5m') -> MCPOutput:
    url = f"{cfg.METRICS_BASE_URL}/metrics"
    retries = cfg.HTTP_RETRIES
    backoff = cfg.HTTP_RETRY_BACKOFF_SECONDS
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=cfg.HTTP_TIMEOUT_SECONDS) as client:
                r = await client.get(url, params={'service': service, 'window': window})
                if r.status_code == 200:
                    return MCPOutput(tool='metrics', success=True, data=r.json(), score=0.9, reason='mock', ts=time.time())
                # 4xx/5xx
                return MCPOutput(tool='metrics', success=False, data={'error': r.text}, score=0.0, ts=time.time())
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(backoff * (attempt + 1))
                continue
            return MCPOutput(tool='metrics', success=False, data={'error': str(e)}, score=0.0, ts=time.time())
