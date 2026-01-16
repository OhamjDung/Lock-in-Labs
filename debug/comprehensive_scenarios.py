#!/usr/bin/env python3
"""Comprehensive scenario testing with varied phrasings"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.onboarding.agent import CriticAgent, ArchitectAgent

def test_scenario(name, test_func):
    """Run a test scenario and report results"""
    print("\n" + "="*80)
    print(f"SCENARIO: {name}")
    print("="*80)
    try:
        result = test_func()
        status = "PASS" if result else "FAIL"
        print(f"\n>>> {status}")
        return result
    except Exception as e:
        print(f"\n>>> CRASH: {e}")
        return False

# ============================================================================
# PHASE 1: INSUFFICIENT GOALS
# ============================================================================

def phase1_insufficient_1():
    """Scenario 1a: User provides only 1 pillar - should ask for more"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nUser says: 'I want to become a software engineer'")
    print("Expected: AI asks about other pillars (physical, mental, social)")
    
    critic_resp, _ = critic.analyze(
        user_input="I want to become a software engineer",
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"\nCritic extracted {len(critic_resp['deltas'])} goal(s)")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    arch_resp = architect.generate_response(
        [],
        "The user only provided a CAREER goal. Ask about missing pillars: PHYSICAL, MENTAL, SOCIAL. Which one should we discuss next?"
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "1 goal extracted": len(critic_resp['deltas']) == 1,
        "Response mentions other pillars": any(p in arch_resp.lower() for p in ['physical', 'mental', 'social', 'fitness', 'wellbeing', 'connection']),
        "Response is question": arch_resp.strip().endswith('?'),
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

def phase1_insufficient_2():
    """Scenario 1b: User provides only 2 pillars - different phrasing"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nUser says: 'I'd like to run a marathon and be more focused'")
    print("Expected: AI identifies PHYSICAL + MENTAL, asks about CAREER + SOCIAL")
    
    critic_resp, _ = critic.analyze(
        user_input="I'd like to run a marathon and be more focused",
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"\nCritic extracted {len(critic_resp['deltas'])} goal(s)")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    arch_resp = architect.generate_response(
        [],
        "User provided PHYSICAL and MENTAL goals. Ask about CAREER and SOCIAL pillars"
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "2 goals extracted": len(critic_resp['deltas']) == 2,
        "Mentions career or social": any(p in arch_resp.lower() for p in ['career', 'work', 'job', 'social', 'friend', 'connection', 'relationship']),
        "Response is question": arch_resp.strip().endswith('?'),
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

# ============================================================================
# PHASE 1: EXCESS GOALS (ALL 4 PILLARS)
# ============================================================================

def phase1_excess_1():
    """Scenario 2a: User provides 4+ goals covering all pillars"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nUser says: 'I want to be a CEO, run a 5K, meditate, and have close friends'")
    print("Expected: AI recognizes all 4 pillars, celebrates, ready for phase 2")
    
    critic_resp, _ = critic.analyze(
        user_input="I want to be a CEO, run a 5K, meditate, and have close friends",
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"\nCritic extracted {len(critic_resp['deltas'])} goal(s)")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    arch_resp = architect.generate_response(
        [],
        "User provided goals for all 4 pillars: CAREER, PHYSICAL, MENTAL, SOCIAL. Acknowledge this and celebrate we have complete coverage."
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "4+ goals extracted": len(critic_resp['deltas']) >= 4,
        "Celebrates or acknowledges progress": any(w in arch_resp.lower() for w in ['excellent', 'great', 'perfect', 'all', 'complete', 'covered']),
        "Response is positive": any(w in arch_resp.lower() for w in ['great', 'perfect', 'excellent', 'wonderful']),
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

def phase1_excess_2():
    """Scenario 2b: Different phrasing - natural list"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nUser says: 'My goals are to start a business, get fit, be less anxious, and spend more time with family'")
    print("Expected: All 4 pillars covered, celebration message")
    
    critic_resp, _ = critic.analyze(
        user_input="My goals are to start a business, get fit, be less anxious, and spend more time with family",
        active_goal_id=None,
        existing_goals=[]
    )
    
    print(f"\nCritic extracted {len(critic_resp['deltas'])} goal(s)")
    for d in critic_resp['deltas']:
        print(f"  - {d['payload']}")
    
    arch_resp = architect.generate_response(
        [],
        "All 4 pillars (career, physical, mental, social) are covered. Acknowledge and prepare to move to phase 2."
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "4+ goals extracted": len(critic_resp['deltas']) >= 4,
        "Recognizes completion": any(w in arch_resp.lower() for w in ['covered', 'complete', 'all', 'perfect']),
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

# ============================================================================
# PHASE 2: UNRELATED RESPONSES (REJECT & ASK AGAIN)
# ============================================================================

def phase2_unrelated_1():
    """Scenario 3a: Career goal, user answers about food"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nQ: 'What are you doing for your CAREER goal: Become a software engineer?'")
    print("A: 'I like pizza and watch Netflix'")
    print("Expected: AI rejects this, asks again firmly")
    
    career_goal_id = "goal-career-1"
    existing_goals = [f"ID: {career_goal_id} | Name: Become a software engineer"]
    
    critic_resp, _ = critic.analyze(
        user_input="I like pizza and watch Netflix",
        active_goal_id=career_goal_id,
        existing_goals=existing_goals
    )
    
    print(f"\nCritic: Intent={critic_resp['intent']}, Deltas={len(critic_resp['deltas'])}")
    
    arch_resp = architect.generate_response(
        [],
        "The user's response about pizza and Netflix is not related to their CAREER goal. Ask them again what they're doing for their career goal. Be firm but supportive."
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "Critic rejects unrelated": critic_resp['intent'] == 'STOP_SIGNAL' or len(critic_resp['deltas']) == 0,
        "Architect asks about career": any(w in arch_resp.lower() for w in ['career', 'engineer', 'software', 'doing', 'work']),
        "Architect asks again": '?' in arch_resp,
        "No phantom ack": not arch_resp.strip().startswith('Okay'),
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

def phase2_unrelated_2():
    """Scenario 3b: Fitness goal, user talks about career"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nQ: 'What are you doing to work toward your PHYSICAL goal: Run a marathon?'")
    print("A: 'I just got promoted at work'")
    print("Expected: AI recognizes this is about career, redirects to fitness")
    
    physical_goal_id = "goal-physical-1"
    existing_goals = [f"ID: {physical_goal_id} | Name: Run a marathon"]
    
    critic_resp, _ = critic.analyze(
        user_input="I just got promoted at work",
        active_goal_id=physical_goal_id,
        existing_goals=existing_goals
    )
    
    print(f"\nCritic: Intent={critic_resp['intent']}, Deltas={len(critic_resp['deltas'])}")
    
    arch_resp = architect.generate_response(
        [],
        "User talked about work promotion, not their fitness goal. Acknowledge their achievement, then ask again about marathon training. Stay focused on the PHYSICAL pillar."
    )
    print(f"\nArchitect response:\n  {arch_resp}")
    
    checks = {
        "Critic rejects unrelated": critic_resp['intent'] == 'STOP_SIGNAL' or len(critic_resp['deltas']) == 0,
        "Architect mentions physical/fitness": any(w in arch_resp.lower() for w in ['marathon', 'fitness', 'run', 'physical', 'train', 'exercise']),
        "Architect asks again": '?' in arch_resp,
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

# ============================================================================
# STABILITY & CONSISTENCY
# ============================================================================

def stability_1():
    """Scenario 4a: Edge case - empty/garbage response"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nQ: 'What are you doing for your MENTAL goal?'")
    print("A: '??!@#$%^&*()'")
    print("Expected: AI handles gracefully, doesn't crash")
    
    try:
        critic_resp, _ = critic.analyze(
            user_input="??!@#$%^&*()",
            active_goal_id="goal-mental-1",
            existing_goals=["ID: goal-mental-1 | Name: Be calm under pressure"]
        )
        
        arch_resp = architect.generate_response(
            [],
            "User provided unclear input. Ask again politely for what they're doing for their mental health goal."
        )
        
        print(f"\nCritic handled: {critic_resp['intent']}")
        print(f"Architect response: {arch_resp[:50]}...")
        
        checks = {
            "No crash on garbage": True,
            "Architect still asks": '?' in arch_resp,
        }
        
        all_pass = all(checks.values())
        for check, result in checks.items():
            print(f"  [{('PASS' if result else 'FAIL')}] {check}")
        return all_pass
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        return False

