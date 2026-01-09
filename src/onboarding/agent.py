import json
import os
import re
from typing import Tuple, List, Dict, Optional
from dotenv import load_dotenv
from src.models import CharacterSheet, ConversationState, Pillar, Goal, SheetDelta
from src.onboarding.prompts import ARCHITECT_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
from src.llm import LLMClient

# Load environment variables
load_dotenv()

llm_client = LLMClient()

def _strip_thinking_block(text: str) -> str:
    """Remove any <thinking>...</thinking> blocks from an LLM response."""
    if not text:
        return text
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

class CriticAgent:
    def analyze(self, user_input: str, active_goal_id: Optional[str], existing_goals: List[str]) -> Tuple[Dict, str]:
        """
        Analyzes the user input to produce atomic state updates (deltas).
        
        Args:
            user_input: The user's latest message.
            active_goal_id: The ID of the goal currently being discussed.
            existing_goals: List of strings in format "ID: <id> | Name: <name>"
        
        Returns:
            A tuple of (parsed_json_response, raw_response_string)
        """
        
        system_prompt = """
        <role_definition>
        You are the Critic (Data Extractor). Your job is to listen to the user and output ATOMIC UPDATES (deltas) for their character sheet.
        You do NOT generate conversation. You ONLY generate JSON data.
        </role_definition>

        <phase1_critical_rule>
        ⚠️ PHASE 1 DETECTION: Active Goal ID = `{active_goal_id}`
        
        **IF Active Goal ID is "None" → YOU ARE IN PHASE 1.**
        
        In Phase 1, the user is listing their LIFE GOALS (aspirations/dreams/ambitions).
        EVERY item they mention MUST use operation: "add_goal".
        
        DO NOT USE "add_quest" OR "update_skill" IN PHASE 1.
        
        ❌ WRONG (Phase 1): {{"operation": "add_quest", "payload": "Have more endurance"}}
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Have more endurance"}}
        
        ❌ WRONG (Phase 1): {{"operation": "update_skill", "payload": "Be more social"}}
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Be more social"}}
        
        ❌ WRONG (Phase 1): {{"operation": "add_quest", "payload": "Be more in tune with myself"}}
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Be more in tune with myself"}}
        
        Phase 1 patterns that are ALWAYS goals (use add_goal):
        - "I want to..." → add_goal
        - "I'd like to..." → add_goal  
        - "I need to..." → add_goal
        - "My goal is to..." → add_goal
        - Any aspiration/desire/ambition → add_goal
        </phase1_critical_rule>

        <context_rules>
        1. **Active Context**: If Active Goal ID is NOT "None", the user is answering about that specific goal. Bias towards `add_quest` for activities and `update_skill` for ratings.
        2. **Goal Creation**: If Active Goal ID is "None" (Phase 1), ALL operations MUST be `add_goal`. You CANNOT add quests or update skills for goals that do not exist yet.
        3. **Skill vs Quest** (ONLY when Active Goal ID exists):
           - "I run 5k" -> `add_quest` (Activity). If multiple activities are listed, output multiple `add_quest` deltas.
           - "I'm a 7 out of 10" / "I'm a beginner" -> `update_skill` (Numeric/Rating)
        4. **Stop Signal**:
           - "That's it", "Nothing else", "No" -> `intent: "STOP_SIGNAL"`
           - "I'm not doing anything", "Haven't started yet", "Nothing" -> `intent: "STOP_SIGNAL"`
        5. **Topic Switching**: If the user talks about a different goal, find its ID in the list below.
        </context_rules>

        <existing_goals_list>
        {existing_goals_list}
        </existing_goals_list>

        <output_schema>
        Return a JSON object with this EXACT structure:
        {{
            "intent": "PROVIDING_INFO" | "STOP_SIGNAL" | "TOPIC_SWITCH" | "QUESTION",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": null,
            "deltas": [
                {{
                    "operation": "add_quest" | "update_skill" | "add_goal" | "add_debuff",
                    "target_id": "UUID from context",
                    "payload": "the actual data"
                }}
            ],
            "feedback_for_architect": "Brief string."
        }}
        
        **CRITICAL ID RULES:**
        1. **NEVER** use "goal_abc123" or "goal_def456". These are examples.
        2. **ALWAYS** use the `Active Goal ID` (provided above) or a real ID from the `Existing Goals List`.
        3. If adding a NEW goal, `target_id` is null.
        4. If adding a quest/skill for an existing goal, `target_id` MUST match a UUID from the context.
        
        **EXAMPLES (DO NOT COPY THESE IDs):**
        
        User says: "I want to become an accountant"
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": null,
            "deltas": [
                {{"operation": "add_goal", "target_id": null, "payload": "Become an accountant"}}
            ],
            "feedback_for_architect": "User added a new goal."
        }}
        
        User says: "I watch YouTube videos about accounting" (Active Goal ID: "aecc27e1-...")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "aecc27e1-...",
            "deltas": [
                {{"operation": "add_quest", "target_id": "aecc27e1-...", "payload": "Watch YouTube videos about accounting"}}
            ],
            "feedback_for_architect": "User mentioned an activity for the active goal."
        }}
        
        User says: "I'm about a 4" (Active Goal ID: "aecc27e1-...")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "aecc27e1-...",
            "deltas": [
                {{"operation": "update_skill", "target_id": "aecc27e1-...", "payload": 4}}
            ],
            "feedback_for_architect": "User provided skill level."
        }}
        
        User says: "I'm not doing anything right now"
        Output:
        {{
            "intent": "STOP_SIGNAL",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": null,
            "deltas": [],
            "feedback_for_architect": "User is not doing anything."
        }}

        User says: "No, that's it"
        Output:
        {{
            "intent": "STOP_SIGNAL",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": null,
            "deltas": [],
            "feedback_for_architect": "User is done providing info."
        }}
        </output_schema>
        """
        
        formatted_prompt = system_prompt.format(
            active_goal_id=active_goal_id if active_goal_id else "None",
            existing_goals_list="\n".join(existing_goals) if existing_goals else "No existing goals."
        )

        messages = [
            {"role": "system", "content": formatted_prompt},
            {"role": "user", "content": user_input}
        ]

        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        try:
            data = json.loads(response_str)
            return data, response_str
        except json.JSONDecodeError:
            print(f"[Critic Error] Failed to parse JSON: {response_str}")
            return {
                "intent": "PROVIDING_INFO",
                "topic_switch_confidence": 0.0,
                "detected_topic_id": active_goal_id,
                "deltas": [],
                "feedback_for_architect": "System error: Failed to parse extraction."
            }, response_str

