"""
Test to verify planner generates roadmap even when RAG returns no results.
Tests the "Become a plumber" orphan goal issue.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.planners import get_planner
from src.models import Pillar

def test_plumber_roadmap():
    print("="*80)
    print("PLUMBER ROADMAP TEST (RAG Fallback)")
    print("="*80)
    
    print("\n1. Testing planner for: 'Become a plumber'")
    print("   (This likely has 0 skills in RAG knowledge base)")
    
    planner = get_planner("CAREER")
    
    try:
        roadmap = planner.generate_roadmap(
            north_star="Become a plumber",
            current_quests=[],
            debuffs=[],
            skill_level=2
        )
        
        print(f"\n2. RESULT: Generated {len(roadmap)} skills")
        
        if len(roadmap) == 0:
            print("\n[FAILURE] Planner returned 0 skills!")
            print("This means the fallback is not working.")
            return False
        else:
            print("\n[SUCCESS] Planner used fallback to generate roadmap!")
            print("\nGenerated Skills:")
            for i, node in enumerate(roadmap, 1):
                prereqs = f" (depends on: {', '.join(node.prerequisites)})" if node.prerequisites else ""
                print(f"  {i}. {node.name}{prereqs}")
            
            # Check for prerequisite chains
            has_chain = any(len(node.prerequisites) > 0 for node in roadmap)
            if has_chain:
                print("\n[GOOD] Roadmap has prerequisite chains (creates depth)")
            else:
                print("\n[WARNING] Roadmap has no prerequisites (all nodes are independent)")
            
            return True
            
    except Exception as e:
        print(f"\n[ERROR] Planner failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_obscure_goal():
    print("\n" + "="*80)
    print("OBSCURE GOAL TEST (Another RAG fallback test)")
    print("="*80)
    
    print("\n1. Testing planner for: 'Become a professional bagpipe player'")
    print("   (Very unlikely to be in knowledge base)")
    
    planner = get_planner("CAREER")
    
    try:
        roadmap = planner.generate_roadmap(
            north_star="Become a professional bagpipe player",
            current_quests=[],
            debuffs=[],
            skill_level=1
        )
        
        print(f"\n2. RESULT: Generated {len(roadmap)} skills")
        
        if len(roadmap) > 0:
            print("\n[SUCCESS] Planner handled obscure goal!")
            print("\nGenerated Skills:")
            for i, node in enumerate(roadmap, 1):
                print(f"  {i}. {node.name}")
            return True
        else:
            print("\n[FAILURE] Planner couldn't handle obscure goal")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return False

if __name__ == "__main__":
    result1 = test_plumber_roadmap()
    result2 = test_obscure_goal()
    
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(f"Plumber test: {'PASS' if result1 else 'FAIL'}")
    print(f"Obscure goal test: {'PASS' if result2 else 'FAIL'}")
    
    if result1 and result2:
        print("\nAll tests passed! Planner can now handle goals with no RAG data.")
    else:
        print("\nSome tests failed. Check the output above for details.")
