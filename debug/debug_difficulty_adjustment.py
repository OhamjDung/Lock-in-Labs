"""
Debug utility for tracking skill tree difficulty adjustments.
Logs the structure of generated skill trees and prerequisite chains.
"""

import json
import os
from datetime import datetime
from pathlib import Path


DEBUG_LOG_DIR = Path(__file__).parent / "difficulty_debug_logs"
DEBUG_LOG_DIR.mkdir(exist_ok=True)


def log_skill_tree_state(user_id: str, skill_tree: dict, label: str = ""):
    """
    Log the entire skill tree structure to a debug file.
    
    Args:
        user_id: User identifier
        skill_tree: The full skill tree dict
        label: Optional label to describe the state (e.g., "before_adjustment", "after_adjustment")
    """
    timestamp = datetime.now().isoformat()
    filename = DEBUG_LOG_DIR / f"{user_id}_tree_{label}_{timestamp.replace(':', '-')}.json"
    
    debug_data = {
        "timestamp": timestamp,
        "user_id": user_id,
        "label": label,
        "tree_structure": skill_tree
    }
    
    with open(filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    
    print(f"[DEBUG] Skill tree logged to: {filename}")
    return filename


def log_prerequisite_chains(user_id: str, skill_tree: dict, label: str = ""):
    """
    Extract and log all prerequisite chains for analysis.
    
    Args:
        user_id: User identifier
        skill_tree: The full skill tree dict
        label: Optional label describing the state
    """
    timestamp = datetime.now().isoformat()
    filename = DEBUG_LOG_DIR / f"{user_id}_prereqs_{label}_{timestamp.replace(':', '-')}.json"
    
    nodes = skill_tree.get("nodes", [])
    
    # Build prerequisite chains
    chains = []
    for node in nodes:
        if node.get("prerequisites"):
            chain = {
                "node_id": node.get("id"),
                "node_name": node.get("name"),
                "node_type": node.get("type"),
                "pillar": node.get("pillar"),
                "prerequisites": node.get("prerequisites"),
                "difficulty": node.get("difficulty"),
                "required_completions": node.get("required_completions")
            }
            chains.append(chain)
    
    debug_data = {
        "timestamp": timestamp,
        "user_id": user_id,
        "label": label,
        "total_nodes": len(nodes),
        "nodes_with_prerequisites": len(chains),
        "prerequisite_chains": chains,
        "node_summary": [
            {
                "id": n.get("id"),
                "name": n.get("name"),
                "type": n.get("type"),
                "pillar": n.get("pillar"),
                "has_prerequisites": bool(n.get("prerequisites")),
                "prereq_count": len(n.get("prerequisites", []))
            }
            for n in nodes
        ]
    }
    
    with open(filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    
    print(f"[DEBUG] Prerequisite chains logged to: {filename}")
    return filename


def log_difficulty_adjustment_request(user_id: str, node_id: str, old_difficulty: str, new_difficulty: str, request_data: dict):
    """
    Log a difficulty adjustment request before processing.
    
    Args:
        user_id: User identifier
        node_id: ID of the node being adjusted
        old_difficulty: Original difficulty level
        new_difficulty: New difficulty level
        request_data: Full request payload
    """
    timestamp = datetime.now().isoformat()
    filename = DEBUG_LOG_DIR / f"{user_id}_adjustment_req_{node_id}_{timestamp.replace(':', '-')}.json"
    
    debug_data = {
        "timestamp": timestamp,
        "user_id": user_id,
        "node_id": node_id,
        "old_difficulty": old_difficulty,
        "new_difficulty": new_difficulty,
        "request_payload": request_data
    }
    
    with open(filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    
    print(f"[DEBUG] Adjustment request logged to: {filename}")
    return filename


def log_difficulty_adjustment_response(user_id: str, node_id: str, response_data: dict, errors: list = None):
    """
    Log the response after difficulty adjustment.
    
    Args:
        user_id: User identifier
        node_id: ID of the node that was adjusted
        response_data: Full response payload
        errors: List of errors if any occurred
    """
    timestamp = datetime.now().isoformat()
    filename = DEBUG_LOG_DIR / f"{user_id}_adjustment_resp_{node_id}_{timestamp.replace(':', '-')}.json"
    
    debug_data = {
        "timestamp": timestamp,
        "user_id": user_id,
        "node_id": node_id,
        "response_payload": response_data,
        "errors": errors or [],
        "has_new_nodes": bool(response_data.get("new_nodes")),
        "new_nodes_count": len(response_data.get("new_nodes", []))
    }
    
    with open(filename, "w") as f:
        json.dump(debug_data, f, indent=2)
    
    print(f"[DEBUG] Adjustment response logged to: {filename}")
    return filename


def list_debug_logs(user_id: str = None):
    """
    List all debug log files, optionally filtered by user ID.
    
    Args:
        user_id: Optional user ID to filter by
    
    Returns:
        List of debug log file paths
    """
    if not DEBUG_LOG_DIR.exists():
        return []
    
    logs = list(DEBUG_LOG_DIR.glob("*.json"))
    
    if user_id:
        logs = [f for f in logs if user_id in f.name]
    
    logs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return logs


def print_debug_summary(user_id: str = None):
    """
    Print a summary of recent debug logs.
    
    Args:
        user_id: Optional user ID to filter by
    """
    logs = list_debug_logs(user_id)
    
    if not logs:
        print(f"No debug logs found for user: {user_id or 'all'}")
        return
    
    print(f"\n{'='*70}")
    print(f"DEBUG LOGS ({len(logs)} total)")
    print(f"{'='*70}\n")
    
    for log_file in logs[:20]:  # Show most recent 20
        print(f"  {log_file.name}")
        try:
            with open(log_file) as f:
                data = json.load(f)
                if "tree_structure" in data:
                    node_count = len(data["tree_structure"].get("nodes", []))
                    print(f"    → Tree with {node_count} nodes")
                elif "prerequisite_chains" in data:
                    chain_count = len(data["prerequisite_chains"])
                    print(f"    → {chain_count} prerequisite chains")
                elif "response_payload" in data:
                    new_nodes = len(data["response_payload"].get("new_nodes", []))
                    print(f"    → Adjustment response with {new_nodes} new nodes")
                    if data.get("errors"):
                        print(f"    → ERRORS: {', '.join(data['errors'])}")
        except Exception as e:
            print(f"    → Error reading: {e}")
        print()


if __name__ == "__main__":
    print("Debug utility for skill tree difficulty adjustments")
    print(f"Logs stored in: {DEBUG_LOG_DIR}")
    print("\nUsage:")
    print("  from debug.debug_difficulty_adjustment import log_skill_tree_state, log_prerequisite_chains")
    print("  log_skill_tree_state(user_id, skill_tree, 'before_adjustment')")
    print("  log_prerequisite_chains(user_id, skill_tree, 'before_adjustment')")
    print("\nRecent logs:")
    print_debug_summary()
