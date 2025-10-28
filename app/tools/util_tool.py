import ast, operator as op, sqlite3, time, json
from .mcp import MCPOutput
from pathlib import Path
from ..config import cfg
ALLOWED = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg, ast.Mod: op.mod}
def _eval(node):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Num): return node.n
    if isinstance(node, ast.BinOp):
        left = _eval(node.left); right = _eval(node.right)
        return ALLOWED[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp):
        return ALLOWED[type(node.op)](_eval(node.operand))
    raise ValueError('unsupported')
def calc(expr: str) -> MCPOutput:
    try:
        node = ast.parse(expr, mode='eval').body
        val = _eval(node)
        return MCPOutput(tool='calc', success=True, data={'result': val}, score=0.9, reason='safe_eval', ts=time.time())
    except Exception as e:
        return MCPOutput(tool='calc', success=False, data={'error': str(e)}, score=0.0, reason='error', ts=time.time())
def run_sql(sql: str) -> MCPOutput:
    try:
        if not sql.strip().lower().startswith('select'):
            return MCPOutput(tool='sql', success=False, data={'error':'only SELECT allowed'}, score=0.0, reason='reject_nonselect', ts=time.time())
        conn = sqlite3.connect(':memory:')
        cur = conn.cursor()
        cur.execute('CREATE TABLE services (name TEXT, p95 INTEGER)')
        # Seed from fixture if available, else from service catalog with defaults
        seeded = False
        fix = Path(__file__).resolve().parent.parent.parent / 'seed_data' / 'metrics_fixture.json'
        if fix.exists():
            try:
                db = json.loads(fix.read_text())
                rows = []
                for name, vals in db.items():
                    if isinstance(vals, dict) and 'p95' in vals:
                        rows.append((name, int(vals['p95'])))
                if rows:
                    cur.executemany('INSERT INTO services VALUES(?,?)', rows)
                    seeded = True
            except Exception:
                pass
        if not seeded:
            # default 200ms for all catalog services
            rows = [(s, 200) for s in cfg.SERVICE_CATALOG]
            cur.executemany('INSERT INTO services VALUES(?,?)', rows)
        cur.execute(sql)
        rows = cur.fetchall()
        return MCPOutput(tool='sql', success=True, data={'rows': rows}, score=0.9, reason='ok', ts=time.time())
    except Exception as e:
        return MCPOutput(tool='sql', success=False, data={'error': str(e)}, score=0.0, reason='error', ts=time.time())
