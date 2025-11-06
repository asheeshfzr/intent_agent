from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from .config import settings
from .router import classify_and_extract
from .trace import record_prov, clear_trace, new_trace_id
from .session_state import get_pending_clarify, set_pending_clarify, clear_pending_clarify
from .tools.metrics_client import call_metrics
from .tools.vector_tool import call_vector
from .tools.util_tool import run_sql
import asyncio, httpx

# Full LangGraph integration
try:
    from langgraph.graph import StateGraph, END
    _LG_AVAILABLE = True
except Exception as e:
    _LG_AVAILABLE = False
    _IMPORT_ERROR = e

class LGState(BaseModel):
    user_id: Optional[str] = None
    query: str
    intent: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    answer: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    clarify_question: Optional[str] = None
    error: Optional[str] = None

# Node functions

def lg_route(state: LGState, settings=None) -> LGState:
    try:
        parsed = classify_and_extract(state.query)
        state.intent = parsed.get('intent')
        state.entities = parsed.get('entities', {})
        state.confidence = float(parsed.get('confidence', 0.0))
        record_prov('intent','router','llm', {'query': state.query}, parsed, state.confidence, 'router_prompt', session_id=state.user_id)
        return state
    except Exception as e:
        state.error = f"Error in lg_route: {str(e)}"
        return state

def lg_plan(state: LGState, settings=None) -> LGState:
    try:
        confidence_threshold = getattr(settings, 'confidence_threshold', 0.6) if settings else 0.6
        
        if not hasattr(state, 'confidence') or state.confidence < confidence_threshold or not getattr(state, 'intent', None):
            state.clarify_question = (
                "Could you clarify what you want to do? For example: metrics for which service and time window, or a topic to search?"
            )
            return state
            
        if state.intent == 'metrics_lookup':
            # Default services if not configured
            default_services = ['payments', 'orders', 'inventory', 'user', 'auth']
            
            # Get service catalog from settings or use default services
            service_catalog = getattr(settings, 'service_catalog', default_services) if settings else default_services
            
            # Normalize service names for comparison
            service_catalog = [s.lower() for s in service_catalog]
            
            # Get service from entities
            svc = (state.entities.get('service') or '').lower() if hasattr(state, 'entities') else None
            
            if not svc:
                state.clarify_question = f"Which service should I get metrics for? Available services: {', '.join(service_catalog)}"
                return state
            
            # Check if service is in catalog (case-insensitive)
            if svc.lower() not in service_catalog:
                # Try to find a close match
                close_matches = [s for s in service_catalog if svc.lower() in s or s in svc.lower()]
                if close_matches:
                    state.clarify_question = f"Did you mean one of these services? {', '.join(close_matches)}"
                else:
                    state.clarify_question = (
                        f"I don't recognize service '{svc}'. "
                        f"Available services: {', '.join(service_catalog)}"
                    )
                return state
                
            # Update service name to the canonical form from catalog
            canonical_svc = next((s for s in service_catalog if s.lower() == svc.lower()), svc)
            state.entities['service'] = canonical_svc
                
            # Check for time window in the query
            if not state.entities.get('window'):
                # Try to extract time window from the query
                time_patterns = [
                    (r'(?:in|for|last|past)\s+(\d+[mhdw])', 1),  # matches: in 5m, for 1h, last 2d, past 1w
                    (r'(\d+[mhdw])\s+(?:ago|back)', 1),          # matches: 5m ago, 1h ago
                    (r'since\s+(\d+[mhdw])\s+ago', 1),          # matches: since 5m ago
                ]
                
                import re
                for pattern, group in time_patterns:
                    match = re.search(pattern, state.query.lower())
                    if match:
                        state.entities['window'] = match.group(group)
                        break
                
                # If still no window, ask for it
                if not state.entities.get('window'):
                    state.clarify_question = "What time window should I use (e.g., 5m, 1h, 24h)?"
                    return state
                
        elif state.intent == 'calc_compare':
            targets = state.entities.get('targets') or []
            if len(targets) < 2:
                state.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
                return state
                
        # For knowledge_lookup or any other intent, we'll just continue
        return state
        
    except Exception as e:
        state.error = f"Error in lg_plan: {str(e)}"
        return state

