import json
import os
import difflib
import re
from typing import Tuple, List, Dict
from dotenv import load_dotenv
from src.models import CharacterSheet, ConversationState, Pillar, Goal, PendingDebuff
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

    def analyze(self, user_input: str, current_sheet: CharacterSheet, history: List[Dict[str, str]] = [], phase: str = "phase1") -> Tuple[CharacterSheet, str, str, List[Dict[str, str]]]:
        """
        Analyzes the user input to extract data and update the character sheet.
        Returns the updated sheet, feedback for the Architect, raw analysis JSON, and pending debuffs.
        
        Phase behavior:
        - phase1: Only extract goals (no current_quests)
        - phase2: Only extract current_quests (goals already exist)
        - Debuffs are always queued for confirmation, never added directly
        """
        
        last_architect_msg = "None"
        # History[-1] is the current user input (if added before call) or we just look for the last assistant msg
        # In main.py, user input is added to history BEFORE calling analyze.
        # So history[-1] is user, history[-2] is assistant.
        if len(history) >= 2 and history[-2]['role'] == 'assistant':
            last_architect_msg = history[-2]['content']
        
        # Phase-specific instructions
        phase_instructions = ""
        if phase == "phase1":
            phase_instructions = """
        **CURRENT PHASE: PHASE 1 - GOAL IDENTIFICATION**
        - You MUST only extract GOALS in this phase. Do NOT extract current_quests.
        - Focus on identifying high-level goals for each pillar.
        - The user can have multiple goals per pillar, but we need at least 1 goal per pillar.
        - Do NOT include "current_quests" in your output - leave that array empty.
        """
        elif phase == "phase2":
            phase_instructions = """
        **CURRENT PHASE: PHASE 2 - CURRENT QUESTS**
        - You CAN extract new goals if the user mentions them.
        - However, you MUST only extract current_quests (habits/actions) for goals that ALREADY EXISTED before this turn.
        - If a new goal is mentioned in this turn, extract it but DO NOT extract current_quests for that new goal yet.
        - You need to collect AT LEAST 2 current_quests for EACH existing goal (to assess the user's skill level).
        - Focus on what the user is currently doing or wants to do to achieve their EXISTING goals.
        - Ask about specific, measurable actions (e.g., "go to gym 3x per week", "code for 1 hour daily").
        - Example: If user says "I also want to learn piano" (new goal) and "I go to the gym 3x a week" (quest for existing goal), extract both but only add the gym quest to the existing physical goal.
        """
        else:
            phase_instructions = f"""
        **CURRENT PHASE: {phase.upper()}**
        - Follow standard extraction rules.
        """
        
        system_prompt = """
        You are the "Critic" and "Data Extractor" for a character creation process.
        Your job is to analyze the user's message and extract structured data for their Character Sheet.
        You must categorize extracted goals and quests into one of the four pillars: Career, Physical, Mental, Social.

        Current Character Sheet:
        {current_sheet_json}
        
        Last Architect Message: "{last_architect_msg}"
        
        {phase_instructions}
        
        Output JSON format:
        {{
            "goals": [
                {{
                    "name": "string",
                    "pillars": ["CAREER" | "PHYSICAL" | "MENTAL" | "SOCIAL"],
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
            *   Assign each goal to its correct `Pillar(s)` (CAREER, PHYSICAL, MENTAL, SOCIAL). A goal can belong to MULTIPLE pillars (e.g., "Playing Volleyball" can be both PHYSICAL and SOCIAL).
            *   Use `"pillars"` (array) in the JSON output, not `"pillar"` (single). Example: `"pillars": ["PHYSICAL", "SOCIAL"]`
            *   **CRITICAL**: Do NOT infer or create goals for pillars the user has not explicitly talked about in their latest response. If the user only talks about fitness, only extract a `PHYSICAL` goal.
            *   **PHASE 1 ONLY**: Extract goals. Do NOT extract current_quests.
            *   **PHASE 2 ONLY**: You CAN extract new goals if mentioned, but ONLY extract current_quests for goals that existed BEFORE this turn. If a new goal is created in this turn, do NOT add current_quests to it yet.

        2.  **Quest Validation**:
            *   Review each `current_quest`. If a quest is vague (e.g., "be healthier"), generate feedback in `feedback_for_architect` asking for a more specific, measurable action.
            *   Example Feedback: "The quest 'be healthier' is vague. Ask the user to specify a concrete action, like 'eat a salad daily'."

        3.  **Stat Inference**:
            *   Estimate stats (1-10) for the pillars the user discussed.

        4.  **Debuff Analysis**:
            *   **ABSOLUTE RULE**: Only identify debuffs if the user EXPLICITLY states they have a problem, issue, or negative behavior.
            *   **CRITICAL - WHAT IS A DEBUFF**: A debuff is ONLY when the user explicitly says they have a PROBLEM:
              - "I have [problem]" (e.g., "I have anxiety", "I have trouble focusing")
              - "I struggle with [problem]" (e.g., "I struggle with procrastination")
              - "I can't [do something]" (e.g., "I can't focus", "I can't stay motivated")
              - "I'm [negative state]" (e.g., "I'm stressed", "I'm lazy", "I'm overwhelmed")
              - "I [negative action]" (e.g., "I procrastinate", "I avoid things")
            *   **CRITICAL - WHAT IS NOT A DEBUFF**: Do NOT extract debuffs from:
              - Activities or habits: "I put on sad music" → NOT a debuff, it's just an activity
              - Coping mechanisms: "I listen to sad music to calm myself down" → NOT a debuff, it's a coping strategy
              - Coping mechanisms: "I sit there for a bit" → NOT avoidance, it's a coping strategy
              - Coping mechanisms: "I start doing something when overwhelmed" → NOT avoidance, it's a coping mechanism
              - Goals or plans: "I would do X" → NOT procrastination, it's a goal
              - Current habits: "I go to the gym" → NOT a problem, it's a habit
              - Descriptions of what they do: "Sometimes I just put on sad music and sit there" → NOT a debuff, it's describing an activity
              - Descriptions of coping: "Sometimes i just like stop, listen to sad music to calm myself down" → NOT a debuff, it's describing a coping mechanism
            *   **EXAMPLES OF WHAT NOT TO EXTRACT**:
              - User says: "Sometimes i just put on sad music and sit there for a bit"
                → WRONG: "Avoidance" or "Emotional Regulation" (these are NOT debuffs - it's just describing an activity/coping mechanism)
                → CORRECT: No debuff extracted (empty array)
              - User says: "Sometimes i just like stop, listen to sad music to calm myself down"
                → WRONG: "Emotional Regulation" (this is NOT a debuff - it's describing a coping mechanism, not stating a problem)
                → CORRECT: No debuff extracted (empty array)
              - User says: "When i get overwhelmed i just start do something, anything"
                → WRONG: "Avoidance" (this is describing a coping mechanism, not stating a problem)
                → CORRECT: No debuff extracted UNLESS user explicitly says "I have a problem with avoidance" or "I struggle with avoiding stillness"
              - User says: "I would do journaling, exercise, etc."
                → WRONG: "Procrastination" (this is a goal/plan, not procrastination)
                → CORRECT: No debuff extracted
            *   **KEY DISTINCTION**: 
              - If user DESCRIBES what they do (e.g., "I listen to music to calm down") → NOT a debuff
              - If user STATES they have a problem (e.g., "I have trouble calming down" or "I can't calm down") → MAYBE a debuff (if they explicitly say it's a problem)
            *   **ONLY extract if the user explicitly states a problem**: 
              - "I procrastinate" → CORRECT: Extract "Procrastination"
              - "I'm anxious" → CORRECT: Extract "Anxiety"
              - "I can't focus" → CORRECT: Extract "Lack of Focus"
              - "I struggle with motivation" → CORRECT: Extract "Lack of Motivation"
              - "I have trouble calming down" → CORRECT: Extract "Difficulty Calming Down" (if they explicitly say it's a problem)
            *   **Provide the exact user quote as `evidence`**. If you cannot find an explicit quote where the user states they have a problem, do NOT add it.
            *   **IMPORTANT**: Debuffs are queued for user confirmation - they are NOT automatically added to the character sheet.
            *   **WHEN IN DOUBT**: If you're not 100% certain the user explicitly stated a problem (not just described an activity or coping mechanism), do NOT extract a debuff. Leave `debuffs_analysis` as an empty array `[]`.
        """
        
        messages = [
            {"role": "system", "content": system_prompt.format(
                current_sheet_json=current_sheet.model_dump_json(), 
                last_architect_msg=last_architect_msg,
                phase_instructions=phase_instructions
            )},
            {"role": "user", "content": user_input}
        ]
        
        # Store pending debuffs to return
        pending_debuffs = []
        
        # Call LLM in JSON mode
        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        # Log the Critic's analysis (it's JSON, but we can still log it)
        print(f"[Critic Analysis]\n{response_str}\n")
        
        try:
            data = json.loads(response_str)

            # Process goals and quests based on phase
            if "goals" in data:
                if phase == "phase1":
                    # PHASE 1: Extract all goals, but handle them based on whether pillar has been asked about
                    # Goals can have multiple pillars
                    for goal_data in data["goals"]:
                        # Support both "pillar" (single) and "pillars" (multiple) for backward compatibility
                        pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
                        if not pillars_data:
                            continue
                        
                        # Convert to Pillar enums
                        pillar_enums = []
                        for p in pillars_data:
                            try:
                                pillar_enums.append(Pillar(p.upper()))
                            except ValueError:
                                continue
                        
                        if not pillar_enums:
                            continue
                        
                        # Check if this goal already exists (by name)
                        goal_name = goal_data.get("name", "")
                        existing_goal = next((g for g in current_sheet.goals if g.name == goal_name), None)
                        
                        if not existing_goal:
                            # Add new goal to the list
                            new_goal = Goal(
                                name=goal_name,
                                pillars=pillar_enums,
                                description=goal_data.get("description"),
                                current_quests=[]  # No quests in phase 1
                            )
                            current_sheet.goals.append(new_goal)
                        else:
                            # Goal exists, update pillars and description if provided
                            # Merge new pillars with existing ones
                            existing_goal.pillars = list(set(existing_goal.pillars + pillar_enums))
                            if goal_data.get("description"):
                                existing_goal.description = goal_data.get("description")
                
                elif phase == "phase2":
                    # PHASE 2: Can extract new goals, but only extract current_quests for goals that existed BEFORE this turn
                    # Store goal names that existed before processing this turn
                    existing_goal_names_before = {g.name for g in current_sheet.goals}
                    
                    # First, process new goals (if any)
                    for goal_data in data["goals"]:
                        # Support both "pillar" (single) and "pillars" (multiple) for backward compatibility
                        pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
                        if not pillars_data:
                            continue
                        
                        # Convert to Pillar enums
                        pillar_enums = []
                        for p in pillars_data:
                            try:
                                pillar_enums.append(Pillar(p.upper()))
                            except ValueError:
                                continue
                        
                        if not pillar_enums:
                            continue
                        
                        goal_name = goal_data.get("name", "")
                        # If this is a new goal, create it (but don't add quests to it yet)
                        if goal_name not in existing_goal_names_before:
                            new_goal = Goal(
                                name=goal_name,
                                pillars=pillar_enums,
                                description=goal_data.get("description"),
                                current_quests=[]  # No quests for newly created goals in this turn
                            )
                            current_sheet.goals.append(new_goal)
                    
                    # Then, only add current_quests to goals that existed BEFORE this turn
                    for goal_data in data["goals"]:
                        goal_name = goal_data.get("name", "")
                        # Only add quests to goals that existed before this turn
                        if goal_name in existing_goal_names_before:
                            goal_obj = next((g for g in current_sheet.goals if g.name == goal_name), None)
                            if goal_obj and "current_quests" in goal_data:
                                for quest in goal_data["current_quests"]:
                                    if quest and quest not in goal_obj.current_quests:
                                        goal_obj.current_quests.append(quest)
            
            # Update stats
            if "stats_career" in data:
                current_sheet.stats_career.update(data["stats_career"])
            if "stats_physical" in data:
                current_sheet.stats_physical.update(data["stats_physical"])
            if "stats_mental" in data:
                current_sheet.stats_mental.update(data["stats_mental"])
            if "stats_social" in data:
                current_sheet.stats_social.update(data["stats_social"])
                
            # Process debuffs - queue them for confirmation instead of adding directly
            if "debuffs_analysis" in data:
                for item in data["debuffs_analysis"]:
                    name = item.get("name")
                    evidence = item.get("evidence", "")
                    confidence = item.get("confidence", "medium")
                    if name and name not in current_sheet.debuffs:
                        # Queue for confirmation instead of adding directly
                        pending_debuffs.append({
                            "name": name,
                            "evidence": evidence,
                            "confidence": confidence
                        })
            
            feedback = data.get("feedback_for_architect", "")
                
            return current_sheet, feedback, response_str, pending_debuffs
            
        except (json.JSONDecodeError, KeyError) as e:
            return current_sheet, f"[System Error: Failed to parse Critic output. Error: {e}]", "", []

