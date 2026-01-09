import json

data = json.load(open('data/test_skill_tree_demo.json'))
tree = data['skill_tree']
nodes = tree['nodes']
career_nodes = [n for n in nodes if n.get('pillar') == 'CAREER']

# Find Accounting Principles
acct_principles = [n for n in career_nodes if 'Accounting Principles' in n.get('name', '')]
print('Found Accounting Principles nodes:')
for n in acct_principles:
    print(f"  {n['name']} (type: {n['type']}, id: {n['id']})")

skill = [n for n in acct_principles if n['type'] == 'Sub-Skill']
if skill:
    skill = skill[0]
    prereqs = skill.get('prerequisites', [])
    print(f'\nSkill prerequisites: {len(prereqs)}')
    for p in prereqs[:10]:
        prereq_node = [n for n in career_nodes if n['id'] == p]
        if prereq_node:
            print(f"  - {p} (type: {prereq_node[0]['type']}, name: {prereq_node[0]['name']})")
        else:
            print(f"  - {p} (not found in career nodes)")
    
    habit_count = len([p for p in prereqs if any(n for n in career_nodes if n['id'] == p and n['type'] == 'Habit')])
    skill_count = len([p for p in prereqs if any(n for n in career_nodes if n['id'] == p and n['type'] == 'Sub-Skill')])
    print(f'\nSummary: {habit_count} habits, {skill_count} other skills in prerequisites')
