"""Test scenarios for Phase 1 goal identification.

This script runs automated test scenarios to verify:
1. Missing goals detection (only 3 pillars mentioned)
2. Misidentified goals detection (wrong pillar assignment)
3. Extra goals detection (more than 4 goals mentioned)

Usage:
    python test_scenarios_phase1.py
"""

import sys
import os

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, PendingDebuff, PendingGoal
from src.onboarding.agent import ArchitectAgent, CriticAgent

def run_test_scenario(scenario_name, user_responses):
    """Run a test scenario with a series of user responses."""
    
    print("\n" + "=" * 70)
    print(f"TEST SCENARIO: {scenario_name}")
    print("=" * 70)
    print()
    
    # Initialize
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
    
    # Start with welcome message
    welcome_msg = "Listen kid, i need you to tell me 4 things. Your career goals, your fitness goals, your mental health goals, and your connection goals, do that for me wont cha"
    print(f"Architect: {welcome_msg}\n")
    state.conversation_history.append({"role": "assistant", "content": welcome_msg})
    
    # Process each user response
    for i, user_input in enumerate(user_responses, 1):
        print(f"\n{'='*70}")
        print(f"Turn {i}")
        print(f"{'='*70}")
        print(f"You: {user_input}\n")
        
        # Process current user input through Critic
        history_plus_user = state.conversation_history + [{"role": "user", "content": user_input}]
        
        # Store goals before processing
        goals_before = {g.name.lower(): g for g in sheet.goals}
        
        # Process through Critic
        sheet, feedback, critic_analysis, new_pending_debuffs = critic.analyze(
            user_input, 
            sheet, 
            history_plus_user,
            state.phase
        )
        
        # Ensure all previous goals are still present
        for goal_name, goal_obj in goals_before.items():
            if not any(g.name.lower() == goal_name for g in sheet.goals):
                print(f"[WARNING] Goal '{goal_obj.name}' was lost, restoring it")
                sheet.goals.append(goal_obj)
        
        # Add user message to history
        state.conversation_history.append({"role": "user", "content": user_input})
        
        # Add new pending debuffs
        for debuff in new_pending_debuffs:
            if not any(d.name == debuff.name for d in state.pending_debuffs):
                state.pending_debuffs.append(debuff)
        
        # Convert pending debuffs and goals
        pending_debuffs_list = [
            {"name": d.name, "evidence": d.evidence, "confidence": d.confidence} 
            for d in state.pending_debuffs
        ]
        
        pending_goals_list = [
            {"name": g.name, "pillars": [p.value for p in g.pillars], "description": g.description}
            for g in state.pending_goals
        ]
        
        # Generate Architect response
        reply, thinking = architect.generate_response(
            state.conversation_history,
            sheet,
            feedback,
            phase=state.phase,
            pending_debuffs=pending_debuffs_list,
            queued_goals=pending_goals_list,
        )
        
        # Remove progress markers
        import re
        reply = re.sub(r'\[Progress:[^\]]*?(\d{1,3})%\]', '', reply, flags=re.IGNORECASE)
        reply = re.sub(r'\[Progress:[^\]]*?\]\s*(\d{1,3})%', '', reply, flags=re.IGNORECASE)
        reply = reply.strip()
        
        print(f"Architect: {reply}\n")
        state.conversation_history.append({"role": "assistant", "content": reply})
        
        # Show current state
        all_pillars_in_goals = set()
        for goal in sheet.goals:
            all_pillars_in_goals.update(goal.pillars)
        missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals]
        covered_pillars = [p.value for p in all_pillars_in_goals]
        
        print(f"[State] Goals: {[g.name for g in sheet.goals]}")
        print(f"[State] Covered pillars: {covered_pillars}")
        print(f"[State] Missing pillars: {missing_pillars}")
        print()
        
        # Check if we should stop (all 4 pillars covered)
        if len(all_pillars_in_goals) >= 4:
            def has_pure_goal_for_pillar(goals, pillar):
                return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
            
            all_pillars_have_pure_goals = all(
                has_pure_goal_for_pillar(sheet.goals, p) for p in Pillar if p in all_pillars_in_goals
            )
            
            if all_pillars_have_pure_goals:
                print("[Test Complete] All 4 pillars covered with pure goals!")
                break
    
    print("\n" + "=" * 70)
    print("FINAL STATE")
    print("=" * 70)
    print(f"Total goals: {len(sheet.goals)}")
    for goal in sheet.goals:
        pillars_str = ", ".join([p.value for p in goal.pillars])
        print(f"  - '{goal.name}' (Pillars: {pillars_str})")
    print()

def main():
    """Run all test scenarios."""
    
    print("=" * 70)
    print("PHASE 1 TEST SCENARIOS")
    print("=" * 70)
    print()
    
    # Scenario 1: Missing goals (only 3 pillars mentioned - missing CAREER)
    scenario1_responses = [
        "I want to gain 20% more muscle mass for my fitness goals. For my mental health, I want to be calm under pressure. And for connections, I want to be more confident."
    ]
    
    # Scenario 2: Misidentified goal (real estate as mental goal)
    scenario2_responses = [
        "For my mental health, I want to go into real estate. For fitness, I want to gain 20% muscle mass. For connections, I want to be more confident. And for mental health again, I want to be calm under pressure."
    ]
    
    # Scenario 3: Extra goals (more than 4 goals - includes volleyball)
    scenario3_responses = [
        "For career I want to go into real estate. I want to gain 20% muscle mass for fitness. For connections I want to be more confident. For mental health I want to be calm under pressure. Also, I want to learn how to spike a volleyball."
    ]
    
    # Run scenarios
    run_test_scenario("1. Missing Goals (Only 3 pillars - missing CAREER)", scenario1_responses)
    run_test_scenario("2. Misidentified Goal (Real estate as MENTAL)", scenario2_responses)
    run_test_scenario("3. Extra Goals (More than 4 goals - includes volleyball)", scenario3_responses)
    
    print("\n" + "=" * 70)
    print("ALL TEST SCENARIOS COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
