import os
from typing import List, Dict, Any
from pathlib import Path

def get_file_tree(root_path: str, ignore_patterns: List[str] = None) -> List[Dict[str, Any]]:
    """
    Recursively scan directory and return tree structure for frontend.
    Format: [ { "key": "path", "label": "name", "children": [...] } ]
    """
    if ignore_patterns is None:
        ignore_patterns = ['.git', '__pycache__', '.venv', '.DS_Store', 'node_modules', '.gemini']

    root = Path(root_path)
    if not root.exists():
        return []

    def _should_ignore(name: str) -> bool:
        return any(pattern in name for pattern in ignore_patterns)

    def _scan_dir(path: Path) -> List[Dict[str, Any]]:
        items = []
        try:
            # Sort: Directories first, then files
            entries = sorted(list(path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for entry in entries:
                if _should_ignore(entry.name):
                    continue

                item = {
                    "key": str(entry.absolute()),
                    "label": entry.name,
                    "type": "directory" if entry.is_dir() else "file"
                }

                if entry.is_dir():
                    children = _scan_dir(entry)
                    if children: # Only add children key if not empty (or always add?)
                        # Frontend often expects 'children' array even if empty for dirs
                        item["children"] = children
                    else:
                        item["children"] = []
                
                items.append(item)
                
        except PermissionError:
            pass # Skip unreadable directories
            
        return items

    # Return list of root's children, or root itself?
    # Usually explorer wants the content of the root.
    return _scan_dir(root)
