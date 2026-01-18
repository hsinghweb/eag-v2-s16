import sys
import os
import subprocess
import requests
import unittest
import sys

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTLINE_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "file_outline.py")
API_URL = "http://localhost:8000"

class TestAgentFeatures(unittest.TestCase):
    
    def test_file_outline_script(self):
        """Verify file_outline.py works on this very file."""
        print(f"\n[Audit] Testing file_outline.py on {__file__}...")
        result = subprocess.run(
            [sys.executable, OUTLINE_SCRIPT, __file__],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[Fail] Output: {result.stderr}")
        
        self.assertEqual(result.returncode, 0, "Script failed to run")
        self.assertIn("CLASS: TestAgentFeatures", result.stdout, "Class missing from outline")
        self.assertIn("FUNC: test_file_outline_script", result.stdout, "Method missing from outline")
        print("[Pass] Outline script works correctly.")

    def test_backend_agent_endpoints(self):
        """Verify backend API is up and running."""
        print("\n[Audit] Pinging API Endpoints...")
        try:
            res = requests.get(f"{API_URL}/health")
            if res.status_code == 200:
                print("[Pass] Health endpoint active.")
            else:
                self.fail(f"Health endpoint failed: {res.status_code}")

            # Chat endpoint should accept requests
            res = requests.post(f"{API_URL}/api/chat", json={"message": "ping"})
            if res.status_code == 200 and res.json().get("status") == "accepted":
                print("[Pass] Chat endpoint active.")
            else:
                self.fail(f"Chat endpoint failed: {res.status_code}")

        except Exception as e:
            self.fail(f"Backend Audit Failed: {e}")

if __name__ == '__main__':
    unittest.main()
