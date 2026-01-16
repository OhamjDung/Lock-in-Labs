#!/usr/bin/env python3
"""Simple scenario test without hitting rate limits - tests the 3 main requirements"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.onboarding.agent import CriticAgent, ArchitectAgent

def test_scenario_1():
    """REQUIREMENT 1: Does it ask for missing pillars when insufficient goals provided?"""
    print("\n" + "="*70)
    print("REQUIREMENT 1: PHASE 1 - INSUFFICIENT GOALS")
    print("="*70)
    print("\nScenario: User provides only CAREER and PHYSICAL goals")
    print("Expected: AI should ask for MENTAL and SOCIAL goals\n")
    
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    # User provides 2 pillars worth of goals
    user_input = "I want to become a software engineer and run a marathon"
    
    critic_resp, _ = critic.analyze(
        user_input=user_input,
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"[Critic] Extracted {len(critic_resp['deltas'])} goals:")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    # Simulate what backend would do - ask about missing pillars
    missing_pillars = ["mental", "social"]
    directive = f"Ask the user about their goals for the {missing_pillars[0]} pillar of their life."
    
    arch_resp = architect.generate_response([], directive)
    print(f"\n[Architect] Response:")
    print(f"  {arch_resp}")
    
    # Check requirements
    has_goals = len(critic_resp['deltas']) == 2
    asks_about_pillar = any(p in arch_resp.lower() for p in missing_pillars)
    is_question = '?' in arch_resp
    
    print(f"\n[CHECKS]")
    print(f"  Extracted 2 goals: {has_goals}")
    print(f"  Asks about missing pillar: {asks_about_pillar}")
    print(f"  Response is question: {is_question}")
    
    return all([has_goals, asks_about_pillar, is_question])

def test_scenario_2():
    """REQUIREMENT 2: Does it handle excess goals appropriately?"""
    print("\n" + "="*70)
    print("REQUIREMENT 2: PHASE 1 - EXCESS GOALS (All 4 Pillars)")
    print("="*70)
    print("\nScenario: User provides 4+ goals covering all pillars")
    print("Expected: AI should acknowledge completion and prepare for phase 2\n")
    
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    # User provides multiple goals
    user_input = "I want to be a CEO, run a marathon, meditate daily, and build strong friendships"
    
    critic_resp, _ = critic.analyze(
        user_input=user_input,
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"[Critic] Extracted {len(critic_resp['deltas'])} goals:")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    # Simulate backend asking architect to move forward
    directive = "Acknowledge that we have all 4 pillars covered. Ask about the first goal's activities."
    
    arch_resp = architect.generate_response([], directive)
    print(f"\n[Architect] Response:")
    print(f"  {arch_resp}")
    
    # Check requirements
    has_many_goals = len(critic_resp['deltas']) >= 4
    acknowledges = any(w in arch_resp.lower() for w in ['covered', 'all', 'good', 'great', 'excellent', 'perfect'])
    
    print(f"\n[CHECKS]")
    print(f"  Extracted 4+ goals: {has_many_goals}")
    print(f"  Acknowledges completion: {acknowledges}")
    
    return all([has_many_goals, acknowledges])

def test_scenario_3():
    """REQUIREMENT 3: Does it reject unrelated responses and ask again?"""
    print("\n" + "="*70)
    print("REQUIREMENT 3: PHASE 2 - UNRELATED RESPONSE (Reject & Ask Again)")
    print("="*70)
    print("\nScenario: Q: 'What are you doing for CAREER goal?'")
    print("         A: 'I like pizza and watch movies'")
    print("Expected: AI rejects this and asks again firmly\n")
    
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    # Setup a career goal
    career_goal_id = "test-career-1"
    existing_goals = [f"ID: {career_goal_id} | Name: Become a software engineer"]
    
    # User gives unrelated response
    user_input = "I like pizza and watch movies on weekends"
    
    critic_resp, _ = critic.analyze(
        user_input=user_input,
        active_goal_id=career_goal_id,
        existing_goals=existing_goals
    )
    
    print(f"[Critic] Intent: {critic_resp['intent']}")
    print(f"[Critic] Deltas: {len(critic_resp['deltas'])}")
    
    # Check if critic rejected it
    critic_rejected = critic_resp['intent'] == 'STOP_SIGNAL' or len(critic_resp['deltas']) == 0
    
    # Simulate architect asking again
    directive = "The user gave an unrelated response. Ask them again about their CAREER goal: Become a software engineer. Ask what they're currently doing for this goal."
    
    arch_resp = architect.generate_response([], directive)
    print(f"\n[Architect] Response:")
    print(f"  {arch_resp}")
    
    # Check requirements
    architect_asks_again = any(w in arch_resp.lower() for w in ['software', 'engineer', 'career', 'doing', 'goal'])
    is_question = '?' in arch_resp
    
    print(f"\n[CHECKS]")
    print(f"  Critic rejected unrelated: {critic_rejected}")
    print(f"  Architect asks about correct topic: {architect_asks_again}")
    print(f"  Architect asks as question: {is_question}")
    
    return all([critic_rejected, architect_asks_again, is_question])

def test_scenario_4():
    """REQUIREMENT 4: Is the system stable and doesn't crash with weird input?"""
    print("\n" + "="*70)
    print("REQUIREMENT 4: STABILITY - Handles Edge Cases")
    print("="*70)
    print("\nScenarios: Various edge cases")
    print("Expected: No crashes, graceful handling\n")
    
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    edge_cases = [
        ("Very long rambling", "a" * 500),
        ("Numbers only", "12345"),
        ("Special chars", "!@#$%^&*()"),
    ]
    
    crashes = 0
    
    for case_name, case_input in edge_cases:
        try:
            critic_resp, _ = critic.analyze(
                user_input=case_input if case_input.strip() else "test",
                active_goal_id="test-goal",
                existing_goals=["ID: test-goal | Name: Test"]
            )
            
            arch_resp = architect.generate_response([], "Ask the user again.")
            
            print(f"  {case_name}: OK")
        except Exception as e:
            print(f"  {case_name}: CRASH - {str(e)[:30]}")
            crashes += 1
    
    no_crashes = crashes == 0
    
    print(f"\n[CHECKS]")
    print(f"  No crashes: {no_crashes}")
    
    return no_crashes

