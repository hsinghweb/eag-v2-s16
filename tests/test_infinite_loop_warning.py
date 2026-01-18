
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.loop import AgentLoop4
from memory.context import ExecutionContextManager
import networkx as nx

def verify_warning(input_data, name):
    instruction = input_data.get("agent_prompt", "")
    print(f"🔍 [{name}] Turn 15 Instruction End: ...{instruction[-100:]}")
    
    expected_warning_part = "WARNING: This is your FINAL turn"
    
    if expected_warning_part in instruction:
        print(f"✅ SUCCESS: {name} final turn warning detected.")
    else:
        print(f"❌ FAILURE: {name} warning NOT found.")
        sys.exit(1)

async def test_infinite_loop_warning():
    print("🧪 Testing Infinite Loop Warning Logic...")

    # 1. Setup Mock MultiMCP
    mock_mcp = MagicMock()
    mock_mcp.route_tool_call = AsyncMock(return_value=MagicMock(content="Tool result"))

    # 2. Initialize Loop
    agent_loop = AgentLoop4(mock_mcp)

    # 3. Setup Context (Shared)
    plan_graph = nx.DiGraph()
    plan_graph.graph['globals_schema'] = {}
    plan_graph.graph['session_id'] = "test"
    plan_graph.graph['original_query'] = "test"
    plan_graph.graph['file_manifest'] = []
    plan_graph.graph['created_at'] = "2023-01-01"
    
    node_id = "STEP_LOOP"
    plan_graph.add_node(node_id, 
        id=node_id,
        agent="ResearcherAgent",
        description="Do research",
        reads=[],
        writes=[],
        status="pending"
    )
    
    context = ExecutionContextManager({"nodes":[], "edges":[]})
    context.plan_graph = plan_graph
    context.multi_mcp = mock_mcp

    # --- Test 1: Tool Loop ---
    print("\n🔹 Subtest 1: Call Tool Loop")
    captured_inputs_tool = []
    async def mock_run_agent_tool(agent_type, input_data):
        captured_inputs_tool.append(input_data)
        return {
            "success": True, 
            "output": {
                "call_tool": {"name": "test_tool", "arguments": {}},
                "thought": "I will keep calling tools."
            }
        }
    
    agent_loop.agent_runner.run_agent = AsyncMock(side_effect=mock_run_agent_tool)
    
    await agent_loop._execute_step(node_id, context) # Execute tool loop

    if len(captured_inputs_tool) < 15:
        print(f"❌ (Tool) Loop terminated early: {len(captured_inputs_tool)} turns")
        sys.exit(1)

    verify_warning(captured_inputs_tool[14], "Tool Loop")

    # --- Test 2: Self Loop (Thinking) ---
    print("\n🔹 Subtest 2: Call Self Loop")
    captured_inputs_self = []
    async def mock_run_agent_self(agent_type, input_data):
        captured_inputs_self.append(input_data)
        return {
            "success": True, 
            "output": {
                "call_self": True,
                "thought": "I will keep thinking.",
                "next_instruction": "Think more."
            }
        }
    
    agent_loop.agent_runner.run_agent = AsyncMock(side_effect=mock_run_agent_self)
    
    # Reset node status to pending to run it again
    context.plan_graph.nodes[node_id]['status'] = 'pending'
    
    await agent_loop._execute_step(node_id, context) # Execute self loop

    if len(captured_inputs_self) < 15:
        print(f"❌ (Self) Loop terminated early: {len(captured_inputs_self)} turns")
        sys.exit(1)

    verify_warning(captured_inputs_self[14], "Self Loop")

if __name__ == "__main__":
    asyncio.run(test_infinite_loop_warning())
