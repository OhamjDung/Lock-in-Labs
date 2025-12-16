import json
import os
from typing import Tuple, List, Dict
from dotenv import load_dotenv
from src.models import CharacterSheet, ConversationState
from src.onboarding.prompts import ARCHITECT_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from src.llm import LLMClient

# Load environment variables
load_dotenv()

llm_client = LLMClient()

class CriticAgent:
    def analyze(self, user_input: str, current_sheet: CharacterSheet, history: List[Dict[str, str]] = []) -> Tuple[CharacterSheet, str]:
        """
        Analyzes the user input to extract data and update the character sheet.
        Returns the updated sheet and any feedback for the Architect.
        """
        
        last_architect_msg = "None"
        # History[-1] is the current user input (if added before call) or we just look for the last assistant msg
        # In main.py, user input is added to history BEFORE calling analyze.
        # So history[-1] is user, history[-2] is assistant.
        if len(history) >= 2 and history[-2]['role'] == 'assistant':
            last_architect_msg = history[-2]['content']
        
        system_prompt = """
        You are the "Critic" and "Data Extractor". 
        Your job is to analyze the user's latest message and extract structured data for their Character Sheet.
        
        Current Character Sheet:
        {current_sheet_json}
        
        Last Architect Message: "{last_architect_msg}"
        
        Output JSON format:
        {{
            "north_star_goals": ["string"],
            "main_quests": ["string"],
            "stats_career": {{"StatName": integer}},
            "stats_physical": {{"StatName": integer}},
            "stats_mental": {{"StatName": integer}},
            "stats_social": {{"StatName": integer}},
            "debuffs_analysis": [
                {{"name": "string", "evidence": "exact quote from user", "confidence": "high|medium|low"}}
            ],
            "skill_tree_updates": [],
            "is_vague": boolean,
            "feedback": "String explaining what is vague or missing"
        }}
        
        INSTRUCTIONS:
        1. 'north_star_goals': Abstract, long-term aspirations (e.g., "Become a Master Coder", "Be Physically Fit").
           - INFERENCE: If the user lists habits (Main Quests) but no high-level goal, INFER the North Star Goal.
             * "Exercise daily" -> "Physical Peak Performance"
             * "Code daily" -> "Mastery of Technology"
             * "Journal daily" -> "Mental Clarity & Self-Reflection"
        2. 'main_quests': Concrete, actionable HABITS or ROUTINES (e.g., "Code 1 hour daily", "Go to gym 3x/week").
           - If the user says "I want to journal", that is a Main Quest ("Journal daily").
           - If the user says "I want to improve communication", that is a North Star Goal.
        3. DEDUPLICATION: Do NOT output items that are semantically similar to existing ones.
        4. STAT INFERENCE: You MUST estimate Stats (1-10) across the 4 Pillars:
           - Career: Focus, Strategy, Wealth, Skill
           - Physical: Strength, Endurance, Agility, Health
           - Mental: Clarity, Resilience, Logic, Creativity
           - Social: Charisma, Empathy, Leadership, Connection
           - If they admit to struggling, lower the stat (e.g., Discipline: 3).
           - If they have a solid routine, raise it (e.g., Vitality: 6).
        5. DEBUFFS: Look for EXPLICIT keywords like "stutter", "distracted", "procrastinate", "injury", "fear", "anxiety", "lack of routine". 
           - REQUIREMENT: You MUST provide the "evidence" (exact quote) for every debuff.
           - STRICT RULE: Do NOT infer debuffs from a busy schedule or multiple hobbies.
           - STRICT RULE: Only add "Digital Distraction" if the user mentions "phone", "social media", "scrolling", "screen", or "internet addiction".
           - DO NOT HALLUCINATE DEBUFFS. If the user does not mention a struggle, do NOT add one.
           - Example: "I stutter" -> Debuff: "Speech Impediment", Evidence: "I stutter"
           - Example: "I scroll too much" -> Debuff: "Digital Distraction", Evidence: "I scroll too much"
           - Example: "I lack routine" -> Debuff: "Lack of Routine Building", Evidence: "I lack routine"
           
           CRITICAL: If you detect a Debuff, you MUST:
           1. Add it to the "debuffs_analysis" list.
           2. In the "feedback" field, suggest a Main Quest to fix it.
              * Feedback format: "Detected Debuff 'X'. Suggest Main Quest: 'Y'."
           
           EXAMPLE JSON OUTPUT FOR DEBUFF:
           {{
               "debuffs_analysis": [
                   {{"name": "Lack of Routine Building", "evidence": "I struggle to keep a schedule", "confidence": "high"}}
               ],
               "feedback": "Detected Debuff 'Lack of Routine Building'. Suggest Main Quest: 'Create a daily schedule'."
           }}
        
        6. QUEST PROPOSALS:
           - IF (and ONLY IF) the user explicitly agrees to a proposal from the 'Last Architect Message' (e.g., "Yes, I'll do that"), THEN add it to 'main_quests'.
           - DO NOT suggest quests for problems that do not exist.
        """
        
        messages = [
            {"role": "system", "content": system_prompt.format(current_sheet_json=current_sheet.model_dump_json(), last_architect_msg=last_architect_msg)},
            {"role": "user", "content": user_input}
        ]
        
        # Call LLM in JSON mode
        # Call LLM in JSON mode
        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        try:
            data = json.loads(response_str)
            # Update sheet with deduplication
            if "north_star_goals" in data:
                for goal in data["north_star_goals"]:
                    # Simple fuzzy check: is the new goal contained in any existing goal or vice versa?
                    is_duplicate = False
                    for existing in current_sheet.north_star_goals:
                        if goal.lower() in existing.lower() or existing.lower() in goal.lower():
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        current_sheet.north_star_goals.append(goal)
            
            if "main_quests" in data:
                for quest in data["main_quests"]:
                    is_duplicate = False
                    for existing in current_sheet.main_quests:
                        if quest.lower() in existing.lower() or existing.lower() in quest.lower():
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        current_sheet.main_quests.append(quest)
                        
            if "stats_career" in data:
                current_sheet.stats_career.update(data["stats_career"])
            if "stats_physical" in data:
                current_sheet.stats_physical.update(data["stats_physical"])
            if "stats_mental" in data:
                current_sheet.stats_mental.update(data["stats_mental"])
            if "stats_social" in data:
                current_sheet.stats_social.update(data["stats_social"])
                
            if "debuffs_analysis" in data:
                for item in data["debuffs_analysis"]:
                    name = item.get("name")
                    evidence = item.get("evidence")
                    if evidence is None:
                        evidence = ""
                    evidence = str(evidence).lower()
                    
                    # Python-side validation for Digital Distraction
                    if name == "Digital Distraction":
                        valid_keywords = ["phone", "social media", "scrolling", "screen", "internet", "tiktok", "instagram", "youtube", "web"]
                        if not any(k in evidence for k in valid_keywords):
                            # Skip this hallucination
                            continue
                            
                    if name and name not in current_sheet.debuffs:
                        current_sheet.debuffs.append(name)
            
            # Fallback for old format if model ignores instructions
            if "debuffs" in data and isinstance(data["debuffs"], list):
                 for debuff in data["debuffs"]:
                    if debuff not in current_sheet.debuffs:
                        current_sheet.debuffs.append(debuff)
                
            feedback = data.get("feedback", "")
            if data.get("is_vague"):
                feedback = f"[System Note: User answer was too vague. {feedback}]"
                
            return current_sheet, feedback
            
        except json.JSONDecodeError:
            return current_sheet, "[System Error: Failed to parse Critic output]"

