import sys
import os
import argparse

# Add the project root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
from datetime import date
from src.models import (
    CharacterSheet,
    ConversationState,
    Pillar,
    SkillTree,
    ReportingState,
)
from src.onboarding.agent import ArchitectAgent, CriticAgent
from src.skill_tree.generator import SkillTreeGenerator
from src.storage import save_profile, load_profile
from tests.test_input import USER_INTERVIEW_V2
from src.planners import CareerPlanner, PhysicalPlanner, MentalPlanner, ConnectionPlanner
from src.llm import LLMClient
from src.reporting import (
    ReportingAgent,
    get_todays_tasks,
    apply_daily_report,
    ensure_daily_schedule_for_date,
)

llm_client = LLMClient()

def classify_north_star(north_star: str) -> str:
    """Classifies the North Star goal into a planner category."""
    prompt = f"""
    You are a classification agent. Your job is to classify the given "North Star Goal" into one of the following categories:

    - Career & Finance
    - Physical Health & Fitness
    - Mental Agility & Emotional Wellbeing
    - Social & Connections

    Goal: "{north_star}"

    Based on the goal, which category does it best fit into? Respond with ONLY the category name.
    """
    messages = [{"role": "user", "content": prompt}]
    response = llm_client.chat_completion(messages)
    # Basic cleaning, assuming the model follows instructions
    return response.strip()

def get_planner(category: str):
    """Returns an instance of the appropriate planner based on the category."""
    category_upper = category.upper()
    if "CAREER" in category_upper:
        return CareerPlanner()
    elif "PHYSICAL" in category_upper:
        return PhysicalPlanner()
    elif "MENTAL" in category_upper:
        return MentalPlanner()
    elif "SOCIAL" in category_upper:
        return ConnectionPlanner()
    else:
        # Default or fallback planner
        return CareerPlanner()

def are_all_pillars_defined(sheet: CharacterSheet) -> bool:
    """Checks if the user has defined a goal for every pillar."""
    return len(sheet.goals) == len(Pillar)

def process_turn(user_input: str, sheet: CharacterSheet, state: ConversationState, architect: ArchitectAgent, critic: CriticAgent):
    """Processes a single turn of the conversation."""
    # 1. Update History
    state.conversation_history.append({"role": "user", "content": user_input})
    
    # 2. Critic Analysis
    sheet, feedback = critic.analyze(user_input, sheet, state.conversation_history)
    
    if feedback:
        print(f"\n[Critic Feedback]: {feedback}")
        
    # 3. Check if all pillars now have goals
    pillars_defined = are_all_pillars_defined(sheet)

    # 4. Goal Prioritization Step
    if pillars_defined and not state.goals_prioritized:
        # All pillars are defined, but we haven't asked the user to rank them yet.
        # The Architect's next job is to ask for this ranking.
        # The user's *next* input will be the ranking.
        # For now, we just generate the "please rank your goals" message.
        
        # We pass a special flag to the architect to generate this specific prompt.
        full_response = architect.generate_response(
            state.conversation_history, 
            sheet, 
            feedback, 
            ask_for_prioritization=True
        )
        print(f"\nArchitect: {full_response}\n")
        state.conversation_history.append({"role": "assistant", "content": full_response})
        
        # We mark that we have prompted for prioritization. The next input will be the ranking.
        state.goals_prioritized = True # We set this to true to signify the *next* step is processing the ranking.
        return False # Not complete yet, waiting for ranking.

    # 5. Handle the ranking input from the user
    if pillars_defined and state.goals_prioritized:
        # The user's input should be their ranked list.
        # For simplicity, we'll assume a format like "1. Career, 2. Physical, ..."
        # A more robust solution would use an LLM to parse the ranking.
        ranked_pillars = re.findall(r'\b(CAREER|PHYSICAL|MENTAL|SOCIAL)\b', user_input, re.IGNORECASE)
        
        if ranked_pillars:
            # Create a new ordered dictionary for the goals, defensively
            new_goals_order = {}
            for p in ranked_pillars:
                try:
                    enum_pillar = Pillar(p.upper())
                except ValueError:
                    # Ignore any unexpected values
                    continue

                if enum_pillar in sheet.goals and enum_pillar not in new_goals_order:
                    new_goals_order[enum_pillar] = sheet.goals[enum_pillar]
            
            if new_goals_order:
                # Update the sheet's goals with the new order
                sheet.goals = new_goals_order
                print("\n[System]: Goal priorities have been updated.")
                
                # Now we can proceed to the final generation.
                is_complete = True
            else:
                print("\nArchitect: I'm sorry, I didn't understand the order. Please list the pillars (Career, Physical, Mental, Social) from most to least important.\n")
                return False
        else:
            # The user didn't provide a clear ranking. Ask again.
            print("\nArchitect: I'm sorry, I didn't understand the order. Please list the pillars (Career, Physical, Mental, Social) from most to least important.\n")
            return False

    else:
        is_complete = False

    # 6. Architect's regular response if not prioritizing or complete
    if not pillars_defined and not is_complete:
        full_response = architect.generate_response(state.conversation_history, sheet, feedback)
        print(f"\nArchitect: {full_response}\n")
        state.conversation_history.append({"role": "assistant", "content": full_response})

    # 7. Final Generation
    if is_complete:
        print("\n[System]: Character profile complete. Running final analysis...")

        # --- Orchestrator Logic ---
        # The orchestrator will now iterate through the prioritized goals
        for pillar, goal in sheet.goals.items():
            print(f"[Orchestrator]: Planning for {pillar.value} Goal: '{goal.name}'")
            
            planner = get_planner(pillar.value)
            print(f"[Orchestrator]: Deploying '{planner.__class__.__name__}'...")

            needed_skill_nodes = planner.generate_roadmap(
                north_star=goal.name,
                current_quests=goal.current_quests,
                debuffs=sheet.debuffs
            )
            
            goal.needed_quests = [node.name for node in needed_skill_nodes]
            print(f"[Orchestrator]: Planner generated {len(goal.needed_quests)} new quests for the {pillar.value} goal.")
        # --- End Orchestrator Logic ---

        print("\n[System]: Generating final Skill Tree...")
        skill_tree_generator = SkillTreeGenerator()
        skill_tree = skill_tree_generator.generate_skill_tree(sheet)
        
        final_profile = {
            "character_sheet": sheet.model_dump(),
            "skill_tree": skill_tree.model_dump()
        }
        
        save_profile(final_profile, "user_01")
        print("\n[System]: Profile saved to data/user_01.json. You may now exit.")
        return True # Signal completion
        
    return False

