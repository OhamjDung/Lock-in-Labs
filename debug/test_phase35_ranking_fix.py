"""
Test script to verify Phase 3.5 pillar ranking fix.

This script tests that when users provide goal rankings in Phase 3.5,
the Critic correctly ignores them (returns empty deltas) instead of
creating spurious goals like "Career", "Social", "Physical", "Connection".
"""

import json
import sys
import os
from typing import Dict, List

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.onboarding.agent import CriticAgent
from src.models import Goal, Pillar

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def test_phase35_ranking_ignored():
    """Test that Phase 3.5 ranking inputs are ignored."""
    critic = CriticAgent()
    
    # Setup: Create some existing goals
    existing_goals = [
        "ID: goal1 | Name: Become a plumber",
        "ID: goal2 | Name: Be more calm when something stressful happens",
        "ID: goal3 | Name: Be more outgoing and talk to more people",
        "ID: goal4 | Name: Be more flexible",
    ]
    
    test_cases = [
        {
            "name": "Ranking with 'then' connector",
            "input": "Career then social then physical then connection",
            "active_goal_id": "goal1",
            "expected_deltas": 0,
        },
        {
            "name": "Ranking with commas and pillar names",
            "input": "Physical, mental, career, social",
            "active_goal_id": "goal1",
            "expected_deltas": 0,
        },
        {
            "name": "Numbered ranking",
            "input": "1. Career, 2. Physical, 3. Mental, 4. Social",
            "active_goal_id": "goal1",
            "expected_deltas": 0,
        },
        {
            "name": "Simple ranking text",
            "input": "Career is most important, then social, then physical, then mental",
            "active_goal_id": "goal1",
            "expected_deltas": 0,
        },
    ]
    
    print_section("TEST: Phase 3.5 Ranking Inputs Should Be Ignored")
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        response, raw = critic.analyze(
            user_input=test_case["input"],
            active_goal_id=test_case["active_goal_id"],
            existing_goals=existing_goals,
            current_phase="phase3.5"
        )
        
        deltas_count = len(response.get("deltas", []))
        expected_count = test_case["expected_deltas"]
        
        passed_test = deltas_count == expected_count
        status = "✅ PASS" if passed_test else "❌ FAIL"
        
        print(f"\n{status} | {test_case['name']}")
        print(f"  Input: \"{test_case['input']}\"")
        print(f"  Expected deltas: {expected_count}, Got: {deltas_count}")
        print(f"  Intent: {response.get('intent')}")
        print(f"  Feedback: {response.get('feedback_for_architect')}")
        
        if deltas_count > 0:
            print(f"  ⚠️  Deltas created (should be empty):")
            for delta in response.get("deltas", []):
                print(f"    - Operation: {delta.get('operation')}, Payload: {delta.get('payload')}")
        
        if passed_test:
            passed += 1
        else:
            failed += 1
    
    return passed, failed


def test_phase1_goals_still_work():
    """Test that Phase 1 goal creation still works (regression test)."""
    critic = CriticAgent()
    
    existing_goals = []
    
    test_cases = [
        {
            "name": "Single goal in Phase 1",
            "input": "Become a plumber",
            "active_goal_id": None,
            "expected_deltas": 1,
            "expected_operation": "add_goal",
        },
        {
            "name": "Compound goal in Phase 1 (should NOT split)",
            "input": "Be more outgoing and talk to more people",
            "active_goal_id": None,
            "expected_deltas": 1,
            "expected_operation": "add_goal",
        },
        {
            "name": "Multiple separate goals in Phase 1",
            "input": "Career wise i want to be a plumber, Mental wise i want to be more calm",
            "active_goal_id": None,
            "expected_deltas": 2,
            "expected_operation": "add_goal",
        },
    ]
    
    print_section("TEST: Phase 1 Goal Creation (Regression Test)")
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        response, raw = critic.analyze(
            user_input=test_case["input"],
            active_goal_id=test_case["active_goal_id"],
            existing_goals=existing_goals,
            current_phase="phase1"
        )
        
        deltas_count = len(response.get("deltas", []))
        expected_count = test_case["expected_deltas"]
        
        passed_test = (
            deltas_count == expected_count and
            all(d.get("operation") == test_case["expected_operation"] for d in response.get("deltas", []))
        )
        status = "✅ PASS" if passed_test else "❌ FAIL"
        
        print(f"\n{status} | {test_case['name']}")
        print(f"  Input: \"{test_case['input']}\"")
        print(f"  Expected deltas: {expected_count}, Got: {deltas_count}")
        
        if deltas_count > 0:
            for i, delta in enumerate(response.get("deltas", [])):
                print(f"  Delta {i+1}: {delta.get('operation')} - {delta.get('payload')}")
        
        if passed_test:
            passed += 1
        else:
            failed += 1
    
    return passed, failed


