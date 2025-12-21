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
            *   **PHASE 1 ONLY**: Extract goals. Do NOT extract current_quests.
            *   **PHASE 2 ONLY**: You CAN extract new goals if mentioned, but ONLY extract current_quests for goals that existed BEFORE this turn. If a new goal is created in this turn, do NOT add current_quests to it yet.

        2.  **Quest Validation**:
            *   Review each `current_quest`. If a quest is vague (e.g., "be healthier"), generate feedback in `feedback_for_architect` asking for a more specific, measurable action.
            *   Example Feedback: "The quest 'be healthier' is vague. Ask the user to specify a concrete action, like 'eat a salad daily'."

        3.  **Stat Inference**:
            *   Estimate stats (1-10) for the pillars the user discussed.

        4.  **Debuff Analysis**:
            *   **CRITICAL**: Only identify debuffs that the user EXPLICITLY mentions. Do NOT infer debuffs from the user's activities or goals.
            *   Examples of explicit mentions: "I procrastinate," "I'm anxious," "I'm stressed," "I can't focus," "I'm lazy."
            *   Do NOT infer debuffs from phrases like "I would do X" or "I want to do Y" - these are goals, not problems.
            *   Do NOT infer procrastination from listing activities - the user is describing what they WANT to do, not what they're avoiding.
            *   If the user says "I would do journaling, exercise, etc." - this is NOT procrastination. It's a goal/plan.
            *   Only add a debuff if the user explicitly states a problem, issue, or negative behavior.
            *   Provide the exact user quote as `evidence`. If you cannot find an explicit quote mentioning the debuff, do NOT add it.
            *   **IMPORTANT**: Debuffs are queued for user confirmation - they are NOT automatically added to the character sheet.
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
                    # PHASE 1: Only extract goals, no current_quests
                    new_pillars_added = 0
                    for goal_data in data["goals"]:
                        pillar = goal_data.get("pillar")
                        if not pillar:
                            continue
                        
                        try:
                            pillar_enum = Pillar(pillar.upper())
                        except ValueError:
                            continue
                        
                        # Limit to one new pillar per turn
                        if pillar_enum not in current_sheet.goals and new_pillars_added >= 1:
                            continue
                        
                        # Create goal if it doesn't exist
                        if pillar_enum not in current_sheet.goals:
                            current_sheet.goals[pillar_enum] = Goal(
                                name=goal_data["name"],
                                pillar=pillar_enum,
                                description=goal_data.get("description"),
                                current_quests=[]  # No quests in phase 1
                            )
                            new_pillars_added += 1
                        else:
                            # Goal exists, update description if provided
                            if goal_data.get("description"):
                                current_sheet.goals[pillar_enum].description = goal_data.get("description")
                
                elif phase == "phase2":
                    # PHASE 2: Can extract new goals, but only extract current_quests for goals that existed BEFORE this turn
                    # Store goals that existed before processing this turn
                    existing_goals_before = set(current_sheet.goals.keys())
                    
                    # First, process new goals (if any)
                    new_pillars_added = 0
                    for goal_data in data["goals"]:
                        pillar = goal_data.get("pillar")
                        if not pillar:
                            continue
                        
                        try:
                            pillar_enum = Pillar(pillar.upper())
                        except ValueError:
                            continue
                        
                        # If this is a new goal, create it (but don't add quests to it yet)
                        if pillar_enum not in current_sheet.goals:
                            current_sheet.goals[pillar_enum] = Goal(
                                name=goal_data["name"],
                                pillar=pillar_enum,
                                description=goal_data.get("description"),
                                current_quests=[]  # No quests for newly created goals in this turn
                            )
                            new_pillars_added += 1
                    
                    # Then, only add current_quests to goals that existed BEFORE this turn
                    for goal_data in data["goals"]:
                        pillar = goal_data.get("pillar")
                        if not pillar:
                            continue
                        
                        try:
                            pillar_enum = Pillar(pillar.upper())
                        except ValueError:
                            continue
                        
                        # Only add quests to goals that existed before this turn
                        if pillar_enum in existing_goals_before:
                            if "current_quests" in goal_data:
                                for quest in goal_data["current_quests"]:
                                    if quest and quest not in current_sheet.goals[pillar_enum].current_quests:
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
    def generate_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", ask_for_prioritization: bool = False, phase: str = "phase1", pending_debuffs: List[Dict[str, str]] = None) -> Tuple[str, str]:
        """
        Generates the Architect's response based on conversation history and Critic feedback.
        Returns the visible response and the thinking block for debugging.
        """
        if pending_debuffs is None:
            pending_debuffs = []
        
        # Calculate progress based on phase
        defined_pillars = len(current_sheet.goals)
        total_pillars = len(Pillar)
        
        if phase == "phase1":
            # Phase 1: Progress based on goals identified
            progress_pct = min(int((defined_pillars / total_pillars) * 100), 75)
        elif phase == "phase2":
            # Phase 2: Progress based on goals + quests
            total_quests = sum(len(g.current_quests) for g in current_sheet.goals.values())
            # We want at least 2 quests per goal (to assess skill level)
            target_quests = max(defined_pillars, 1) * 2
            quest_progress = min(total_quests / target_quests * 25, 25)
            progress_pct = 75 + int(quest_progress)
        else:
            progress_pct = 95

        # Determine which pillars are still missing goals
        missing_pillars = [p.value for p in Pillar if p not in current_sheet.goals]
        
        # Phase-specific instructions
        phase_instruction = ""
        if phase == "phase1":
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 1 - GOAL IDENTIFICATION**
        - Your ONLY job is to help the user identify goals for each of the four pillars: {', '.join([p.value for p in Pillar])}.
        - **CRITICAL**: Before determining what's missing, CHECK the "Current Sheet State" above to see which goals have ALREADY been extracted.
        - The "Missing Pillars" field shows which pillars still need goals - use this, NOT just the conversation history.
        - Do NOT ask about goals that are already in the Current Sheet State.
        - Do NOT ask about current habits, actions, or quests yet - that comes in Phase 2.
        - Focus on WHAT they want to achieve, not HOW they'll achieve it.
        - Missing pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
        - If there are missing pillars, guide the user to define a goal for one of them.
        - Example: "This is a great start. Now, let's think about your career. What is a major goal you have for your professional life?"
        """
        elif phase == "phase2":
            phase_instruction = f"""
        **CURRENT PHASE: PHASE 2 - CURRENT QUESTS**
        - All four pillars now have goals. Your job is to ask about current habits and actions.
        - You need to collect AT LEAST 2 current_quests for EACH goal (to assess the user's skill level).
        - Ask about WHAT the user is CURRENTLY doing or HAS DONE to achieve their goals - NOT what they need to learn or will do in the future.
        - Focus on specific, measurable actions they're already taking (e.g., "I go to gym 3x per week", "I code for 1 hour daily", "I practice SQL queries").
        - Do NOT ask about future skills, tools, or technologies they need to learn - that will be handled later by the system (Planners will generate needed_quests).
        - Ask about each goal: "For your [goal name], what are you currently doing? What have you been working on?"
        - If a goal already has 1 quest, ask for another one: "You mentioned [quest]. What else are you doing for [goal name]?"
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
            phase_instruction = """
        **CURRENT PHASE: PHASE 3.5 - GOAL PRIORITIZATION**
        - All goals and quests are complete. Ask the user to rank their goals.
        - Present all four goals clearly and ask them to rank from most to least important.
        """
        
        system_prompt_with_context = f"""{ARCHITECT_SYSTEM_PROMPT}

        [System Context]
        Current Phase: {phase.upper()}
        Current Profile Completion: {progress_pct}%
        Current Sheet State: {current_sheet.model_dump_json()}
        Missing Pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
        Pending Debuffs: {len(pending_debuffs)} waiting for confirmation
        
        {phase_instruction}
        
        Instruction: 
        1.  Follow the phase-specific instructions above.
        2.  **CRITICAL**: You MUST end every response with at least one question. Never just recap or summarize without asking something. If you recap what the user said, you MUST follow it with a question to keep the conversation moving.
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
        6.  **CRITICAL - Only Use Explicit Information from THIS Conversation**: 
            - ONLY reference things the user has explicitly stated in the conversation history provided to you.
            - Do NOT infer, assume, or mention anything the user hasn't directly said.
            - **ABSOLUTE RULE**: Do NOT use information from few-shot examples - those are just examples of how to ask questions, NOT facts about this user. If an example mentions "teacher," that does NOT mean this user is a teacher.
            - Do NOT mention jobs, careers, hobbies, or activities unless the user explicitly mentioned them.
            - **ABSOLUTE RULE**: If the user mentions specific activities (like journaling, exercise, vocal practice, volleyball, coding, family), ONLY ask about those. Do NOT assume they have a job, are a teacher, or do anything else they haven't mentioned.
            - **ABSOLUTE RULE**: If the user says "I would do X, Y, Z" - they are describing activities, NOT their current job. Do NOT assume they have a job unless they explicitly say "I work as..." or "I am a..."
            - **ABSOLUTE RULE**: Do NOT mention anxiety, stress, or mental health issues unless the user explicitly mentions them.
            - **ABSOLUTE RULE**: Track each user response separately. If they talk about productivity in one message and social connections in another, don't mix them up. Keep responses about different topics separate.
        7.  **Focus on Goals, Not Implementation Details** (Phase 1) / **Focus on Current Actions** (Phase 2):
            - **Phase 1**: Ask about WHAT the user wants to achieve (their goals), not HOW to achieve it.
            - **Phase 2**: Ask about WHAT the user is CURRENTLY doing or HAS DONE, NOT what they need to learn or will do in the future.
            - Do NOT ask about specific costs, budgets, steps, methods, or implementation details.
            - Do NOT ask "How much would it cost?" or "What's the first step?" - focus on their goals and what they're doing to reach them.
            - Do NOT ask about future skills or technologies to learn - focus on current actions and habits. The system will generate needed_quests later.
            - Example (Phase 1): Instead of "How much would a restaurant cost?" ask "What do you want to achieve as a chef?"
            - Example (Phase 2): Instead of "What skills do you need to learn?" ask "What are you currently doing to work toward that goal?"
        8.  **Suggest Solutions, Don't Ask for Them**:
            - When the user mentions a problem or challenge, SUGGEST a solution rather than asking them what they should do.
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
            # This is for the final turn after prioritization is done.
            if not missing_pillars: # All pillars are defined
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
