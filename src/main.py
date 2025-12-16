import sys
import os

# Add the project root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
from src.models import CharacterSheet, ConversationState
from src.agent import ArchitectAgent, CriticAgent

def is_sheet_complete(sheet: CharacterSheet, history: list) -> bool:
    # Simple completion logic
    # Require all stats to be non-zero to ensure a full profile is built
    # or at least a significant portion of them.
    # Let's require at least 2 stats to be non-zero to avoid premature exit
    # if the user just mentions one thing.
    non_zero_stats = sum(1 for val in sheet.core_stats.values() if val > 0)
    
    # Count user turns
    user_turns = sum(1 for msg in history if msg.get('role') == 'user')

    # Only complete if we have enough data AND enough conversation depth
    # Let's increase the turn count to 5 to ensure a deeper conversation
    # Or ensure that we have ALL 3 stats filled
    all_stats_filled = all(val > 0 for val in sheet.core_stats.values())

    return (
        len(sheet.north_star_goals) > 0 and
        len(sheet.main_quests) > 0 and
        all_stats_filled and 
        user_turns >= 4 
    )

def main():
    print("Initializing System... [The Architect is waking up]")
    
    # Initialize State
    sheet = CharacterSheet(user_id="user_01")
    state = ConversationState(
        missing_fields=["north_star_goals", "main_quests", "core_stats"],
        current_topic="Intro"
    )
    
    architect = ArchitectAgent()
    critic = CriticAgent()
    
    # Initial greeting
    print("\nArchitect: Welcome. I see potential in you. Tell me, in the perfect version of your future, what is the first thing you do when you wake up?\n")
    state.conversation_history.append({"role": "assistant", "content": "Welcome. I see potential in you. Tell me, in the perfect version of your future, what is the first thing you do when you wake up?"})
    
    while True:
        try:
            user_input = input("You: ")
        except EOFError:
            break
            
        if user_input.lower() in ["exit", "quit"]:
            break
            
        # 1. Update History
        state.conversation_history.append({"role": "user", "content": user_input})
        
        # 2. Critic Loop (Reflexion)
        # In a real app, this runs in parallel or before the Architect
        sheet, feedback = critic.analyze(user_input, sheet, state.conversation_history)
        
        if feedback:
            print(f"\n[Critic Feedback]: {feedback}")
            
        # Check completion status AFTER Critic update but BEFORE Architect response
        is_complete = is_sheet_complete(sheet, state.conversation_history)

        # 3. Architect Response
        full_response = architect.generate_response(state.conversation_history, sheet, feedback, is_final_turn=is_complete)
        
        # 4. Parse Thinking vs Response
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", full_response, re.DOTALL)
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            print(f"\n[Architect Thinking]: {thinking_content}")
            
            # Remove thinking tag for the user display
            clean_response = re.sub(r"<thinking>.*?</thinking>", "", full_response, flags=re.DOTALL).strip()
        else:
            clean_response = full_response
            
        print(f"\nArchitect: {clean_response}\n")
        
        # Update history with full response (including thinking, so the model remembers its train of thought)
        state.conversation_history.append({"role": "assistant", "content": full_response})
        
        # Only break if complete AND the Architect has finished their thought process (no question mark at the end of response)
        # This is a heuristic: if the Architect ends with a question, they expect an answer.
        if is_complete:
            # Robust check: Remove all bracketed content [Progress: ...] [Stats: ...]
            # and check if the remaining text ends with a question mark.
            
            text_to_check = clean_response
            # Remove [Progress: ...] block
            # Handle cases where percentage is inside or outside the brackets
            text_to_check = re.sub(r"\[Progress:[^\]]*\](\s*\d*%)?", "", text_to_check)
            # Remove [Stats Updated: ...] block
            text_to_check = re.sub(r"\[Stats Updated:[^\]]*\]", "", text_to_check)
            
            text_to_check = text_to_check.strip()
            
            # Check for question mark at the end (handling potential quotes)
            # More lenient check: look for ? in the last 10 characters to handle quotes, parens, etc.
            if "?" not in text_to_check[-10:]:
                 break
            else:
                 # If Architect asked a question, we must continue even if stats are full
                 pass
        
    print("\n--- Character Creation Complete ---")
    print(sheet.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
