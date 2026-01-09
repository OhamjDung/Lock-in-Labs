import json

data = json.load(open('data/test_skill_tree_demo.json'))
tree = data['skill_tree']
nodes = tree['nodes']

career_nodes = [n for n in nodes if n.get('pillar') == 'CAREER']
goal = [n for n in career_nodes if n['type'] == 'Goal'][0]

print(f"Goal: {goal['name']}")
print(f"Goal prerequisites: {len(goal.get('prerequisites', []))}")

# Find skills that are prerequisites of the goal
skill_ids = goal.get('prerequisites', [])
skills = [n for n in career_nodes if n['id'] in skill_ids and n['type'] == 'Sub-Skill']

print(f"\nFound {len(skills)} skills under goal:")
for s in skills[:5]:
    prereq_count = len(s.get('prerequisites', []))
    print(f"  - {s['name']}: {prereq_count} prerequisites")

# Find habits that are in skill prerequisites (correct way)
print(f"\nFinding habits for each skill (from skill.prerequisites):")
for skill in skills[:5]:
    # Find habits that are in the skill's prerequisites list
    habit_ids = [p for p in skill.get('prerequisites', [])]
    habits = [n for n in career_nodes if n['id'] in habit_ids and n['type'] == 'Habit']
    other_skills = [n for n in career_nodes if n['id'] in habit_ids and n['type'] == 'Sub-Skill']
    print(f"  - {skill['name']}: {len(habits)} habits, {len(other_skills)} other skills in prerequisites")
    for h in habits[:3]:
        print(f"      * {h['name']}")
