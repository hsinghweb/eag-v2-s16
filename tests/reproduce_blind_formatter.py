
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.loop import AgentLoop4
from memory.context import ExecutionContextManager
import networkx as nx

async def test_formatter_globals_injection():
    print("🧪 Starting Blind Formatter Bug Reproduction...")

    # 1. Setup Mock Data
    canned_globals = {
        "research_summary": "The sky is blue.",
        "code_analysis": "Python is great."
    }
    
    # 2. Setup Mock MultiMCP (not strictly needed for this test but required by init)
    mock_mcp = MagicMock()
    
    # 3. Initialize Loop
    agent_loop = AgentLoop4(mock_mcp)
    
    # 4. Mock AgentRunner to capture inputs
    # We want to see what is passed to run_agent when agent_type="FormatterAgent"
    agent_loop.agent_runner.run_agent = AsyncMock(return_value={"success": True, "output": {"final_report": "Done"}})
    
    # 5. Setup Context manually to avoid full graph building overhead
    # We need a plan graph with a FormatterAgent node
    plan_graph = nx.DiGraph()
    plan_graph.graph['globals_schema'] = canned_globals
    plan_graph.graph['session_id'] = "test_session"
    plan_graph.graph['original_query'] = "test query"
    plan_graph.graph['file_manifest'] = []
    plan_graph.graph['created_at'] = "2023-01-01"
    
    node_id = "T_FORMAT"
    plan_graph.add_node(node_id, 
        id=node_id,
        agent="FormatterAgent",
        description="Format the report",
        reads=[],
        writes=["final_report"],
        status="pending"
    )
    
    context = ExecutionContextManager(
        {"nodes": [], "edges": []}, # Empty init, we built graph above manually
        session_id="test_session"
    )
    context.plan_graph = plan_graph # Swap with our populated graph
    context.multi_mcp = mock_mcp
    
    # 6. Execute the step directly
    print(f"🏃 Executing step {node_id}...")
    await agent_loop._execute_step(node_id, context)
    
    # 7. Verify Capture
    # Get specific call args
    call_args = agent_loop.agent_runner.run_agent.call_args
    if not call_args:
        print("❌ AgentRunner.run_agent was NEVER called.")
        sys.exit(1)
        
    args, kwargs = call_args
    agent_type = args[0]
    input_data = args[1]
    
    print(f"👀 Agent Type: {agent_type}")
    print(f"📦 Input Keys: {list(input_data.keys())}")
    
    if agent_type != "FormatterAgent":
        print(f"❌ Wrong agent execution: {agent_type}")
        sys.exit(1)

    # CHECK FOR THE FIX
    if "all_globals_schema" in input_data:
        print("✅ SUCCESS: 'all_globals_schema' WAS injected.")
        print(f"   Content: {input_data['all_globals_schema']}")
        if input_data['all_globals_schema'] == canned_globals:
             print("   (Content matches expected globals)")
        else:
             print("   (⚠️ Content mismatch)")
        sys.exit(0)
    else:
        print("❌ FAILURE: 'all_globals_schema' is MISSING from input.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_formatter_globals_injection())