class ArchitectAgent:
    # The opening text that should be filtered from history to prevent Gemma from repeating it
    OPENING_TEXT_PREFIX = "Listen kid"
    
    def generate_response(self, history: List[Dict[str, str]], directive: str) -> str:
        """
        Generates a natural language response based on a specific DIRECTIVE.
        """
        system_prompt = f"""
        You are the Architect. Your goal is to guide the user through onboarding.
        
        **YOUR INSTRUCTION (DIRECTIVE):**
        {directive}
        
        **CRITICAL RULES (MUST FOLLOW):**
        1. **OBEY THE DIRECTIVE EXACTLY**: The directive above is your ONLY instruction. Do what it says, nothing more, nothing less.
        2. **ONE GOAL AT A TIME**: Only discuss the goal mentioned in the directive. NEVER mention or transition to other goals unless the directive explicitly says "move on to" a new goal.
        3. **Response Format**: 
           - One brief acknowledgement of user's input (optional, 1 sentence max)
           - The EXACT question from the directive
           - Nothing else. No extra questions. No additional topics.
        4. **Tone**: Professional, supportive, concise.
        
        **ABSOLUTELY FORBIDDEN:**
        - Repeating or paraphrasing previous messages from the conversation
        - Saying "Listen kid, i need you to tell me 4 things" or similar opening messages
        - Moving to a different goal (career, physical, mental, social) unless directive says to
        - Adding questions not in the directive
        - Saying "let's move on" or "finally" unless the directive tells you to transition
        - Asking about skill level unless the directive says to ask for skill level
        - Ignoring any part of the directive
        
        If the directive has multiple parts (e.g., "acknowledge X, then ask Y"), you MUST do ALL parts in your response.
        """
        
        # Filter out the opening message from history to prevent Gemma from repeating it
        # The opening message starts with "Listen kid" and confuses smaller models
        filtered_history = []
        for msg in history:
            content = msg.get("content", "")
            # Skip the opening message (starts with "Listen kid")
            if msg.get("role") == "assistant" and content.startswith(self.OPENING_TEXT_PREFIX):
                continue
            filtered_history.append(msg)
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(filtered_history)
        
        response = llm_client.chat_completion(messages)
        return _strip_thinking_block(response)
