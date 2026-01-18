
import sys
import unittest
import networkx as nx
from pathlib import Path
from datetime import datetime

# Add root to sys.path
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.graph_adapter import get_graph_data
from core.explorer_utils import get_file_tree

class TestFileMatrix(unittest.TestCase):
    
    def test_graph_adapter(self):
        """Verify Graph Adapter serialization"""
        print("\n🧪 Testing Graph Adapter...")
        G = nx.DiGraph()
        
        # robust data types
        now = datetime.now()
        tags = {"critical", "reviewed"}
        
        G.add_node("ROOT", description="Start", created=now, tags=tags)
        G.add_node("STEP_1", description="Next Step")
        G.add_edge("ROOT", "STEP_1", weight=0.5)
        
        data = get_graph_data(G)
        
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertEqual(len(data["nodes"]), 2)
        self.assertEqual(len(data["edges"]), 1)
        
        # Check serialization
        root_node = next(n for n in data["nodes"] if n["id"] == "ROOT")
        self.assertIsInstance(root_node["created"], str) # Datetime -> ISO Str
        self.assertIsInstance(root_node["tags"], list) # Set -> List
        print("  ✅ Graph serialized correctly.")

    def test_explorer_utils(self):
        """Verify File Explorer Utils"""
        print("\n🧪 Testing Explorer Utils...")
        # Use simple known dir (e.g. core/)
        target_dir = root_dir / "core"
        
        tree = get_file_tree(str(target_dir))
        
        self.assertIsInstance(tree, list)
        self.assertGreater(len(tree), 0)
        
        # Find loop.py
        loop_file = next((item for item in tree if item["label"] == "loop.py"), None)
        self.assertIsNotNone(loop_file)
        self.assertEqual(loop_file["type"], "file")
        
        print(f"  ✅ Found {len(tree)} items in core/")
        print("  ✅ Tree structure valid.")

if __name__ == "__main__":
    unittest.main(verbosity=2)
