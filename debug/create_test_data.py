import json
from pathlib import Path

# Load final skill tree
base_path = Path(__file__).parent.parent
with open(base_path / 'data' / 'skill_tree_final.json', 'r', encoding='utf-8') as f:
    final_tree = json.load(f)

# Create test data in the format the viewer expects
test_data = {
    "character_sheet": {
        "user_id": "8OgBJwxGgRc1No7mi6tbVwmOZE13",
        "habit_progress": {}
    },
    "skill_tree": {
        "nodes": final_tree['nodes']
    }
}

# Save to test data file
with open('frontend/test/skill_tree_test_data.json', 'w', encoding='utf-8') as f:
    json.dump(test_data, f, indent=2)

print(f"Created test data with {len(final_tree['nodes'])} nodes")
