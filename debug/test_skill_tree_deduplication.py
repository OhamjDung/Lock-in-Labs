"""
Test script to verify skill tree deduplication logic.
This will load the existing profile, regenerate the skill tree, and verify that:
1. Skills with the same name are reused across goals (no duplicates)
2. Shared skills appear as prerequisites for multiple goals
3. The tree has a proper interconnected structure
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import CharacterSheet
from src.skill_tree.generator import SkillTreeGenerator
from src.planners import get_planner

def load_profile(user_id: str):
    """Load profile from data folder."""
    profile_path = Path(__file__).parent.parent / "data" / f"{user_id}.json"
    with open(profile_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_skill_tree(skill_tree):
    """Analyze skill tree for deduplication metrics."""
    print("\n" + "="*80)
    print("SKILL TREE ANALYSIS")
    print("="*80)
    
    # Count nodes by type
    node_counts = {}
    for node in skill_tree.nodes:
        node_counts[node.type.value] = node_counts.get(node.type.value, 0) + 1
    
    print(f"\nNode Counts:")
    for node_type, count in node_counts.items():
        print(f"  {node_type}: {count}")
    
    # Find duplicate skill names
    skill_names = {}
    for node in skill_tree.nodes:
        if node.type.value == "Sub-Skill":
            if node.name in skill_names:
                skill_names[node.name].append(node.id)
            else:
                skill_names[node.name] = [node.id]
    
    duplicates = {name: ids for name, ids in skill_names.items() if len(ids) > 1}
    
    print(f"\n{'='*80}")
    if duplicates:
        print(f"❌ FOUND {len(duplicates)} DUPLICATE SKILLS:")
        for name, ids in duplicates.items():
            print(f"  '{name}': {len(ids)} copies")
            for id in ids:
                print(f"    - {id}")
    else:
        print("✅ NO DUPLICATE SKILLS - All skills are unique!")
    
    # Find shared skills (skills that are prerequisites for multiple goals)
    skill_usage = {}  # skill_id -> list of goal_ids that depend on it
    for node in skill_tree.nodes:
        if node.type.value == "Goal":
            for prereq_id in node.prerequisites:
                if prereq_id not in skill_usage:
                    skill_usage[prereq_id] = []
                skill_usage[prereq_id].append(node.id)
    
    shared_skills = {skill_id: goals for skill_id, goals in skill_usage.items() if len(goals) > 1}
    
    print(f"\n{'='*80}")
    if shared_skills:
        print(f"✅ FOUND {len(shared_skills)} SHARED SKILLS (connected to multiple goals):")
        for skill_id, goal_ids in shared_skills.items():
            skill_node = next((n for n in skill_tree.nodes if n.id == skill_id), None)
            skill_name = skill_node.name if skill_node else "Unknown"
            goal_names = []
            for goal_id in goal_ids:
                goal_node = next((n for n in skill_tree.nodes if n.id == goal_id), None)
                if goal_node:
                    goal_names.append(goal_node.name)
            print(f"  '{skill_name}' ({skill_id})")
            print(f"    Connected to {len(goal_ids)} goals: {', '.join(goal_names)}")
    else:
        print("⚠️  NO SHARED SKILLS - Each skill only feeds into one goal")
    
    # Find orphan goals (goals with no prerequisites)
    orphan_goals = [n for n in skill_tree.nodes if n.type.value == "Goal" and not n.prerequisites]
    
    print(f"\n{'='*80}")
    if orphan_goals:
        print(f"❌ FOUND {len(orphan_goals)} ORPHAN GOALS (no prerequisites):")
        for goal in orphan_goals:
            print(f"  - {goal.name} (ID: {goal.id})")
    else:
        print("✅ NO ORPHAN GOALS - All goals have prerequisites!")
    
    print("\n" + "="*80 + "\n")

def main():
    user_id = "8OgBJwxGgRc1No7mi6tbVwmOZE13"
    
    print("Loading profile...")
    profile_data = load_profile(user_id)
    sheet = CharacterSheet(**profile_data['character_sheet'])
    
    print(f"\nProfile loaded: {sheet.user_id}")
    print(f"Goals: {len(sheet.goals)}")
    
    # First, let's regenerate roadmaps for goals that have needed_quests but no roadmap
    print("\n" + "="*80)
    print("REGENERATING ROADMAPS (simulating onboarding fix)")
    print("="*80)
    
    for goal in sheet.goals:
        if goal.pillars and not goal.roadmap and goal.needed_quests:
            print(f"\nRegenerating roadmap for: {goal.name}")
            print(f"  Pillar: {goal.pillars[0].value}, Skill Level: {goal.skill_level}")
            
            planner = get_planner(goal.pillars[0].value)
            skill_nodes = planner.generate_roadmap(
                north_star=goal.name,
                current_quests=goal.current_quests,
                debuffs=sheet.debuffs,
                skill_level=goal.skill_level or 1
            )
            goal.roadmap = skill_nodes
            print(f"  Generated {len(skill_nodes)} roadmap nodes")
        elif not goal.pillars:
            print(f"\n⚠️  Skipping '{goal.name}' - no pillars assigned")
    
    # Now generate skill tree
    print("\n" + "="*80)
    print("GENERATING SKILL TREE")
    print("="*80)
    
    generator = SkillTreeGenerator()
    skill_tree = generator.generate_skill_tree(sheet)
    
    # Analyze results
    analyze_skill_tree(skill_tree)
    
    # Save updated skill tree
    output_path = Path(__file__).parent.parent / "skill_tree_deduped.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(skill_tree.model_dump(), f, indent=4)
    
    print(f"✅ Skill tree saved to: {output_path}")

if __name__ == "__main__":
    main()
