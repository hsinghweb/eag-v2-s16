
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from memory.context import ExecutionContextManager

def test_rich_context_saving():
    print("🧪 Testing Amnesic User Fix (Rich Context Saving)...")
    
    # 1. Setup Mock
    # We need to mock _handle_user_interaction_rich because we don't want real input
    
    context = ExecutionContextManager({"nodes":[], "edges":[]})
    context._handle_user_interaction_rich = MagicMock(return_value="Yes, do it.")
    
    # 2. Simulate Clarification Output
    step_id = "STEP_CLARIFY"
    output = {
        "clarificationMessage": "Should I deploy to production?",
        "options": ["Yes", "No"],
        "writes_to": "user_decision",
        "thought": "I need to ask the user."
    }
    
    # 3. Add node data manually
    context.plan_graph.add_node(step_id, 
        id=step_id,
        agent="ClarificationAgent",
        writes=["user_decision"],
        status="running"
    )
    
    # 4. Trigger mark_done (which contains our fix)
    print(f"🏃 Marking step {step_id} as done...")
    asyncio.run(context.mark_done(step_id, output))
    
    # 5. Verify Global State
    saved_value = context.plan_graph.graph['globals_schema'].get("user_decision")
    
    print(f"DEBUG: Saved Value Type: {type(saved_value)}")
    print(f"DEBUG: Saved Value Content: {repr(saved_value)}")

    if saved_value is None:
        print("❌ FAILURE: user_decision is None")
        sys.exit(1)

    expected_q = 'Agent asked: "Should I deploy to production?"'
    expected_a = 'User said: "Yes, do it."'
    
    if expected_q not in saved_value:
        print(f"❌ FAILURE: Question missing.\nExpected: {expected_q}\nGot: {saved_value}")
        sys.exit(1)
        
    if expected_a not in saved_value:
        print(f"❌ FAILURE: Answer missing.\nExpected: {expected_a}\nGot: {saved_value}")
        sys.exit(1)

    print("✅ SUCCESS: Rich context saved correctly.")

if __name__ == "__main__":
    test_rich_context_saving()
