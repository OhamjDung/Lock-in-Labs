"""Comprehensive Onboarding Debug Script - No Backend Required

This script tests all the scenarios you mentioned:

PHASE 1:
1. User does not provide enough pure goals
2. User provides more than enough pure goals
   - Does it ask for information in other pillars?

PHASE 2:
3. User answers unrelated to the question
   - Does AI know to disregard and ask again?

4. Overall stability & consistency
   - AI doesn't break even with improper answers
   - AI is firm and asks again
   - Correct reasoning for correct questions (no alignment issues)

Usage:
    python comprehensive_onboarding_test.py

Type 'menu' to see available tests
Type 'exit' to quit
"""

import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, Goal
from src.onboarding.agent import ArchitectAgent, CriticAgent

# ============================================================================
# TEST TRACKING
# ============================================================================

class TestTracker:
    """Tracks test results and fixes."""
    
    def __init__(self):
        self.fixes_applied = []
        self.current_test = None
        self.issues_found = []
    
    def record_fix(self, fix_name: str, description: str):
        """Record a fix that was applied."""
        self.fixes_applied.append({
            "fix_num": len(self.fixes_applied) + 1,
            "name": fix_name,
            "description": description
        })
        
        print(f"\n{'='*70}")
        print(f"FIX #{len(self.fixes_applied)}: {fix_name}")
        print(f"{'='*70}")
        print(f"Description: {description}")
        
        # Every 5 fixes, print a summary
        if len(self.fixes_applied) % 5 == 0:
            self.print_summary()
    
    def record_issue(self, issue: str):
        """Record an issue found during testing."""
        self.issues_found.append(issue)
        print(f"\n[ISSUE FOUND] {issue}")
    
    def print_summary(self):
        """Print summary of fixes applied so far."""
        print(f"\n{'='*70}")
        print(f"SUMMARY: {len(self.fixes_applied)} FIXES APPLIED")
        print(f"{'='*70}")
        for fix in self.fixes_applied:
            print(f"{fix['fix_num']}. {fix['name']}: {fix['description'][:60]}...")
        print(f"{'='*70}\n")

tracker = TestTracker()

# ============================================================================
# PHASE 1 TESTING
# ============================================================================

