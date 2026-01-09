"""
Test script to run skill tree generation with a pre-built profile.
Uses the data from the user's onboarding session.
"""

import sys
import os
import json

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, Goal, Pillar, SkillTree
from src.skill_tree.generator import SkillTreeGenerator
from src.planners import get_planner
from src.storage import save_profile

# Debug log path
DEBUG_LOG = r'd:\Noobcept\Lock In Labs\.cursor\debug.log'

def log_debug(location, message, data, hypothesis_id):
    """Write a debug log entry."""
    import time
    entry = {
        "location": location,
        "message": message,
        "data": data,
        "timestamp": time.time() * 1000,
        "sessionId": "debug-session",
        "hypothesisId": hypothesis_id
    }
    with open(DEBUG_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def main():
    user_id = "AwY9SCGMYHS8gCaMXf51jLnMwIj2"
    
    print("=" * 60)
    print("SKILL TREE GENERATION PIPELINE TEST")
    print("=" * 60)
    
    # Create CharacterSheet with goals from the onboarding session
    # IMPORTANT: Goals must have pillars assigned!
    sheet = CharacterSheet(user_id=user_id)
    
    # Goal 1: Career
    goal1 = Goal(
        name="Become an accountant",
        pillars=[Pillar.CAREER],
        current_quests=["Watch YouTube videos about accounting", "Taking an accounting bootcamp"],
        skill_level=None
    )
    
    # Goal 2: Physical
    goal2 = Goal(
        name="Have more endurance",
        pillars=[Pillar.PHYSICAL],
        current_quests=["Go for a run once a week"],
        skill_level=6
    )
    
    # Goal 3: Mental
    goal3 = Goal(
        name="Be more in tune with myself",
        pillars=[Pillar.MENTAL],
        current_quests=[],
        skill_level=3
    )
    
    # Goal 4: Social
    goal4 = Goal(
        name="Be able to talk to more people",
        pillars=[Pillar.SOCIAL],
        current_quests=[],
        skill_level=4
    )
    
    sheet.goals = [goal1, goal2, goal3, goal4]
    
    print("\n[STEP 1] Created CharacterSheet with goals:")
    for g in sheet.goals:
        pillars_str = [p.value for p in g.pillars]
        print(f"  - {g.name} | Pillars: {pillars_str} | Quests: {len(g.current_quests)} | Skill: {g.skill_level}")
    
    log_debug(
        "test_pipeline:step1",
        "CharacterSheet created with goals",
        {"goals": [{"name": g.name, "pillars": [p.value for p in g.pillars], "quests": g.current_quests} for g in sheet.goals]},
        "H1"
    )
    
    # PHASE 4: Run planners to generate needed_quests
    print("\n[STEP 2] Running planners to generate needed_quests...")
    
    for goal in sheet.goals:
        print(f"\n  Processing goal: '{goal.name}'")
        print(f"    Pillars: {[p.value for p in goal.pillars]}")
        
        log_debug(
            "test_pipeline:planner_check",
            f"Checking goal for planner",
            {"goal_name": goal.name, "pillars": [p.value for p in goal.pillars], "has_pillars": bool(goal.pillars)},
            "H2"
        )
        
        if goal.pillars:
            pillar_value = goal.pillars[0].value
            print(f"    Using planner for pillar: {pillar_value}")
            
            try:
                planner = get_planner(pillar_value)
                print(f"    Planner type: {planner.__class__.__name__}")
                
                needed_skill_nodes = planner.generate_roadmap(
                    north_star=goal.name,
                    current_quests=goal.current_quests,
                    debuffs=sheet.debuffs
                )
                
                goal.needed_quests = [node.name for node in needed_skill_nodes]
                print(f"    Generated {len(goal.needed_quests)} needed_quests:")
                for nq in goal.needed_quests:
                    print(f"      - {nq}")
                
                log_debug(
                    "test_pipeline:planner_result",
                    f"Planner generated needed_quests",
                    {"goal_name": goal.name, "needed_quests": goal.needed_quests},
                    "H2-H3"
                )
            except Exception as e:
                print(f"    ERROR running planner: {e}")
                log_debug(
                    "test_pipeline:planner_error",
                    f"Planner failed",
                    {"goal_name": goal.name, "error": str(e)},
                    "H2"
                )
        else:
            print(f"    SKIPPED - No pillars assigned!")
            log_debug(
                "test_pipeline:no_pillars",
                f"SKIPPED - Goal has no pillars",
                {"goal_name": goal.name},
                "H1"
            )
    
    # Summary before skill tree generation
    print("\n[STEP 3] Goals after planner phase:")
    for g in sheet.goals:
        print(f"  - {g.name}: {len(g.needed_quests)} needed_quests")
        if g.needed_quests:
            for nq in g.needed_quests[:3]:
                print(f"      - {nq}")
            if len(g.needed_quests) > 3:
                print(f"      ... and {len(g.needed_quests) - 3} more")
    
    log_debug(
        "test_pipeline:pre_skilltree",
        "Goals before skill tree generation",
        {"goals": [{"name": g.name, "pillars": [p.value for p in g.pillars], "needed_quests": g.needed_quests} for g in sheet.goals]},
        "H3"
    )
    
    # PHASE 5: Generate skill tree
    print("\n[STEP 4] Generating skill tree...")
    
    skill_tree_generator = SkillTreeGenerator()
    skill_tree = skill_tree_generator.generate_skill_tree(sheet)
    
    # Analyze the generated skill tree
    print(f"\n[STEP 5] Skill tree analysis:")
    print(f"  Total nodes: {len(skill_tree.nodes)}")
    
    node_types = {}
    node_pillars = {}
    for node in skill_tree.nodes:
        node_type = node.type.value if hasattr(node.type, 'value') else str(node.type)
        node_pillar = node.pillar.value if hasattr(node.pillar, 'value') else str(node.pillar)
        node_types[node_type] = node_types.get(node_type, 0) + 1
        node_pillars[node_pillar] = node_pillars.get(node_pillar, 0) + 1
    
    print(f"  By type: {node_types}")
    print(f"  By pillar: {node_pillars}")
    
    # Check for prerequisites
    nodes_with_prereqs = sum(1 for n in skill_tree.nodes if n.prerequisites)
    print(f"  Nodes with prerequisites: {nodes_with_prereqs}")
    
    log_debug(
        "test_pipeline:post_skilltree",
        "Skill tree generated",
        {
            "nodes_count": len(skill_tree.nodes),
            "node_types": node_types,
            "node_pillars": node_pillars,
            "nodes_with_prereqs": nodes_with_prereqs
        },
        "H3"
    )
    
    # Print detailed node info
    print("\n[STEP 6] Node details:")
    for node in skill_tree.nodes:
        node_type = node.type.value if hasattr(node.type, 'value') else str(node.type)
        node_pillar = node.pillar.value if hasattr(node.pillar, 'value') else str(node.pillar)
        prereqs = len(node.prerequisites) if node.prerequisites else 0
        print(f"  [{node_type}] {node.name} | Pillar: {node_pillar} | Prerequisites: {prereqs}")
    
    # Save the profile
    print("\n[STEP 7] Saving profile...")
    
    profile_data = {
        "character_sheet": sheet.model_dump(),
        "skill_tree": skill_tree.model_dump()
    }
    
    save_profile(profile_data, user_id)
    print(f"  Profile saved for user: {user_id}")
    
    log_debug(
        "test_pipeline:saved",
        "Profile saved",
        {"user_id": user_id, "nodes_count": len(skill_tree.nodes)},
        "H3"
    )
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print("\nNow refresh the frontend and check the Blueprint page!")

if __name__ == "__main__":
    main()
