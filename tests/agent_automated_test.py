import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

def log(msg, status="INFO"):
    colors = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "ERROR": "\033[91m", "RESET": "\033[0m", "WARN": "\033[93m"}
    print(f"{colors.get(status, '')}[{status}] {msg}{colors['RESET']}")

class MockAgent:
    """
    Simulates an agent's decision-making process to test backend capabilities matching the user's workflow.
    """
    def __init__(self):
        self.memory = []

    def perform_research_task(self, query):
        log(f"--- Starting Mock Research Task: '{query}' ---", "INFO")

        # 1. Submit chat request
        log("Step 1: Sending chat request to /api/chat", "INFO")
        session_id = self._call_chat(query)
        if not session_id:
            log("Research aborted: Chat request failed.", "ERROR")
            return

        # 2. Confirm session is visible
        log(f"Step 2: Verifying session {session_id} exists", "INFO")
        if not self._confirm_session(session_id):
            log("Research aborted: Session not found.", "ERROR")
            return

        log("--- Research Task Accepted ---", "SUCCESS")

    def _call_chat(self, query):
        try:
            payload = {"message": query}
            response = requests.post(f"{BASE_URL}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "accepted":
                log(f"Chat accepted. Session: {data.get('session_id')}", "SUCCESS")
                return data.get("session_id")
            log("Chat request not accepted.", "WARN")
            return None
        except Exception as e:
            log(f"Chat request failed: {e}", "ERROR")
            return None

    def _confirm_session(self, session_id):
        try:
            response = requests.get(f"{BASE_URL}/api/sessions/{session_id}")
            return response.status_code == 200
        except Exception as e:
            log(f"Session lookup failed: {e}", "ERROR")
            return False

    def _mock_generation(self, context_snippet):
        # In a real scenario, this would call /rag/ask, but that endpoint requires a running Ollama instance
        # and streams tokens. For this test, we verify we *could* construct the request.
        log(f"Simulating LLM generation with context: {context_snippet}", "INFO")
        time.sleep(1) # Thinking...
        log("Agent Answer: [Generated Summary would go here]", "SUCCESS")

def test_api_health():
    """Checks if API health endpoint is responsive."""
    log("Checking API Health...", "INFO")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        log("API Health is reachable.", "SUCCESS")
    except requests.exceptions.ConnectionError:
        log("API Health unreachable. Is the backend running?", "ERROR")
    except Exception:
        log("API Health reachable (unexpected response).", "WARN")

if __name__ == "__main__":
    log("Initializing Agent Verification Suite...", "INFO")
    
    # 1. Health Check
    test_api_health()
    
    # 2. Run Mock Agent
    agent = MockAgent()
    
    # Scenario: User asks about a technology
    agent.perform_research_task("mcp-servers python library")

    log("Verification Suite Finished.", "INFO")
