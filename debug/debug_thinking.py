"""Debug script to check thinking content for 'Have a lot of friend groups'"""

import sys
import os
# Add project root to path (go up one level from debug/ folder)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# Also add debug folder to path so we can import from it
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_phase2_quest_extraction import Phase2TestRunner, ThinkingValidator
from src.models import CharacterSheet, Goal, Pillar

# Create a test runner
runner = Phase2TestRunner()

# Run test 1 and capture thinking records
print("Running TEST 1 to capture thinking records...")
result = runner.run_test_1()

# Get thinking records from the test
print("\n" + "="*70)
print("THINKING RECORDS FOR 'Have a lot of friend groups'")
print("="*70)

# We need to access thinking_records from the test
# Let's check what the validator sees
validator = ThinkingValidator()
sheet = runner.architect.current_sheet if hasattr(runner.architect, 'current_sheet') else None

# Try to find thinking records in the test output
# Actually, let's just run a focused test on the validator
test_goal_name = "Have a lot of friend groups"
test_thinking_samples = [
    "I'm asking about social goals. User wants to have many friend groups.",
    "Current quest status: Have a lot of friend groups has 0/2 quests. Asking about current activities.",
    "I need to ask about friend groups and social connections.",
    "User mentioned social events and clubs. This relates to building friend groups.",
    "Asking about the social goal related to friend groups."
]

print("\nTesting validator with sample thinking:")
for i, thinking in enumerate(test_thinking_samples, 1):
    sheet_test = CharacterSheet(user_id="test")
    sheet_test.goals = [
        Goal(name="Have a lot of friend groups", pillars=[Pillar.SOCIAL], description="", current_quests=[], skill_level=None),
        Goal(name="Drop shipping business", pillars=[Pillar.CAREER], description="", current_quests=[], skill_level=None),
    ]
    passed, error = validator.validate_goal_understanding(thinking, test_goal_name, sheet_test)
    print(f"\nSample {i}:")
    print(f"  Thinking: {thinking}")
    print(f"  Result: {'PASS' if passed else 'FAIL'}")
    if not passed:
        print(f"  Error: {error}")