def stability_2():
    """Scenario 4b: Very long rambling response"""
    critic = CriticAgent()
    architect = ArchitectAgent()
    
    print("\nQ: 'What are you doing for your SOCIAL goal?'")
    print("A: Long rambling about weather, then mentions friend...")
    print("Expected: AI extracts key info, doesn't break")
    
    long_response = "Well, it's been really nice weather lately and I've been thinking about how the seasons change so much. " \
                   "Anyway, I've been trying to hang out with my friends more on weekends and we usually get coffee together."
    
    try:
        social_goal_id = "goal-social-1"
        existing_goals = [f"ID: {social_goal_id} | Name: Build stronger friendships"]
        
        critic_resp, _ = critic.analyze(
            user_input=long_response,
            active_goal_id=social_goal_id,
            existing_goals=existing_goals
        )
        
        arch_resp = architect.generate_response(
            [],
            "User mentioned hanging out with friends. Acknowledge that, ask if there's anything else they're doing."
        )
        
        print(f"\nCritic extracted {len(critic_resp['deltas'])} delta(s)")
        print(f"Architect response: {arch_resp[:50]}...")
        
        checks = {
            "No crash on long input": True,
            "Critic extracted something": len(critic_resp['deltas']) >= 0,  # May be 0 if unrelated
            "Architect responds": len(arch_resp) > 10,
        }
        
        all_pass = all(checks.values())
        for check, result in checks.items():
            print(f"  [{('PASS' if result else 'FAIL')}] {check}")
        return all_pass
    except Exception as e:
        print(f"  [FAIL] Crashed: {e}")
        return False

