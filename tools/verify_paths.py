
import sys
import os
import yaml
from pathlib import Path
import re

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
os.chdir(root_dir)

print(f"[INFO] Verifying paths from Root: {root_dir}")

def check_file(path_str, description):
    path = Path(path_str)
    if not path.is_absolute():
        path = root_dir / path
    
    if path.exists():
        print(f"[OK] Found {description}: {path_str}")
        return True
    else:
        print(f"[MISSING] {description}: {path_str} (Resolved: {path})")
        return False

all_passed = True

# 1. Check Agent Config
print("\n--- Checking Agent Config ---")
try:
    with open("config/agent_config.yaml", "r") as f:
        agent_config = yaml.safe_load(f)["agents"]
        for agent, data in agent_config.items():
            if "prompt_file" in data:
                if not check_file(data["prompt_file"], f"{agent} Prompt"):
                    all_passed = False
except Exception as e:
    print(f"[ERROR] reading agent_config.yaml: {e}")
    all_passed = False

# 2. Check MultiMCP Config
print("\n--- Checking MultiMCP Server Scripts ---")
try:
    with open("mcp_servers/multi_mcp.py", "r") as f:
        content = f.read()
        matches = re.findall(r'"args":\s*\["run",\s*"(.*?)"\]', content)
        for script in matches:
             if not check_file(script, "MCP Server Script"):
                 all_passed = False
except Exception as e:
    print(f"[ERROR] reading multi_mcp.py: {e}")
    all_passed = False

# 3. Check Sandbox Path
print("\n--- Checking Sandbox Import ---")
if not check_file("tools/sandbox.py", "Sandbox Tool"):
    all_passed = False

# 4. Check MCP Server Config (YAML)
print("\n--- Checking MCP Server YAML ---")
try:
    with open("config/mcp_server_config.yaml", "r") as f:
        mcp_config = yaml.safe_load(f)["mcp_servers"]
        for server in mcp_config:
            if "cwd" in server:
                 if not check_file(server["cwd"], f"{server.get('id', 'unknown')} CWD"):
                     all_passed = False
            if "script" in server and not server["script"].startswith("http"):
                 potential_path = Path("mcp_servers") / server["script"]
                 if not check_file(str(potential_path), f"{server.get('id', 'unknown')} Script"):
                     all_passed = False

except Exception as e:
    print(f"[ERROR] reading mcp_server_config.yaml: {e}")
    all_passed = False

print("\n--- Summary ---")
if all_passed:
    print("[SUCCESS] ALL CHECKS PASSED. Paths are valid.")
    sys.exit(0)
else:
    print("[FAILURE] ERRORS FOUND. See above.")
    sys.exit(1)
