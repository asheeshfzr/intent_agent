import httpx
from typing import Any, Dict, Optional
from ..config import settings


async def call_metrics(service: str, window: str = "1h", timeout: Optional[float] = None) -> Dict[str, Any]:
    """
    Lightweight metrics mock client used by the orchestrator.
    Returns mock metrics data for the specified service and time window.
    """
    # Mock data generation
    import random
    from datetime import datetime, timedelta
    
    try:
        # Generate some mock metrics data
        current_time = datetime.utcnow()
        
        # Parse window (e.g., '5m', '1h', '24h')
        if window.endswith('m'):
            minutes = int(window[:-1])
            start_time = current_time - timedelta(minutes=minutes)
        elif window.endswith('h'):
            hours = int(window[:-1])
            start_time = current_time - timedelta(hours=hours)
        elif window.endswith('d'):
            days = int(window[:-1])
            start_time = current_time - timedelta(days=days)
        else:
            start_time = current_time - timedelta(minutes=5)  # default to 5 minutes
        
        # Generate mock metrics
        metrics = {
            'service': service,
            'window': window,
            'start_time': start_time.isoformat(),
            'end_time': current_time.isoformat(),
            'p95_latency': round(random.uniform(200, 400), 2),  # Ensure p95 is above 200ms for testing
            'p99_latency': round(random.uniform(100, 300), 2),
            'error_rate': round(random.uniform(0.1, 5.0), 2),
            'request_count': random.randint(1000, 10000),
            'success_rate': round(random.uniform(95.0, 99.9), 2),
            'status': 'success'
        }
        
        return {
            'success': True,
            'data': metrics,
            'message': f'Mock metrics for {service} (last {window})'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'service': service,
            'window': window,
            'message': f'Failed to generate mock metrics: {str(e)}'
        }