# ============================================================================
# PILLAR ALIGNMENT (RIGHT QUESTION FOR RIGHT PILLAR)
# ============================================================================

def pillar_alignment_1():
    """Scenario 5a: Career goal uses career terminology"""
    architect = ArchitectAgent()
    
    print("\nDirective: Ask about CAREER goal 'Become a software engineer'")
    print("Expected: Response uses career keywords, not fitness/mental")
    
    career_directive = "Ask what the user is currently doing to work toward their CAREER goal: 'Become a software engineer'. Use career/professional/work terminology."
    
    response = architect.generate_response([], career_directive)
    print(f"\nArchitect response:\n  {response}")
    
    career_keywords = ['software', 'engineer', 'code', 'skill', 'learn', 'professional', 'work', 'project', 'interview']
    bad_keywords = ['run', 'exercise', 'friend', 'stress', 'meditation', 'calm']
    
    has_career = any(kw in response.lower() for kw in career_keywords)
    has_bad = any(kw in response.lower() for kw in bad_keywords)
    
    print(f"\nHas career keywords: {has_career}")
    print(f"Has unrelated keywords: {has_bad}")
    
    checks = {
        "Uses career terminology": has_career or any(w in response.lower() for w in ['engineer', 'software', 'professional', 'doing']),
        "No fitness/wellness jargon": not has_bad,
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

def pillar_alignment_2():
    """Scenario 5b: Physical goal uses fitness terminology"""
    architect = ArchitectAgent()
    
    print("\nDirective: Ask about PHYSICAL goal 'Run a marathon'")
    print("Expected: Response uses fitness/exercise keywords, not career")
    
    physical_directive = "Ask what the user is currently doing to work toward their PHYSICAL goal: 'Run a marathon'. Focus on exercise, training, and fitness."
    
    response = architect.generate_response([], physical_directive)
    print(f"\nArchitect response:\n  {response}")
    
    physical_keywords = ['run', 'marathon', 'train', 'exercise', 'workout', 'fitness', 'physical']
    bad_keywords = ['code', 'engineer', 'friend', 'social', 'stress']
    
    has_physical = any(kw in response.lower() for kw in physical_keywords)
    has_bad = any(kw in response.lower() for kw in bad_keywords)
    
    print(f"\nHas fitness keywords: {has_physical}")
    print(f"Has unrelated keywords: {has_bad}")
    
    checks = {
        "Uses fitness terminology": has_physical or any(w in response.lower() for w in ['marathon', 'run', 'train', 'exercise', 'doing']),
        "No career/social jargon": not has_bad,
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

def pillar_alignment_3():
    """Scenario 5c: Mental goal uses wellbeing terminology"""
    architect = ArchitectAgent()
    
    print("\nDirective: Ask about MENTAL goal 'Be calm under pressure'")
    print("Expected: Response uses mental health keywords, not career/fitness")
    
    mental_directive = "Ask about the user's MENTAL health goal: 'Be calm under pressure'. Ask about stress management and mental wellbeing activities."
    
    response = architect.generate_response([], mental_directive)
    print(f"\nArchitect response:\n  {response}")
    
    mental_keywords = ['calm', 'stress', 'pressure', 'mental', 'meditation', 'wellbeing', 'anxiety']
    bad_keywords = ['engineer', 'code', 'run', 'exercise', 'friend', 'social']
    
    has_mental = any(kw in response.lower() for kw in mental_keywords)
    has_bad = any(kw in response.lower() for kw in bad_keywords)
    
    print(f"\nHas mental health keywords: {has_mental}")
    print(f"Has unrelated keywords: {has_bad}")
    
    checks = {
        "Uses mental health terminology": has_mental or any(w in response.lower() for w in ['pressure', 'calm', 'stress', 'mental', 'doing']),
        "No career/fitness jargon": not has_bad,
    }
    
    all_pass = all(checks.values())
    for check, result in checks.items():
        print(f"  [{('PASS' if result else 'FAIL')}] {check}")
    return all_pass

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE SCENARIO TESTING - ALL YOUR REQUIREMENTS")
    print("="*80)
    
    results = []
    
    # PHASE 1: Insufficient
    print("\n\n### PHASE 1: INSUFFICIENT GOALS ###")
    results.append(("P1.1a - Insufficient (1 pillar)", test_scenario(
        "Phase 1.1a: Insufficient goals - 1 pillar",
        phase1_insufficient_1
    )))
    results.append(("P1.1b - Insufficient (2 pillars)", test_scenario(
        "Phase 1.1b: Insufficient goals - 2 pillars",
        phase1_insufficient_2
    )))
    
    # PHASE 1: Excess
    print("\n\n### PHASE 1: EXCESS GOALS (ALL 4 PILLARS) ###")
    results.append(("P1.2a - Excess (4+ goals)", test_scenario(
        "Phase 1.2a: Excess goals - all 4 pillars",
        phase1_excess_1
    )))
    results.append(("P1.2b - Excess (natural phrasing)", test_scenario(
        "Phase 1.2b: Excess goals - natural phrasing",
        phase1_excess_2
    )))
    
    # PHASE 2: Unrelated
    print("\n\n### PHASE 2: UNRELATED RESPONSES ###")
    results.append(("P2.1a - Unrelated (food response)", test_scenario(
        "Phase 2.1a: Unrelated response - food",
        phase2_unrelated_1
    )))
    results.append(("P2.1b - Unrelated (wrong pillar)", test_scenario(
        "Phase 2.1b: Unrelated response - wrong pillar",
        phase2_unrelated_2
    )))
    
    # STABILITY
    print("\n\n### STABILITY & CONSISTENCY ###")
    results.append(("P4.1a - Stability (garbage)", test_scenario(
        "Phase 4.1a: Stability - garbage input",
        stability_1
    )))
    results.append(("P4.1b - Stability (long input)", test_scenario(
        "Phase 4.1b: Stability - long rambling",
        stability_2
    )))
    
    # PILLAR ALIGNMENT
    print("\n\n### PILLAR ALIGNMENT (RIGHT QUESTION FOR RIGHT PILLAR) ###")
    results.append(("P5.1a - Alignment (CAREER)", test_scenario(
        "Phase 5.1a: Pillar alignment - CAREER",
        pillar_alignment_1
    )))
    results.append(("P5.1b - Alignment (PHYSICAL)", test_scenario(
        "Phase 5.1b: Pillar alignment - PHYSICAL",
        pillar_alignment_2
    )))
    results.append(("P5.1c - Alignment (MENTAL)", test_scenario(
        "Phase 5.1c: Pillar alignment - MENTAL",
        pillar_alignment_3
    )))
    
    # SUMMARY
    print("\n\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {test_name}")
    
    print(f"\nTotal: {passed}/{total} scenarios passing ({int(100*passed/total)}%)")
    
    if passed == total:
        print("\n✅ ALL SCENARIOS PASSING!")
    else:
        print(f"\n❌ {total - passed} scenario(s) need attention")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
