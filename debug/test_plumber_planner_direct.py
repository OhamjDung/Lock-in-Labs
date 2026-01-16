"""Test that the planner generates roadmap for 'Become a plumber' goal."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.planners import get_planner

def test_plumber_planner():
    """Test planner for plumber goal."""
    
    print("Testing planner for 'Become a plumber' goal...")
    
    planner = get_planner("CAREER")
    
    roadmap = planner.generate_roadmap(
        north_star="Become a plumber",
        current_quests=[],
        debuffs=[],
        skill_level=2
    )
    
    print(f"\n[OK] Planner generated {len(roadmap)} skills:")
    for i, node in enumerate(roadmap, 1):
        prereqs = ", ".join(node.prerequisites) if node.prerequisites else "None"
        print(f"  {i}. {node.name}")
        print(f"     ID: {node.id}")
        print(f"     Prerequisites: {prereqs}")
    
    if len(roadmap) == 0:
        print("\n[ERROR] Planner returned empty roadmap!")
        return False
    
    print("\n[SUCCESS] Planner successfully generated roadmap!")
    return True

if __name__ == "__main__":
    success = test_plumber_planner()
    sys.exit(0 if success else 1)
