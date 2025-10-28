import re
from .config import cfg
def extract_entities(query: str):
    q = query.lower()
    service = None
    window = None
    m = re.search(r'for (service )?([a-z0-9_-]+)', q)
    if m:
        service = m.group(2)
    m2 = re.search(r'last (\d+)(m|min|s)', q)
    if m2:
        window = m2.group(1) + m2.group(2)
    for s in cfg.SERVICE_CATALOG:
        if s in q:
            service = s
    return {'service': service, 'window': window}