def test_phase2_activities_still_work():
    """Test that Phase 2 activity extraction still works (regression test)."""
    critic = CriticAgent()
    
    goal_id = "test-goal-id"
    existing_goals = [f"ID: {goal_id} | Name: Become a plumber"]
    
    test_cases = [
        {
            "name": "Single activity in Phase 2",
            "input": "I watch YouTube videos about plumbing",
            "active_goal_id": goal_id,
            "expected_deltas": 1,
            "expected_operation": "add_quest",
        },
        {
            "name": "Compound activities in Phase 2 (should split)",
            "input": "I watch videos and read books",
            "active_goal_id": goal_id,
            "expected_deltas": 2,
            "expected_operation": "add_quest",
        },
        {
            "name": "Skill rating in Phase 2",
            "input": "7",
            "active_goal_id": goal_id,
            "expected_deltas": 1,
            "expected_operation": "update_skill",
        },
    ]
    
    print_section("TEST: Phase 2 Activity Extraction (Regression Test)")
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        response, raw = critic.analyze(
            user_input=test_case["input"],
            active_goal_id=test_case["active_goal_id"],
            existing_goals=existing_goals,
            current_phase="phase2"
        )
        
        deltas_count = len(response.get("deltas", []))
        expected_count = test_case["expected_deltas"]
        
        passed_test = (
            deltas_count == expected_count and
            all(d.get("operation") == test_case["expected_operation"] for d in response.get("deltas", []))
        )
        status = "✅ PASS" if passed_test else "❌ FAIL"
        
        print(f"\n{status} | {test_case['name']}")
        print(f"  Input: \"{test_case['input']}\"")
        print(f"  Expected deltas: {expected_count}, Got: {deltas_count}")
        
        if deltas_count > 0:
            for i, delta in enumerate(response.get("deltas", [])):
                print(f"  Delta {i+1}: {delta.get('operation')} - {delta.get('payload')}")
        
        if passed_test:
            passed += 1
        else:
            failed += 1
    
    return passed, failed


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("  PHASE 3.5 RANKING FIX - VERIFICATION TEST SUITE")
    print("="*70)
    
    try:
        # Run tests
        p1, f1 = test_phase35_ranking_ignored()
        p2, f2 = test_phase1_goals_still_work()
        p3, f3 = test_phase2_activities_still_work()
        
        # Summary
        total_passed = p1 + p2 + p3
        total_failed = f1 + f2 + f3
        total_tests = total_passed + total_failed
        
        print_section("TEST SUMMARY")
        print(f"\nPhase 3.5 Ranking Tests:     {p1} passed, {f1} failed")
        print(f"Phase 1 Goal Tests:         {p2} passed, {f2} failed")
        print(f"Phase 2 Activity Tests:     {p3} passed, {f3} failed")
        print(f"\n{'─'*70}")
        print(f"TOTAL:                      {total_passed} passed, {total_failed} failed out of {total_tests}")
        
        if total_failed == 0:
            print(f"\n🎉 ALL TESTS PASSED! The Phase 3.5 ranking fix is working correctly!")
            return 0
        else:
            print(f"\n⚠️  {total_failed} test(s) failed. The fix may need adjustment.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