def lg_act(state: LGState, settings=None) -> LGState:
    if getattr(state, 'clarify_question', None):
        return state
        
    try:
        if not hasattr(state, 'intent'):
            state.error = "No intent specified"
            return state
            
        if state.intent == 'metrics_lookup':
            svc = state.entities.get('service') if hasattr(state, 'entities') else None
            window = state.entities.get('window', '5m') if hasattr(state, 'entities') else '5m'
            metric = state.entities.get('metric', 'p95_latency') if hasattr(state, 'entities') else 'p95_latency'
            
            if not svc:
                state.error = "No service specified for metrics lookup"
                return state
                
            # Get metrics for the service
            try:
                import asyncio
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # Run the async function in the event loop
                    metrics = loop.run_until_complete(call_metrics(svc, window, metric))
                    
                    if metrics and metrics.get('success'):
                        metrics_data = metrics.get('data', {})
                        p95 = metrics_data.get('p95_latency', 0)
                        # Format the response to match the expected format
                        state.answer = f"{svc} p95={p95}ms"
                        if p95 > 200:  # Add threshold indicator if needed
                            state.answer += " > 200ms"
                        state.data = {
                            'service': svc,
                            'window': window,
                            'p95_latency': p95,
                            'p99_latency': metrics_data.get('p99_latency'),
                            'error_rate': metrics_data.get('error_rate'),
                            'request_count': metrics_data.get('request_count')
                        }
                    else:
                        error_msg = metrics.get('error', 'Unknown error')
                        state.clarify_question = f"Could not fetch metrics for {svc}: {error_msg}. Please try again or specify a different service."
                finally:
                    # Always clean up the event loop
                    loop.close()
            except Exception as e:
                state.error = f"Error fetching metrics: {str(e)}"
                import traceback
                state.error += f"\n\nTraceback:\n{traceback.format_exc()}"
        elif state.intent == 'knowledge_lookup':
            vec = call_vector(state.query)
            record_prov('vector','tool','vector', {'query':state.query}, vec.dict(), vec.score, 'vector_search', session_id=state.user_id)
            knowledge_score_min = getattr(settings, 'KNOWLEDGE_SCORE_MIN', 0.7)
            if vec.success and vec.score >= knowledge_score_min:
                top = vec.data.get('top', {})
                title = (top.get('payload',{}) or {}).get('title','unknown')
                snippet = (top.get('payload',{}) or {}).get('text','')[:300]
                state.answer = f"Found doc: {title} - snippet: {snippet}"
                state.data = {'query': state.query, 'top': {'title': title, 'snippet': snippet}}
            else:
                # fallback docs
                try:
                    r = httpx.get(f'{settings.DOCS_BASE_URL}/search', params={'q': state.query}, timeout=settings.HTTP_TIMEOUT_SECONDS)
                    docs = r.json()
                    record_prov('http_docs','tool','http_docs', {'q':state.query}, docs, 0.5, 'http_fallback', session_id=state.user_id)
                    if docs.get('items'):
                        t = docs['items'][0]
                        state.answer = 'Found doc: ' + t['title']
                        state.data = {'query': state.query, 'top': {'title': t['title'], 'snippet': t.get('snippet','')}}
                        return state
                except Exception:
                    pass
                state.clarify_question = 'No reliable docs found. Clarify?'
        elif state.intent == 'calc_compare':
            sql_res = run_sql('SELECT * FROM services')
            rows = sql_res.data.get('rows', [])
            d = {r[0]: r[1] for r in rows}
            targets = state.entities.get('targets') or []
            if len(targets) < 2:
                state.clarify_question = "Which two services should I compare (e.g., payments vs orders)?"
                return state
            a, b = targets[:2]
            if a in d and b in d:
                diff = d[a] - d[b]
                state.answer = f"{a.capitalize()} p95={d[a]}ms, {b.capitalize()} p95={d[b]}ms, diff={diff}ms"
                state.data = {'targets': [a,b], 'p95s': {a: d[a], b: d[b]}, 'diff_ms': diff}
            else:
                state.clarify_question = 'Targets not found in table'
    except Exception as e:
        state.error = str(e)
    return state

def lg_reflect(state: LGState, settings=None) -> LGState:
    try:
        if getattr(state, 'clarify_question', None):
            set_pending_clarify(getattr(state, 'user_id', None), state.clarify_question)
        else:
            clear_pending_clarify(getattr(state, 'user_id', None))
    except Exception as e:
        state.error = f"Error in reflection: {str(e)}"
    return state

