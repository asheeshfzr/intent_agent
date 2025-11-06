"""
Mock Docs Service
-----------------
Simulates an external documents service endpoint for local testing.
Runs on port 9010 when started via start_local.sh.
"""

from fastapi import FastAPI

app = FastAPI(title="Docs Mock Service", version="1.0")

# Example mock data
MOCK_DOCS = {
    "123": {"title": "Invoice 123", "status": "processed"},
    "456": {"title": "Budget Report Q2", "status": "pending"},
}


@app.get("/docs/{doc_id}")
async def get_doc(doc_id: str):
    """
    Mock endpoint that returns document details for testing.
    """
    return MOCK_DOCS.get(doc_id, {"error": "Document not found"})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "docs_mock"}
