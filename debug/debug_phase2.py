"""Interactive Phase 2 debugging script.

Pre-populates goals from Phase 1 and allows interactive testing of Phase 2 quest extraction.
"""

import sys
import os
import json

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, Goal
from src.onboarding.agent import ArchitectAgent, CriticAgent


def create_initial_sheet():
    """Create a CharacterSheet with Phase 1 goals pre-populated."""
    sheet = CharacterSheet(user_id="debug_user")
    
    # Pre-populate with the 4 goals from Phase 1 (from console logs)
    goals = [
        Goal(
            name="Spike a volleyball",
            pillars=[Pillar.PHYSICAL],
            description="The user wants to be able to spike a volleyball.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Network effectively",
            pillars=[Pillar.SOCIAL],
            description="The user wants to be able to network effectively.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Be calm under pressure",
            pillars=[Pillar.MENTAL],
            description="The user wants to be calm under pressure.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Be a chef",
            pillars=[Pillar.CAREER],
            description="The user wants to be a chef.",
            current_quests=[],
            skill_level=None
        ),
    ]
    
    sheet.goals = goals
    return sheet


def is_goal_complete_for_phase2(goal):
    """Check if a goal is complete for Phase 2 (has 2+ quests or skill_level)."""
    return len(goal.current_quests) >= 2 or goal.skill_level is not None


def get_current_pillar_for_phase2(sheet: CharacterSheet):
    """Determine which pillar to ask about next in Phase 2 (first pillar with incomplete goals)."""
    def get_pillars_with_incomplete_goals(goals):
        """Get pillars that have goals that are incomplete (need 2+ quests OR skill_level)."""
        pillars_with_incomplete = set()
        for goal in goals:
            if not is_goal_complete_for_phase2(goal):
                pillars_with_incomplete.update(goal.pillars)
        return pillars_with_incomplete
    
    incomplete_pillars = get_pillars_with_incomplete_goals(sheet.goals)
    # Cycle through pillars in order, find first one with incomplete goals
    for p in Pillar:
        if p in incomplete_pillars:
            return p.value
    return None


def print_sheet_state(sheet: CharacterSheet):
    """Print the current state of the CharacterSheet."""
    print("\n" + "=" * 70)
    print("CURRENT CHARACTER SHEET STATE")
    print("=" * 70)
    print(f"Total Goals: {len(sheet.goals)}")
    print()
    
    for goal in sheet.goals:
        pillars_str = ", ".join([p.value for p in goal.pillars])
        quest_count = len(goal.current_quests)
        skill_level_str = f" (skill: {goal.skill_level})" if goal.skill_level is not None else ""
        print(f"  [{pillars_str}] '{goal.name}'{skill_level_str}")
        print(f"      Quests ({quest_count}/2): {goal.current_quests if goal.current_quests else '[]'}")
        if goal.description:
            print(f"      Description: {goal.description}")
        print()
    
    print("=" * 70 + "\n")