# Conditional edges

def _needs_clarify(state: LGState, settings=None):
    if settings and hasattr(settings, 'confidence_threshold'):
        threshold = settings.confidence_threshold
    else:
        threshold = 0.6  # Default threshold
    return bool(state.clarify_question) or (hasattr(state, 'confidence') and state.confidence < threshold)

def _has_answer(state: LGState):
    return bool(getattr(state, 'answer', None)) and not getattr(state, 'clarify_question', None)

def _decide_next_node(state: LGState, settings=None) -> str:
    """Determine the next node based on the current state.
    
    Args:
        state: The current state of the graph
        settings: Optional settings object with configuration
        
    Returns:
        str: The next node key ('clarify', 'finalize', or 'error')
    """
    try:
        if getattr(state, 'error', None):
            error_msg = str(getattr(state, 'error', 'Unknown error'))
            print(f"[DEBUG] _decide_next_node: Error detected: {error_msg}")
            return 'error'
            
        if _needs_clarify(state, settings):
            print("[DEBUG] _decide_next_node: Needs clarification")
            return 'clarify'
            
        if _has_answer(state):
            print("[DEBUG] _decide_next_node: Has answer, finalizing")
            return 'finalize'
            
        print("[DEBUG] _decide_next_node: Defaulting to clarify")
        return 'clarify'
        
    except Exception as e:
        print(f"[ERROR] Error in _decide_next_node: {str(e)}")
        return 'error'

# Build and cache the LangGraph graph
_graph = None

def _build_graph():
    global _graph
    if _graph is not None:
        print("[DEBUG] Returning cached graph")
        return _graph
        
    print("[DEBUG] Building LangGraph...")
    
    # Import settings here to ensure it's available in all nodes
    from .config import settings
    
    # Create a wrapper function that injects settings into each node function's globals
    def wrap_node_func(func):
        def wrapper(state: LGState):
            # Make settings available in the function's globals
            import sys
            module = sys.modules[func.__module__]
            original_globals = getattr(module, 'settings', None)
            setattr(module, 'settings', settings)
            
            try:
                print(f"[DEBUG] Executing node: {func.__name__}")
                result = func(state)
                print(f"[DEBUG] Node {func.__name__} completed. State: {result}")
                return result
            except Exception as e:
                print(f"[ERROR] Error in node {func.__name__}: {str(e)}")
                state.error = f"Error in {func.__name__}: {str(e)}"
                return state
            finally:
                # Restore original globals
                if original_globals is not None:
                    setattr(module, 'settings', original_globals)
                else:
                    delattr(module, 'settings')
        return wrapper
    
    try:
        # Initialize the graph
        from langgraph.graph import StateGraph, END
        
        print("[DEBUG] Creating new StateGraph...")
        g = StateGraph(LGState)
        
        # Add nodes with wrapped functions
        print("[DEBUG] Adding nodes to the graph...")
        nodes = {
            'route': wrap_node_func(lg_route),
            'plan': wrap_node_func(lg_plan),
            'act': wrap_node_func(lg_act),
            'reflect': wrap_node_func(lg_reflect)
        }
        
        for node_name, node_func in nodes.items():
            print(f"[DEBUG] Adding node: {node_name}")
            g.add_node(node_name, node_func)
        
        # Set the entry point
        print("[DEBUG] Setting entry point to 'route'")
        g.set_entry_point('route')
        
        # Add edges
        print("[DEBUG] Adding edges to the graph...")
        edges = [
            ('route', 'plan'),
            ('plan', 'act'),
            ('act', 'reflect')
        ]
        
        for src, dst in edges:
            print(f"[DEBUG] Adding edge: {src} -> {dst}")
            g.add_edge(src, dst)
        
        # Add conditional edges from reflect node
        print("[DEBUG] Adding conditional edges from 'reflect' node...")
        from functools import partial
        
        # Create a partial function that includes settings
        decide_func = partial(_decide_next_node, settings=settings)
        
        g.add_conditional_edges(
            'reflect',
            decide_func,
            {
                'clarify': END,
                'finalize': END,
                'error': END
            }
        )
        
        # Debug graph structure
        print("[DEBUG] Graph structure:")
        print(f"- Nodes: {list(g.nodes.keys())}")
        print(f"- Entry point: {getattr(g, 'entry_point', 'NOT SET')}")
        
        # Compile the graph
        print("[DEBUG] Compiling graph...")
        try:
            _graph = g.compile()
            print("[DEBUG] Graph compiled successfully")
        except Exception as compile_error:
            print(f"[ERROR] Failed to compile graph: {str(compile_error)}")
            print("[DEBUG] Graph state before compilation:")
            print(f"- Nodes: {list(g.nodes.keys())}")
            print(f"- Entry point: {getattr(g, 'entry_point', 'NOT SET')}")
            raise
            
        return _graph
        
    except Exception as e:
        import traceback
        error_msg = f"[ERROR] Failed to build graph: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise ValueError(error_msg) from e

