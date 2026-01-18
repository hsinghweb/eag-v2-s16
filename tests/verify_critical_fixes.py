
import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from memory.context import ExecutionContextManager
from core.loop import AgentLoop4
import networkx as nx

class TestCriticalFixes(unittest.IsolatedAsyncioTestCase):
    
    async def test_1_list_as_string_crash(self):
        """Test a) List-as-String Crash Fix"""
        print("\n🧪 Test 1: List-as-String Crash (memory/context.py)")
        context = ExecutionContextManager({"nodes":[], "edges":[]})
        
        # Test cases
        input_str = "['url1', 'url2']"
        expected = ['url1', 'url2']
        result = context._ensure_parsed_value(input_str)
        
        print(f"  Input: {input_str}")
        print(f"  Output: {result}")
        
        self.assertEqual(result, expected, "Failed to parse stringified list")
        self.assertIsInstance(result, list, "Output is not a list")
        print("  ✅ PASS: Stringified list parsed correctly.")

    async def test_2_blind_formatter(self):
        """Test b) Blind Formatter Fix"""
        print("\n🧪 Test 2: Blind Formatter (core/loop.py)")
        
        # Setup
        mock_mcp = MagicMock()
        loop = AgentLoop4(mock_mcp)
        loop.agent_runner.run_agent = AsyncMock(return_value={"success": True, "output": {"thought": "done"}})
        
        # Create Context with Globals
        plan_graph = nx.DiGraph()
        plan_graph.graph['globals_schema'] = {'research_summary': 'Important Content'}
        plan_graph.graph['session_id'] = "val_test"
        plan_graph.graph['original_query'] = "test" 
        plan_graph.graph['file_manifest'] = [] 
        plan_graph.graph['created_at'] = "2024-01-01"
        
        node_id = "STEP_FORMAT"
        plan_graph.add_node(node_id, id=node_id, agent="FormatterAgent", reads=[], writes=[], description="Format report")
        
        context = ExecutionContextManager({"nodes":[], "edges":[]})
        context.plan_graph = plan_graph
        context.multi_mcp = mock_mcp
        
        # Execute
        await loop._execute_step(node_id, context)
        
        # Verify call args
        call_args = loop.agent_runner.run_agent.call_args
        self.assertIsNotNone(call_args, "Agent was not run")
        
        agent_type, input_data = call_args[0]
        self.assertEqual(agent_type, "FormatterAgent")
        
        # CRITICAL CHECK: all_globals_schema must be present
        self.assertIn("all_globals_schema", input_data, "all_globals_schema missing from input")
        self.assertEqual(input_data["all_globals_schema"], {'research_summary': 'Important Content'})
        print("  ✅ PASS: FormatterAgent received globals_schema.")

    async def test_3_zombie_hang(self):
        """Test c) Zombie Hang / Bootstrap Context"""
        print("\n🧪 Test 3: Zombie Hang / Bootstrap Context (core/loop.py)")
        
        mock_mcp = MagicMock()
        loop = AgentLoop4(mock_mcp)
        
        # Mock AgentRunner to capture when specific agents are called
        call_order = []
        
        async def mock_run_agent(agent_type, *args, **kwargs):
            call_order.append(f"run_{agent_type}")
            if agent_type == "PlannerAgent":
                return {
                    "success": True, 
                    "output": {"plan_graph": {"nodes": [{"id": "ROOT"}], "edges": []}}
                }
            return {"success": True, "output": {}}
            
        loop.agent_runner.run_agent = AsyncMock(side_effect=mock_run_agent)
        
        # Mock _execute_dag to check if context exists
        loop._execute_dag = AsyncMock()
        
        # We need to spy on ExecutionContextManager creation
        with patch('core.loop.ExecutionContextManager') as MockContext:
            mock_instance = MagicMock()
            mock_instance.plan_graph.graph = {'globals_schema': {}}
            MockContext.return_value = mock_instance
            
            await loop.run("test query", [], {}, [])
            
            # Check if Context was created BEFORE PlannerAgent
            # In the code: 
            # 1. Context created (Bootstrap)
            # 2. Planner ran
            
            # Verify MockContext was called
            self.assertTrue(MockContext.called, "ExecutionContextManager not initialized")
            
            # Verify arguments of first call to Context implies bootstrap
            init_args = MockContext.call_args[0]
            graph_arg = init_args[0]
            
            # Should have "PLANNING" node
            has_planning_node = any(n['id'] == 'PLANNING' for n in graph_arg.get('nodes', []))
            self.assertTrue(has_planning_node, "Bootstrap graph did not contain 'PLANNING' node")
            
            print("  ✅ PASS: Bootstrap Context initialized with PLANNING node.")

    async def test_4_infinite_loop_warning(self):
        """Test d) Infinite Loop Warning"""
        print("\n🧪 Test 4: Infinite Loop Warning (core/loop.py)")
        
        mock_mcp = MagicMock()
        loop = AgentLoop4(mock_mcp)
        
        # Mock to simulate 15 turns
        captured_inputs = []
        
        async def mock_run_agent(agent_type, input_data):
            captured_inputs.append(input_data)
            return {
                "success": True, 
                "output": {"call_tool": {"name": "wait", "arguments": {}}, "thought": "waiting..."}
            }
            
        loop.agent_runner.run_agent = AsyncMock(side_effect=mock_run_agent)
        loop.multi_mcp.route_tool_call = AsyncMock(return_value=MagicMock(content="done"))
        
        # Setup simple context
        node_id = "STEP_LOOP"
        plan_graph = nx.DiGraph()
        plan_graph.graph['globals_schema'] = {}
        plan_graph.graph['session_id'] = "test"
        plan_graph.graph['original_query'] = "test"
        plan_graph.graph['file_manifest'] = []
        plan_graph.graph['created_at'] = "2024-01-01"
        plan_graph.add_node(node_id, id=node_id, agent="TestAgent", reads=[], writes=[], status="pending", description="Test loop")
        
        context = ExecutionContextManager({"nodes":[], "edges":[]})
        context.plan_graph = plan_graph
        context.multi_mcp = mock_mcp
        
        await loop._execute_step(node_id, context)
        
        # Check 15th turn (index 14)
        if len(captured_inputs) >= 15:
            last_prompt = captured_inputs[14].get("agent_prompt", "")
            self.assertIn("WARNING: This is your FINAL turn", last_prompt, "Warning not found in final turn prompt")
            print("  ✅ PASS: Final turn warning detected.")
        else:
            self.fail(f"Loop finished too early: {len(captured_inputs)} turns")

if __name__ == '__main__':
    unittest.main(verbosity=0)
