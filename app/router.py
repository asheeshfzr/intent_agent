import json, os
from .llm_local import LocalLLM
from .qa_utils import extract_entities
from .config import settings
LLM = LocalLLM()

def _load_router_prompt() -> str:
    # Construct the full path to the router prompt file
    prompt_dir = os.path.join(settings.prompts_path, settings.prompt_version)
    prompt_file = os.path.join(prompt_dir, 'router.txt')
    
    try:
        with open(prompt_file, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"[ERROR] Failed to load router prompt from {prompt_file}: {str(e)}")
        # Fallback minimal prompt with entity extraction examples
        return (
            "You are an agentic router. Return JSON with keys intent, confidence, entities, reasoning.\n"
            "For metrics_lookup intent, extract 'service' and 'window' entities.\n"
            "Example 1:\n"
            "Q: what is the p95 for service payments in last 5m?\n"
            "A: {\"intent\":\"metrics_lookup\",\"confidence\":0.95,\"entities\":{\"service\":\"payments\",\"window\":\"5m\"},\"reasoning\":\"metrics query with service and window\"}\n\n"
            "Query: "
        )
PROMPT = _load_router_prompt()
def _extract_service_name(query: str) -> str:
    """Extract service name from the query using pattern matching."""
    import re
    
    # Common service names to look for
    service_keywords = ['payments', 'orders', 'inventory', 'shipping', 'auth', 'authentication', 'user', 'catalog']
    
    # First, try to find service name using patterns
    patterns = [
        r'service\s+([a-zA-Z0-9_-]+)',
        r'for\s+([a-zA-Z0-9_-]+)\s+service',
        r'([a-zA-Z0-9_-]+)\s+service',
        r'service:\s*([a-zA-Z0-9_-]+)',
        r'p95\s+(?:latency|for|of)\s+([a-zA-Z0-9_-]+)',
        r'metrics\s+for\s+([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            service = match.group(1).strip()
            # If the extracted service is a common word that's not a service, skip it
            if service.lower() not in ['the', 'a', 'an', 'for', 'in', 'last', 'of', 'with']:
                return service.lower()
    
    # If no pattern matched, look for service keywords in the query
    for word in query.split():
        word = word.strip('.,!?;:()[]{}')
        if word.lower() in service_keywords:
            return word.lower()
    
    # If still not found, look for any word that comes after 'service' or 'for'
    words = re.findall(r'\b(?:service|for|metrics|p95|latency)\s+([a-zA-Z0-9_-]+)', query, re.IGNORECASE)
    if words:
        return words[0].lower()
        
    return None

def classify_and_extract(query: str) -> dict:
    """Classify the intent and extract entities from the query.
    
    Returns:
        dict: A dictionary with 'intent', 'confidence', 'entities', and 'reasoning' keys.
    """
    # Default services for fallback
    default_services = ['payments', 'orders', 'inventory', 'user', 'auth']
    
    # Create a default response
    default_response = {
        'intent': 'unknown',
        'confidence': 0.5,
        'entities': {},
        'reasoning': 'fallback'
    }
    
    # First, try to extract entities directly from the query
    extracted_entities = extract_entities(query)
    
    # Check if this is a metrics lookup query
    metrics_keywords = ['p95', 'latency', 'metrics', 'response time', 'throughput', 'status of', 'status for']
    is_metrics_query = any(keyword in query.lower() for keyword in metrics_keywords)
    
    # Enhanced service extraction for metrics queries
    if is_metrics_query:
        # Try to extract service name using multiple methods
        service_name = _extract_service_name(query)
        
        # If we found a service name, use it
        if service_name:
            extracted_entities['service'] = service_name
            default_response.update({
                'intent': 'metrics_lookup',
                'confidence': 0.9,
                'entities': {'service': service_name},
                'reasoning': 'extracted service from metrics query'
            })
    
    try:
        # Append the query to the prompt
        prompt = f"{PROMPT}{query}"
        
        # Get the raw response from the LLM
        raw = LLM.generate(prompt, max_tokens=settings.router_max_tokens, temperature=0.0)
        
        # Try to parse the JSON response
        try:
            # Find JSON in the response (in case there's extra text)
            json_start = raw.find('{')
            json_end = raw.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                js = raw[json_start:json_end]
                parsed = json.loads(js)
                
                # Ensure all required fields are present
                result = default_response.copy()
                
                # If this looks like a metrics query, ensure we have the right intent
                if is_metrics_query:
                    parsed['intent'] = 'metrics_lookup'
                    parsed['confidence'] = max(parsed.get('confidence', 0.5), 0.9)
                    if 'reasoning' in parsed:
                        parsed['reasoning'] += "; overridden to metrics_lookup based on query keywords"
                    else:
                        parsed['reasoning'] = "overridden to metrics_lookup based on query keywords"
                
                # Initialize entities if not present
                if 'entities' not in parsed:
                    parsed['entities'] = {}
                
                # Handle metrics lookup specific logic
                if parsed.get('intent') == 'metrics_lookup':
                    # Use extracted service if available, otherwise try to get from query
                    service_name = extracted_entities.get('service') or _extract_service_name(query)
                    
                    # If we have a service name, use it
                    if service_name:
                        parsed['entities']['service'] = service_name.lower()
                        if 'reasoning' in parsed:
                            parsed['reasoning'] += "; using service from query"
                        else:
                            parsed['reasoning'] = "using service from query"
                    
                    # If still no service, try to find one in the query
                    if 'service' not in parsed['entities'] or not parsed['entities']['service']:
                        for word in query.lower().split():
                            word = word.strip('.,!?;:()[]{}')
                            if word in default_services:
                                parsed['entities']['service'] = word
                                if 'reasoning' in parsed:
                                    parsed['reasoning'] += f"; found service '{word}' in query"
                                else:
                                    parsed['reasoning'] = f"found service '{word}' in query"
                                break
                
                # Merge with extracted entities, giving priority to parsed ones
                for k, v in extracted_entities.items():
                    if k not in parsed['entities'] or not parsed['entities'][k]:
                        parsed['entities'][k] = v
                
                # Ensure we have a valid response
                result.update({
                    'intent': parsed.get('intent', 'unknown'),
                    'confidence': float(parsed.get('confidence', 0.5)),
                    'entities': parsed.get('entities', {}),
                    'reasoning': parsed.get('reasoning', 'LLM response')
                })
                
                # Debug output
                print(f"[Router] Processed query: {query}")
                print(f"[Router] Extracted entities: {extracted_entities}")
                print(f"[Router] Final parsed output: {result}")
                
                return result
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[Router] Error parsing LLM response: {e}")
            # Fall through to keyword matching
    
    except Exception as e:
        print(f"[Router] Error in classify_and_extract: {e}")
    
    # Fallback to keyword matching if LLM fails or returns invalid response
    ql = query.lower()
    
    # Enhanced metrics lookup detection
    if is_metrics_query or any(k in ql for k in ['p95', 'latency', 'p99', 'error rate', 'status of', 'status for']):
        # Try to find a service in the query
        service_name = None
        for word in ql.split():
            word = word.strip('.,!?;:()[]{}')
            if word in default_services:
                service_name = word
                break
        
        return {
            'intent': 'metrics_lookup',
            'confidence': 0.95,
            'entities': {'service': service_name} if service_name else {},
            'reasoning': 'keyword match: metrics-related terms' + (f' with service {service_name}' if service_name else '')
        }
        
    if any(k in ql for k in ['how to', 'configure', 'setup', 'install', 'docs', 'document']):
        return {
            'intent': 'knowledge_lookup',
            'confidence': 0.9,
            'entities': extract_entities(query),
            'reasoning': 'keyword match: documentation-related terms'
        }
        
    if any(k in ql for k in ['compare', 'difference', 'sum', 'calculate', 'calc']):
        # Try to find services to compare
        services = [word for word in ql.split() if word in default_services]
        return {
            'intent': 'calc_compare',
            'confidence': 0.93,
            'entities': {'targets': services} if services else {},
            'reasoning': 'keyword match: calculation/compare terms' + (f' with services {services}' if services else '')
        }
    
    return default_response