class ArchitectAgent:
    def generate_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", is_final_turn: bool = False) -> str:
        """
        Generates the Architect's response based on conversation history and Critic feedback.
        """
        # Calculate progress
        filled_fields = 0
        total_fields = 4 # North Star, Main Quests, Stats, Debuffs
        if current_sheet.north_star_goals: filled_fields += 1
        if current_sheet.main_quests: filled_fields += 1
        # Stats are weighted more heavily
        # Check if at least one stat in ANY category is > 0
        all_stats = {**current_sheet.stats_career, **current_sheet.stats_physical, **current_sheet.stats_mental, **current_sheet.stats_social}
        non_zero_stats = sum(1 for val in all_stats.values() if val > 0)
        if non_zero_stats >= 1: filled_fields += 1
        if non_zero_stats >= 2: filled_fields += 1 # Bonus for getting deeper
        if current_sheet.debuffs: filled_fields += 1  
        
        # Adjust total fields to 5 to account for the extra stat weight
        total_fields = 5
        
        if is_final_turn:
            progress_pct = 100
        else:
            progress_pct = min(int((filled_fields / total_fields) * 100), 95) # Cap at 95 until final
        
        system_prompt_with_context = f"""{ARCHITECT_SYSTEM_PROMPT}

        [System Context]
        Current Profile Completion: {progress_pct}%
        Current Sheet State: {current_sheet.model_dump_json()}
        
        Instruction: 
        1. You MUST include a progress bar at the end of your response in this format:
           [Progress: ||||||....] {progress_pct}%
           (Use exactly 20 characters for the bar. Example: [||||||||||..........] 50%)
        2. You can optionally mention the completion percentage to encourage the user if they are close.
        3. If you have assigned stats in your response, explicitly list them in a summary block like:
           [Stats Updated: Intelligence: X, Vitality: Y, Discipline: Z]
        4. If the Critic Feedback suggests a Main Quest for a Debuff, PROPOSE it to the user. Do not assume they accept it. Ask them.
        """

        if is_final_turn:
            system_prompt_with_context += """
            
            [FINAL TURN INSTRUCTION]
            The Character Sheet is now complete. 
            Do NOT ask any more questions.
            Instead, provide a grand, encouraging summary of the user's profile.
            Welcome them to the "Game of Life" (or "Lock In Labs").
            Tell them their journey begins now.
            """

        messages = [{"role": "system", "content": system_prompt_with_context}]
        
        # Add few-shot examples
        messages.extend(FEW_SHOT_EXAMPLES)
        
        # Add history
        messages.extend(history)
        
        # Inject feedback if present
        if feedback:
            messages.append({"role": "system", "content": feedback})
            
        response = llm_client.chat_completion(messages)
        return response