def run_interactive_session():
    """Runs the main interactive loop for the user."""
    print("Initializing System... [The Architect is waking up]")
    
    sheet = CharacterSheet(user_id="user_01")
    state = ConversationState(
        missing_fields=["north_star_goals", "current_quests", "stats_career", "stats_physical", "stats_mental", "stats_social"],
        current_topic="Intro"
    )
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    welcome_message = "Welcome. I see potential in you. Tell me, in the perfect version of your future, what is the first thing you do when you wake up?"
    print(f"\nArchitect: {welcome_message}\n")
    state.conversation_history.append({"role": "assistant", "content": welcome_message})
    
    prompt = "You: "
    while True:
        try:
            user_input = input(prompt)
        except EOFError:
            break
            
        if user_input.lower() in ["exit", "quit"]:
            break
            
        if not user_input or not user_input.strip():
            prompt = ""
            continue
        
        prompt = "You: "
        
        if process_turn(user_input, sheet, state, architect, critic):
            break

def run_test_simulation():
    """Runs a non-interactive simulation using test data."""
    print("Initializing Test Simulation...")
    
    sheet = CharacterSheet(user_id="user_01")
    state = ConversationState(
        missing_fields=["north_star_goals", "current_quests", "stats_career", "stats_physical", "stats_mental", "stats_social"],
        current_topic="Intro"
    )
    architect = ArchitectAgent()
    critic = CriticAgent()

    # Split the interview into turns based on blank lines
    turns = [turn.strip() for turn in USER_INTERVIEW_V2.strip().split('\n\n') if turn.strip()]

    welcome_message = "Listen kid, I've seen a lot of people come through that door. Most of 'em don't know what they want. But you? You got that look. The look of someone who's gotta find their way outta this concrete jungle. So here's what I need to know: in some perfect future, when that alarm clock goes off and you're finally livin' the dream—what's the first thing you do?"
    print(f"\nArchitect: {welcome_message}\n")
    state.conversation_history.append({"role": "assistant", "content": welcome_message})

    for i, turn_input in enumerate(turns):
        print(f"You: {turn_input}")
        if process_turn(turn_input, sheet, state, architect, critic):
            print("\nSimulation complete.")
            break
    else:
        print("\nSimulation finished all turns.")


