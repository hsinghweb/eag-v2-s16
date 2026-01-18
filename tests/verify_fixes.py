
import asyncio
import sys
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from memory.context import ExecutionContextManager

def test_stringified_parser():
    print("\n🧪 Testing Stringified List Parser...")
    
    # Setup Context with mocked plan
    plan_graph = nx.DiGraph()
    # Malformed list string
    plan_graph.graph['globals_schema'] = {
        "valid_list": "['a', 'b']",
        "valid_json": '{"k": "v"}',
        "plain_string": "hello",
        "complex": "['https://example.com/foo?bar=1']" 
    }
    plan_graph.graph['session_id'] = "test"
    plan_graph.graph['original_query'] = "test"
    plan_graph.graph['file_manifest'] = []
    plan_graph.graph['created_at'] = "2023-01-01"
    
    context = ExecutionContextManager(
        {"nodes": [], "edges": []}
    )
    context.plan_graph = plan_graph # Swap
    
    # Test _ensure_parsed_value direct
    val1 = context._ensure_parsed_value("['a', 'b']")
    if val1 == ['a', 'b']:
        print("✅ List parsed correctly")
    else:
        print(f"❌ List parse failed: {val1}")
        
    val2 = context._ensure_parsed_value('{"k": "v"}')
    if val2 == {'k': 'v'}:
        print("✅ JSON parsed correctly")
    else:
        print(f"❌ JSON parse failed: {val2}")

    # Test get_inputs
    reads = ["valid_list", "valid_json", "plain_string"]
    inputs = context.get_inputs(reads)
    
    if isinstance(inputs["valid_list"], list):
        print("✅ get_inputs: valid_list is List")
    else:
        print(f"❌ get_inputs: valid_list is {type(inputs['valid_list'])}")
        
    if isinstance(inputs["valid_json"], dict):
        print("✅ get_inputs: valid_json is Dict")
    else:
        print(f"❌ get_inputs: valid_json is {type(inputs['valid_json'])}")


def test_bootstrap_graph_update():
    print("\n🧪 Testing Bootstrap Graph Update...")
    
    # 1. Create Bootstrap Context
    bootstrap_graph = {
        "nodes": [{"id": "PLANNING", "agent": "PlannerAgent"}],
        "edges": []
    }
    context = ExecutionContextManager(bootstrap_graph)
    
    # Verify Initial State
    if "PLANNING" in context.plan_graph.nodes:
        print("✅ Bootstrap node 'PLANNING' present")
    else:
        print("❌ Bootstrap node missing")
        return

    # 2. Simulate Planner Output
    real_plan = {
        "nodes": [
            {"id": "STEP_1", "agent": "ResearchAgent", "reads": [], "writes": []},
            {"id": "STEP_2", "agent": "WriterAgent", "reads": [], "writes": []}
        ],
        "edges": [
            {"source": "STEP_1", "target": "STEP_2"}
        ]
    }
    
    # 3. Update
    context.update_with_plan(real_plan)
    
    # 4. Verify Update
    nodes = list(context.plan_graph.nodes)
    if "PLANNING" not in nodes:
        print("✅ Bootstrap node removed")
    else:
        print("❌ Bootstrap node still present")
        
    if "STEP_1" in nodes and "STEP_2" in nodes:
        print("✅ New nodes present")
    else:
         print(f"❌ New nodes missing. Nodes: {nodes}")
         
    if context.plan_graph.has_edge("STEP_1", "STEP_2"):
        print("✅ Edges present")
    else:
        print("❌ Edges missing")

if __name__ == "__main__":
    import networkx as nx 
    try:
        test_stringified_parser()
        test_bootstrap_graph_update()
        print("\n✨ All tests completed.")
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
