"""Debug script for a specific user response.

Tests the response:
"OK for Career I want to make a successful drop shipping business for mental I want to be More calm under pressure for my physical goal I want to be able to debt lift 200kg and for which connection goal I want to be able to have like a lot of friend groups and be able to talk to all"
"""

import sys
import os

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, PendingDebuff, PendingGoal
from src.onboarding.agent import ArchitectAgent, CriticAgent

def debug_response():
    """Debug a specific user response."""
    
    print("=" * 70)
    print("DEBUGGING SPECIFIC USER RESPONSE")
    print("=" * 70)
    print()
    
    # Initialize
    sheet = CharacterSheet(user_id="debug_user")
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
    
    # The specific user response to test
    user_input = "OK for Career I want to make a successful drop shipping business for mental I want to be More calm under pressure for my physical goal I want to be able to debt lift 200kg and for which connection goal I want to be able to have like a lot of friend groups and be able to talk to all"
    
    print(f"User: {user_input}\n")
    print("=" * 70)
    print("PROCESSING...")
    print("=" * 70)
    print()
    
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
    
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()
    
    print("CRITIC FEEDBACK:")
    print(feedback)
    print()
    
    print("EXTRACTED GOALS:")
    for i, goal in enumerate(sheet.goals, 1):
        pillars_str = ", ".join([p.value for p in goal.pillars])
        print(f"  {i}. '{goal.name}' (Pillars: {pillars_str})")
        if goal.description:
            print(f"     Description: {goal.description}")
    print()
    
    # Check for misclassifications
    all_pillars_in_goals = set()
    for goal in sheet.goals:
        all_pillars_in_goals.update(goal.pillars)
    missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals]
    covered_pillars = [p.value for p in all_pillars_in_goals]
    
    print("PILLAR COVERAGE:")
    print(f"  Covered: {covered_pillars}")
    print(f"  Missing: {missing_pillars}")
    print()
    
    # Check for extra goals
    if len(sheet.goals) > 4:
        print(f"[WARNING] EXTRA GOALS DETECTED: {len(sheet.goals)} goals total (more than 4 required)")
    else:
        print(f"[OK] Goal count: {len(sheet.goals)} (expected: 4)")
    print()
    
    print("ARCHITECT RESPONSE:")
    print(f"Architect: {reply}\n")
    
    # Check if misclassification question was asked
    if "did you mean" in reply.lower() or "did you mean this as" in reply.lower():
        print("[WARNING] MISCLASSIFICATION QUESTION DETECTED IN RESPONSE")
        print("   (This might be a false positive - check if it's correct)")
    else:
        print("[OK] No misclassification questions asked (correct - all goals properly classified)")
    print()
    
    # Check if extra goals question was asked
    if "prioritize" in reply.lower() or "keep all" in reply.lower() or "focus on" in reply.lower():
        if len(sheet.goals) > 4:
            print("[OK] Extra goals question asked (correct)")
        else:
            print("[WARNING] Extra goals question asked but only 4 goals exist (might be false positive)")
    else:
        if len(sheet.goals) > 4:
            print("[WARNING] Extra goals question NOT asked (should have been asked)")
        else:
            print("[OK] No extra goals question (correct - exactly 4 goals)")
    print()

if __name__ == "__main__":
    debug_response()