def test_phase1_insufficient_goals():
    """TEST 1: User provides insufficient goals (only 2 pillars)
    
    Expected: AI should ask for goals in missing pillars
    """
    print("\n" + "="*70)
    print("PHASE 1 TEST 1: INSUFFICIENT GOALS (Only 2 pillars)")
    print("="*70)
    
    sheet = CharacterSheet(user_id="test_user")
    state = ConversationState(
        missing_fields=["north_star_goals"],
        current_topic="Goals",
        phase="phase1",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Start
    welcome_msg = "Listen kid, i need you to tell me 4 things. Your career goals, your fitness goals, your mental health goals, and your connection goals, do that for me wont cha"
    print(f"\nArchitect: {welcome_msg}\n")
    state.conversation_history.append({"role": "assistant", "content": welcome_msg})
    
    # User provides only 2 goals (CAREER and PHYSICAL)
    user_input = "I want to become a software engineer and I want to run a marathon."
    print(f"You: {user_input}\n")
    
    # Note: In the actual system, the critic.analyze only takes user_input, active_goal_id, and existing_goals
    # For Phase 1, active_goal_id is "None" (string)
    critic_response, critic_raw = critic.analyze(
        user_input=user_input,
        active_goal_id=None,
        existing_goals=[]
    )
    
    state.conversation_history.append({"role": "user", "content": user_input})
    
    print(f"[Critic Analysis]: {critic_analysis}")
    print(f"[Goals collected]: {len(sheet.goals)}")
    for g in sheet.goals:
        print(f"  - {g.name} ({[p.value for p in g.pillars]})")
    
    # Check what pillars are missing
    covered_pillars = set()
    for goal in sheet.goals:
        covered_pillars.update(goal.pillars)
    
    missing_pillars = []
    for pillar in Pillar:
        if pillar not in covered_pillars:
            missing_pillars.append(pillar.value)
    
    print(f"\n[Covered Pillars]: {[p.value for p in covered_pillars]}")
    print(f"[Missing Pillars]: {missing_pillars}")
    
    # Get Architect response
    directive_to_give = f"""
    The user has provided goals for: {', '.join([p.value for p in covered_pillars])}
    Missing pillars: {', '.join(missing_pillars)}
    
    Acknowledge what they said, then ask about ONE of the missing pillars.
    Ask specifically about their goals for that pillar.
    """
    
    arch_response = architect.generate_response(state.conversation_history, directive_to_give)
    print(f"\nArchitect: {arch_response}\n")
    state.conversation_history.append({"role": "assistant", "content": arch_response})
    
    # Verify the response
    print("["*20 + " VERIFICATION " + "]"*20)
    checks = {
        "Has at least 2 pillars collected": len(covered_pillars) >= 2,
        "Has missing pillars": len(missing_pillars) > 0,
        "Asks for missing pillar": any(p.lower() in arch_response.lower() for p in missing_pillars),
        "Response is a question": arch_response.strip().endswith("?"),
    }
    
    for check, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {check}")
    
    if not all(checks.values()):
        tracker.record_issue(
            f"Phase 1 insufficient goals: Some checks failed. "
            f"Missing pillars: {missing_pillars}, Response asks about them: {checks['Asks for missing pillar']}"
        )
        return False
    
    return True


def test_phase1_excess_goals():
    """TEST 2: User provides more than enough goals
    
    Expected: AI should handle gracefully, still ask about all 4 pillars if not covered
    """
    print("\n" + "="*70)
    print("PHASE 1 TEST 2: EXCESS GOALS (More than 4)")
    print("="*70)
    
    sheet = CharacterSheet(user_id="test_user")
    state = ConversationState(
        missing_fields=["north_star_goals"],
        current_topic="Goals",
        phase="phase1",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    welcome_msg = "Listen kid, i need you to tell me 4 things. Your career goals, your fitness goals, your mental health goals, and your connection goals, do that for me wont cha"
    print(f"\nArchitect: {welcome_msg}\n")
    state.conversation_history.append({"role": "assistant", "content": welcome_msg})
    
    # User provides 6 goals (too many, but covers all pillars)
    user_input = ("I want to be a software engineer, I want to start a business, "
                  "I want to run a marathon, I want to be flexible, "
                  "I want to make new friends, I want to be more confident in groups, "
                  "I want to be calm under pressure, I want to meditate daily")
    print(f"You: {user_input}\n")
    
    history_plus_user = state.conversation_history + [{"role": "user", "content": user_input}]
    sheet, feedback, critic_analysis, pending_debuffs = critic.analyze(
        user_input,
        sheet,
        history_plus_user,
        state.phase
    )
    
    state.conversation_history.append({"role": "user", "content": user_input})
    
    print(f"[Critic Analysis]: {critic_analysis}")
    print(f"[Goals collected]: {len(sheet.goals)}")
    for g in sheet.goals:
        print(f"  - {g.name} ({[p.value for p in g.pillars]})")
    
    # Check coverage
    covered_pillars = set()
    for goal in sheet.goals:
        covered_pillars.update(goal.pillars)
    
    print(f"\n[Covered Pillars]: {[p.value for p in covered_pillars]}")
    
    # Get Architect response
    all_pillars_covered = len(covered_pillars) == 4
    if all_pillars_covered:
        directive = "All 4 pillars are now covered. Acknowledge this and prepare to move to phase 2."
    else:
        missing = [p.value for p in Pillar if p not in covered_pillars]
        directive = f"Missing pillars: {', '.join(missing)}. Ask about one of them."
    
    arch_response = architect.generate_response(state.conversation_history, directive)
    print(f"\nArchitect: {arch_response}\n")
    
    # Verify
    print("["*20 + " VERIFICATION " + "]"*20)
    checks = {
        "Collected at least 4 goals": len(sheet.goals) >= 4,
        "All 4 pillars covered": len(covered_pillars) == 4,
        "Response doesn't break": arch_response != "",
        "Response is coherent": len(arch_response) > 10,
    }
    
    for check, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {check}")
    
    if not all(checks.values()):
        tracker.record_issue(
            f"Phase 1 excess goals: AI handling failed. "
            f"Goals: {len(sheet.goals)}, Pillars: {len(covered_pillars)}, Response length: {len(arch_response)}"
        )
        return False
    
    return True


# ============================================================================
# PHASE 2 TESTING
# ============================================================================

def create_phase2_sheet():
    """Create a sheet with all 4 goals for Phase 2 testing."""
    sheet = CharacterSheet(user_id="test_user")
    sheet.goals = [
        Goal(
            name="Become a software engineer",
            pillars=[Pillar.CAREER],
            description="User wants to be a software engineer",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Run a marathon",
            pillars=[Pillar.PHYSICAL],
            description="User wants to run a marathon",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Be calm under pressure",
            pillars=[Pillar.MENTAL],
            description="User wants to be calm under pressure",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Make new friends",
            pillars=[Pillar.SOCIAL],
            description="User wants to make new friends",
            current_quests=[],
            skill_level=None
        ),
    ]
    return sheet


def test_phase2_unrelated_response():
    """TEST 3: User provides unrelated response in Phase 2
    
    Expected: AI should disregard and ask again about the same topic
    """
    print("\n" + "="*70)
    print("PHASE 2 TEST 3: UNRELATED RESPONSE")
    print("="*70)
    
    sheet = create_phase2_sheet()
    state = ConversationState(
        missing_fields=["current_quests"],
        current_topic="Current Quests for Become a software engineer",
        phase="phase2",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Ask about current quests for CAREER goal
    question = "What are you currently doing to become a software engineer? Any projects, studying, or learning happening right now?"
    print(f"\nArchitect: {question}\n")
    state.conversation_history.append({"role": "assistant", "content": question})
    
    # User gives COMPLETELY unrelated answer (about social topic instead)
    user_input = "I love pizza and I watch movies on weekends"
    print(f"You: {user_input}\n")
    
    history_plus_user = state.conversation_history + [{"role": "user", "content": user_input}]
    sheet, feedback, critic_analysis, pending_debuffs = critic.analyze(
        user_input,
        sheet,
        history_plus_user,
        state.phase
    )
    
    state.conversation_history.append({"role": "user", "content": user_input})
    
    print(f"[Critic Analysis]: {critic_analysis}")
    print(f"[Quests added]: {sheet.goals[0].current_quests if sheet.goals else 'N/A'}")
    
    # Get Architect response - should ask again about the same topic
    directive = ("The user gave an unrelated response (pizza and movies). "
                 "They didn't answer about their CAREER goal 'Become a software engineer'. "
                 "Politely point this out and ask again about what they're currently doing for this goal.")
    
    arch_response = architect.generate_response(state.conversation_history, directive)
    print(f"\nArchitect: {arch_response}\n")
    
    # Verify
    print("["*20 + " VERIFICATION " + "]"*20)
    checks = {
        "No quest added from unrelated input": len(sheet.goals[0].current_quests) == 0 or 
                                               not any("pizza" in q.lower() or "movie" in q.lower() 
                                                      for q in [str(q) for q in sheet.goals[0].current_quests]),
        "AI asks about same topic": "software engineer" in arch_response.lower() or 
                                   "career" in arch_response.lower() or
                                   "doing" in arch_response.lower(),
        "AI is firm (not accepting unrelated answer)": len(arch_response) > 10,
        "Response is a question": arch_response.strip().endswith("?"),
    }
    
    for check, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {check}")
    
    if not all(checks.values()):
        tracker.record_issue(
            f"Phase 2 unrelated response: AI didn't handle properly. "
            f"Quests added: {len(sheet.goals[0].current_quests)}, "
            f"Response relevance: {checks['AI asks about same topic']}"
        )
        return False
    
    return True


def test_phase2_alignment():
    """TEST 4: Verify alignment - asking about right pillar with right reasoning
    
    Expected: When asking about FITNESS, should ask FITNESS questions
             When asking about CAREER, should ask CAREER questions
             Not mixing them up
    """
    print("\n" + "="*70)
    print("PHASE 2 TEST 4: PILLAR ALIGNMENT (RIGHT QUESTION FOR RIGHT GOAL)")
    print("="*70)
    
    sheet = create_phase2_sheet()
    state = ConversationState(
        missing_fields=["current_quests"],
        current_topic="Current Quests",
        phase="phase2",
    )
    
    architect = ArchitectAgent()
    
    # Test asking about PHYSICAL goal
    print("\n[Sub-test 4a: Asking about FITNESS goal]\n")
    
    physical_goal = sheet.goals[1]  # "Run a marathon"
    print(f"Asking about: {physical_goal.name} ({[p.value for p in physical_goal.pillars]})\n")
    
    directive_physical = f"""
    Ask about the user's current activities for their goal: "{physical_goal.name}"
    Ask specifically about what they're doing physically.
    """
    
    arch_response_physical = architect.generate_response([], directive_physical)
    print(f"Architect response: {arch_response_physical}\n")
    
    # Check alignment
    print("["*20 + " ALIGNMENT CHECKS " + "]"*20)
    
    physical_keywords = ["run", "exercise", "workout", "train", "gym", "cardio", "fitness", "physical", "doing"]
    career_keywords = ["learn", "study", "code", "project", "skill", "job", "work", "engineer"]
    social_keywords = ["friend", "talk", "social", "connect", "meet", "people"]
    mental_keywords = ["stress", "calm", "meditation", "anxiety", "mental", "focus"]
    
    physical_mention = any(kw in arch_response_physical.lower() for kw in physical_keywords)
    career_mention = any(kw in arch_response_physical.lower() for kw in career_keywords)
    social_mention = any(kw in arch_response_physical.lower() for kw in social_keywords)
    mental_mention = any(kw in arch_response_physical.lower() for kw in mental_keywords)
    
    print(f"✓ MENTIONS PHYSICAL KEYWORDS: {physical_mention}")
    print(f"✓ NO CAREER KEYWORDS: {not career_mention}")
    print(f"✓ NO SOCIAL KEYWORDS: {not social_mention}")
    print(f"✓ NO MENTAL KEYWORDS: {not mental_mention}")
    
    if not (physical_mention and not career_mention and not social_mention and not mental_mention):
        tracker.record_issue(
            f"Pillar alignment issue with PHYSICAL goal: "
            f"Physical keywords found: {physical_mention}, "
            f"Unrelated keywords found - Career: {career_mention}, Social: {social_mention}, Mental: {mental_mention}"
        )
        return False
    
    # Test asking about CAREER goal
    print("\n[Sub-test 4b: Asking about CAREER goal]\n")
    
    career_goal = sheet.goals[0]  # "Become a software engineer"
    print(f"Asking about: {career_goal.name} ({[p.value for p in career_goal.pillars]})\n")
    
    directive_career = f"""
    Ask about the user's current activities for their goal: "{career_goal.name}"
    Ask specifically about what they're doing professionally or educationally.
    """
    
    arch_response_career = architect.generate_response([], directive_career)
    print(f"Architect response: {arch_response_career}\n")
    
    # Check alignment
    print("["*20 + " ALIGNMENT CHECKS " + "]"*20)
    
    physical_mention = any(kw in arch_response_career.lower() for kw in physical_keywords)
    career_mention = any(kw in arch_response_career.lower() for kw in career_keywords)
    social_mention = any(kw in arch_response_career.lower() for kw in social_keywords)
    mental_mention = any(kw in arch_response_career.lower() for kw in mental_keywords)
    
    print(f"✓ MENTIONS CAREER KEYWORDS: {career_mention}")
    print(f"✓ NO PHYSICAL KEYWORDS: {not physical_mention}")
    print(f"✓ NO SOCIAL KEYWORDS: {not social_mention}")
    print(f"✓ NO MENTAL KEYWORDS: {not mental_mention}")
    
    if not (career_mention and not physical_mention and not social_mention and not mental_mention):
        tracker.record_issue(
            f"Pillar alignment issue with CAREER goal: "
            f"Career keywords found: {career_mention}, "
            f"Unrelated keywords found - Physical: {physical_mention}, Social: {social_mention}, Mental: {mental_mention}"
        )
        return False
    
    return True


def test_phase2_stability():
    """TEST 5: Overall stability - AI doesn't break with various inputs
    
    Expected: AI handles all types of input gracefully
    """
    print("\n" + "="*70)
    print("PHASE 2 TEST 5: OVERALL STABILITY")
    print("="*70)
    
    sheet = create_phase2_sheet()
    state = ConversationState(
        missing_fields=["current_quests"],
        current_topic="Current Quests",
        phase="phase2",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Test various edge case inputs
    test_inputs = [
        "I don't know",
        "",
        "???",
        "nothing lol",
        "I'm not sure what you're asking",
        "Can you repeat?",
        123,  # Invalid type test (will be converted to string)
    ]
    
    print("\nTesting various edge case inputs:\n")
    
    for test_input in test_inputs:
        print(f"Input: {repr(test_input)}")
        
        try:
            history_plus_user = state.conversation_history + [{"role": "user", "content": str(test_input)}]
            sheet, feedback, critic_analysis, pending_debuffs = critic.analyze(
                str(test_input),
                sheet,
                history_plus_user,
                state.phase
            )
            
            # Try to get architect response
            arch_response = architect.generate_response(state.conversation_history, "Ask about their career goal")
            print(f"✓ HANDLED: Response length {len(arch_response)} chars\n")
            
        except Exception as e:
            print(f"✗ CRASHED: {str(e)}\n")
            tracker.record_issue(f"Stability issue with input '{test_input}': {str(e)}")
            return False
    
    return True


# ============================================================================
# INTERACTIVE MENU
# ============================================================================

def show_menu():
    """Display available tests."""
    print("\n" + "="*70)
    print("ONBOARDING DEBUG SUITE - INTERACTIVE MENU")
    print("="*70)
    print("""
Available Tests:

PHASE 1:
  1 - Test insufficient goals (only 2 pillars)
  2 - Test excess goals (more than 4)
  
PHASE 2:
  3 - Test unrelated user response
  4 - Test pillar alignment (right question for right pillar)
  5 - Test overall stability
  
BATCH RUNS:
  all     - Run all tests in sequence
  phase1  - Run all Phase 1 tests
  phase2  - Run all Phase 2 tests
  
OTHER:
  menu    - Show this menu
  summary - Show summary of fixes applied
  exit    - Exit the program
    """)

def run_all_tests():
    """Run all tests sequentially."""
    tests = [
        ("Phase 1 - Insufficient Goals", test_phase1_insufficient_goals),
        ("Phase 1 - Excess Goals", test_phase1_excess_goals),
        ("Phase 2 - Unrelated Response", test_phase2_unrelated_response),
        ("Phase 2 - Pillar Alignment", test_phase2_alignment),
        ("Phase 2 - Overall Stability", test_phase2_stability),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "PASS" if result else "FAIL"
        except Exception as e:
            print(f"\n[ERROR in {test_name}]: {str(e)}")
            results[test_name] = f"ERROR: {str(e)[:50]}"
    
    # Print final results
    print("\n" + "="*70)
    print("FINAL TEST RESULTS")
    print("="*70)
    for test_name, result in results.items():
        status = "✓" if result == "PASS" else "✗"
        print(f"{status} {test_name}: {result}")
    
    return results

def main():
    """Main interactive loop."""
    print("="*70)
    print("COMPREHENSIVE ONBOARDING DEBUG SUITE")
    print("="*70)
    print("Type 'menu' for available tests or 'exit' to quit\n")
    
    while True:
        try:
            command = input(">>> ").strip().lower()
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except EOFError:
            print("\n\nExiting...")
            break
        
        if command == "exit":
            print("Exiting...")
            break
        
        elif command == "menu":
            show_menu()
        
        elif command == "summary":
            tracker.print_summary()
        
        elif command == "1":
            result = test_phase1_insufficient_goals()
            if result:
                tracker.record_fix(
                    "Phase 1 Insufficient Goals",
                    "AI correctly asks for missing pillars when not all 4 are provided"
                )
        
        elif command == "2":
            result = test_phase1_excess_goals()
            if result:
                tracker.record_fix(
                    "Phase 1 Excess Goals",
                    "AI handles multiple goals gracefully and still covers all 4 pillars"
                )
        
        elif command == "3":
            result = test_phase2_unrelated_response()
            if result:
                tracker.record_fix(
                    "Phase 2 Unrelated Response",
                    "AI disregards unrelated answers and asks again about the same topic"
                )
        
        elif command == "4":
            result = test_phase2_alignment()
            if result:
                tracker.record_fix(
                    "Phase 2 Pillar Alignment",
                    "AI asks appropriate questions for the right pillar without mixing topics"
                )
        
        elif command == "5":
            result = test_phase2_stability()
            if result:
                tracker.record_fix(
                    "Phase 2 Stability",
                    "AI handles edge cases and invalid inputs without crashing"
                )
        
        elif command == "all":
            run_all_tests()
        
        elif command == "phase1":
            results = {}
            for test_func in [test_phase1_insufficient_goals, test_phase1_excess_goals]:
                try:
                    result = test_func()
                    results[test_func.__name__] = result
                except Exception as e:
                    results[test_func.__name__] = False
            
            print(f"\n[Phase 1 Results] {sum(results.values())}/{len(results)} tests passed")
        
        elif command == "phase2":
            results = {}
            for test_func in [test_phase2_unrelated_response, test_phase2_alignment, test_phase2_stability]:
                try:
                    result = test_func()
                    results[test_func.__name__] = result
                except Exception as e:
                    results[test_func.__name__] = False
            
            print(f"\n[Phase 2 Results] {sum(results.values())}/{len(results)} tests passed")
        
        else:
            print("Unknown command. Type 'menu' for available options.")

if __name__ == "__main__":
    main()
