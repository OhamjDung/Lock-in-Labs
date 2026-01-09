"""Interactive terminal script to run onboarding chat.

This script lets you chat with the Architect in the terminal, typing your
own responses and seeing the conversation flow naturally.

Usage:
    python debug_onboarding.py
"""

import sys
import os

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, PendingDebuff, PendingGoal
from src.onboarding.agent import ArchitectAgent, CriticAgent

def debug_onboarding():
    """Run an interactive onboarding chat session in the terminal."""
    
    print("=" * 70)
    print("ONBOARDING CHAT - Terminal Mode")
    print("=" * 70)
    print("Type your responses and press Enter. Type 'exit' or 'quit' to end.")
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
    
    # Interactive loop
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting...")
            break
            
        if user_input.lower() in ["exit", "quit"]:
            print("\nExiting...")
            break
            
        if not user_input:
            continue
        
        # Process current user input through Critic first
        history_plus_user = state.conversation_history + [{"role": "user", "content": user_input}]
        
        # Store goals before processing to detect new ones
        goals_before = {g.name.lower(): g for g in sheet.goals}
        
        # Process current message through Critic
        sheet, feedback, critic_analysis, new_pending_debuffs = critic.analyze(
            user_input, 
            sheet, 
            history_plus_user,
            state.phase
        )
        
        # Ensure all previous goals are still present (safety check)
        for goal_name, goal_obj in goals_before.items():
            if not any(g.name.lower() == goal_name for g in sheet.goals):
                print(f"[WARNING] Goal '{goal_obj.name}' was lost during processing, restoring it")
                sheet.goals.append(goal_obj)
        
        # Add user message to history after processing
        state.conversation_history.append({"role": "user", "content": user_input})
        
        # Add new pending debuffs to state
        for debuff in new_pending_debuffs:
            # Check if debuff already exists
            if not any(d.name == debuff.name for d in state.pending_debuffs):
                state.pending_debuffs.append(debuff)
        
        # Determine current phase based on sheet state
        all_pillars_in_goals = set()
        for goal in sheet.goals:
            all_pillars_in_goals.update(goal.pillars)
        pillars_with_goals = list(all_pillars_in_goals)
        defined_pillars = len(pillars_with_goals)
        total_pillars = 4
        all_goals_defined = defined_pillars >= total_pillars
        
        # Check if all goals have at least 2 quests
        all_goals_have_quests = all_goals_defined and all(
            len(g.current_quests) >= 2 
            for g in sheet.goals
        )
        
        # Phase transition logic
        def has_pure_goal_for_pillar(goals, pillar):
            """Check if a pillar has at least one pure goal (single-pillar goal)."""
            return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
        
        all_4_pillars_covered = len(all_pillars_in_goals) >= 4
        all_pillars_have_pure_goals = all(
            has_pure_goal_for_pillar(sheet.goals, p) for p in Pillar if p in all_pillars_in_goals
        ) if all_4_pillars_covered else False
        
        if state.phase == "phase1" and all_4_pillars_covered and all_pillars_have_pure_goals:
            print(f"\n[Phase Transition] Moving from phase1 to phase2!")
            state.phase = "phase2"
        
        def is_goal_complete_for_phase2(goal):
            return len(goal.current_quests) >= 2 or goal.skill_level is not None
        
        all_goals_complete = all_4_pillars_covered and all(
            is_goal_complete_for_phase2(g) 
            for g in sheet.goals
        ) if all_4_pillars_covered else False
        
        if state.phase == "phase2" and all_goals_complete:
            print(f"\n[Phase Transition] Moving from phase2 to phase3!")
            state.phase = "phase3"
        
        # Convert pending debuffs to the format expected by Architect
        pending_debuffs_list = [
            {"name": d.name, "evidence": d.evidence, "confidence": d.confidence} 
            for d in state.pending_debuffs
        ]
        
        # Convert pending goals
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
        
        # Remove progress markers from reply for cleaner terminal output
        import re
        reply = re.sub(r'\[Progress:[^\]]*?(\d{1,3})%\]', '', reply, flags=re.IGNORECASE)
        reply = re.sub(r'\[Progress:[^\]]*?\]\s*(\d{1,3})%', '', reply, flags=re.IGNORECASE)
        reply = reply.strip()
        
        print(f"\nArchitect: {reply}\n")
        state.conversation_history.append({"role": "assistant", "content": reply})
        
        # Debug info
        if sheet.goals:
            print(f"[Debug] Current goals ({len(sheet.goals)}): {[g.name for g in sheet.goals]}")
        if state.pending_debuffs:
            print(f"[Debug] Pending debuffs: {[d.name for d in state.pending_debuffs]}")
        print(f"[Debug] Phase: {state.phase}\n")

if __name__ == "__main__":
    debug_onboarding()