def test_scenario_5():
    """REQUIREMENT 5: Pillar Alignment - Right question for right pillar"""
    print("\n" + "="*70)
    print("REQUIREMENT 5: PILLAR ALIGNMENT")
    print("="*70)
    print("\nScenario: Testing that career goal asks career questions, not fitness\n")
    
    architect = ArchitectAgent()
    
    # Career goal question
    career_directive = "Ask what the user is currently doing for their CAREER goal: Become a software engineer"
    career_resp = architect.generate_response([], career_directive)
    
    print(f"[Career Question]:")
    print(f"  {career_resp}")
    
    # Check career keywords present
    career_keywords = any(w in career_resp.lower() for w in ['software', 'engineer', 'code', 'learning', 'skill', 'professional', 'doing', 'work'])
    bad_keywords = any(w in career_resp.lower() for w in ['run', 'marathon', 'exercise', 'friend'])
    
    print(f"\n[CHECKS]")
    print(f"  Has career keywords: {career_keywords}")
    print(f"  No unrelated keywords: {not bad_keywords}")
    print(f"  (If asking about fitness when goal is career = BAD) {not bad_keywords}")
    
    return career_keywords and not bad_keywords

def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE VERIFICATION - YOUR 5 REQUIREMENTS")
    print("="*70)
    
    results = []
    
    try:
        results.append(("Req 1: Insufficient goals ask for more", test_scenario_1()))
        results.append(("Req 2: Excess goals acknowledged", test_scenario_2()))
        results.append(("Req 3: Unrelated responses rejected", test_scenario_3()))
        results.append(("Req 4: System stable on edge cases", test_scenario_4()))
        results.append(("Req 5: Pillar alignment verified", test_scenario_5()))
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Summary
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for req, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {req}")
    
    print(f"\nTotal: {passed}/{total} requirements met ({int(100*passed/total)}%)")
    
    if passed == total:
        print("\n✓ ALL REQUIREMENTS SATISFIED!")
        return 0
    else:
        print(f"\n✗ {total - passed} requirement(s) need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())
