import sys
import os
import time

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models import CharacterSheet, ConversationState
from src.agent import ArchitectAgent, CriticAgent
import re

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
    
    # Pre-defined inputs to simulate the conversation
    inputs = [
        "I would do some journaling, and then excercise, and then some vocal practice to improve my communication skills. Then i would love to dedicate some time to volleyball, to coding, and to family and friends.",
        "journaling would be 15 mins, excersing would be about 1h30 a day for 2 to 3 times a week, vocal practice will be at the start or end of everyday - probably the start so i can just plan out my day as well. And volleyball will be on the days theres no gym. And coding will be 3-5 hs a day, friends and family will be 2-3 hs a day but i can manage by like studying with friends and eating with family and such.",
        "I always forget and get distracted. I always start scrolling on my phone ya know. Especially if theres something i need to do that day, i just want to spend like the morning getting all the routines out of the way"
    ]
    
    for user_input in inputs:
        print(f"You: {user_input}")
        
        # 1. Update History
        state.conversation_history.append({"role": "user", "content": user_input})
        
        # 2. Critic Loop
        sheet, feedback = critic.analyze(user_input, sheet, state.conversation_history)
        
        if feedback:
            print(f"\n[Critic Feedback]: {feedback}")
            
        # Check completion status
        is_complete = False
        # We need to replicate the logic from main.py or import it, but for now let's just pass False 
        # unless we want to test the final turn logic specifically. 
        # Actually, let's just assume the last input triggers completion for testing purposes if we want.
        # But to be accurate, we should check the sheet.
        non_zero_stats = sum(1 for val in sheet.core_stats.values() if val > 0)
        user_turns = len(inputs) # In simulation we know the total turns
        # This is a bit hacky for simulation, but let's just pass False for now to see the flow, 
        # or True on the last one.
        
        is_final_turn = (user_input == inputs[-1])

        # 3. Architect Response
        full_response = architect.generate_response(state.conversation_history, sheet, feedback, is_final_turn=is_final_turn)
        
        # 4. Parse Thinking vs Response
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", full_response, re.DOTALL)
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            print(f"\n[Architect Thinking]: {thinking_content}")
            clean_response = re.sub(r"<thinking>.*?</thinking>", "", full_response, flags=re.DOTALL).strip()
        else:
            clean_response = full_response
            
        print(f"\nArchitect: {clean_response}\n")
        state.conversation_history.append({"role": "assistant", "content": full_response})
        
        # Wait a bit to avoid rate limits
        time.sleep(2)

    print("\n--- Character Creation Complete (Simulation) ---")
    print(sheet.model_dump_json(indent=2))

if __name__ == "__main__":
    main()