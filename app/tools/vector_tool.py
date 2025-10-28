from typing import List, Dict, Any
from ..tools.mcp import MCPOutput
from ..config import cfg
import time, os
QDRANT_AVAILABLE = False
ST_AVAILABLE = False
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance
    QDRANT_AVAILABLE = True
except Exception:
    QDRANT_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer
    ST_AVAILABLE = True
except Exception:
    ST_AVAILABLE = False
from sklearn.feature_extraction.text import TfidfVectorizer
from pathlib import Path
from ..config import cfg
DOC_DIR = Path(cfg.DOCS_DIR)
_docs = [p.read_text() for p in DOC_DIR.glob('*.md')] if DOC_DIR.exists() else []
_titles = [p.name for p in DOC_DIR.glob('*.md')] if DOC_DIR.exists() else []
_TFIDF = None
_MAT = None
if _docs:
    _TFIDF = TfidfVectorizer().fit(_docs)
    _MAT = _TFIDF.transform(_docs)
_qdrant = None
_emb = None
if QDRANT_AVAILABLE and cfg.USE_QDRANT:
    try:
        _qdrant = QdrantClient(url=cfg.QDRANT_URL)
        if ST_AVAILABLE:
            _emb = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        _qdrant = None
def call_vector(query: str, k: int = 5) -> MCPOutput:
    if _qdrant and _emb:
        vec = _emb.encode([query])[0].tolist()
        try:
            hits = _qdrant.search(collection_name='agent_docs', query_vector=vec, limit=k, with_payload=True)
            items = [{'id': h.id, 'score': float(h.score), 'payload': h.payload} for h in hits]
            top = items[0] if items else None
            return MCPOutput(tool='vector', success=bool(items), data={'top': top, 'items': items}, score=top['score'] if top else 0.0, reason='qdrant', ts=time.time())
        except Exception:
            pass
    if not _docs or _TFIDF is None:
        return MCPOutput(tool='vector', success=False, data={'items': []}, score=0.0, reason='no_docs', ts=time.time())
    qv = _TFIDF.transform([query])
    scores = (_MAT @ qv.T).toarray().squeeze().tolist()
    idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    items = [{'id': i, 'score': float(scores[i]), 'title': _titles[i], 'text': _docs[i]} for i in idx]
    top = items[0] if items else None
    return MCPOutput(tool='vector', success=bool(items), data={'top': top, 'items': items}, score=top['score'] if top else 0.0, reason='tfidf', ts=time.time())
