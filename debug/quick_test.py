"""Quick test for misclassification question."""
import sys
import os
# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar
from src.onboarding.agent import ArchitectAgent, CriticAgent

sheet = CharacterSheet(user_id="test")
state = ConversationState(
    missing_fields=["north_star_goals", "current_quests", "stats_career", "stats_physical", "stats_mental", "stats_social"],
    current_topic="Intro",
    phase="phase1",
)

architect = ArchitectAgent()
critic = CriticAgent()

welcome_msg = "Listen kid, i need you to tell me 4 things. Your career goals, your fitness goals, your mental health goals, and your connection goals, do that for me wont cha"
state.conversation_history.append({"role": "assistant", "content": welcome_msg})

user_input = "OK for Career I want to make a successful drop shipping business for mental I want to be More calm under pressure for my physical goal I want to be able to debt lift 200kg and for which connection goal I want to be able to have like a lot of friend groups and be able to talk to all"

print("User:", user_input)
print()

history_plus_user = state.conversation_history + [{"role": "user", "content": user_input}]
sheet, feedback, critic_analysis, new_pending_debuffs = critic.analyze(
    user_input, 
    sheet, 
    history_plus_user,
    state.phase
)

state.conversation_history.append({"role": "user", "content": user_input})

print("Feedback:", feedback)
print()

pending_debuffs_list = [{"name": d.name, "evidence": d.evidence, "confidence": d.confidence} for d in state.pending_debuffs]
pending_goals_list = [{"name": g.name, "pillars": [p.value for p in g.pillars], "description": g.description} for g in state.pending_goals]

reply, thinking = architect.generate_response(
    state.conversation_history,
    sheet,
    feedback,
    phase=state.phase,
    pending_debuffs=pending_debuffs_list,
    queued_goals=pending_goals_list,
)

print("Architect:", reply)
print()
print("Does it ask about misclassification?", "real estate" in reply.lower() and ("mental" in reply.lower() or "career" in reply.lower()) and "did you mean" in reply.lower())
