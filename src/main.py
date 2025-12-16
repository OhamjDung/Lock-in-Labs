import sys
import re
from src.models import CharacterSheet, ConversationState
from src.agent import ArchitectAgent, CriticAgent

def is_sheet_complete(sheet: CharacterSheet) -> bool:
    # Simple completion logic
    return (
        len(sheet.north_star_goals) > 0 and
        len(sheet.main_quests) > 0 and
        len(sheet.core_stats) > 0
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
    
    while not is_sheet_complete(sheet):
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
        sheet, feedback = critic.analyze(user_input, sheet)
        
        if feedback:
            print(f"\n[Critic Feedback]: {feedback}")
            
        # 3. Architect Response
        full_response = architect.generate_response(state.conversation_history, feedback)
        
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
        
    print("\n--- Character Creation Complete ---")
    print(sheet.model_dump_json(indent=2))

if __name__ == "__main__":
    main()
