from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pathlib import Path
from ..config import cfg
app = FastAPI(title='docs-mock')
DOC_DIR = Path(cfg.DOCS_DIR)
@app.get('/search')
def search(q: str = Query(...), k: int = 3):
    items = []
    for p in DOC_DIR.glob('*.md'):
        t = p.read_text()
        if q.lower() in t.lower() or q.lower() in p.name.lower():
            items.append({'title': p.name, 'snippet': t[:400]})
    return JSONResponse(content={'items': items[:k]})
