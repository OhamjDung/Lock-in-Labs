"""Generate a fresh skill tree with all the new fixes applied."""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.skill_tree.generator import SkillTreeGenerator
from backend.api import CharacterSheet

def generate_tree():
    """Generate skill tree for the test user."""
    
    # Load the user profile
    profile_path = Path("data/8OgBJwxGgRc1No7mi6tbVwmOZE13.json")
    
    print(f"Loading profile from: {profile_path}")
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile_data = json.load(f)
    
    # Create CharacterSheet from profile (extract from nested structure)
    if 'character_sheet' in profile_data:
        character_sheet = CharacterSheet(**profile_data['character_sheet'])
    else:
        character_sheet = CharacterSheet(**profile_data)
    
    print(f"\nGenerating skill tree for user: {character_sheet.user_id}")
    print(f"Goals to process: {len(character_sheet.goals)}")
    for goal in character_sheet.goals:
        pillars_str = ", ".join(goal.pillars) if goal.pillars else "No pillar"
        goal_name = goal.description or goal.name
        print(f"  - {goal_name} ({pillars_str})")
    
    # Generate skill tree
    generator = SkillTreeGenerator()
    skill_tree = generator.generate_skill_tree(character_sheet)
    
    # Convert to dict for JSON serialization (SkillTree is a Pydantic model)
    tree_dict = skill_tree.model_dump()
    
    # Save to file
    output_path = Path("skill_tree_new_logic.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tree_dict, f, indent=2)
    
    print(f"\n✅ Skill tree generated successfully!")
    print(f"📁 Saved to: {output_path}")
    print(f"\n📊 Tree Statistics:")
    print(f"  - Total nodes: {len(tree_dict['nodes'])}")
    
    # Count node types
    node_types = {}
    for node in tree_dict['nodes']:
        node_type = node['type']
        node_types[node_type] = node_types.get(node_type, 0) + 1
    
    print(f"\n📋 Node Types:")
    for node_type, count in sorted(node_types.items()):
        print(f"  - {node_type}: {count}")
    
    # Check for duplicates
    skill_names = [node['name'] for node in tree_dict['nodes'] if node['type'] == 'sub-skill']
    duplicate_names = [name for name in set(skill_names) if skill_names.count(name) > 1]
    
    if duplicate_names:
        print(f"\n⚠️  Warning: Found {len(duplicate_names)} duplicate skill names:")
        for name in duplicate_names:
            print(f"  - {name} (appears {skill_names.count(name)} times)")
    else:
        print(f"\n✅ No duplicate skills found!")
    
    # Show sample habits
    print(f"\n🎯 Sample Habits (Actionability Check):")
    habit_nodes = [node for node in tree_dict['nodes'] if node['type'] == 'habit'][:5]
    for i, habit in enumerate(habit_nodes, 1):
        print(f"  {i}. {habit['name']}")
    
    return tree_dict

if __name__ == "__main__":
    generate_tree()
