from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import json
from pathlib import Path
app = FastAPI(title='metrics-mock')
HERE = Path(__file__).resolve().parent.parent.parent
FIXTURE = HERE / 'seed_data' / 'metrics_fixture.json'
db = {}
if FIXTURE.exists():
    db = json.loads(FIXTURE.read_text())
@app.get('/metrics')
def get_metrics(service: str = Query(...), window: str = Query('5m')):
    key = service.lower()
    if key in db:
        d = db[key].copy()
        d.update({'service': service, 'window': window})
        return JSONResponse(content=d)
    return JSONResponse(content={'error':'not_found','service':service}, status_code=404)
