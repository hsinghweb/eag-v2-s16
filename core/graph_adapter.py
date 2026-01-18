import networkx as nx
from typing import Dict, List, Any
import json
from datetime import datetime

def _serialize_value(val: Any) -> Any:
    """Helper to serialize complex types for JSON"""
    if isinstance(val, (datetime)):
        return val.isoformat()
    if isinstance(val, (set)):
        return list(val)
    return val

def get_graph_data(graph: nx.DiGraph) -> Dict[str, Any]:
    """
    Convert NetworkX graph to frontend-friendly JSON structure.
    Target format: { "nodes": [...], "edges": [...] }
    """
    nodes = []
    edges = []

    # Process Nodes
    for node_id, data in graph.nodes(data=True):
        # Create a safe copy of data for serialization
        safe_data = {k: _serialize_value(v) for k, v in data.items()}
        
        # Ensure ID is present
        safe_data["id"] = node_id
        
        # Add label if missing
        if "description" in safe_data:
            safe_data["label"] = safe_data["description"][:30] + "..." if len(safe_data["description"]) > 30 else safe_data["description"]
        else:
            safe_data["label"] = node_id

        nodes.append(safe_data)

    # Process Edges
    for source, target, data in graph.edges(data=True):
        edge_obj = {
            "source": source,
            "target": target,
            "id": f"{source}->{target}"
        }
        # Merge edge attributes
        edge_obj.update({k: _serialize_value(v) for k, v in data.items()})
        edges.append(edge_obj)

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "generated_at": datetime.utcnow().isoformat()
        }
    }
