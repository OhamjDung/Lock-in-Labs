"""Generate skill tree for a custom profile."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import CharacterSheet, Goal, Pillar
from src.skill_tree.generator import SkillTreeGenerator
from src.planners import get_planner

def create_custom_profile():
    """Create a character sheet with the specified goals."""
    
    goals = [
        Goal(
            id="goal_1",
            name="Become a plumber",
            pillars=[Pillar.CAREER],
            current_quests=[],
            needed_quests=[],
            description=None,
            skill_level=1,  # N/A -> default to 1
            roadmap=[]
        ),
        Goal(
            id="goal_2",
            name="Be more calm when something stressful happens",
            pillars=[Pillar.MENTAL],
            current_quests=[],
            needed_quests=[],
            description=None,
            skill_level=3,
            roadmap=[]
        ),
        Goal(
            id="goal_3",
            name="Be more outgoing and talk to more people",
            pillars=[Pillar.SOCIAL],
            current_quests=[],
            needed_quests=[],
            description=None,
            skill_level=1,  # N/A -> default to 1
            roadmap=[]
        ),
        Goal(
            id="goal_4",
            name="Be more flexible",
            pillars=[Pillar.PHYSICAL],
            current_quests=[],
            needed_quests=[],
            description=None,
            skill_level=2,
            roadmap=[]
        )
    ]
    
    character_sheet = CharacterSheet(
        user_id="custom_profile",
        goals=goals,
        debuffs=[]
    )
    
    return character_sheet

def generate_skill_tree():
    """Generate skill tree with planner + generator."""
    
    print("Creating custom profile...")
    character_sheet = create_custom_profile()
    
    print(f"\nGoals:")
    for goal in character_sheet.goals:
        print(f"  - {goal.name} ({goal.pillars[0].value}) - Skill Level: {goal.skill_level}")
    
    # Run planners for each goal
    print("\nRunning planners...")
    for goal in character_sheet.goals:
        if goal.pillars and (not goal.roadmap or len(goal.roadmap) == 0):
            print(f"  Planning: {goal.name}")
            planner = get_planner(goal.pillars[0].value)
            
            roadmap = planner.generate_roadmap(
                north_star=goal.name,
                current_quests=goal.current_quests,
                debuffs=character_sheet.debuffs,
                skill_level=goal.skill_level or 1
            )
            
            goal.roadmap = roadmap
            goal.needed_quests = [node.name for node in roadmap]
            print(f"    Generated {len(roadmap)} skills")
    
    # Generate skill tree
    print("\nGenerating skill tree...")
    generator = SkillTreeGenerator()
    skill_tree = generator.generate_skill_tree(character_sheet)
    
    # Convert to dict
    tree_dict = skill_tree.model_dump()
    
    # Save skill tree
    output_path = Path(__file__).parent.parent / 'custom_skill_tree.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tree_dict, f, indent=2)
    
    print(f"\n✅ Skill tree saved to: {output_path}")
    print(f"   Total nodes: {len(tree_dict['nodes'])}")
    
    # Count by type
    node_types = {}
    for node in tree_dict['nodes']:
        node_type = node['type']
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    print(f"\nNode breakdown:")
    for node_type, count in sorted(node_types.items()):
        print(f"  - {node_type}: {count}")
    
    # Create test data for viewer
    test_data = {
        "character_sheet": {
            "user_id": "custom_profile",
            "habit_progress": {}
        },
        "skill_tree": {
            "nodes": tree_dict['nodes']
        }
    }
    
    viewer_data_path = Path(__file__).parent.parent / 'frontend' / 'test' / 'skill_tree_test_data.json'
    with open(viewer_data_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, indent=2)
    
    print(f"\n✅ Viewer data updated: {viewer_data_path}")
    print(f"\n📊 To view in browser:")
    print(f"   1. Open: http://localhost:8080/skill_tree_viewer.html")
    print(f"   2. Click 'Load New Tree' button")
    print(f"   3. Use pillar filters to explore different goals")
    
    return tree_dict

if __name__ == "__main__":
    generate_skill_tree()
