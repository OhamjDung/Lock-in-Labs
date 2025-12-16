import json
import os
from typing import Tuple, List, Dict
from src.models import CharacterSheet, ConversationState
from src.prompts import ARCHITECT_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES

# Placeholder for LLM client
# In a real implementation, you would initialize OpenAI or Gemini client here
class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # self.client = OpenAI(api_key=self.api_key)

    def chat_completion(self, messages, model="gpt-4o", json_mode=False):
        # This is a mock implementation. 
        # Replace with actual API call:
        # response = self.client.chat.completions.create(
        #     model=model,
        #     messages=messages,
        #     response_format={"type": "json_object"} if json_mode else None
        # )
        # return response.choices[0].message.content
        
        print(f"\n[System] Calling LLM with {len(messages)} messages (JSON Mode: {json_mode})...")
        if json_mode:
            # Mock extraction logic for demonstration
            return json.dumps({
                "north_star_goals": ["Be a great developer"],
                "main_quests": ["Build a SaaS"],
                "core_stats": {"Intelligence": 5},
                "debuffs": [],
                "missing_fields": ["debuffs"],
                "is_vague": False
            })
        else:
            # Mock response logic
            return """<thinking>
User input received. Mocking response.
</thinking>
This is a mock response from the Architect. Please configure the LLM client in src/agent.py to get real responses."""

llm_client = LLMClient()

class CriticAgent:
    def analyze(self, user_input: str, current_sheet: CharacterSheet) -> Tuple[CharacterSheet, str]:
        """
        Analyzes the user input to extract data and update the character sheet.
        Returns the updated sheet and any feedback for the Architect.
        """
        
        system_prompt = """
        You are the "Critic" and "Data Extractor". 
        Your job is to analyze the user's latest message and extract structured data for their Character Sheet.
        
        Current Character Sheet:
        {current_sheet_json}
        
        Output JSON format:
        {{
            "north_star_goals": [],
            "main_quests": [],
            "core_stats": {{}},
            "debuffs": [],
            "skill_tree_updates": [],
            "is_vague": boolean,
            "feedback": "String explaining what is vague or missing"
        }}
        
        If the user's answer is vague (e.g., "I want to be better"), set is_vague to true and provide feedback.
        Only include fields that have NEW information.
        """
        
        messages = [
            {"role": "system", "content": system_prompt.format(current_sheet_json=current_sheet.model_dump_json())},
            {"role": "user", "content": user_input}
        ]
        
        # Call LLM in JSON mode
        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        try:
            data = json.loads(response_str)
            
            # Update sheet
            if "north_star_goals" in data:
                current_sheet.north_star_goals.extend(data["north_star_goals"])
            if "main_quests" in data:
                current_sheet.main_quests.extend(data["main_quests"])
            if "core_stats" in data:
                current_sheet.core_stats.update(data["core_stats"])
            if "debuffs" in data:
                current_sheet.debuffs.extend(data["debuffs"])
                
            feedback = data.get("feedback", "")
            if data.get("is_vague"):
                feedback = f"[System Note: User answer was too vague. {feedback}]"
                
            return current_sheet, feedback
            
        except json.JSONDecodeError:
            return current_sheet, "[System Error: Failed to parse Critic output]"

class ArchitectAgent:
    def generate_response(self, history: List[Dict[str, str]], feedback: str = "") -> str:
        """
        Generates the Architect's response based on conversation history and Critic feedback.
        """
        messages = [{"role": "system", "content": ARCHITECT_SYSTEM_PROMPT}]
        
        # Add few-shot examples
        messages.extend(FEW_SHOT_EXAMPLES)
        
        # Add history
        messages.extend(history)
        
        # Inject feedback if present
        if feedback:
            messages.append({"role": "system", "content": feedback})
            
        response = llm_client.chat_completion(messages)
        return response