# Entry point for adapter

def run_langgraph(query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    print(f"[DEBUG] run_langgraph called with query: {query}, user_id: {user_id}")
    
    # Initialize default response
    default_response = {
        'answer': 'Unable to process request',
        'status': 'error',
        'trace': []
    }
    
    if not _LG_AVAILABLE:
        error_msg = f"LangGraph is not available: {_IMPORT_ERROR}"
        print(f"[ERROR] {error_msg}")
        default_response['answer'] = error_msg
        return default_response
    
    if not query or not isinstance(query, str):
        error_msg = "Invalid query: query must be a non-empty string"
        print(f"[ERROR] {error_msg}")
        default_response['answer'] = error_msg
        return default_response
    
    trace_id = new_trace_id()
    clear_trace(trace_id)
    
    try:
        print("[DEBUG] Building LangGraph...")
        app = _build_graph()
        
        if app is None:
            error_msg = "Failed to build LangGraph: app is None"
            print(f"[ERROR] {error_msg}")
            default_response['answer'] = error_msg
            return default_response
        
        # Initialize state with query and user_id
        try:
            state = LGState(query=query, user_id=user_id or 'anonymous')
            print(f"[DEBUG] Initial state: {state.dict() if hasattr(state, 'dict') else state}")
        except Exception as e:
            error_msg = f"Failed to initialize state: {str(e)}"
            print(f"[ERROR] {error_msg}")
            default_response['answer'] = error_msg
            return default_response
        
        try:
            # Run the graph
            print("[DEBUG] Invoking LangGraph...")
            out = app.invoke(state)
            print(f"[DEBUG] Graph execution completed. Output type: {type(out)}")
            
            # Convert output to dictionary
            out_dict = {}
            if hasattr(out, 'dict'):
                out_dict = out.dict()
                print("[DEBUG] Converted Pydantic model to dict")
            elif hasattr(out, '__dict__'):
                out_dict = vars(out)
                print("[DEBUG] Converted object to dict using vars()")
            elif isinstance(out, dict):
                out_dict = out
                print("[DEBUG] Output is already a dict")
            else:
                out_dict = {'raw_output': str(out)}
                print(f"[DEBUG] Output is of type {type(out)}, converting to string")
            
            print(f"[DEBUG] Processed output dict: {out_dict}")
            
            # Handle different response types
            if out_dict.get("clarify_question"):
                return {
                    'answer': str(out_dict["clarify_question"]),
                    'status': 'clarify',
                    'trace': [],
                    'data': out_dict.get('data', {})
                }
                
            if out_dict.get("answer"):
                return {
                    'answer': str(out_dict["answer"]),
                    'status': 'done',
                    'trace': [],
                    'data': out_dict.get('data', {})
                }
                
            if out_dict.get("error"):
                error_msg = str(out_dict.get("error", "Unknown error in graph execution"))
                print(f"[ERROR] {error_msg}")
                default_response['answer'] = error_msg
                return default_response
                
            print("[WARNING] No valid response fields found in output")
            default_response['answer'] = 'The system encountered an unexpected state'
            return default_response
            
        except Exception as invoke_error:
            error_msg = f"Error invoking graph: {str(invoke_error)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            default_response['answer'] = f"Error processing request: {str(invoke_error)}"
            return default_response
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        error_msg = f"Fatal error in run_langgraph: {str(e)}"
        print(f"[ERROR] {error_msg}\n{error_trace}")
        default_response['answer'] = 'A system error occurred while processing your request'
        return default_response
