import json, os, random

path = os.path.join('data', 'user_01.json')
with open(path, 'r', encoding='utf-8') as f:
    profile = json.load(f)

cs = profile.get('character_sheet', {})
skill_tree = profile.get('skill_tree', {})
nodes = skill_tree.get('nodes', []) or []

# Group Habit node IDs by pillar
habits_by_pillar = {}
for node in nodes:
    type_val = node.get('type')
    # In the JSON, habit nodes use "Habit" (capitalized), so be case-insensitive here
    if isinstance(type_val, str) and type_val.lower() == 'habit':
        pillar = node.get('pillar')
        node_id = node.get('id')
        if pillar and node_id:
            habits_by_pillar.setdefault(pillar, []).append(node_id)

# New habit_progress: 1–2 ACTIVE per pillar, rest LOCKED
new_habit_progress = {}
for pillar, habit_ids in habits_by_pillar.items():
    if not habit_ids:
        continue
    k = min(2, len(habit_ids))
    active_ids = set(random.sample(habit_ids, k))
    for hid in habit_ids:
        new_habit_progress[hid] = {
            "node_id": hid,
            "status": "ACTIVE" if hid in active_ids else "LOCKED",
            "completed_total": 0,
            "completed_since_last_report": 0,
            "last_completed_date": None,
            "streak_days": 0,
        }

# Reset character_sheet but keep stats/goals/debuffs
profile["character_sheet"] = {
    "user_id": cs.get("user_id"),
    "goals": cs.get("goals", {}),
    "stats_career": cs.get("stats_career", {}),
    "stats_physical": cs.get("stats_physical", {}),
    "stats_mental": cs.get("stats_mental", {}),
    "stats_social": cs.get("stats_social", {}),
    "debuffs": cs.get("debuffs", []),
    "xp_total": 0,
    "xp_career": 0,
    "xp_physical": 0,
    "xp_mental": 0,
    "xp_social": 0,
    "habit_progress": new_habit_progress,
    "daily_reports": [],
    "last_report_date": None,
}

with open(path, 'w', encoding='utf-8') as f:
    json.dump(profile, f, indent=4, ensure_ascii=False)

print("Reset character_sheet and randomized 1–2 ACTIVE habits per pillar.")