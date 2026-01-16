"""
Test to verify improved habit generation with strict actionability rules.
"""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import CharacterSheet, Goal, Pillar
from src.skill_tree.generator import SkillTreeGenerator
from src.planners import get_planner

def test_habit_actionability():
    print("="*80)
    print("HABIT ACTIONABILITY TEST")
    print("="*80)
    
    # Create a minimal character sheet with one goal
    sheet = CharacterSheet(user_id="test_user")
    
    # Create a goal with a roadmap
    goal = Goal(
        name="Get better at Python",
        pillars=[Pillar.CAREER],
        current_quests=[],
        needed_quests=[],
        skill_level=3
    )
    
    sheet.goals = [goal]
    
    # Generate roadmap using planner
    print("\n1. Generating roadmap for: Get better at Python")
    planner = get_planner("CAREER")
    roadmap = planner.generate_roadmap(
        north_star="Get better at Python",
        current_quests=[],
        debuffs=[],
        skill_level=3
    )
    goal.roadmap = roadmap
    print(f"   Generated {len(roadmap)} skills")
    
    # Generate skill tree (which will generate habits)
    print("\n2. Generating skill tree (with habits)...")
    generator = SkillTreeGenerator()
    skill_tree = generator.generate_skill_tree(sheet)
    
    # Analyze habits
    habits = [n for n in skill_tree.nodes if n.type.value == "Habit"]
    
    print(f"\n3. Generated {len(habits)} habits")
    print("\n" + "="*80)
    print("HABIT QUALITY ANALYSIS")
    print("="*80)
    
    forbidden_patterns = [
        "Complete 1",
        "Complete the",
        "Practice ",
        " task"
    ]
    
    good_patterns = [
        "Write",
        "Read",
        "Solve",
        "Run",
        "Code",
        "Create",
        "Build",
        "Analyze",
        "Perform"
    ]
    
    good_count = 0
    bad_count = 0
    
    print("\nGOOD HABITS (Actionable):")
    for habit in habits:
        is_bad = any(pattern in habit.name for pattern in forbidden_patterns)
        has_good_verb = any(habit.name.startswith(verb) for verb in good_patterns)
        has_number = any(char.isdigit() for char in habit.name)
        
        if not is_bad and has_good_verb and has_number:
            print(f"  [OK] {habit.name}")
            good_count += 1
        else:
            if bad_count == 0:
                print("\nBAD HABITS (Not Actionable):")
            print(f"  [X] {habit.name}")
            bad_count += 1
    
    print(f"\n{'='*80}")
    print(f"SCORE: {good_count}/{len(habits)} habits are actionable ({good_count/len(habits)*100:.0f}%)")
    print(f"{'='*80}")
    
    if good_count == len(habits):
        print("\nSUCCESS! All habits are actionable!")
    elif good_count > len(habits) * 0.7:
        print("\nPARTIAL SUCCESS - Most habits are good, but some need work")
    else:
        print("\nFAILURE - Most habits are still using lazy templates")
        print("\nTroubleshooting:")
        print("1. Check if LLM is actually being called (vs falling back)")
        print("2. Verify the prompt is being sent correctly")
        print("3. Check API key rotation and rate limits")

def test_directive_flow():
    """Debug test to trace directive through the system"""
    print("="*80)
    print("DIRECTIVE FLOW DEBUG TEST")
    print("="*80)
    print("\nNOTE: Add this to OnboardingModule.jsx to intercept LLM calls:")
    print("""
    // Add before calling getArchitectResponse():
    console.log('[DEBUG] About to call LLM with:', {
        directive: architectDirective,
        reasoning: architectReasoning,
        userMessage: userMessage,
        characterSheet: sheet,
        timestamp: new Date().toISOString()
    });
    
    // Add inside getArchitectResponse() response handler:
    .then(response => {
        console.log('[DEBUG] LLM Response received:', {
            input_directive: <the directive you sent>,
            input_reasoning: <the reasoning you sent>,
            actual_response: response,
            matches_directive: response.includes('<key phrase from directive>'),
            timestamp: new Date().toISOString()
        });
        return response;
    })
    """)
    
    print("\nKey questions to answer with the logs:")
    print("1. Is the directive being passed to the LLM call?")
    print("2. Does the LLM response handler show the directive was received?")
    print("3. Is there a fallback mechanism overriding the directive?")
    print("4. Is the response being modified AFTER the LLM returns it?")

if __name__ == "__main__":
    test_habit_actionability()
    print("\n\n")
    test_directive_flow()