class ArchitectAgent:
    def generate_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", ask_for_prioritization: bool = False, phase: str = "phase1", pending_debuffs: List[Dict[str, str]] = None, current_pillar: str = None, queued_goals: List[Dict[str, str]] = None) -> Tuple[str, str]:
        """
        Generates the Architect's response based on conversation history and Critic feedback.
        Returns the visible response and the thinking block for debugging.
        """
        if pending_debuffs is None:
            pending_debuffs = []
        if queued_goals is None:
            queued_goals = []
        
        # Calculate progress based on phase
        # Count pillars that have at least 1 goal (accounting for multi-pillar goals)
        all_pillars_in_goals = set()
        for goal in current_sheet.goals:
            all_pillars_in_goals.update(goal.pillars)
        pillars_with_goals = list(all_pillars_in_goals)
        defined_pillars = len(pillars_with_goals)
        total_pillars = len(Pillar)
        
        if phase == "phase1":
            # Phase 1: Progress based on goals identified (need at least 1 goal per pillar)
            progress_pct = min(int((defined_pillars / total_pillars) * 100), 75)
        elif phase == "phase2":
            # Phase 2: Progress based on goals + quests
            total_goals = len(current_sheet.goals)
            total_quests = sum(len(g.current_quests) for g in current_sheet.goals)
            # We want at least 2 quests per goal (to assess skill level)
            target_quests = max(total_goals, 1) * 2
            quest_progress = min(total_quests / target_quests * 25, 25) if target_quests > 0 else 0
            progress_pct = 75 + int(quest_progress)
        elif phase == "phase3" or phase == "phase3.5":
            # Phase 3/3.5: Debuff confirmation and prioritization
            progress_pct = 85
        elif phase == "phase4":
            # Phase 4: Skill tree generation
            progress_pct = 95
        else:
            progress_pct = 100

        # Determine which pillars are still missing goals (need at least 1 goal per pillar)
        missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals]
        
        # Phase-specific instructions
        phase_instruction = ""
        if phase == "phase1":
            # Helper function to check if pillar has pure goal
            def has_pure_goal_for_pillar(goals, pillar):
                return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
            
            # Check which pillars need pure goals
            pillars_needing_pure_goals = []
            for p in Pillar:
                if p in all_pillars_in_goals and not has_pure_goal_for_pillar(current_sheet.goals, p):
                    pillars_needing_pure_goals.append(p.value)
            
            # Format queued goals for current pillar
            queued_goals_text = ""
            if queued_goals and len(queued_goals) > 0:
                queued_list = "\n".join([f"- {g['name']} ({', '.join(g['pillars'])})" for g in queued_goals])
                queued_goals_text = f"\n- **Queued Goals for Current Pillar**: The user mentioned these goals earlier for {current_pillar if current_pillar else 'this pillar'}. Present them first:\n{queued_list}\n"
            
            current_pillar_text = f"\n- **Current Pillar Being Asked About**: {current_pillar if current_pillar else 'None (all pillars have goals)'}" if current_pillar else ""
            
            pure_goal_requirement = ""
            if current_pillar and current_pillar in pillars_needing_pure_goals:
                pure_goal_requirement = f"\n- **CRITICAL - PURE GOAL REQUIRED**: The {current_pillar} pillar currently has goals, but NONE of them are pure goals (goals that belong only to {current_pillar}). You MUST ask the user for at least one pure goal for {current_pillar} before moving to the next pillar. Ask: 'I see you have goals for {current_pillar}, but I need at least one goal that's specifically just for {current_pillar}. What's a goal you have that's only about {current_pillar}?'"
            
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 1 - GOAL IDENTIFICATION ONLY**
        
        **🚫 ABSOLUTE PROHIBITION - DO NOT ASK ABOUT PRIORITIZATION 🚫**
        - **NEVER** ask about prioritization, ranking, importance, or which goal is most important in Phase 1.
        - **NEVER** ask questions like: "Do you want to prioritize any of these goals?", "Which goal is most important?", "What's your biggest priority?", or "Should we rank these?"
        - Prioritization happens in Phase 3.5, NOT Phase 1. You are currently in Phase 1.
        - If all 4 pillars have goals, simply confirm them and wait. Do NOT ask about prioritization.
        
        - Your ONLY job is to help the user identify WHAT they want to achieve (their goals) for each of the four pillars: {', '.join([p.value for p in Pillar])}.
        - **CRITICAL**: Before determining what's missing, CHECK the "Current Sheet State" above to see which goals have ALREADY been extracted.
        - The "Missing Pillars" field shows which pillars still need goals - use this, NOT just the conversation history.
        - Do NOT ask about goals that are already in the Current Sheet State.
        - **ONE PILLAR PER RESPONSE**: Focus on ONLY ONE missing pillar per response. Do not ask about multiple pillars in the same message.
        - **GO THROUGH PILLARS ONE BY ONE**: Work through missing pillars systematically. Once you've asked about a pillar, move to the next missing pillar. Do not revisit a pillar you've already asked about in this phase unless the user said something contradictory.
        - **PURE GOAL REQUIREMENT**: You must ensure each pillar has at least one pure goal (a goal that belongs to only that pillar) before moving to the next pillar. If a pillar only has multi-pillar goals, ask for a pure goal.
        {pure_goal_requirement}
        {current_pillar_text}
        {queued_goals_text}
        - **GOAL CONFIRMATION**: If the user mentions goals for a pillar you've already asked about, ask them to confirm: "I see you mentioned [goal] for [pillar]. Is that correct? Should I add that as another goal for [pillar]?"
        - **ABSOLUTE RULE - PHASE 1 ONLY**: Do NOT ask about:
          * Current habits, actions, routines, or what they're doing now (that's Phase 2)
          * How they'll achieve their goals
          * Implementation details, steps, methods, or processes
          * Skills they need to learn
          * Tools or resources they need
          * Costs, budgets, or financial details
          * Specific routines or schedules
          * **PRIORITIZATION, RANKING, OR IMPORTANCE** (that's Phase 3.5 - ABSOLUTELY FORBIDDEN in Phase 1)
        - **ONLY ASK ABOUT**: What they WANT to achieve (the goal itself), not how to get there.
        - Missing pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
        - **CRITICAL**: Even if you see goals for all four pillars in the Current Sheet State, you are STILL in Phase 1. Do NOT ask about prioritization. The system will automatically move to Phase 2 when all goals are confirmed.
        - If there are missing pillars, guide the user to define a goal for one of them.
        - If there are NO missing pillars (all 4 pillars have goals), acknowledge this but DO NOT ask about prioritization. Simply confirm the goals and wait for the system to transition to Phase 2.
        - **ABSOLUTE RULE - WHEN ASKING ABOUT MISSING PILLARS**: When asking about a missing pillar (e.g., Mental), ONLY ask about their GOALS for that pillar. Do NOT assume they have problems, anxiety, stress, or issues. 
          * Ask: "What's your goal for your mental wellbeing?" 
          * NOT "How are you managing anxiety?" (unless they explicitly mentioned anxiety)
          * NOT "What's your goal for managing anxiety?" (unless they explicitly mentioned anxiety)
          * NOT "What do you want to do about your anxiety?" (unless they explicitly mentioned anxiety)
        - **ABSOLUTE RULE - IN YOUR THINKING**: When you see a missing pillar, ONLY think "Missing: [Pillar name]" and plan to ask about goals. Do NOT think "Missing: [Pillar] - specifically how they manage [problem]" unless the user explicitly mentioned that problem.
        - Examples of GOOD Phase 1 questions:
          * "What's a major goal you have for your career?"
          * "What do you want to achieve with your physical health?"
          * "What's your goal for your mental wellbeing?"
          * "What do you want in your social life?"
        - Examples of BAD Phase 1 questions (these belong in Phase 2 or Phase 3.5):
          * "What's your current exercise routine?" (asks about current actions - Phase 2)
          * "How often do you go to the gym?" (asks about current habits - Phase 2)
          * "What skills do you need to learn?" (asks about implementation - Phase 2)
          * "How much would that cost?" (asks about implementation details - Phase 2)
          * "Which goal is most important?" (asks about prioritization - Phase 3.5)
          * "What's your biggest priority?" (asks about prioritization - Phase 3.5)
        """
        elif phase == "phase2":
            # Get goals for current pillar with incomplete quests
            current_pillar_enum = None
            if current_pillar:
                try:
                    current_pillar_enum = Pillar(current_pillar.upper())
                except ValueError:
                    pass
            
            goals_for_current_pillar = []
            if current_pillar_enum:
                goals_for_current_pillar = [
                    g for g in current_sheet.goals 
                    if current_pillar_enum in g.pillars and len(g.current_quests) < 2
                ]
            
            goals_list_text = ""
            if goals_for_current_pillar:
                goals_list = "\n".join([
                    f"  - {g.name} ({len(g.current_quests)}/2 quests): {', '.join(g.current_quests) if g.current_quests else 'No quests yet'}"
                    for g in goals_for_current_pillar
                ])
                goals_list_text = f"\n- **Goals in {current_pillar if current_pillar else 'current pillar'} needing quests**:\n{goals_list}\n"
            
            current_pillar_text = f"\n- **Current Pillar Being Asked About**: {current_pillar if current_pillar else 'None (all goals complete)'}" if current_pillar else ""
            
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 2 - CURRENT QUESTS**
        - All four pillars now have goals. Your job is to ask about current habits and actions.
        - **🚫 ABSOLUTE PROHIBITION - DO NOT END THE CONVERSATION 🚫**
          * **NEVER** provide a closing message, summary, or "welcome to the journey" message in Phase 2.
          * **NEVER** say things like "Well, there you have it", "You've got a roadmap", "Welcome to the journey", or "Take a deep breath, kid. You've got this."
          * **NEVER** end with a statement - you MUST always end with a question asking about current_quests.
          * Phase 2 is about collecting current_quests - you are NOT done until ALL goals have at least 2 current_quests.
        - **🚫 ABSOLUTE PROHIBITION - DO NOT GIVE ADVICE OR SUGGEST SOLUTIONS IN PHASE 2 🚫**
          * **NEVER** suggest solutions, give advice, or tell the user what they should do in Phase 2.
          * **NEVER** say things like "Here's something you could try", "You could try X", "I suggest you do Y", or "Would you be open to trying Z?"
          * Phase 2 is ONLY about DATA COLLECTION - asking what they're CURRENTLY doing, not what they SHOULD do.
          * If the user mentions a problem or challenge, just ask them what they're currently doing about it - DO NOT suggest solutions.
          * Example (WRONG): "Here's something you could try: a short guided meditation" → FORBIDDEN in Phase 2
          * Example (CORRECT): "What are you currently doing to manage stress? Are you doing anything specific right now?"
        - **CRITICAL - ALWAYS ASK A QUESTION**: You MUST end every response with at least one question asking about current_quests. Do NOT summarize, recap, or end the conversation. You are in Phase 2, which means you need to collect current_quests for each goal.
        - **PILLAR CYCLING**: Cycle through all four pillars systematically (CAREER → PHYSICAL → MENTAL → SOCIAL).
        - **ONLY ASK ABOUT INCOMPLETE GOALS**: Only ask about goals in pillars that have incomplete goals (goals with < 2 current_quests).
        - After completing a pillar (all goals have 2+ quests), move to the next pillar with incomplete goals.
        {current_pillar_text}
        {goals_list_text}
        - **GOAL-BY-GOAL QUESTIONING - ONE GOAL AT A TIME**: For each goal in the current pillar, ask about its current_quests ONE AT A TIME:
          * **🚫 CRITICAL PROHIBITION**: Do NOT ask about multiple goals at once. Do NOT list multiple activities or goals in a single question.
          * **🚫 FORBIDDEN QUESTIONS**: 
            - "For each of these activities – exercise, journaling, vocal practice... what's the current situation?" → FORBIDDEN
            - "What's the current situation for each of these goals?" → FORBIDDEN
            - "For exercise, journaling, vocal practice... what are you doing?" → FORBIDDEN
          * **CORRECT APPROACH**: Ask about ONE goal at a time, focusing on the first incomplete goal in the current pillar.
          * If a goal has 0 quests, ask: "For your [goal name], what are you currently doing? What have you been working on?"
          * If a goal has 1 quest, ask: "You mentioned [quest]. What else are you doing for [goal name]?"
          * After a goal has 2+ quests, move to the next goal in that pillar.
          * **EXAMPLE (CORRECT)**: "For your exercise goal, what are you currently doing? What have you been working on?" → CORRECT
        - **STARTING PHASE 2**: When Phase 2 just started, immediately ask about the FIRST goal in the FIRST pillar with incomplete goals. Do NOT summarize Phase 1 or give a closing message. Ask about ONE goal only: "For your [goal name], what are you currently doing to work toward that?"
        - You need to collect AT LEAST 2 current_quests for EACH goal (to assess the user's skill level).
        - Ask about WHAT the user is CURRENTLY doing or HAS DONE to achieve their goals - NOT what they need to learn or will do in the future.
        - Focus on specific, measurable actions they're already taking (e.g., "I go to gym 3x per week", "I code for 1 hour daily", "I practice SQL queries").
        - Do NOT ask about future skills, tools, or technologies they need to learn - that will be handled later by the system (Planners will generate needed_quests).
        - **USE CRITIC FEEDBACK**: The Critic provides feedback to help you ask more specific questions. Use this feedback to ask more detailed, targeted questions.
          * Example: If Critic says "Consider asking them to specify what 'more organized' looks like in practice – for example, 'tracking tasks' or 'creating a schedule'", ask: "You mentioned wanting to be more organized. What specifically does that look like for you? Are you thinking about tracking tasks, creating a schedule, or something else?"
          * Incorporate the Critic's suggestions naturally into your questions to get more specific, actionable information.
        - Example: If user says "I want to become a data analyst", ask "What are you currently doing to work toward that? Are you taking any courses, practicing with data, or working on projects?" NOT "What skills do you need to learn?"
        """
        elif phase == "phase3":
            debuff_list = "\n".join([
                f"- {d['name']} (evidence: '{d.get('evidence', 'N/A')}', confidence: {d.get('confidence', 'medium')})"
                for d in pending_debuffs
            ])
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 3 - DEBUFF CONFIRMATION**
        - You have {len(pending_debuffs)} pending debuff(s) that need user confirmation.
        - Present each debuff ONE AT A TIME and ask the user to confirm if it applies to them.
        - Pending debuffs:
        {debuff_list}
        - Example: "I noticed you mentioned '{pending_debuffs[0].get('evidence', 'N/A') if pending_debuffs else 'N/A'}'. Would you say you're dealing with {pending_debuffs[0].get('name', 'this issue') if pending_debuffs else 'this issue'}?"
        - Wait for the user to confirm or reject before moving to the next debuff.
        - Once all debuffs are confirmed or rejected, move to goal prioritization.
        """
        elif phase == "phase3.5":
            # List all goals for the Architect to present
            goal_list = []
            for goal in current_sheet.goals:
                pillars_str = ", ".join([p.value for p in goal.pillars])
                goal_list.append(f"- {goal.name} ({pillars_str})")
            goals_text = "\n".join(goal_list) if goal_list else "your goals"
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 3.5 - GOAL PRIORITIZATION**
        - All goals and quests are complete. Your ONLY job is to ask the user to rank their goals.
        - Present all goals clearly and ask them to rank from most to least important.
        - Goals to rank:
        {goals_text}
        - Do NOT ask why they prioritized one over another - just ask for the ranking.
        - Once they provide the ranking (e.g., "Career then Physical then Mental then Social"), acknowledge it briefly and the system will proceed automatically.
        - **CRITICAL**: After the user provides a ranking, do NOT ask more questions. Simply acknowledge the ranking and let the system transition.
        """
        elif phase == "phase4":
            phase_instruction = """
        **CURRENT PHASE: PHASE 4 - SKILL TREE GENERATION**
        - The user has completed prioritization. The system is now generating their skill tree.
        - **🚫 ABSOLUTE PROHIBITION - DO NOT ASK QUESTIONS IN PHASE 4 🚫**
          * **NEVER** ask any questions in Phase 4.
          * **NEVER** ask about goals, quests, or anything else.
          * Simply acknowledge that the skill tree is being generated and the onboarding is complete.
          * Your response should be brief and final - just acknowledge completion.
        - This is the final step - the onboarding is complete.
        - Example response: "Perfect! I've got everything I need. Your skill tree is being generated now."
        """
        
        # Format Critic feedback for display
        critic_feedback_text = ""
        if feedback:
            critic_feedback_text = f"\n        Critic Feedback: {feedback}\n"
        
        system_prompt_with_context = f"""{ARCHITECT_SYSTEM_PROMPT}

        [System Context]
        Current Phase: {phase.upper()}
        Current Profile Completion: {progress_pct}%
        Current Sheet State: {current_sheet.model_dump_json()}
        Missing Pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
        Pending Debuffs: {len(pending_debuffs)} waiting for confirmation{critic_feedback_text}
        
        {phase_instruction}
        
        Instruction: 
        1.  Follow the phase-specific instructions above.
        2.  **🚫 CRITICAL - PHASE 1 PROHIBITION 🚫**: If you are in Phase 1, you MUST ask about missing goals. You MUST NEVER ask about prioritization, ranking, importance, or which goal is most important - that is Phase 3.5. Even if all 4 pillars have goals, you are still in Phase 1 until the system transitions you. DO NOT ask questions like "Do you want to prioritize any of these goals?" or "Which goal is most important?" - these are FORBIDDEN in Phase 1.
        3.  **CRITICAL**: You MUST end every response with at least one question. Never just recap or summarize without asking something. If you recap what the user said, you MUST follow it with a question to keep the conversation moving. BUT make sure your question is about missing goals or goal confirmation, NOT about prioritization.
        3.  You MUST include a progress bar at the end of your response in this format:
           [Progress: ||||||....] {progress_pct}%
           (Use exactly 20 characters for the bar.)
        4.  If the Critic provides feedback on a vague quest, you must relay that to the user and ask for clarification.
        5.  **CRITICAL - Check Current Sheet State First**: 
            - **BEFORE** determining what's missing, ALWAYS check the "Current Sheet State" in the System Context above.
            - The Current Sheet State shows ALL goals that have been extracted so far - use this as the source of truth.
            - The "Missing Pillars" field is calculated from the Current Sheet State - trust this field.
            - Do NOT ask about goals that are already in the Current Sheet State, even if you don't see them in the recent conversation.
            - Only use conversation history to understand the user's latest response, not to determine what goals exist.
        6.  **CRITICAL - ABSOLUTE NO INFERENCE RULE**: 
            - **ONLY reference things the user has EXPLICITLY stated in the conversation history provided to you.**
            - **ABSOLUTE RULE - NO INFERENCE**: Do NOT infer, assume, or mention ANYTHING the user hasn't directly said.
            - **EXAMPLES OF WHAT NOT TO DO**:
              * User says "data analysis" → DO NOT mention "anxiety" or "how they manage anxiety" (they never said it)
              * User says "vocal practice" → DO NOT mention "social anxiety" or "anxiety when talking to people" (they never said it)
              * User says "journaling" → DO NOT mention "stress management" or "anxiety" (they never said it)
              * User says "volleyball is just fun and cardio" → DO NOT mention "anxiety" or "how they manage anxiety" (they never said it)
              * User says "volleyball is just fun and cardio" → DO NOT think "Missing: Mental pillar - specifically how they manage anxiety" (they never mentioned anxiety)
              * User says "I would do X, Y, Z" → DO NOT infer they have problems, anxiety, or issues (they're just describing activities)
            - **ABSOLUTE RULE**: Do NOT use information from few-shot examples - those are just examples of how to ask questions, NOT facts about this user. If an example mentions "teacher" or "anxiety", that does NOT mean this user is a teacher or has anxiety.
            - **ABSOLUTE RULE**: Do NOT mention jobs, careers, hobbies, or activities unless the user explicitly mentioned them.
            - **ABSOLUTE RULE**: If the user mentions specific activities (like journaling, exercise, vocal practice, volleyball, coding, family), ONLY ask about those. Do NOT assume they have a job, are a teacher, have anxiety, or do anything else they haven't mentioned.
            - **ABSOLUTE RULE**: If the user says "I would do X, Y, Z" - they are describing activities/goals, NOT their current job or problems. Do NOT assume they have a job, anxiety, or any issues unless they explicitly say "I work as...", "I am a...", "I have anxiety", "I'm anxious", etc.
            - **ABSOLUTE RULE**: Do NOT mention anxiety, stress, mental health issues, or any problems unless the user EXPLICITLY mentions them using words like "I have anxiety", "I'm anxious", "I'm stressed", "I struggle with X", etc.
            - **ABSOLUTE RULE**: In your thinking block, ONLY state what the user explicitly said. Do NOT add inferences like "they mentioned anxiety" or "specifically related to their anxiety" if they didn't say it.
            - **ABSOLUTE RULE**: When a pillar is missing, ONLY think "Missing: [Pillar name]" and plan to ask about goals. Do NOT think "Missing: [Pillar] - specifically how they manage [problem]" or "specifically related to [problem]" unless the user explicitly mentioned that problem.
            - **ABSOLUTE RULE**: Track each user response separately. If they talk about productivity in one message and social connections in another, don't mix them up. Keep responses about different topics separate.
        7.  **Focus on Goals, Not Implementation Details** (Phase 1) / **Focus on Current Actions** (Phase 2):
            - **Phase 1 - GOALS ONLY**: 
              * Ask ONLY about WHAT the user wants to achieve (their goals), not HOW to achieve it.
              * Do NOT ask about current habits, routines, actions, or what they're doing now.
              * Do NOT ask about implementation details, steps, methods, costs, budgets, skills to learn, or tools needed.
              * Example (GOOD): "What's a major goal you have for your career?" 
              * Example (BAD): "What's your current exercise routine?" or "How often do you go to the gym?" (these are Phase 2 questions)
            - **Phase 2 - CURRENT ACTIONS ONLY**: 
              * Ask about WHAT the user is CURRENTLY doing or HAS DONE, NOT what they need to learn or will do in the future.
              * Focus on specific, measurable actions they're already taking.
              * Do NOT ask about future skills or technologies to learn - the system will generate needed_quests later.
              * Example (GOOD): "What are you currently doing to work toward that goal? Are you taking any courses, practicing, or working on projects?"
              * Example (BAD): "What skills do you need to learn?" (this is not Phase 2 - system handles this later)
        8.  **Suggest Solutions, Don't Ask for Them** (Phase 1 and Phase 3 only - NOT Phase 2):
            - **CRITICAL**: This rule does NOT apply in Phase 2. Phase 2 is ONLY about data collection - asking what they're currently doing, not suggesting solutions.
            - **Phase 2**: If the user mentions a problem, just ask "What are you currently doing about that?" - DO NOT suggest solutions.
            - **Phase 1 and Phase 3**: When the user mentions a problem or challenge, SUGGEST a solution rather than asking them what they should do.
            - Instead of "What's one thing you could do *right now*?" say "Here's something you could try: [specific suggestion]."
            - Instead of "How do you think you'll handle that?" say "When you face [challenge], try [suggestion]."
            - Example: If they say "I need more discipline," suggest "Try setting a specific time each day for [activity]. That builds structure."
        9.  **Smooth Transitions**:
            - When moving between topics, reference what the user just said.
            - Use simple, direct language. Avoid idioms like "spinning your wheels."
            - Example: "You mentioned [X]. Now let's talk about [Y]."
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
            # This is for the final turn after prioritization is done (phase3.5 or later).
            # Only provide final summary if we're in phase3.5 or later AND all pillars have goals
            if phase in ["phase3.5", "phase4", "phase5"] and not missing_pillars:
                 system_prompt_with_context += """
                
                [FINAL TURN INSTRUCTION]
                All pillars have goals and they have been prioritized. Do NOT ask any more questions.
                Provide a grand, encouraging summary of the user's profile.
                Welcome them to their journey.
                """

        messages = [{"role": "system", "content": system_prompt_with_context}]
        
        # Add few-shot examples with a warning
        # IMPORTANT: These are ONLY examples of how to ask questions. They are NOT facts about the current user.
        messages.append({"role": "system", "content": "[IMPORTANT] The following examples are ONLY demonstrations of question style. Do NOT use any information from them (like jobs, activities, or problems) unless the user explicitly mentions those same things."})
        messages.extend(FEW_SHOT_EXAMPLES)
        
        # Add history
        messages.extend(history)
        
        # Inject feedback if present
        if feedback:
            messages.append({"role": "system", "content": f"[Critic's Feedback]: {feedback}"})

        response = llm_client.chat_completion(messages)
        
        # Extract and log thinking block before stripping
        thinking_content = ""
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL | re.IGNORECASE)
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            print(f"[Architect Thinking]\n{thinking_content}\n")
        
        # Hide internal thinking traces from the user-facing chat
        visible_response = _strip_thinking_block(response)
        return visible_response, thinking_content
