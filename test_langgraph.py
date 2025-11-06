import sys
import os
from app.orchestrator_langgraph import run_langgraph
from app.config import settings

def test_langgraph():
    # Test with a simple query
    test_queries = [
        "What's the status of payments service?",
        "Compare payments and orders services",
        "Search for documentation about authentication"
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Testing query: {query}")
        print(f"{'='*80}")
        
        try:
            # Enable langgraph for testing
            settings.use_langgraph = True
            
            # Run the query through the langgraph orchestrator
            result = run_langgraph(query, "test_user")
            
            # Print the result
            print("\nResult:")
            print(f"- Status: {result.get('status', 'unknown')}")
            if 'answer' in result:
                print(f"- Answer: {result['answer']}")
            if 'error' in result:
                print(f"- Error: {result['error']}")
            if 'clarify_question' in result:
                print(f"- Clarification needed: {result['clarify_question']}")
                
        except Exception as e:
            print(f"\nError processing query '{query}': {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Add the project root to the Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    print("Starting LangGraph test...")
    test_langgraph()
    print("\nTest completed.")