def _load_models_from_profile(user_id: str) -> tuple[CharacterSheet, SkillTree] | None:
    """Helper to load CharacterSheet and SkillTree models from stored JSON profile."""

    data = load_profile(user_id)
    if not data:
        print(f"No existing profile found for user_id='{user_id}'. Run onboarding first.")
        return None

    sheet_data = data.get("character_sheet") or {"user_id": user_id}
    tree_data = data.get("skill_tree") or {"nodes": []}

    sheet = CharacterSheet(**sheet_data)
    tree = SkillTree(**tree_data)
    return sheet, tree


def run_reporting_session(user_id: str = "user_01") -> None:
    """Run a simple end-of-day reporting loop using the ReportingAgent."""

    models = _load_models_from_profile(user_id)
    if models is None:
        return

    sheet, tree = models

    current_date = date.today().isoformat()
    todays_tasks = get_todays_tasks(sheet, tree, current_date=current_date)

    # Ensure we have a per-day schedule persisted on the sheet so the
    # frontend (and future tools) can render today's plan without having to
    # recompute it.
    ensure_daily_schedule_for_date(sheet, todays_tasks, current_date=current_date)

    state = ReportingState(
        user_id=user_id,
        current_date=current_date,
        todays_tasks=todays_tasks,
        phase="collecting",
    )

    agent = ReportingAgent()

    print("\n[Reporting] Daily check-in for", current_date)
    print(agent.initial_message(state))

    while True:
        try:
            user_input = input("You: ")
        except EOFError:
            break

        lowered = user_input.strip().lower()
        if lowered in {"exit", "quit"}:
            print("[Reporting] Exiting without saving a report.")
            return

        # Record in reporting state history
        state.conversation_history.append({"role": "user", "content": user_input})

        # Handle confirmation flow depending on phase.
        if "confirm" in lowered or "done" in lowered:
            if state.phase == "collecting":
                # First confirm: build a draft report (including schedule) but
                # do NOT apply or save yet. Let the user review it.
                draft = agent.finalize_report(state, sheet, tree)
                state.pending_report = draft
                state.phase = "review"
                state.review_feedback = []

                print("\n[Reporting] Here's a draft summary of your day:")
                print(draft.summary)
                print(
                    "\n[Reporting] Does this schedule and summary work for you? "
                    "You can type feedback to adjust it, or type 'confirm' again to accept and save."
                )
                continue

            if state.phase == "review":
                # Second confirm: finalize, attach any feedback, then apply/save.
                draft = state.pending_report
                if draft is None:
                    print("[Reporting] No draft report found; starting over.")
                    state.phase = "collecting"
                    continue

                if state.review_feedback:
                    feedback_text = " ".join(state.review_feedback)
                    prefix = "User feedback on summary/schedule:\n"
                    if draft.free_text:
                        draft.free_text += "\n\n" + prefix + feedback_text
                    else:
                        draft.free_text = prefix + feedback_text

                apply_daily_report(sheet, tree, draft)

                final_profile = {
                    "character_sheet": sheet.model_dump(),
                    "skill_tree": tree.model_dump(),
                }
                save_profile(final_profile, user_id)

                print("\n[Reporting] Report saved for", current_date)
                print("Summary:", draft.summary)
                return

        # Non-confirm input handling.
        if state.phase == "review":
            # Treat this as feedback on the proposed summary/schedule.
            state.review_feedback.append(user_input)
            print(
                "[Reporting] Got it. I've noted that feedback. "
                "When you're happy with the summary, type 'confirm' again to save."
            )
            continue

        # Regular conversational flow during the collecting phase.
        reply = agent.generate_reply(state, sheet, tree, user_input)
        state.conversation_history.append({"role": "assistant", "content": reply})
        print("Reporting Agent:", reply)

def main():
    parser = argparse.ArgumentParser(description="Run the Life RPG simulation.")
    parser.add_argument('--test', action='store_true', help='Run the simulation with test data.')
    parser.add_argument(
        '--mode',
        choices=['onboarding', 'reporting'],
        default='onboarding',
        help='Choose between onboarding (default) and daily reporting modes.',
    )

    args = parser.parse_args()

    if args.mode == 'reporting':
        run_reporting_session()
    else:
        if args.test:
            run_test_simulation()
        else:
            run_interactive_session()

if __name__ == "__main__":
    main()
