"""Comprehensive onboarding test script.

Tests Phase 1 and Phase 2 goal and quest extraction with expected results.
"""

import sys
import os

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar
from src.onboarding.agent import ArchitectAgent, CriticAgent

def test_phase1():
    """Test Phase 1 goal extraction."""
    print("=" * 70)
    print("PHASE 1 TESTING")
    print("=" * 70)
    print()
    
    sheet = CharacterSheet(user_id="test_user")
    state = ConversationState(
        missing_fields=[
            "north_star_goals",
            "current_quests",
            "stats_career",
            "stats_physical",
            "stats_mental",
            "stats_social",
        ],
        current_topic="Intro",
        phase="phase1",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Test 1: First input - should add 2 goals
    print("TEST 1: First input")
    print("-" * 70)
    test_input_1 = "i want to be able to be calm under pressure and i want to be a chef,"
    print(f"User: {test_input_1}\n")
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_1,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    print(f"Goals after test 1: {len(sheet.goals)}")
    for goal in sheet.goals:
        print(f"  - '{goal.name}' (Pillars: {[p.value for p in goal.pillars]})")
    
    # Expected: 2 goals
    # - "Be calm under pressure" (MENTAL)
    # - "Be a chef" (CAREER)
    expected_goals_1 = [
        ("Be calm under pressure", ["MENTAL"]),
        ("Be a chef", ["CAREER"]),
    ]
    
    print("\nExpected goals:")
    for name, pillars in expected_goals_1:
        print(f"  - '{name}' (Pillars: {pillars})")
    
    # Check results - use simple matching for goal names
    success_1 = len(sheet.goals) == 2
    if success_1:
        for expected_name, expected_pillars in expected_goals_1:
            found = False
            for goal in sheet.goals:
                goal_pillars = [p.value for p in goal.pillars]
                # Check if key words from expected name appear in goal name
                expected_words = set(expected_name.lower().split())
                goal_words = set(goal.name.lower().split())
                # Remove common words
                common_words = {"a", "an", "the", "to", "be", "be able", "be able to", "become", "improve"}
                expected_words = expected_words - common_words
                goal_words = goal_words - common_words
                # Check if they share significant words
                if expected_words & goal_words:  # Intersection
                    # Check if pillars match (allow if at least one expected pillar is present)
                    if any(p in goal_pillars for p in expected_pillars):
                        found = True
                        print(f"  [OK] Found: '{goal.name}' (pillars: {goal_pillars}) (matches expected '{expected_name}' with pillars {expected_pillars})")
                        break
            if not found:
                success_1 = False
                print(f"  [FAIL] Missing or incorrect: {expected_name}")
                # Show what we have
                for goal in sheet.goals:
                    goal_pillars = [p.value for p in goal.pillars]
                    if set(goal_pillars) == set(expected_pillars):
                        print(f"    Found goal with same pillars: '{goal.name}'")
    
    print(f"\nTest 1 Result: {'[PASS]' if success_1 else '[FAIL]'}\n")
    
    # Test 2: Second input - should add 2 more goals
    print("TEST 2: Second input")
    print("-" * 70)
    test_input_2 = "i want to spike a volleyball and i want to be able to networking"
    print(f"User: {test_input_2}\n")
    
    state.conversation_history.append({"role": "user", "content": test_input_1})
    state.conversation_history.append({"role": "assistant", "content": "Test response"})
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_2,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    print(f"Goals after test 2: {len(sheet.goals)}")
    for goal in sheet.goals:
        print(f"  - '{goal.name}' (Pillars: {[p.value for p in goal.pillars]})")
    
    # Expected: 4 goals total
    # - "Be calm under pressure" (MENTAL)
    # - "Be a chef" (CAREER)
    # - "Spike a volleyball" (PHYSICAL)
    # - "Be able to network" (SOCIAL)
    expected_goals_2 = [
        ("Be calm under pressure", ["MENTAL"]),
        ("Be a chef", ["CAREER"]),
        ("Spike a volleyball", ["PHYSICAL"]),
        ("Be able to network", ["SOCIAL"]),
    ]
    
    print("\nExpected goals:")
    for name, pillars in expected_goals_2:
        print(f"  - '{name}' (Pillars: {pillars})")
    
    # Check results - use simple matching for goal names
    success_2 = len(sheet.goals) == 4
    if success_2:
        for expected_name, expected_pillars in expected_goals_2:
            found = False
            for goal in sheet.goals:
                goal_pillars = [p.value for p in goal.pillars]
                # Check if key words from expected name appear in goal name
                expected_words = set(expected_name.lower().split())
                goal_words = set(goal.name.lower().split())
                # Remove common words
                common_words = {"a", "an", "the", "to", "be", "be able", "be able to", "become", "improve"}
                expected_words = expected_words - common_words
                goal_words = goal_words - common_words
                # Check if they share significant words
                if expected_words & goal_words:  # Intersection
                    # Check if pillars match (allow if at least one expected pillar is present)
                    if any(p in goal_pillars for p in expected_pillars):
                        found = True
                        print(f"  [OK] Found: '{goal.name}' (pillars: {goal_pillars}) (matches expected '{expected_name}' with pillars {expected_pillars})")
                        break
            if not found:
                success_2 = False
                print(f"  [FAIL] Missing or incorrect: {expected_name}")
                # Show what we have
                for goal in sheet.goals:
                    goal_pillars = [p.value for p in goal.pillars]
                    if set(goal_pillars) == set(expected_pillars):
                        print(f"    Found goal with same pillars: '{goal.name}'")
    
    print(f"\nTest 2 Result: {'[PASS]' if success_2 else '[FAIL]'}\n")
    
    return sheet, state, success_1 and success_2

def test_phase2(sheet, state):
    """Test Phase 2 quest extraction."""
    print("=" * 70)
    print("PHASE 2 TESTING")
    print("=" * 70)
    print()
    
    state.phase = "phase2"
    critic = CriticAgent()
    
    # Test 3: Mental quests
    print("TEST 3: Mental current quests")
    print("-" * 70)
    test_input_3 = "currently i manage that stress with breathing exercises and listening to music"
    print(f"User: {test_input_3}\n")
    
    state.conversation_history.append({"role": "user", "content": test_input_3})
    state.conversation_history.append({"role": "assistant", "content": "Test response"})
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_3,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    # Find the mental goal
    mental_goal = None
    for goal in sheet.goals:
        if Pillar.MENTAL in goal.pillars:
            mental_goal = goal
            break
    
    if mental_goal:
        print(f"Mental goal: '{mental_goal.name}'")
        print(f"Quests: {mental_goal.current_quests}")
        expected_quests = ["breathing exercises", "listening to music"]
        print(f"Expected quests: {expected_quests}")
        
        success_3 = len(mental_goal.current_quests) == 2
        if success_3:
            for expected_quest in expected_quests:
                found = any(expected_quest.lower() in quest.lower() or quest.lower() in expected_quest.lower() 
                           for quest in mental_goal.current_quests)
                if not found:
                    success_3 = False
                    print(f"  [FAIL] Missing quest: {expected_quest}")
        print(f"\nTest 3 Result: {'[PASS]' if success_3 else '[FAIL]'}\n")
    else:
        print("[FAIL] No mental goal found!")
        success_3 = False
        print(f"\nTest 3 Result: [FAIL]\n")
    
    # Test 4: Career quests
    print("TEST 4: Career current quests")
    print("-" * 70)
    test_input_4 = "im currently practicing knife skills and making some new recipes"
    print(f"User: {test_input_4}\n")
    
    state.conversation_history.append({"role": "user", "content": test_input_4})
    state.conversation_history.append({"role": "assistant", "content": "Test response"})
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_4,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    # Find the career goal
    career_goal = None
    for goal in sheet.goals:
        if Pillar.CAREER in goal.pillars:
            career_goal = goal
            break
    
    if career_goal:
        print(f"Career goal: '{career_goal.name}'")
        print(f"Quests: {career_goal.current_quests}")
        expected_quests = ["knife skills", "making new recipes"]
        print(f"Expected quests: {expected_quests}")
        
        success_4 = len(career_goal.current_quests) == 2
        if success_4:
            for expected_quest in expected_quests:
                found = any(expected_quest.lower() in quest.lower() or quest.lower() in expected_quest.lower() 
                           for quest in career_goal.current_quests)
                if not found:
                    success_4 = False
                    print(f"  [FAIL] Missing quest: {expected_quest}")
        print(f"\nTest 4 Result: {'[PASS]' if success_4 else '[FAIL]'}\n")
    else:
        print("[FAIL] No career goal found!")
        success_4 = False
        print(f"\nTest 4 Result: [FAIL]\n")
    
    # Test 5: Physical quests (should be 0, then ask for skill level)
    print("TEST 5: Physical current quests (should be 0)")
    print("-" * 70)
    test_input_5 = "i want more focused practice sessions. Whether its Plyometrics or Dedicated spiking practice. Currently i dont do them but i want to do them"
    print(f"User: {test_input_5}\n")
    
    state.conversation_history.append({"role": "user", "content": test_input_5})
    state.conversation_history.append({"role": "assistant", "content": "Test response"})
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_5,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    # Find the physical goal
    physical_goal = None
    for goal in sheet.goals:
        if Pillar.PHYSICAL in goal.pillars:
            physical_goal = goal
            break
    
    if physical_goal:
        print(f"Physical goal: '{physical_goal.name}'")
        print(f"Quests: {physical_goal.current_quests}")
        print(f"Expected: 0 quests (user said they don't do them currently)")
        
        success_5 = len(physical_goal.current_quests) == 0
        print(f"\nTest 5 Result: {'[PASS]' if success_5 else '[FAIL]'}\n")
        
        # Test 5b: Skill level
        print("TEST 5b: Physical skill level")
        print("-" * 70)
        test_input_5b = "3"
        print(f"User: {test_input_5b}\n")
        
        state.conversation_history.append({"role": "user", "content": test_input_5b})
        state.conversation_history.append({"role": "assistant", "content": "Test response"})
        
        sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
            test_input_5b,
            sheet,
            state.conversation_history,
            state.phase
        )
        
        # Re-find physical goal after analysis
        physical_goal_after = None
        for goal in sheet.goals:
            if Pillar.PHYSICAL in goal.pillars:
                physical_goal_after = goal
                break
        
        print(f"Physical goal skill level (before): {physical_goal.skill_level}")
        print(f"Physical goal skill level (after): {physical_goal_after.skill_level if physical_goal_after else 'Goal not found'}")
        
        # Check all goals to see which one got the skill level
        print("\nAll goals and their skill levels:")
        for goal in sheet.goals:
            print(f"  - '{goal.name}' (pillars: {[p.value for p in goal.pillars]}): skill_level = {goal.skill_level}")
        
        if physical_goal_after:
            physical_goal = physical_goal_after
        
        print(f"Expected: 3")
        
        success_5b = physical_goal.skill_level == 3
        print(f"\nTest 5b Result: {'[PASS]' if success_5b else '[FAIL]'}\n")
    else:
        print("[FAIL] No physical goal found!")
        success_5 = False
        success_5b = False
        print(f"\nTest 5 Result: [FAIL]\n")
        print(f"\nTest 5b Result: [FAIL]\n")
    
    # Test 6: Social quests
    print("TEST 6: Social current quests")
    print("-" * 70)
    test_input_6 = "I just try to meet new people but i want to focus on specific networking techniques"
    print(f"User: {test_input_6}\n")
    
    state.conversation_history.append({"role": "user", "content": test_input_6})
    state.conversation_history.append({"role": "assistant", "content": "Test response"})
    
    sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
        test_input_6,
        sheet,
        state.conversation_history,
        state.phase
    )
    
    # Find the social goal
    social_goal = None
    for goal in sheet.goals:
        if Pillar.SOCIAL in goal.pillars:
            social_goal = goal
            break
    
    if social_goal:
        print(f"Social goal: '{social_goal.name}'")
        print(f"Quests: {social_goal.current_quests}")
        expected_quests = ["meeting new people"]
        print(f"Expected quests: {expected_quests}")
        
        success_6 = len(social_goal.current_quests) == 1
        if success_6:
            found = any("meet" in quest.lower() or "people" in quest.lower() 
                       for quest in social_goal.current_quests)
            if not found:
                success_6 = False
                print(f"  ❌ Missing quest: meeting new people")
        print(f"\nTest 6 Result: {'[PASS]' if success_6 else '[FAIL]'}\n")
        
        # Test 6b: Skill level
        print("TEST 6b: Social skill level")
        print("-" * 70)
        test_input_6b = "7"
        print(f"User: {test_input_6b}\n")
        
        state.conversation_history.append({"role": "user", "content": test_input_6b})
        state.conversation_history.append({"role": "assistant", "content": "Test response"})
        
        sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
            test_input_6b,
            sheet,
            state.conversation_history,
            state.phase
        )
        
        # Re-find the social goal after analysis (in case goal objects were updated)
        social_goal_after = None
        for goal in sheet.goals:
            if Pillar.SOCIAL in goal.pillars:
                social_goal_after = goal
                break
        
        print(f"Social goal skill level (before): {social_goal.skill_level}")
        print(f"Social goal skill level (after): {social_goal_after.skill_level if social_goal_after else 'Goal not found'}")
        
        # Check all goals to see which one got the skill level
        print("\nAll goals and their skill levels:")
        for goal in sheet.goals:
            print(f"  - '{goal.name}' (pillars: {[p.value for p in goal.pillars]}): skill_level = {goal.skill_level}")
        
        # Use the updated goal reference
        if social_goal_after:
            social_goal = social_goal_after
        print(f"Expected: 7")
        
        success_6b = social_goal.skill_level == 7
        print(f"\nTest 6b Result: {'[PASS]' if success_6b else '[FAIL]'}\n")
    else:
        print("[FAIL] No social goal found!")
        success_6 = False
        success_6b = False
        print(f"\nTest 6 Result: [FAIL]\n")
        print(f"\nTest 6b Result: [FAIL]\n")
    
    return success_3 and success_4 and success_5 and success_5b and success_6 and success_6b

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("COMPREHENSIVE ONBOARDING TEST SUITE")
    print("=" * 70)
    print()
    
    # Run Phase 1 tests
    sheet, state, phase1_success = test_phase1()
    
    if not phase1_success:
        print("=" * 70)
        print("PHASE 1 TESTS HAD SOME FAILURES - Continuing to Phase 2 anyway")
        print("=" * 70)
        print()
    
    # Run Phase 2 tests
    phase2_success = test_phase2(sheet, state)
    
    # Final summary
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Phase 1: {'[PASS]' if phase1_success else '[FAIL]'}")
    print(f"Phase 2: {'[PASS]' if phase2_success else '[FAIL]'}")
    print()
    
    if phase1_success and phase2_success:
        print("[SUCCESS] ALL TESTS PASSED!")
    else:
        print("[FAIL] Some tests failed. Check the output above for details.")
    print()

if __name__ == "__main__":
    main()

