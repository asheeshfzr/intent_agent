import json, os
from .llm_local import LocalLLM
from .qa_utils import extract_entities
from .config import cfg
LLM = LocalLLM()

def _load_router_prompt() -> str:
    p = os.path.join(cfg.PROMPTS_DIR, cfg.ROUTER_PROMPT_VERSION)
    try:
        with open(p, 'r') as f:
            return f.read()
    except Exception:
        # Fallback minimal prompt
        return (
            "You are an agentic router. Return JSON with keys intent, confidence, entities, reasoning.\n"
            "Few-shot examples included above.\nQuery: "
        )
PROMPT = _load_router_prompt()
def classify_and_extract(query: str):
    # Append the query without using .format to avoid KeyError from JSON braces in the template
    prompt = f"{PROMPT}{query}\n"
    raw = LLM.generate(prompt, max_tokens=cfg.ROUTER_MAX_TOKENS, temperature=0.0)
    try:
        js = raw[raw.find('{'): raw.rfind('}')+1]
        parsed = json.loads(js)
        if 'entities' not in parsed:
            parsed['entities'] = extract_entities(query)
        return parsed
    except Exception:
        ql = query.lower()
        if any(k in ql for k in ['p95','latency','p99','error rate']):
            return {'intent':'metrics_lookup','confidence':0.95,'entities':extract_entities(query),'reasoning':'keyword'}
        if any(k in ql for k in ['how to','configure','setup','install','docs','document']):
            return {'intent':'knowledge_lookup','confidence':0.9,'entities':extract_entities(query),'reasoning':'keyword'}
        if any(k in ql for k in ['compare','difference','sum','calculate','calc']):
            return {'intent':'calc_compare','confidence':0.93,'entities':extract_entities(query),'reasoning':'keyword'}
        return {'intent':'unknown','confidence':0.5,'entities':extract_entities(query),'reasoning':'fallback'}
