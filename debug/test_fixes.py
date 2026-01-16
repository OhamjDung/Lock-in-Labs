#!/usr/bin/env python3
"""Quick test script to verify the 3 fixes were applied"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.onboarding.agent import CriticAgent, ArchitectAgent

def test_fix_1_critic_strictness():
    """Test Fix #1: Critic rejects unrelated input"""
    print("\n" + "="*70)
    print("TEST FIX #1: Critic Strictness (Reject Unrelated Input)")
    print("="*70)
    
    critic = CriticAgent()
    
    # Set up a career goal
    career_goal_id = "test-career-goal"
    existing_goals = [f"ID: {career_goal_id} | Name: Become a software engineer"]
    
    # User gives completely unrelated response
    user_input = "I like pizza and watch movies on weekends"
    
    critic_response, _ = critic.analyze(
        user_input=user_input,
        active_goal_id=career_goal_id,
        existing_goals=existing_goals
    )
    
    print(f"User Input: {user_input}")
    print(f"Active Goal: Become a software engineer (CAREER)")
    print(f"\nCritic Response:")
    print(f"  Intent: {critic_response.get('intent')}")
    print(f"  Deltas: {len(critic_response.get('deltas', []))}")
    for delta in critic_response.get('deltas', []):
        print(f"    - {delta['operation']}: {delta['payload']}")
    
    # Check if fix was applied
    is_stop_signal = critic_response.get('intent') == 'STOP_SIGNAL'
    no_deltas = len(critic_response.get('deltas', [])) == 0
    no_bad_quests = not any('pizza' in str(d).lower() or 'movie' in str(d).lower() 
                            for d in critic_response.get('deltas', []))
    
    passed = is_stop_signal or (no_deltas and no_bad_quests)
    
    print(f"\n[FIX VERIFICATION]")
    print(f"  Intent is STOP_SIGNAL: {is_stop_signal}")
    print(f"  No deltas extracted: {no_deltas}")
    print(f"  No pizza/movie quests: {no_bad_quests}")
    print(f"\nFIX #1: {'PASS' if passed else 'FAIL'}")
    
    return passed

def test_fix_2_no_phantom_ack():
    """Test Fix #2: No phantom acknowledgments"""
    print("\n" + "="*70)
    print("TEST FIX #2: No Phantom Acknowledgments")
    print("="*70)
    
    architect = ArchitectAgent()
    
    # Directive that does NOT include acknowledgment
    directive = "Ask the user: 'What are you doing for your CAREER goal?'"
    
    response = architect.generate_response([], directive)
    
    print(f"Directive: {directive}")
    print(f"\nArchitect Response:")
    print(f"  {response}")
    
    # Check if fix was applied
    has_phantom_ack = "Okay, a " in response or response.startswith("Okay")
    starts_with_question = "?" in response
    
    passed = not has_phantom_ack and starts_with_question
    
    print(f"\n[FIX VERIFICATION]")
    print(f"  No 'Okay, a X' phantom acknowledgment: {not has_phantom_ack}")
    print(f"  Contains question: {starts_with_question}")
    print(f"\nFIX #2: {'PASS' if passed else 'FAIL'}")
    
    return passed

def test_fix_3_celebration():
    """Test Fix #3: Check system prompt mentions celebration logic"""
    print("\n" + "="*70)
    print("TEST FIX #3: Phase Celebration Logic")
    print("="*70)
    
    # We can't test this directly without backend, but we can check if the code mentions it
    import subprocess
    
    result = subprocess.run(
        ["grep", "-n", "Excellent!", "backend/api.py"],
        capture_output=True,
        text=True,
        cwd="d:\\Noobcept\\Lock In Labs"
    )
    
    celebration_code_exists = "Excellent!" in result.stdout
    
    print(f"Checking backend/api.py for celebration message...")
    if celebration_code_exists:
        print(f"  Found celebration message: {result.stdout.strip()}")
        passed = True
    else:
        print(f"  Celebration message not found in code")
        passed = False
    
    print(f"\nFIX #3: {'PASS' if passed else 'FAIL'}")
    
    return passed

def main():
    print("\n" + "="*70)
    print("QUICK FIX VERIFICATION TEST")
    print("="*70)
    
    try:
        results = []
        
        # Test each fix
        results.append(("Fix #1 (Critic Strictness)", test_fix_1_critic_strictness()))
        results.append(("Fix #2 (No Phantom ACKs)", test_fix_2_no_phantom_ack()))
        results.append(("Fix #3 (Celebration)", test_fix_3_celebration()))
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        passed_count = sum(1 for _, passed in results if passed)
        
        for fix_name, passed in results:
            status = "PASS" if passed else "FAIL"
            print(f"  {fix_name}: {status}")
        
        print(f"\nTotal: {passed_count}/3 fixes verified")
        
        if passed_count == 3:
            print("\nAll fixes verified successfully!")
        else:
            print(f"\n{3 - passed_count} fix(es) need attention")
        
        return 0 if passed_count == 3 else 1
    
    except Exception as e:
        print(f"\nError during test: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