def main():
    """Interactive Phase 2 debugging session."""
    print("=" * 70)
    print("PHASE 2 DEBUGGING SESSION")
    print("=" * 70)
    print("\nPre-populated goals from Phase 1:")
    print("  1. Spike a volleyball (PHYSICAL)")
    print("  2. Network effectively (SOCIAL)")
    print("  3. Be calm under pressure (MENTAL)")
    print("  4. Be a chef (CAREER)")
    print("\nStarting Phase 2 quest extraction...")
    print("Type 'quit' or 'exit' to end the session.")
    print("Type 'state' to see current sheet state.")
    print("-" * 70)
    
    # Initialize
    sheet = create_initial_sheet()
    state = ConversationState(
        missing_fields=["current_quests"],
        current_topic="Current Quests",
        phase="phase2",
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Goal state tracking: track which goals have been asked about and their status
    # Format: {goal_name: {"asked_about_activities": bool, "asked_about_skill": bool, "last_question_was": str}}
    goal_state_tracker = {}
    for goal in sheet.goals:
        goal_state_tracker[goal.name] = {
            "asked_about_activities": False,
            "asked_about_skill": False,
            "last_question_was": None,
            "last_response_indicated_no_activities": False
        }
    
    # Show initial state
    print_sheet_state(sheet)
    
    # Start with initial Architect message
    current_pillar = get_current_pillar_for_phase2(sheet)
    arch_response, arch_thinking = architect.generate_response(
        history=state.conversation_history,
        current_sheet=sheet,
        feedback="",
        phase="phase2",
        pending_debuffs=[],
        current_pillar=current_pillar,
        goal_state_tracker=goal_state_tracker,
        should_ask_skill_level=False,
        target_goal_name=None,
    )
    
    print("[ARCHITECT THINKING]:")
    print(arch_thinking if arch_thinking else "(No thinking provided)")
    print()
    
    print("[ARCHITECT]:")
    print(arch_response)
    print()
    
    # Add to history
    state.conversation_history.append({"role": "assistant", "content": arch_response})
    
    # Interactive loop
    while True:
        try:
            user_input = input("\n[YOU]: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nEnding debugging session.")
                break
            
            if user_input.lower() == 'state':
                print_sheet_state(sheet)
                continue
            
            if not user_input:
                continue
            
            # Add user message to history
            state.conversation_history.append({"role": "user", "content": user_input})
            
            # Determine which goal was just asked about from the last Architect message
            target_goal_name_for_critic = None
            last_architect_msg = None
            for msg in reversed(state.conversation_history):
                if msg.get("role") == "assistant":
                    last_architect_msg = msg.get("content", "")
                    break
            
            # Try to extract the goal name from the last Architect question
            if last_architect_msg:
                # Look for patterns like "work on [goal name]" or "to work on [goal name]"
                import re
                match = re.search(r"work on ([^?\.]+)", last_architect_msg, re.IGNORECASE)
                if match:
                    potential_goal = match.group(1).strip()
                    # Check if this matches any existing goal
                    for goal in sheet.goals:
                        if goal.name.lower() in potential_goal.lower() or potential_goal.lower() in goal.name.lower():
                            target_goal_name_for_critic = goal.name
                            break
            
            # Analyze with Critic - pass target goal name for context
            print("\n[CRITIC] Analyzing...")
            if target_goal_name_for_critic:
                print(f"[CRITIC] [CONTEXT] Target goal: '{target_goal_name_for_critic}' - user response should relate to this goal")
            sheet, feedback, analysis_json, pending_debuffs = critic.analyze(
                user_input,
                sheet,
                state.conversation_history,
                state.phase,
                target_goal_name=target_goal_name_for_critic
            )
            
            # Print Critic analysis
            try:
                analysis_data = json.loads(analysis_json)
                print("\n[CRITIC ANALYSIS]:")
                if "analysis_trace" in analysis_data:
                    print(f"  Trace: {analysis_data['analysis_trace']}")
                if "goals" in analysis_data:
                    print(f"  Extracted {len(analysis_data['goals'])} goal(s)")
                    for goal_data in analysis_data['goals']:
                        print(f"    - '{goal_data.get('name', 'N/A')}'")
                        if goal_data.get('current_quests'):
                            print(f"      Quests: {goal_data['current_quests']}")
                        if goal_data.get('skill_level'):
                            print(f"      Skill Level: {goal_data['skill_level']}")
                if feedback:
                    print(f"  Feedback: {feedback}")
            except json.JSONDecodeError:
                print(f"  Raw JSON: {analysis_json[:200]}...")
            
            # Update goal state tracker based on Critic feedback and user response
            print(f"\n[DEBUG] ========== CRITIC FEEDBACK ANALYSIS ==========")
            print(f"[DEBUG] Critic feedback: {feedback}")
            print(f"[DEBUG] User input: {user_input[:150]}...")
            
            # Check user input for explicit "don't do" or "currently don't" phrases
            user_input_lower = user_input.lower()
            no_activity_phrases = [
                "currently i dont",
                "currently i don't",
                "i dont do",
                "i don't do",
                "i dont currently",
                "i don't currently",
                "currently dont",
                "currently don't",
                "dont do them",
                "don't do them",
                "i dont do them",
                "i don't do them"
            ]
            user_said_no_activities = any(phrase in user_input_lower for phrase in no_activity_phrases)
            
            if user_said_no_activities:
                print(f"[DEBUG] ✓ Detected 'no activities' phrase in user input")
            else:
                print(f"[DEBUG] ✗ No 'no activities' phrase detected in user input")
            
            # Check if feedback indicates no activities
            feedback_says_no_activities = feedback and ("no current activities" in feedback.lower() or "ask them to self-assess" in feedback.lower())
            if feedback_says_no_activities:
                print(f"[DEBUG] ✓ Critic feedback indicates no activities")
            
            # Find which goal this is about by checking the last Architect question
            last_architect_msg = None
            for msg in reversed(state.conversation_history):
                if msg.get("role") == "assistant":
                    last_architect_msg = msg.get("content", "")
                    break
            
            print(f"[DEBUG] Last Architect message: {last_architect_msg[:100] if last_architect_msg else 'None'}...")
            
            # If user said no activities OR feedback says no activities, mark it
            if user_said_no_activities or feedback_says_no_activities:
                # Try to identify which goal was asked about
                matched_goal = None
                for goal_name in goal_state_tracker:
                    if last_architect_msg and goal_name.lower() in last_architect_msg.lower():
                        matched_goal = goal_name
                        goal_state_tracker[goal_name]["last_response_indicated_no_activities"] = True
                        goal_state_tracker[goal_name]["asked_about_activities"] = True  # We did ask about activities
                        print(f"[DEBUG] Matched '{goal_name}' to last Architect question")
                        print(f"[GOAL STATE] Marked '{goal_name}' as having no current activities (asked about activities, user said none)")
                        break
                
                if not matched_goal:
                    print(f"[DEBUG] WARNING: Could not match user response to any goal from last Architect question")
            
            print(f"[DEBUG] ===========================================\n")
            
            # Also check if goals now have quests - means user provided activities
            # This should happen AFTER the Critic analysis updates the sheet
            for goal in sheet.goals:
                if goal.name in goal_state_tracker:
                    prev_quest_count = len([q for q in goal.current_quests if q])  # Count non-empty quests
                    # Re-check after Critic update
                    current_quest_count = len(goal.current_quests)
                    
                    if current_quest_count >= 2:
                        goal_state_tracker[goal.name]["asked_about_activities"] = True
                        goal_state_tracker[goal.name]["last_response_indicated_no_activities"] = False
                        if prev_quest_count < 2:
                            print(f"[GOAL STATE] Goal '{goal.name}' now has {current_quest_count} quests (was {prev_quest_count}) - marked as having activities")
                    elif current_quest_count > 0:
                        # User provided some activities but not enough
                        goal_state_tracker[goal.name]["asked_about_activities"] = True
                        print(f"[GOAL STATE] Goal '{goal.name}' has {current_quest_count} quests (need 2) - marked as asked about activities")
                    
                    if goal.skill_level is not None:
                        goal_state_tracker[goal.name]["asked_about_skill"] = True
                        print(f"[GOAL STATE] Goal '{goal.name}' now has skill level {goal.skill_level}")
            
            # Update goal state: mark goals that now have quests or skill levels as complete
            for goal in sheet.goals:
                if goal.name in goal_state_tracker:
                    if len(goal.current_quests) >= 2:
                        goal_state_tracker[goal.name]["asked_about_activities"] = True
                    if goal.skill_level is not None:
                        goal_state_tracker[goal.name]["asked_about_skill"] = True
            
            # Show updated sheet state
            print_sheet_state(sheet)
            
            # Print goal state tracker
            print("\n[GOAL STATE TRACKER]:")
            for goal_name, state_info in goal_state_tracker.items():
                print(f"  '{goal_name}':")
                print(f"    - Asked about activities: {state_info['asked_about_activities']}")
                print(f"    - Asked about skill: {state_info['asked_about_skill']}")
                print(f"    - Last question was: {state_info['last_question_was']}")
                print(f"    - Response indicated no activities: {state_info['last_response_indicated_no_activities']}")
            
            # Determine current pillar for next question
            current_pillar = get_current_pillar_for_phase2(sheet)
            print(f"\n[DEBUG] Current pillar for next question: {current_pillar}")
            
            # Check conversation history to see if we already asked about current activities
            # and got a response indicating no activities
            last_architect_msg = None
            for msg in reversed(state.conversation_history):
                if msg.get("role") == "assistant":
                    last_architect_msg = msg.get("content", "")
                    break
            
            # Determine which goal we should ask about and what stage we're at
            target_goal_name = None
            should_ask_skill_level = False
            
            print(f"\n[DEBUG] ========== GOAL SELECTION REASONING ==========")
            print(f"[DEBUG] Current pillar: {current_pillar}")
            
            if current_pillar:
                current_pillar_enum = Pillar(current_pillar.upper())
                incomplete_goals = [
                    g for g in sheet.goals 
                    if current_pillar_enum in g.pillars and not is_goal_complete_for_phase2(g)
                ]
                print(f"[DEBUG] Incomplete goals in {current_pillar}: {[g.name + f'({len(g.current_quests)}/2 quests, skill:{g.skill_level})' for g in incomplete_goals]}")
                
                if incomplete_goals:
                    target_goal = incomplete_goals[0]
                    target_goal_name = target_goal.name
                    
                    print(f"[DEBUG] Selected target goal: '{target_goal_name}'")
                    print(f"[DEBUG]   - Quest count: {len(target_goal.current_quests)}/2")
                    print(f"[DEBUG]   - Skill level: {target_goal.skill_level}")
                    print(f"[DEBUG]   - Is complete? {is_goal_complete_for_phase2(target_goal)}")
                    
                    # Check if we already asked about activities for this goal
                    if target_goal_name in goal_state_tracker:
                        goal_state = goal_state_tracker[target_goal_name]
                        print(f"[DEBUG] Goal state for '{target_goal_name}':")
                        print(f"[DEBUG]   - Asked about activities: {goal_state['asked_about_activities']}")
                        print(f"[DEBUG]   - Asked about skill: {goal_state['asked_about_skill']}")
                        print(f"[DEBUG]   - Last question was: {goal_state['last_question_was']}")
                        print(f"[DEBUG]   - Response indicated no activities: {goal_state['last_response_indicated_no_activities']}")
                        
                        if goal_state["last_response_indicated_no_activities"]:
                            should_ask_skill_level = True
                            print(f"[DEBUG] REASONING: User already said no activities → Should ask for skill level")
                        elif not goal_state["asked_about_activities"]:
                            print(f"[DEBUG] REASONING: Haven't asked about activities yet → Should ask about activities")
                        elif goal_state["asked_about_activities"] and len(target_goal.current_quests) < 2 and target_goal.skill_level is None:
                            # We asked, but goal still incomplete - check if user said no activities
                            if "currently i dont" in user_input.lower() or "currently i don't" in user_input.lower() or "i dont do" in user_input.lower():
                                should_ask_skill_level = True
                                goal_state_tracker[target_goal_name]["last_response_indicated_no_activities"] = True
                                print(f"[DEBUG] REASONING: User response contains 'dont do' → Should ask for skill level")
                            else:
                                print(f"[DEBUG] REASONING: Already asked, goal incomplete, but user didn't explicitly say no activities → Need to check feedback")
                        else:
                            print(f"[DEBUG] REASONING: Already asked about activities, checking if we need skill level...")
                    else:
                        print(f"[DEBUG] REASONING: No goal state found for '{target_goal_name}' → First time asking")
            else:
                print(f"[DEBUG] REASONING: No current pillar → All goals complete?")
            
            print(f"[DEBUG] Final decision: target_goal_name='{target_goal_name}', should_ask_skill_level={should_ask_skill_level}")
            print(f"[DEBUG] ===========================================\n")
            
            # Generate Architect response with goal state info
            arch_response, arch_thinking = architect.generate_response(
                history=state.conversation_history,
                current_sheet=sheet,
                feedback=feedback,
                phase="phase2",
                pending_debuffs=pending_debuffs,
                current_pillar=current_pillar,
                goal_state_tracker=goal_state_tracker,
                should_ask_skill_level=should_ask_skill_level,
                target_goal_name=target_goal_name,
            )
            
            print("[ARCHITECT THINKING]:")
            print(arch_thinking if arch_thinking else "(No thinking provided)")
            print()
            
            print("[ARCHITECT]:")
            print(arch_response)
            print()
            
            # Update goal state tracker after generating response (to track what we just asked)
            if target_goal_name and target_goal_name in goal_state_tracker:
                if should_ask_skill_level:
                    goal_state_tracker[target_goal_name]["last_question_was"] = "skill_level"
                    goal_state_tracker[target_goal_name]["asked_about_skill"] = True
                else:
                    # Only mark as asked if we're asking for the first time
                    if not goal_state_tracker[target_goal_name]["asked_about_activities"]:
                        goal_state_tracker[target_goal_name]["asked_about_activities"] = True
                        goal_state_tracker[target_goal_name]["last_question_was"] = "activities"
            
            # Add Architect response to history
            state.conversation_history.append({"role": "assistant", "content": arch_response})
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Ending session.")
            break
        except Exception as e:
            print(f"\n[ERROR]: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()

