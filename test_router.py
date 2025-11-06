from app.router import classify_and_extract
def test_router():
    p = classify_and_extract('what is the p95 latency for service payments in last 5m?')
    assert 'intent' in p
