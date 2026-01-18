
import asyncio
import sys
import yaml
from pathlib import Path

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from mcp_servers.multi_mcp import MultiMCP

def test_config_loading():
    print("🧪 Testing MultiMCP Config Loading...")
    try:
        mcp = MultiMCP()
        configs = mcp.server_configs
        print(f"  Loaded configs: {list(configs.keys())}")
        
        expected = ["documents", "websearch"] # IDs from yaml
        for exp in expected:
            if exp in configs:
                print(f"  ✅ Found config: {exp}")
            else:
                print(f"  ❌ Missing config: {exp}")
                
        # Check specific config values
        rag = configs.get("documents")
        if rag and rag["command"] == "uv" and "server_rag.py" in rag["args"][1]:
             print(f"  ✅ RAG config correct: {rag}")
        else:
             print(f"  ❌ RAG config incorrect: {rag}")

    except Exception as e:
        print(f"  ❌ MultiMCP Init Failed: {e}")

if __name__ == "__main__":
    test_config_loading()
