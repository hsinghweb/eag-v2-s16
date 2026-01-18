
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from memory.context import ExecutionContextManager

def test_extraction_fallbacks():
    print("🧪 Testing Extraction Fallbacks (Issue #6)...")
    
    context = ExecutionContextManager({"nodes":[], "edges":[]})
    # Reset globals
    context.plan_graph.graph['globals_schema'] = {}

    # --- Scenario 1: Extraction from Code Execution (Priority 1) ---
    print("\n🔹 Scenario 1: Code Execution Result")
    step_id = "STEP_CODE"
    context.plan_graph.add_node(step_id, id=step_id, agent="CoderAgent", writes=["code_var"], status="running")
    
    # Mock output with NO direct write, but code execution has it
    output_1 = {"thought": "I calculated it."} 
    # Mock execution result
    # We need to simulate how loop calls mark_done. 
    # But wait, context.mark_done calls auto_execute_code if needed.
    # To simplify, we can mock _has_executable_code and _auto_execute_code or just pass fully formed output 
    # IF mark_done relies on _merge_execution_results having happened?
    # Looking at mark_done: it calls _auto_execute_code internally if _has_executable_code is true.
    
    # Let's verify `mark_done` logic directly.
    # It extracts from `execution_result` if available.
    
    # We'll simulate that `_auto_execute_code` returns success
    context._has_executable_code = MagicMock(return_value=True)
    context._auto_execute_code = AsyncMock(return_value={
        "status": "success",
        "result": {"code_var": "FoundInCode"}
    })
    
    asyncio.run(context.mark_done(step_id, output_1))
    
    if context.plan_graph.graph['globals_schema'].get("code_var") == "FoundInCode":
        print("✅ Success: Extracted from Code Execution")
    else:
        print(f"❌ Failure: Code extract failed. Got: {context.plan_graph.graph['globals_schema'].get('code_var')}")

    # --- Scenario 2: Direct JSON Output (Priority 2) ---
    print("\n🔹 Scenario 2: Direct JSON Output")
    step_id_2 = "STEP_JSON"
    context.plan_graph.add_node(step_id_2, id=step_id_2, agent="ThinkerAgent", writes=["json_var"], status="running")
    
    context._has_executable_code = MagicMock(return_value=False)
    
    output_2 = {"json_var": "FoundInJSON"}
    asyncio.run(context.mark_done(step_id_2, output_2))
    
    if context.plan_graph.graph['globals_schema'].get("json_var") == "FoundInJSON":
        print("✅ Success: Extracted from Direct JSON")
    else:
        print(f"❌ Failure: JSON extract failed. Got: {context.plan_graph.graph['globals_schema'].get('json_var')}")

    # --- Scenario 3: Fallback to final_answer (Priority 3) ---
    print("\n🔹 Scenario 3: Fallback to final_answer")
    step_id_3 = "STEP_FALLBACK"
    context.plan_graph.add_node(step_id_3, id=step_id_3, agent="SummarizerAgent", writes=["summary_var"], status="running")
    
    # Output does NOT have 'summary_var' key, but has 'final_answer'
    output_3 = {"final_answer": "FoundInFinalAnswer", "thought": "Here is the summary."}
    asyncio.run(context.mark_done(step_id_3, output_3))
    
    if context.plan_graph.graph['globals_schema'].get("summary_var") == "FoundInFinalAnswer":
        print("✅ Success: Extracted from final_answer Fallback")
    else:
        print(f"❌ Failure: Fallback extract failed. Got: {context.plan_graph.graph['globals_schema'].get('summary_var')}")

    # --- Verification of Priority ---
    # If both present, which wins?
    # Code > JSON > Fallback
    
if __name__ == "__main__":
    from unittest.mock import AsyncMock
    test_extraction_fallbacks()
