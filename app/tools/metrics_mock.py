"""
Mock Metrics Service
--------------------
Simulates a metrics collection or monitoring endpoint.
Runs on port 9000 when started via start_local.sh.
"""

from fastapi import FastAPI, Request

app = FastAPI(title="Metrics Mock Service", version="1.0")


@app.post("/metrics")
async def collect_metrics(request: Request):
    """
    Mock endpoint to receive metrics payloads.
    """
    data = await request.json()
    print("[Mock Metrics] Received payload:", data)
    return {"status": "received", "payload_size": len(str(data))}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "metrics_mock"}
