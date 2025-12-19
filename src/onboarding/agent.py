import json
import os
import difflib
import re
from typing import Tuple, List, Dict
from dotenv import load_dotenv
from src.models import CharacterSheet, ConversationState, Pillar, Goal
from src.onboarding.prompts import ARCHITECT_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from src.llm import LLMClient

# Load environment variables
load_dotenv()

llm_client = LLMClient()


def _strip_thinking_block(text: str) -> str:
    """Remove any <thinking>...</thinking> blocks from an LLM response before showing it to the user."""
    if not text:
        return text

    # Remove full thinking blocks
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Clean up any stray opening/closing tags if the model didn't close properly
    cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

class CriticAgent:
    def _deduplicate_list(self, items: List[str], similarity_threshold: float = 0.8) -> List[str]:
        """
        Deduplicates a list of strings based on semantic similarity.
        Keeps the shorter, more concise item.
        """
        if not items:
            return []
        
        to_remove = set()
        
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                item1, item2 = items[i], items[j]
                if item1 in to_remove or item2 in to_remove:
                    continue
                
                ratio = difflib.SequenceMatcher(None, item1.lower(), item2.lower()).ratio()
                
                if ratio > similarity_threshold:
                    # Mark the longer one for removal
                    if len(item1) > len(item2):
                        to_remove.add(item1)
                    else:
                        to_remove.add(item2)
                        
        return [item for item in items if item not in to_remove]

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
        You are the "Critic" and "Data Extractor" for a character creation process.
        Your job is to analyze the user's message and extract structured data for their Character Sheet.
        You must categorize extracted goals and quests into one of the four pillars: Career, Physical, Mental, Social.

        Current Character Sheet:
        {current_sheet_json}
        
        Last Architect Message: "{last_architect_msg}"
        
        Output JSON format:
        {{
            "goals": [
                {{
                    "name": "string",
                    "pillar": "CAREER|PHYSICAL|MENTAL|SOCIAL",
                    "current_quests": ["string"],
                    "description": "Optional string"
                }}
            ],
            "stats_career": {{"StatName": integer}},
            "stats_physical": {{"StatName": integer}},
            "stats_mental": {{"StatName": integer}},
            "stats_social": {{"StatName": integer}},
            "debuffs_analysis": [
                {{"name": "string", "evidence": "exact quote from user", "confidence": "high|medium|low"}}
            ],
            "feedback_for_architect": "String with feedback for the Architect agent to guide the user."
        }}
        
        INSTRUCTIONS:
        1.  **Conservative Goal Extraction**:
            *   Analyze the user's **most recent message only**.
            *   Identify high-level goals and concrete habits mentioned in that message.
            *   Assign each goal to its correct `Pillar` (CAREER, PHYSICAL, MENTAL, SOCIAL).
            *   **CRITICAL**: Do NOT infer or create goals for pillars the user has not explicitly talked about in their latest response. If the user only talks about fitness, only extract a `PHYSICAL` goal.

        2.  **Quest Validation**:
            *   Review each `current_quest`. If a quest is vague (e.g., "be healthier"), generate feedback in `feedback_for_architect` asking for a more specific, measurable action.
            *   Example Feedback: "The quest 'be healthier' is vague. Ask the user to specify a concrete action, like 'eat a salad daily'."

        3.  **Stat Inference**:
            *   Estimate stats (1-10) for the pillars the user discussed.

        4.  **Debuff Analysis**:
            *   Identify explicit debuffs (e.g., "procrastinate," "anxious"). Provide the exact user quote as `evidence`.
            *   If you find a debuff, suggest a quest to address it in `feedback_for_architect`.
        """
        
        messages = [
            {"role": "system", "content": system_prompt.format(current_sheet_json=current_sheet.model_dump_json(), last_architect_msg=last_architect_msg)},
            {"role": "user", "content": user_input}
        ]
        
        # Call LLM in JSON mode
        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        try:
            data = json.loads(response_str)

            # Process goals and quests
            if "goals" in data:
                # To avoid jumping to "all pillars complete" in a single turn,
                # limit each user message to at most ONE new pillar goal.
                new_pillars_added = 0

                for goal_data in data["goals"]:
                    pillar = goal_data.get("pillar")
                    if not pillar:
                        continue  # Skip if pillar is missing

                    # Robustly map the pillar string to the Pillar enum.
                    try:
                        pillar_enum = Pillar(pillar.upper())
                    except ValueError:
                        # Ignore unknown/invalid pillar labels from the model.
                        continue

                    # If this would be a second+ new pillar in this turn, skip it
                    if pillar_enum not in current_sheet.goals and new_pillars_added >= 1:
                        continue

                    # If a goal for this pillar doesn't exist, create it
                    if pillar_enum not in current_sheet.goals:
                        current_sheet.goals[pillar_enum] = Goal(
                            name=goal_data["name"],
                            pillar=pillar_enum,
                            description=goal_data.get("description")
                        )
                        new_pillars_added += 1

                    # Add current quests to the goal
                    if "current_quests" in goal_data:
                        for quest in goal_data["current_quests"]:
                            # Avoid duplicates
                            if quest not in current_sheet.goals[pillar_enum].current_quests:
                                current_sheet.goals[pillar_enum].current_quests.append(quest)
            
            # Update stats
            if "stats_career" in data:
                current_sheet.stats_career.update(data["stats_career"])
            if "stats_physical" in data:
                current_sheet.stats_physical.update(data["stats_physical"])
            if "stats_mental" in data:
                current_sheet.stats_mental.update(data["stats_mental"])
            if "stats_social" in data:
                current_sheet.stats_social.update(data["stats_social"])
                
            # Process debuffs
            if "debuffs_analysis" in data:
                for item in data["debuffs_analysis"]:
                    name = item.get("name")
                    if name and name not in current_sheet.debuffs:
                        current_sheet.debuffs.append(name)
            
            feedback = data.get("feedback_for_architect", "")
                
            return current_sheet, feedback
            
        except (json.JSONDecodeError, KeyError) as e:
            return current_sheet, f"[System Error: Failed to parse Critic output. Error: {e}]"

class ArchitectAgent:
    def generate_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", ask_for_prioritization: bool = False) -> str:
        """
        Generates the Architect's response based on conversation history and Critic feedback.
        """
        # Calculate progress based on defined goals for each pillar
        defined_pillars = len(current_sheet.goals)
        total_pillars = len(Pillar)
        
        progress_pct = min(int((defined_pillars / total_pillars) * 100), 95)

        # Determine which pillars are still missing goals
        missing_pillars = [p.value for p in Pillar if p not in current_sheet.goals]
        
        system_prompt_with_context = f"""{ARCHITECT_SYSTEM_PROMPT}

        [System Context]
        Current Profile Completion: {progress_pct}%
        Current Sheet State: {current_sheet.model_dump_json()}
        Missing Pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
        
        Instruction: 
        1.  Your primary goal is to guide the user to define a goal for each of the four pillars: {', '.join([p.value for p in Pillar])}.
        2.  If there are missing pillars, your response should gently guide the user towards defining a goal for one of them.
            *   Example: "This is a great start. Now, let's think about your career. What is a major goal you have for your professional life?"
        3.  You MUST include a progress bar at the end of your response in this format:
           [Progress: ||||||....] {progress_pct}%
           (Use exactly 20 characters for the bar.)
        4.  If the Critic provides feedback on a vague quest, you must relay that to the user and ask for clarification.
        """

        if ask_for_prioritization:
            system_prompt_with_context += """
            
            [PRIORITIZATION INSTRUCTION]
            All four pillars now have goals. Your next task is to ask the user to rank them.
            Present the four goals clearly to the user.
            Ask them to rank these goals from most to least important.
            Make it clear that their ranking will determine the focus of their journey.
            Example: "We've set goals for all four pillars of your life. Now, let's prioritize. Please rank the following from most to least important for you right now: [Goal 1], [Goal 2], [Goal 3], [Goal 4]."
            """
        else:
            # This is for the final turn after prioritization is done.
            if not missing_pillars: # All pillars are defined
                 system_prompt_with_context += """
                
                [FINAL TURN INSTRUCTION]
                All pillars have goals and they have been prioritized. Do NOT ask any more questions.
                Provide a grand, encouraging summary of the user's profile.
                Welcome them to their journey.
                """

        messages = [{"role": "system", "content": system_prompt_with_context}]
        
        # Add few-shot examples
        messages.extend(FEW_SHOT_EXAMPLES)
        
        # Add history
        messages.extend(history)
        
        # Inject feedback if present
        if feedback:
            messages.append({"role": "system", "content": f"[Critic's Feedback]: {feedback}"})

        response = llm_client.chat_completion(messages)
        # Hide internal thinking traces from the user-facing chat
        visible_response = _strip_thinking_block(response)
        return visible_response
