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
    def analyze(self, user_input: str, active_goal_id: Optional[str], existing_goals: List[str], current_phase: Optional[str] = None) -> Tuple[Dict, str]:
        """
        Analyzes the user input to produce atomic state updates (deltas).
        
        Args:
            user_input: The user's latest message.
            active_goal_id: The ID of the goal currently being discussed.
            existing_goals: List of strings in format "ID: <id> | Name: <name>"
            current_phase: Current phase (phase1, phase2, phase3.5, phase4)
        
        Returns:
            A tuple of (parsed_json_response, raw_response_string)
        """
        
        system_prompt = """
        <role_definition>
        You are the Critic (Data Extractor). Your job is to listen to the user and output ATOMIC UPDATES (deltas) for their character sheet.
        You do NOT generate conversation. You ONLY generate JSON data.
        </role_definition>

        <phase_detection>
        🎯 **CURRENT PHASE: {current_phase}**
        📋 **ACTIVE GOAL ID: {active_goal_id}**

        **PHASE 3.5 SPECIAL RULE** 🏆
        If current_phase is "phase3.5", user is providing GOAL RANKINGS/PRIORITIES, NOT new goals!
        
        🚨 **CRITICAL: IGNORE PILLAR RANKING INPUTS** 🚨
        Phase 3.5 inputs like these should be IGNORED (return empty deltas):
        - "Career then social then physical then connection"
        - "Physical, mental, career, social"  
        - "1. Career, 2. Physical, 3. Mental, 4. Social"
        - Any text listing pillar names in order
        
        For Phase 3.5 ranking inputs:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": null,
            "deltas": [],
            "feedback_for_architect": "User provided goal ranking. No character sheet updates needed."
        }}
        </phase_detection>

        <phase1_critical_rule>
        ⚠️ PHASE 1 DETECTION: Active Goal ID = `{active_goal_id}`
        
        **IF Active Goal ID is "None" → YOU ARE IN PHASE 1.**
        
        In Phase 1, the user is listing their LIFE GOALS (aspirations/dreams/ambitions).
        EVERY item they mention MUST use operation: "add_goal".
        
        🚨 **CRITICAL: NO SPLITTING IN PHASE 1** 🚨
        - Keep compound goal statements as ONE goal: "Be more outgoing and talk to more people" → ONE add_goal
        - Do NOT split goals connected by "and" in Phase 1
        - Only split activities in Phase 2 (when Active Goal ID exists)
        
        DO NOT USE "add_quest" OR "update_skill" IN PHASE 1.
        
        ❌ WRONG (Phase 1): {{"operation": "add_quest", "payload": "Have more endurance"}}
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Have more endurance"}}
        
        ❌ WRONG (Phase 1): {{"operation": "update_skill", "payload": "Be more social"}}
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Be more social"}}
        
        ❌ WRONG (Phase 1): Two deltas for "Be outgoing and talk to people"
        ✅ CORRECT (Phase 1): {{"operation": "add_goal", "payload": "Be more outgoing and talk to people"}}
        
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
           - **Numeric-only input (e.g., "1", "7", "10")**: ALWAYS treat as `update_skill` with that number as the payload.
           - **Action/Activity Description**: Any mention of concrete actions, steps, routines, or behaviors = `add_quest`. Examples:
             * "I run 5k" → add_quest
             * "I watch YouTube videos" → add_quest
             * "Whenever i go outside i try to talk to more people" → add_quest: "Talk to more people when going outside"
             * "I've been practicing stretches" → add_quest: "Practice stretches"
             * "I joined a gym" → add_quest: "Attend gym"
           - **COMPOUND ACTIVITIES (Multiple actions in one sentence - PHASE 2 ONLY)**: Split into separate add_quest operations:
             * "I watch videos and read books" → TWO deltas: add_quest: "Watch videos", add_quest: "Read books"
             * "I study online and practice coding" → TWO deltas: add_quest: "Study online", add_quest: "Practice coding"
             * "I go to gym and do cardio" → TWO deltas: add_quest: "Go to gym", add_quest: "Do cardio"
             * "I'm watching instructional videos and reading up about certifications" → TWO deltas: add_quest: "Watch instructional videos", add_quest: "Read about certifications"
           - **Restatement of Goal (NOT an action)**: If user just rephrases the goal without describing what they're doing → add_quest anyway (it's still info about their goal)
           - **Rating/Skill Level**: "I'm a 7 out of 10", "I'm a beginner", "I'd say moderate" → `update_skill` (extract numeric value or map text to 1-10)
        4. **Stop Signal**:
           - "That's it", "Nothing else", "No" → `intent: "STOP_SIGNAL"`
           - "I'm not doing anything", "Haven't started yet", "Nothing" → `intent: "STOP_SIGNAL"`
           - Only use STOP_SIGNAL when user explicitly says they're NOT doing anything or they're finished
        5. **Topic Switching**: If the user talks about a different goal, find its ID in the list below.
        6. **CRITICAL: VALIDATION RULE - Reject Unrelated Input**:
           - When Active Goal ID is NOT "None", STRICTLY validate that user response is RELEVANT to that goal.
           - If user response is about leisure, food, entertainment, or other UNRELATED topics, REJECT it.
           - Return: `intent: "STOP_SIGNAL"`, empty `deltas: []`, and `feedback: "Input not related to active goal. Architect should ask again."`
           - Examples of REJECTION:
             * Goal: "Become a software engineer" (CAREER) | User: "I like pizza and watch movies" → REJECT ✗
             * Goal: "Run a marathon" (PHYSICAL) | User: "I enjoy eating ice cream" → REJECT ✗
             * Goal: "Be more social" (SOCIAL) | User: "I like watching TV shows" → REJECT ✗
           - Only extract quest if user response describes CONCRETE ACTIONS toward the active goal.
        7. **CRITICAL**: When Active Goal ID exists, assume ALL substantive input is about that goal (add_quest) UNLESS it's clearly a rating/skill level.
        </context_rules>

        <existing_goals_list>
        {existing_goals}
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
        
        User says: "Whenever I go outside I try to talk to more people" (Active Goal ID: "xyz789-...", goal is "Connection wise i want to be more outgoing")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "xyz789-...",
            "deltas": [
                {{"operation": "add_quest", "target_id": "xyz789-...", "payload": "Talk to more people when going outside"}}
            ],
            "feedback_for_architect": "User described a concrete action they're taking."
        }}
        
        User says: "I watch instructional videos and read about certifications online" (Active Goal ID: "aecc27e1-...")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "aecc27e1-...",
            "deltas": [
                {{"operation": "add_quest", "target_id": "aecc27e1-...", "payload": "Watch instructional videos"}},
                {{"operation": "add_quest", "target_id": "aecc27e1-...", "payload": "Read about certifications online"}}
            ],
            "feedback_for_architect": "User described multiple activities for the active goal."
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
        
        User says: "1" (Active Goal ID: "aecc27e1-...")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "aecc27e1-...",
            "deltas": [
                {{"operation": "update_skill", "target_id": "aecc27e1-...", "payload": 1}}
            ],
            "feedback_for_architect": "User rated their skill level as 1."
        }}
        
        User says: "7" (Active Goal ID: "aecc27e1-...")
        Output:
        {{
            "intent": "PROVIDING_INFO",
            "topic_switch_confidence": 0.0,
            "detected_topic_id": "aecc27e1-...",
            "deltas": [
                {{"operation": "update_skill", "target_id": "aecc27e1-...", "payload": 7}}
            ],
            "feedback_for_architect": "User rated their skill level as 7."
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
            current_phase=current_phase if current_phase else "phase1",
            active_goal_id=active_goal_id if active_goal_id else "None",
            existing_goals="\n".join(existing_goals) if existing_goals else "No existing goals."
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
        # Extract key constraint from directive if it's a skill level question
        is_skill_level_request = "scale of 1-10" in directive or "rate their" in directive.lower() or "rate your" in directive.lower()
        
        system_prompt = f"""
        You are the Architect. Your ONLY job is to follow the DIRECTIVE below exactly.
        
        ════════════════════════════════════════════════════════════════════════════════
        🔴 **ABSOLUTE DIRECTIVE (MUST FOLLOW - DO NOT DEVIATE)**
        ════════════════════════════════════════════════════════════════════════════════
        
        {directive}
        
        ════════════════════════════════════════════════════════════════════════════════
        
        **THIS IS YOUR COMPLETE INSTRUCTION.** Do EXACTLY what the directive says. Nothing more. Nothing less.
        
        **CRITICAL ENFORCEMENT RULES:**
        1. **FOLLOW THE DIRECTIVE WORD FOR WORD**: If directive says "ask about skill level", ask ONLY about skill level. Do NOT mention other goals.
        2. **GOAL LOCK-IN**: {'⚠️ YOU ARE LOCKED TO ASK ONLY ABOUT SKILL LEVEL FOR THE CURRENT GOAL. DO NOT MENTION ANY OTHER GOALS.' if is_skill_level_request else 'Focus on the goal specified in the directive.'}
        3. **NO EXTRA CONTENT**: Do not add preamble, small talk, or anything not in the directive.
        4. **RESPONSE FORMAT**: Follow the structure in the directive exactly.
        
        **IF DIRECTIVE SAYS "CRITICAL"**: 
        - This is a HARD REQUIREMENT
        - Do NOT violate it under any circumstances
        - Do NOT transition to other goals
        - Do NOT mention other topics
        
        **EXAMPLE COMPLIANCE:**
        - ❌ WRONG: Directive says "ask about their career skill level" → You say "Now let's discuss mental health"
        - ✅ RIGHT: Directive says "ask about their career skill level" → You say "On a scale of 1-10, how would you rate your current skill level in this area?"
        
        - ❌ WRONG: Directive says "stay focused on Become a plumber" → You say "Let's move to mental health"  
        - ✅ RIGHT: Directive says "stay focused on Become a plumber" → You ask about Become a plumber only
        
        **YOUR RESPONSE MUST CONTAIN:**
        {f"- A skill level rating question (1-10 scale)" if is_skill_level_request else "- Content specified in the directive"}
        
        **YOUR RESPONSE MUST NOT CONTAIN:**
        {f"- Any mention of other goals (mental, career, physical, social unless it's the current focus)" if is_skill_level_request else ""}
        - Anything not in the directive
        - Questions about different goals
        
        You will now generate your response following ONLY the directive above.
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
        cleaned = _strip_thinking_block(response)
        
        # DEBUG: Log if response violates directive constraints
        if is_skill_level_request:
            violates_goal_constraint = any(other_goal in cleaned.lower() 
                for other_goal in ['mental health', 'mental wellbeing', 'fitness', 'connection', 'social', 'physical', 'career'])
            if violates_goal_constraint and '1-10' not in cleaned and 'scale' not in cleaned.lower():
                print(f"[DEBUG-CONSTRAINT-VIOLATION] Response violates skill level directive!")
                print(f"  Directive: {directive[:100]}...")
                print(f"  Response: {cleaned[:100]}...")

        # Guardrail: strip phantom numeric acknowledgements when user never sent a number
        last_user = next((m.get("content", "") for m in reversed(filtered_history) if m.get("role") == "user"), "")
        if last_user and not re.search(r"\d", last_user):
            cleaned = re.sub(r"^(?:okay|ok|alright)[\s,]*a?\s*\d+\s*[\.:-]?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = cleaned.lstrip(" .,-")

        return cleaned
