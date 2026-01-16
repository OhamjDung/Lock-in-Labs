"""Generate skill tree by simulating the full API flow (planner + generator)."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skill_tree.generator import SkillTreeGenerator
from src.models import CharacterSheet
from src.planners import get_planner

def generate_tree_with_planner():
    """Load profile, run planner for empty roadmaps, then generate tree."""
    
    profile_path = Path("data/8OgBJwxGgRc1No7mi6tbVwmOZE13.json")
    
    print(f"Loading profile from: {profile_path}")
    with open(profile_path, 'r', encoding='utf-8-sig') as f:
        profile_data = json.load(f)
    
    # Create CharacterSheet
    if 'character_sheet' in profile_data:
        character_sheet = CharacterSheet(**profile_data['character_sheet'])
    else:
        character_sheet = CharacterSheet(**profile_data)
    
    print(f"\nCharacter: {character_sheet.user_id}")
    print(f"Goals: {len(character_sheet.goals)}\n")
    
    # SIMULATE API FLOW: Run planners for goals with empty roadmaps
    for goal in character_sheet.goals:
        if goal.pillars and (not goal.roadmap or len(goal.roadmap) == 0):
            print(f"Running planner for orphan goal: {goal.name}")
            planner = get_planner(goal.pillars[0].value)
            
            roadmap = planner.generate_roadmap(
                north_star=goal.name,
                current_quests=goal.current_quests,
                debuffs=character_sheet.debuffs,
                skill_level=goal.skill_level or 1
            )
            
            goal.roadmap = roadmap
            goal.needed_quests = [node.name for node in roadmap]
            
            print(f"  Generated {len(roadmap)} skills")
    
    # Now generate skill tree with updated roadmaps
    print(f"\nGenerating skill tree...")
    generator = SkillTreeGenerator()
    skill_tree = generator.generate_skill_tree(character_sheet)
    
    # Convert and save
    tree_dict = skill_tree.model_dump()
    
    output_path = Path("skill_tree_final.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tree_dict, f, indent=2)
    
    print(f"\n[OK] Skill tree generated!")
    print(f"Output: {output_path}")
    print(f"\nStatistics:")
    print(f"  Total nodes: {len(tree_dict['nodes'])}")
    
    # Check plumber goal
    plumber = next((n for n in tree_dict['nodes'] if n['id'] == 'goal_become_a_plumber'), None)
    if plumber:
        print(f"\nPlumber goal:")
        print(f"  Prerequisites: {len(plumber['prerequisites'])}")
        if plumber['prerequisites']:
            print(f"  Skills:")
            for prereq_id in plumber['prerequisites'][:5]:
                skill = next((n for n in tree_dict['nodes'] if n['id'] == prereq_id), None)
                if skill:
                    print(f"    - {skill['name']}")
    
    # Check habit variety
    habits = [n for n in tree_dict['nodes'] if n['type'] == 'Habit']
    habit_names = [h['name'] for h in habits]
    duplicates = [name for name in set(habit_names) if habit_names.count(name) > 1]
    
    print(f"\nHabit check:")
    print(f"  Total habits: {len(habits)}")
    print(f"  Unique names: {len(set(habit_names))}")
    if duplicates:
        print(f"  [WARNING] Duplicates found: {duplicates}")
    else:
        print(f"  [OK] All unique!")
    
    # Check descriptions
    legacy_descs = [n for n in tree_dict['nodes'] if 'Legacy skill' in n.get('description', '')]
    print(f"\nDescription check:")
    if legacy_descs:
        print(f"  [WARNING] Found {len(legacy_descs)} nodes with 'Legacy skill...' descriptions")
    else:
        print(f"  [OK] No legacy description leaks!")

if __name__ == "__main__":
    generate_tree_with_planner()
