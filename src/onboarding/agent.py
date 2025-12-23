# import json
# import os
# import difflib
# import re
# from typing import Tuple, List, Dict
# from dotenv import load_dotenv
# from src.models import CharacterSheet, ConversationState, Pillar, Goal, PendingDebuff
# from src.onboarding.prompts import ARCHITECT_SYSTEM_PROMPT, FEW_SHOT_EXAMPLES
# from src.llm import LLMClient

# # Load environment variables
# load_dotenv()

# llm_client = LLMClient()


# def _strip_thinking_block(text: str) -> str:
#     """Remove any <thinking>...</thinking> blocks from an LLM response before showing it to the user."""
#     if not text:
#         return text

#     # Remove full thinking blocks
#     cleaned = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE)
#     # Clean up any stray opening/closing tags if the model didn't close properly
#     cleaned = re.sub(r"</?thinking>", "", cleaned, flags=re.IGNORECASE)
#     return cleaned.strip()

# class CriticAgent:
#     def _deduplicate_list(self, items: List[str], similarity_threshold: float = 0.8) -> List[str]:
#         """
#         Deduplicates a list of strings based on semantic similarity.
#         Keeps the shorter, more concise item.
#         """
#         if not items:
#             return []
        
#         to_remove = set()
        
#         for i in range(len(items)):
#             for j in range(i + 1, len(items)):
#                 item1, item2 = items[i], items[j]
#                 if item1 in to_remove or item2 in to_remove:
#                     continue
                
#                 ratio = difflib.SequenceMatcher(None, item1.lower(), item2.lower()).ratio()
                
#                 if ratio > similarity_threshold:
#                     # Mark the longer one for removal
#                     if len(item1) > len(item2):
#                         to_remove.add(item1)
#                     else:
#                         to_remove.add(item2)
                        
#         return [item for item in items if item not in to_remove]

#     def analyze(self, user_input: str, current_sheet: CharacterSheet, history: List[Dict[str, str]] = [], phase: str = "phase1") -> Tuple[CharacterSheet, str, str, List[Dict[str, str]]]:
#         """
#         Analyzes the user input to extract data and update the character sheet.
#         Returns the updated sheet, feedback for the Architect, raw analysis JSON, and pending debuffs.
        
#         Phase behavior:
#         - phase1: Only extract goals (no current_quests)
#         - phase2: Only extract current_quests (goals already exist)
#         - Debuffs are always queued for confirmation, never added directly
#         """
        
#         last_architect_msg = "None"
#         # History[-1] is the current user input (if added before call) or we just look for the last assistant msg
#         # In main.py, user input is added to history BEFORE calling analyze.
#         # So history[-1] is user, history[-2] is assistant.
#         if len(history) >= 2 and history[-2]['role'] == 'assistant':
#             last_architect_msg = history[-2]['content']
        
#         # Phase-specific instructions
#         phase_instructions = ""
#         if phase == "phase1":
#             phase_instructions = """
#         **CURRENT PHASE: PHASE 1 - GOAL IDENTIFICATION**
#         - You MUST only extract GOALS in this phase. Do NOT extract current_quests.
#         - Focus on identifying high-level goals for each pillar.
#         - The user can have multiple goals per pillar, but we need at least 1 goal per pillar.
#         - Do NOT include "current_quests" in your output - leave that array empty.
#         """
#         elif phase == "phase2":
#             phase_instructions = """
#         **CURRENT PHASE: PHASE 2 - CURRENT QUESTS**
#         - You CAN extract new goals if the user mentions them.
#         - However, you MUST only extract current_quests (habits/actions) for goals that ALREADY EXISTED before this turn.
#         - If a new goal is mentioned in this turn, extract it but DO NOT extract current_quests for that new goal yet.
#         - You need to collect AT LEAST 2 current_quests for EACH existing goal (to assess the user's skill level).
#         - Focus on what the user is currently doing or wants to do to achieve their EXISTING goals.
#         - Ask about specific, measurable actions (e.g., "go to gym 3x per week", "code for 1 hour daily").
#         - Example: If user says "I also want to learn piano" (new goal) and "I go to the gym 3x a week" (quest for existing goal), extract both but only add the gym quest to the existing physical goal.
#         """
#         else:
#             phase_instructions = f"""
#         **CURRENT PHASE: {phase.upper()}**
#         - Follow standard extraction rules.
#         """
        
#         system_prompt = """
#         You are the "Critic" and "Data Extractor" for a character creation process.
#         Your job is to analyze the user's message and extract structured data for their Character Sheet.
#         You must categorize extracted goals and quests into one of the four pillars: Career, Physical, Mental, Social.

#         Current Character Sheet:
#         {current_sheet_json}
        
#         Last Architect Message: "{last_architect_msg}"
        
#         {phase_instructions}
        
#         Output JSON format:
#         {{
#             "goals": [
#                 {{
#                     "name": "string",
#                     "pillars": ["CAREER" | "PHYSICAL" | "MENTAL" | "SOCIAL"],
#                     "current_quests": ["string"],
#                     "description": "Optional string"
#                 }}
#             ],
#             "stats_career": {{"StatName": integer}},
#             "stats_physical": {{"StatName": integer}},
#             "stats_mental": {{"StatName": integer}},
#             "stats_social": {{"StatName": integer}},
#             "debuffs_analysis": [
#                 {{"name": "string", "evidence": "exact quote from user", "confidence": "high|medium|low"}}
#             ],
#             "feedback_for_architect": "String with feedback for the Architect agent to guide the user."
#         }}
        
#         INSTRUCTIONS:
#         1.  **Conservative Goal Extraction - CRITICAL DISTINCTIONS**:
#             *   Analyze the user's **most recent message only**.
#             *   **CRITICAL - GOAL vs ACTIVITY/HABIT**:
#               - **GOAL** = What the user wants to ACHIEVE or BECOME (outcome/desired state)
#                 * Examples of CORRECT goals: "Build muscle", "Increase stamina", "Jump higher", "Understand myself better", "Be more in touch with myself", "Improve communication skills", "Become a data analyst", "Strengthen relationships"
#                 * Goals should be specific enough to be meaningful but high-level enough to allow multiple paths
#               - **ACTIVITY/HABIT** = What the user DOES to achieve a goal (method/action)
#                 * Examples of activities (NOT goals): "Journaling", "Exercise", "Meditation", "Going to the gym", "Coding", "Playing volleyball"
#                 * These should be extracted as `current_quests` (in Phase 2), NOT as goals
#               - **WRONG**: "Journaling" as a goal → Should be "Understand myself better" or "Be more in touch with myself"
#               - **WRONG**: "Exercise" as a goal → Should be "Build muscle", "Increase stamina", "Jump higher", or "Improve cardiovascular health"
#               - **WRONG**: "Learn to Code" as a goal → Should be "Become a software engineer" or "Build software applications"
#               - **CORRECT**: "Improve Communication Skills" is a goal (outcome)
#               - **CORRECT**: "Spend Time with Family and Friends" is a goal (desired state/outcome)
#             *   **CRITICAL - GOAL SPECIFICITY**:
#               - Goals should be specific enough to be meaningful (not too vague like "Exercise" or "Be healthy")
#               - But not so specific they're just activities (not "Journaling" or "Go to gym 3x per week")
#               - Examples:
#                 * Too vague: "Exercise", "Be healthy", "Learn", "Code"
#                 * Too specific (activity): "Journaling", "Meditation", "Going to the gym"
#                 * Just right: "Build muscle", "Increase stamina", "Understand myself better", "Improve communication skills"
#             *   **CRITICAL - DUPLICATE DETECTION**:
#               - Before adding a new goal, check if it overlaps with existing goals
#               - "Learn Data Analysis" and "Learn to Code" are duplicates/overlapping → Merge into one goal like "Become a data analyst" or "Master data science"
#               - "Exercise" and "Build muscle" → If user says "exercise", extract as "Build muscle" or "Improve fitness" (more specific goal)
#               - If goals are similar/overlapping, merge them into one more comprehensive goal
#             *   Assign each goal to its correct `Pillar(s)` (CAREER, PHYSICAL, MENTAL, SOCIAL). A goal can belong to MULTIPLE pillars (e.g., "Playing Volleyball" can be both PHYSICAL and SOCIAL, but "Play Volleyball" is an activity - the goal might be "Improve athleticism" or "Build social connections through sports").
#             *   Use `"pillars"` (array) in the JSON output, not `"pillar"` (single). Example: `"pillars": ["PHYSICAL", "SOCIAL"]`
#             *   **CRITICAL**: Do NOT infer or create goals for pillars the user has not explicitly talked about in their latest response. If the user only talks about fitness, only extract a `PHYSICAL` goal.
#             *   **PHASE 1 ONLY**: Extract goals. Do NOT extract current_quests.
#             *   **PHASE 2 ONLY**: You CAN extract new goals if mentioned, but ONLY extract current_quests for goals that existed BEFORE this turn. If a new goal is created in this turn, do NOT add current_quests to it yet.

#         2.  **Quest Validation**:
#             *   Review each `current_quest`. If a quest is vague (e.g., "be healthier"), generate feedback in `feedback_for_architect` asking for a more specific, measurable action.
#             *   Example Feedback: "The quest 'be healthier' is vague. Ask the user to specify a concrete action, like 'eat a salad daily'."

#         3.  **Stat Inference**:
#             *   Estimate stats (1-10) for the pillars the user discussed.

#         4.  **Debuff Analysis**:
#             *   **ABSOLUTE RULE**: Only identify debuffs if the user EXPLICITLY states they have a problem, issue, or negative behavior.
#             *   **CRITICAL - WHAT IS A DEBUFF**: A debuff is ONLY when the user explicitly says they have a PROBLEM:
#               - "I have [problem]" (e.g., "I have anxiety", "I have trouble focusing")
#               - "I struggle with [problem]" (e.g., "I struggle with procrastination")
#               - "I can't [do something]" (e.g., "I can't focus", "I can't stay motivated")
#               - "I'm [negative state]" (e.g., "I'm stressed", "I'm lazy", "I'm overwhelmed")
#               - "I [negative action]" (e.g., "I procrastinate", "I avoid things")
#             *   **CRITICAL - WHAT IS NOT A DEBUFF**: Do NOT extract debuffs from:
#               - Activities or habits: "I put on sad music" → NOT a debuff, it's just an activity
#               - Coping mechanisms: "I listen to sad music to calm myself down" → NOT a debuff, it's a coping strategy
#               - Coping mechanisms: "I sit there for a bit" → NOT avoidance, it's a coping strategy
#               - Coping mechanisms: "I start doing something when overwhelmed" → NOT avoidance, it's a coping mechanism
#               - Goals or plans: "I would do X" → NOT procrastination, it's a goal
#               - Current habits: "I go to the gym" → NOT a problem, it's a habit
#               - Descriptions of what they do: "Sometimes I just put on sad music and sit there" → NOT a debuff, it's describing an activity
#               - Descriptions of coping: "Sometimes i just like stop, listen to sad music to calm myself down" → NOT a debuff, it's describing a coping mechanism
#             *   **EXAMPLES OF WHAT NOT TO EXTRACT**:
#               - User says: "Sometimes i just put on sad music and sit there for a bit"
#                 → WRONG: "Avoidance" or "Emotional Regulation" (these are NOT debuffs - it's just describing an activity/coping mechanism)
#                 → CORRECT: No debuff extracted (empty array)
#               - User says: "Sometimes i just like stop, listen to sad music to calm myself down"
#                 → WRONG: "Emotional Regulation" (this is NOT a debuff - it's describing a coping mechanism, not stating a problem)
#                 → CORRECT: No debuff extracted (empty array)
#               - User says: "When i get overwhelmed i just start do something, anything"
#                 → WRONG: "Avoidance" (this is describing a coping mechanism, not stating a problem)
#                 → CORRECT: No debuff extracted UNLESS user explicitly says "I have a problem with avoidance" or "I struggle with avoiding stillness"
#               - User says: "I would do journaling, exercise, etc."
#                 → WRONG: "Procrastination" (this is a goal/plan, not procrastination)
#                 → CORRECT: No debuff extracted
#             *   **KEY DISTINCTION**: 
#               - If user DESCRIBES what they do (e.g., "I listen to music to calm down") → NOT a debuff
#               - If user STATES they have a problem (e.g., "I have trouble calming down" or "I can't calm down") → MAYBE a debuff (if they explicitly say it's a problem)
#             *   **ONLY extract if the user explicitly states a problem**: 
#               - "I procrastinate" → CORRECT: Extract "Procrastination"
#               - "I'm anxious" → CORRECT: Extract "Anxiety"
#               - "I can't focus" → CORRECT: Extract "Lack of Focus"
#               - "I struggle with motivation" → CORRECT: Extract "Lack of Motivation"
#               - "I have trouble calming down" → CORRECT: Extract "Difficulty Calming Down" (if they explicitly say it's a problem)
#             *   **Provide the exact user quote as `evidence`**. If you cannot find an explicit quote where the user states they have a problem, do NOT add it.
#             *   **IMPORTANT**: Debuffs are queued for user confirmation - they are NOT automatically added to the character sheet.
#             *   **WHEN IN DOUBT**: If you're not 100% certain the user explicitly stated a problem (not just described an activity or coping mechanism), do NOT extract a debuff. Leave `debuffs_analysis` as an empty array `[]`.
#         """
        
#         messages = [
#             {"role": "system", "content": system_prompt.format(
#                 current_sheet_json=current_sheet.model_dump_json(), 
#                 last_architect_msg=last_architect_msg,
#                 phase_instructions=phase_instructions
#             )},
#             {"role": "user", "content": user_input}
#         ]
        
#         # Store pending debuffs to return
#         pending_debuffs = []
        
#         # Call LLM in JSON mode
#         response_str = llm_client.chat_completion(messages, json_mode=True)
        
#         # Log the Critic's analysis (it's JSON, but we can still log it)
#         print(f"[Critic Analysis]\n{response_str}\n")
        
#         try:
#             data = json.loads(response_str)

#             # Process goals and quests based on phase
#             if "goals" in data:
#                 if phase == "phase1":
#                     # PHASE 1: Extract all goals, but handle them based on whether pillar has been asked about
#                     # Goals can have multiple pillars
#                     for goal_data in data["goals"]:
#                         # Support both "pillar" (single) and "pillars" (multiple) for backward compatibility
#                         pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
#                         if not pillars_data:
#                             continue
                        
#                         # Convert to Pillar enums
#                         pillar_enums = []
#                         for p in pillars_data:
#                             try:
#                                 pillar_enums.append(Pillar(p.upper()))
#                             except ValueError:
#                                 continue
                        
#                         if not pillar_enums:
#                             continue
                        
#                         goal_name = goal_data.get("name", "")
                        
#                         # Check for duplicate/overlapping goals (by name similarity and pillar overlap)
#                         existing_goal = None
#                         for existing in current_sheet.goals:
#                             # Exact match
#                             if existing.name.lower() == goal_name.lower():
#                                 existing_goal = existing
#                                 break
#                             # Similarity check for overlapping goals (e.g., "Learn Data Analysis" vs "Learn to Code")
#                             similarity = difflib.SequenceMatcher(None, existing.name.lower(), goal_name.lower()).ratio()
#                             # Check if they share pillars (more likely to be duplicates)
#                             if similarity > 0.6 and any(p in existing.pillars for p in pillar_enums):
#                                 # Merge: use the more specific or comprehensive goal name
#                                 if len(goal_name) > len(existing.name) or "data" in goal_name.lower() or "analysis" in goal_name.lower():
#                                     # Update existing goal with new name if it's more specific
#                                     existing.name = goal_name
#                                     existing.description = goal_data.get("description", existing.description)
#                                     # Merge pillars
#                                     for p in pillar_enums:
#                                         if p not in existing.pillars:
#                                             existing.pillars.append(p)
#                                 existing_goal = existing
#                                 break
                        
#                         if not existing_goal:
#                             # Add new goal to the list
#                             new_goal = Goal(
#                                 name=goal_name,
#                                 pillars=pillar_enums,
#                                 description=goal_data.get("description"),
#                                 current_quests=[]  # No quests in phase 1
#                             )
#                             current_sheet.goals.append(new_goal)
#                         else:
#                             # Goal exists, update pillars and description if provided
#                             # Merge new pillars with existing ones
#                             existing_goal.pillars = list(set(existing_goal.pillars + pillar_enums))
#                             if goal_data.get("description"):
#                                 existing_goal.description = goal_data.get("description")
                
#                 elif phase == "phase2":
#                     # PHASE 2: Can extract new goals, but only extract current_quests for goals that existed BEFORE this turn
#                     # Store goal names that existed before processing this turn
#                     existing_goal_names_before = {g.name for g in current_sheet.goals}
                    
#                     # First, process new goals (if any) with duplicate detection
#                     for goal_data in data["goals"]:
#                         # Support both "pillar" (single) and "pillars" (multiple) for backward compatibility
#                         pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
#                         if not pillars_data:
#                             continue
                        
#                         # Convert to Pillar enums
#                         pillar_enums = []
#                         for p in pillars_data:
#                             try:
#                                 pillar_enums.append(Pillar(p.upper()))
#                             except ValueError:
#                                 continue

#                         if not pillar_enums:
#                             continue

#                         goal_name = goal_data.get("name", "")
                        
#                         # Check for duplicate/overlapping goals (by name similarity and pillar overlap)
#                         existing_goal = None
#                         for existing in current_sheet.goals:
#                             # Exact match
#                             if existing.name.lower() == goal_name.lower():
#                                 existing_goal = existing
#                                 break
#                             # Similarity check for overlapping goals
#                             similarity = difflib.SequenceMatcher(None, existing.name.lower(), goal_name.lower()).ratio()
#                             # Check if they share pillars (more likely to be duplicates)
#                             if similarity > 0.6 and any(p in existing.pillars for p in pillar_enums):
#                                 # Merge: use the more specific or comprehensive goal name
#                                 if len(goal_name) > len(existing.name) or "data" in goal_name.lower() or "analysis" in goal_name.lower():
#                                     # Update existing goal with new name if it's more specific
#                                     existing.name = goal_name
#                                     existing.description = goal_data.get("description", existing.description)
#                                     # Merge pillars
#                                     for p in pillar_enums:
#                                         if p not in existing.pillars:
#                                             existing.pillars.append(p)
#                                 existing_goal = existing
#                                 break
                        
#                         # If this is a new goal (not duplicate), create it (but don't add quests to it yet)
#                         if not existing_goal and goal_name not in existing_goal_names_before:
#                             new_goal = Goal(
#                                 name=goal_name,
#                                 pillars=pillar_enums,
#                                 description=goal_data.get("description"),
#                                 current_quests=[]  # No quests for newly created goals in this turn
#                             )
#                             current_sheet.goals.append(new_goal)
                    
#                     # Then, only add current_quests to goals that existed BEFORE this turn
#                     for goal_data in data["goals"]:
#                         goal_name = goal_data.get("name", "")
#                         # Only add quests to goals that existed before this turn
#                         if goal_name in existing_goal_names_before:
#                             goal_obj = next((g for g in current_sheet.goals if g.name == goal_name), None)
#                             if goal_obj and "current_quests" in goal_data:
#                                 for quest in goal_data["current_quests"]:
#                                     if quest and quest not in goal_obj.current_quests:
#                                         goal_obj.current_quests.append(quest)
            
#             # Update stats
#             if "stats_career" in data:
#                 current_sheet.stats_career.update(data["stats_career"])
#             if "stats_physical" in data:
#                 current_sheet.stats_physical.update(data["stats_physical"])
#             if "stats_mental" in data:
#                 current_sheet.stats_mental.update(data["stats_mental"])
#             if "stats_social" in data:
#                 current_sheet.stats_social.update(data["stats_social"])
                
#             # Process debuffs - queue them for confirmation instead of adding directly
#             if "debuffs_analysis" in data:
#                 for item in data["debuffs_analysis"]:
#                     name = item.get("name")
#                     evidence = item.get("evidence", "")
#                     confidence = item.get("confidence", "medium")
#                     if name and name not in current_sheet.debuffs:
#                         # Queue for confirmation instead of adding directly
#                         pending_debuffs.append({
#                             "name": name,
#                             "evidence": evidence,
#                             "confidence": confidence
#                         })
            
#             feedback = data.get("feedback_for_architect", "")
                
#             return current_sheet, feedback, response_str, pending_debuffs
            
#         except (json.JSONDecodeError, KeyError) as e:
#             return current_sheet, f"[System Error: Failed to parse Critic output. Error: {e}]", "", []

# class ArchitectAgent:
#     def generate_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", ask_for_prioritization: bool = False, phase: str = "phase1", pending_debuffs: List[Dict[str, str]] = None, current_pillar: str = None, queued_goals: List[Dict[str, str]] = None) -> Tuple[str, str]:
#         """
#         Generates the Architect's response based on conversation history and Critic feedback.
#         Returns the visible response and the thinking block for debugging.
#         """
#         if pending_debuffs is None:
#             pending_debuffs = []
#         if queued_goals is None:
#             queued_goals = []
        
#         # Calculate progress based on phase
#         # Count pillars that have at least 1 goal (accounting for multi-pillar goals)
#         all_pillars_in_goals = set()
#         for goal in current_sheet.goals:
#             all_pillars_in_goals.update(goal.pillars)
#         pillars_with_goals = list(all_pillars_in_goals)
#         defined_pillars = len(pillars_with_goals)
#         total_pillars = len(Pillar)
        
#         if phase == "phase1":
#             # Phase 1: Progress based on goals identified (need at least 1 goal per pillar)
#             progress_pct = min(int((defined_pillars / total_pillars) * 100), 75)
#         elif phase == "phase2":
#             # Phase 2: Progress based on goals + quests
#             total_goals = len(current_sheet.goals)
#             total_quests = sum(len(g.current_quests) for g in current_sheet.goals)
#             # We want at least 2 quests per goal (to assess skill level)
#             target_quests = max(total_goals, 1) * 2
#             quest_progress = min(total_quests / target_quests * 25, 25) if target_quests > 0 else 0
#             progress_pct = 75 + int(quest_progress)
#         elif phase == "phase3" or phase == "phase3.5":
#             # Phase 3/3.5: Debuff confirmation and prioritization
#             progress_pct = 85
#         elif phase == "phase4":
#             # Phase 4: Skill tree generation
#             progress_pct = 95
#         else:
#             progress_pct = 100

#         # Determine which pillars are still missing goals (need at least 1 goal per pillar)
#         missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals]
        
#         # Phase-specific instructions
#         phase_instruction = ""
#         if phase == "phase1":
#             # Helper function to check if pillar has pure goal
#             def has_pure_goal_for_pillar(goals, pillar):
#                 return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
            
#             # Check which pillars need pure goals
#             pillars_needing_pure_goals = []
#             for p in Pillar:
#                 if p in all_pillars_in_goals and not has_pure_goal_for_pillar(current_sheet.goals, p):
#                     pillars_needing_pure_goals.append(p.value)
            
#             # Format queued goals for current pillar
#             queued_goals_text = ""
#             if queued_goals and len(queued_goals) > 0:
#                 queued_list = "\n".join([f"- {g['name']} ({', '.join(g['pillars'])})" for g in queued_goals])
#                 queued_goals_text = f"\n- **Queued Goals for Current Pillar**: The user mentioned these goals earlier for {current_pillar if current_pillar else 'this pillar'}. Present them first:\n{queued_list}\n"
            
#             current_pillar_text = f"\n- **Current Pillar Being Asked About**: {current_pillar if current_pillar else 'None (all pillars have goals)'}" if current_pillar else ""
            
#             pure_goal_requirement = ""
#             if current_pillar and current_pillar in pillars_needing_pure_goals:
#                 pure_goal_requirement = f"\n- **CRITICAL - PURE GOAL REQUIRED**: The {current_pillar} pillar currently has goals, but NONE of them are pure goals (goals that belong only to {current_pillar}). You MUST ask the user for at least one pure goal for {current_pillar} before moving to the next pillar. Ask: 'I see you have goals for {current_pillar}, but I need at least one goal that's specifically just for {current_pillar}. What's a goal you have that's only about {current_pillar}?'"
            
#             phase_instruction = f"""
#         **CURRENT PHASE: PHASE 1 - GOAL IDENTIFICATION ONLY**
        
#         **🚫 ABSOLUTE PROHIBITION - DO NOT ASK ABOUT PRIORITIZATION 🚫**
#         - **NEVER** ask about prioritization, ranking, importance, or which goal is most important in Phase 1.
#         - **NEVER** ask questions like: "Do you want to prioritize any of these goals?", "Which goal is most important?", "What's your biggest priority?", or "Should we rank these?"
#         - Prioritization happens in Phase 3.5, NOT Phase 1. You are currently in Phase 1.
#         - If all 4 pillars have goals, simply confirm them and wait. Do NOT ask about prioritization.
        
#         - Your ONLY job is to help the user identify WHAT they want to achieve (their goals) for each of the four pillars: {', '.join([p.value for p in Pillar])}.
#         - **CRITICAL**: Before determining what's missing, CHECK the "Current Sheet State" above to see which goals have ALREADY been extracted.
#         - The "Missing Pillars" field shows which pillars still need goals - use this, NOT just the conversation history.
#         - Do NOT ask about goals that are already in the Current Sheet State.
#         - **ONE PILLAR PER RESPONSE**: Focus on ONLY ONE missing pillar per response. Do not ask about multiple pillars in the same message.
#         - **GO THROUGH PILLARS ONE BY ONE**: Work through missing pillars systematically. Once you've asked about a pillar, move to the next missing pillar. Do not revisit a pillar you've already asked about in this phase unless the user said something contradictory.
#         - **PURE GOAL REQUIREMENT**: You must ensure each pillar has at least one pure goal (a goal that belongs to only that pillar) before moving to the next pillar. If a pillar only has multi-pillar goals, ask for a pure goal.
#         {pure_goal_requirement}
#         {current_pillar_text}
#         {queued_goals_text}
#         - **GOAL CONFIRMATION**: If the user mentions goals for a pillar you've already asked about, ask them to confirm: "I see you mentioned [goal] for [pillar]. Is that correct? Should I add that as another goal for [pillar]?"
#         - **ABSOLUTE RULE - PHASE 1 ONLY**: Do NOT ask about:
#           * Current habits, actions, routines, or what they're doing now (that's Phase 2)
#           * How they'll achieve their goals
#           * Implementation details, steps, methods, or processes
#           * Skills they need to learn
#           * Tools or resources they need
#           * Costs, budgets, or financial details
#           * Specific routines or schedules
#           * **PRIORITIZATION, RANKING, OR IMPORTANCE** (that's Phase 3.5 - ABSOLUTELY FORBIDDEN in Phase 1)
#         - **ONLY ASK ABOUT**: What they WANT to achieve (the goal itself), not how to get there.
#         - Missing pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
#         - **CRITICAL**: Even if you see goals for all four pillars in the Current Sheet State, you are STILL in Phase 1. Do NOT ask about prioritization. The system will automatically move to Phase 2 when all goals are confirmed.
#         - If there are missing pillars, guide the user to define a goal for one of them.
#         - If there are NO missing pillars (all 4 pillars have goals), acknowledge this but DO NOT ask about prioritization. Simply confirm the goals and wait for the system to transition to Phase 2.
#         - **ABSOLUTE RULE - WHEN ASKING ABOUT MISSING PILLARS**: When asking about a missing pillar (e.g., Mental), ONLY ask about their GOALS for that pillar. Do NOT assume they have problems, anxiety, stress, or issues. 
#           * Ask: "What's your goal for your mental wellbeing?" 
#           * NOT "How are you managing anxiety?" (unless they explicitly mentioned anxiety)
#           * NOT "What's your goal for managing anxiety?" (unless they explicitly mentioned anxiety)
#           * NOT "What do you want to do about your anxiety?" (unless they explicitly mentioned anxiety)
#         - **ABSOLUTE RULE - IN YOUR THINKING - CHECK CURRENT SHEET STATE FIRST**: 
#           * **STEP 1 - CHECK CURRENT SHEET STATE**: Before determining what's missing, ALWAYS check the "Current Sheet State" in System Context. List what goals exist:
#             - Example: "Current Sheet State shows: 'Become a Chef' (CAREER), 'Be Calm Under Pressure' (MENTAL), 'Improve athleticism' (PHYSICAL)."
#           * **STEP 2 - DETERMINE MISSING PILLARS**: Only think "Missing: [Pillar name]" for pillars that have NO goals in Current Sheet State.
#             - **CRITICAL**: If Current Sheet State shows "Be Calm Under Pressure" with pillar MENTAL, then MENTAL is NOT missing. Do NOT think "Missing: Mental pillar".
#             - **CRITICAL**: "Be Calm Under Pressure" IS a Mental goal. If it exists in Current Sheet State, Mental pillar is COVERED.
#             - Use the "Missing Pillars" field from System Context as the source of truth - trust this field completely.
#           * **STEP 3 - NO INFERENCE OF PROBLEMS**: 
#             - **ABSOLUTE PROHIBITION**: Do NOT infer "stress and anxiety" when the user says "be calm under pressure" or "better method".
#             - "Be calm under pressure" is a GOAL, not a statement about having stress/anxiety problems.
#             - If user says "I want to be calm under pressure" → This is a Mental GOAL, NOT a statement about having anxiety.
#             - If user says "I want a better method" (without mentioning stress/anxiety), do NOT think "how they manage stress and anxiety".
#             - Only think about what they explicitly said: "User wants a better method for calming down" or "User wants to be calm under pressure (Mental goal)."
#           * **ABSOLUTE PROHIBITION**: Do NOT think "Missing: [Pillar] - specifically how they manage [problem]" unless:
#             1. The pillar has NO goals in Current Sheet State (check first!), AND
#             2. The user explicitly mentioned that problem (not inferred from goals)
#           * **CRITICAL EXAMPLES**:
#             - User says: "I want to be calm under pressure"
#             - Current Sheet State: "Be Calm Under Pressure" (MENTAL)
#             - CORRECT: "Current Sheet State shows 'Be Calm Under Pressure' (MENTAL). Mental pillar is already covered. Missing: [check Missing Pillars field - Mental should NOT be listed]."
#             - WRONG: "Missing: Mental pillar - specifically how they manage stress and anxiety" → WRONG! Mental already has a goal ("Be Calm Under Pressure"), and user didn't mention stress/anxiety.
#           * **ANOTHER CRITICAL EXAMPLE**:
#             - User says: "I want a better method" (after already having "Be Calm Under Pressure" goal)
#             - Current Sheet State: "Be Calm Under Pressure" (MENTAL)
#             - CORRECT: "Current Sheet State shows 'Be Calm Under Pressure' (MENTAL). Mental pillar is already covered. User wants a better method for achieving their goal. Missing: [check other pillars from Missing Pillars field]."
#             - WRONG: "Missing: Mental pillar - specifically how they manage stress and anxiety" → WRONG! Mental already has a goal, and user didn't mention stress/anxiety.
#         - Examples of GOOD Phase 1 questions:
#           * "What's a major goal you have for your career?"
#           * "What do you want to achieve with your physical health?"
#           * "What's your goal for your mental wellbeing?"
#           * "What do you want in your social life?"
#         - Examples of BAD Phase 1 questions (these belong in Phase 2 or Phase 3.5):
#           * "What's your current exercise routine?" (asks about current actions - Phase 2)
#           * "How often do you go to the gym?" (asks about current habits - Phase 2)
#           * "What skills do you need to learn?" (asks about implementation - Phase 2)
#           * "How much would that cost?" (asks about implementation details - Phase 2)
#           * "Which goal is most important?" (asks about prioritization - Phase 3.5)
#           * "What's your biggest priority?" (asks about prioritization - Phase 3.5)
#         """
#         elif phase == "phase2":
#             # Get goals for current pillar with incomplete quests
#             current_pillar_enum = None
#             if current_pillar:
#                 try:
#                     current_pillar_enum = Pillar(current_pillar.upper())
#                 except ValueError:
#                     pass
            
#             goals_for_current_pillar = []
#             if current_pillar_enum:
#                 goals_for_current_pillar = [
#                     g for g in current_sheet.goals 
#                     if current_pillar_enum in g.pillars and len(g.current_quests) < 2
#                 ]
            
#             goals_list_text = ""
#             if goals_for_current_pillar:
#                 goals_list = "\n".join([
#                     f"  - {g.name} ({len(g.current_quests)}/2 quests): {', '.join(g.current_quests) if g.current_quests else 'No quests yet'}"
#                     for g in goals_for_current_pillar
#                 ])
#                 goals_list_text = f"\n- **Goals in {current_pillar if current_pillar else 'current pillar'} needing quests**:\n{goals_list}\n"
            
#             current_pillar_text = f"\n- **Current Pillar Being Asked About**: {current_pillar if current_pillar else 'None (all goals complete)'}" if current_pillar else ""
            
#             phase_instruction = f"""
#         **CURRENT PHASE: PHASE 2 - CURRENT QUESTS**
#         - All four pillars now have goals. Your job is to ask about current habits and actions.
#         - **🚫 ABSOLUTE PROHIBITION - DO NOT END THE CONVERSATION 🚫**
#           * **NEVER** provide a closing message, summary, or "welcome to the journey" message in Phase 2.
#           * **NEVER** say things like "Well, there you have it", "You've got a roadmap", "Welcome to the journey", or "Take a deep breath, kid. You've got this."
#           * **NEVER** end with a statement - you MUST always end with a question asking about current_quests.
#           * Phase 2 is about collecting current_quests - you are NOT done until ALL goals have at least 2 current_quests.
#         - **🚫 ABSOLUTE PROHIBITION - DO NOT GIVE ADVICE OR SUGGEST SOLUTIONS IN PHASE 2 🚫**
#           * **NEVER** suggest solutions, give advice, or tell the user what they should do in Phase 2.
#           * **NEVER** say things like "Here's something you could try", "You could try X", "I suggest you do Y", or "Would you be open to trying Z?"
#           * Phase 2 is ONLY about DATA COLLECTION - asking what they're CURRENTLY doing, not what they SHOULD do.
#           * If the user mentions a problem or challenge, just ask them what they're currently doing about it - DO NOT suggest solutions.
#           * Example (WRONG): "Here's something you could try: a short guided meditation" → FORBIDDEN in Phase 2
#           * Example (CORRECT): "What are you currently doing to manage stress? Are you doing anything specific right now?"
#         - **CRITICAL - ALWAYS ASK A QUESTION**: You MUST end every response with at least one question asking about current_quests. Do NOT summarize, recap, or end the conversation. You are in Phase 2, which means you need to collect current_quests for each goal.
#         - **PILLAR CYCLING**: Cycle through all four pillars systematically (CAREER → PHYSICAL → MENTAL → SOCIAL).
#         - **ONLY ASK ABOUT INCOMPLETE GOALS**: Only ask about goals in pillars that have incomplete goals (goals with < 2 current_quests).
#         - After completing a pillar (all goals have 2+ quests), move to the next pillar with incomplete goals.
#         {current_pillar_text}
#         {goals_list_text}
#         - **GOAL-BY-GOAL QUESTIONING - ONE GOAL AT A TIME**: For each goal in the current pillar, ask about its current_quests ONE AT A TIME:
#           * **🚫 CRITICAL PROHIBITION**: Do NOT ask about multiple goals at once. Do NOT list multiple activities or goals in a single question.
#           * **🚫 FORBIDDEN QUESTIONS**: 
#             - "For each of these activities – exercise, journaling, vocal practice... what's the current situation?" → FORBIDDEN
#             - "What's the current situation for each of these goals?" → FORBIDDEN
#             - "For exercise, journaling, vocal practice... what are you doing?" → FORBIDDEN
#           * **CORRECT APPROACH**: Ask about ONE goal at a time, focusing on the first incomplete goal in the current pillar.
#           * If a goal has 0 quests, ask: "For your [goal name], what are you currently doing? What have you been working on?"
#           * If a goal has 1 quest, ask: "You mentioned [quest]. What else are you doing for [goal name]?"
#           * After a goal has 2+ quests, move to the next goal in that pillar.
#           * **EXAMPLE (CORRECT)**: "For your exercise goal, what are you currently doing? What have you been working on?" → CORRECT
#         - **STARTING PHASE 2**: When Phase 2 just started, immediately ask about the FIRST goal in the FIRST pillar with incomplete goals. Do NOT summarize Phase 1 or give a closing message. Ask about ONE goal only: "For your [goal name], what are you currently doing to work toward that?"
#         - You need to collect AT LEAST 2 current_quests for EACH goal (to assess the user's skill level).
#         - Ask about WHAT the user is CURRENTLY doing or HAS DONE to achieve their goals - NOT what they need to learn or will do in the future.
#         - Focus on specific, measurable actions they're already taking (e.g., "I go to gym 3x per week", "I code for 1 hour daily", "I practice SQL queries").
#         - Do NOT ask about future skills, tools, or technologies they need to learn - that will be handled later by the system (Planners will generate needed_quests).
#         - **USE CRITIC FEEDBACK**: The Critic provides feedback to help you ask more specific questions. Use this feedback to ask more detailed, targeted questions.
#           * Example: If Critic says "Consider asking them to specify what 'more organized' looks like in practice – for example, 'tracking tasks' or 'creating a schedule'", ask: "You mentioned wanting to be more organized. What specifically does that look like for you? Are you thinking about tracking tasks, creating a schedule, or something else?"
#           * Incorporate the Critic's suggestions naturally into your questions to get more specific, actionable information.
#         - Example: If user says "I want to become a data analyst", ask "What are you currently doing to work toward that? Are you taking any courses, practicing with data, or working on projects?" NOT "What skills do you need to learn?"
#         """
#         elif phase == "phase3":
#             debuff_list = "\n".join([
#                 f"- {d['name']} (evidence: '{d.get('evidence', 'N/A')}', confidence: {d.get('confidence', 'medium')})"
#                 for d in pending_debuffs
#             ])
#             phase_instruction = f"""
#         **CURRENT PHASE: PHASE 3 - DEBUFF CONFIRMATION**
#         - You have {len(pending_debuffs)} pending debuff(s) that need user confirmation.
#         - Present each debuff ONE AT A TIME and ask the user to confirm if it applies to them.
#         - Pending debuffs:
#         {debuff_list}
#         - Example: "I noticed you mentioned '{pending_debuffs[0].get('evidence', 'N/A') if pending_debuffs else 'N/A'}'. Would you say you're dealing with {pending_debuffs[0].get('name', 'this issue') if pending_debuffs else 'this issue'}?"
#         - Wait for the user to confirm or reject before moving to the next debuff.
#         - Once all debuffs are confirmed or rejected, move to goal prioritization.
#         """
#         elif phase == "phase3.5":
#             # List all goals for the Architect to present
#             goal_list = []
#             for goal in current_sheet.goals:
#                 pillars_str = ", ".join([p.value for p in goal.pillars])
#                 goal_list.append(f"- {goal.name} ({pillars_str})")
#             goals_text = "\n".join(goal_list) if goal_list else "your goals"
#             phase_instruction = f"""
#         **CURRENT PHASE: PHASE 3.5 - GOAL PRIORITIZATION**
#         - All goals and quests are complete. Your ONLY job is to ask the user to rank their goals.
#         - Present all goals clearly and ask them to rank from most to least important.
#         - Goals to rank:
#         {goals_text}
#         - Do NOT ask why they prioritized one over another - just ask for the ranking.
#         - Once they provide the ranking (e.g., "Career then Physical then Mental then Social"), acknowledge it briefly and the system will proceed automatically.
#         - **CRITICAL**: After the user provides a ranking, do NOT ask more questions. Simply acknowledge the ranking and let the system transition.
#         """
#         elif phase == "phase4":
#             phase_instruction = """
#         **CURRENT PHASE: PHASE 4 - SKILL TREE GENERATION**
#         - The user has completed prioritization. The system is now generating their skill tree.
#         - **🚫 ABSOLUTE PROHIBITION - DO NOT ASK QUESTIONS IN PHASE 4 🚫**
#           * **NEVER** ask any questions in Phase 4.
#           * **NEVER** ask about goals, quests, or anything else.
#           * Simply acknowledge that the skill tree is being generated and the onboarding is complete.
#           * Your response should be brief and final - just acknowledge completion.
#         - This is the final step - the onboarding is complete.
#         - Example response: "Perfect! I've got everything I need. Your skill tree is being generated now."
#         """
        
#         # Format Critic feedback for display
#         critic_feedback_text = ""
#         if feedback:
#             critic_feedback_text = f"\n        Critic Feedback: {feedback}\n"
        
#         system_prompt_with_context = f"""{ARCHITECT_SYSTEM_PROMPT}

#         [System Context]
#         Current Phase: {phase.upper()}
#         Current Profile Completion: {progress_pct}%
#         Current Sheet State: {current_sheet.model_dump_json()}
#         Missing Pillars: {', '.join(missing_pillars) if missing_pillars else 'None'}
#         Pending Debuffs: {len(pending_debuffs)} waiting for confirmation{critic_feedback_text}
        
#         {phase_instruction}
        
#         Instruction: 
#         1.  Follow the phase-specific instructions above.
#         2.  **🚫 CRITICAL - PHASE 1 PROHIBITION 🚫**: If you are in Phase 1, you MUST ask about missing goals. You MUST NEVER ask about prioritization, ranking, importance, or which goal is most important - that is Phase 3.5. Even if all 4 pillars have goals, you are still in Phase 1 until the system transitions you. DO NOT ask questions like "Do you want to prioritize any of these goals?" or "Which goal is most important?" - these are FORBIDDEN in Phase 1.
#         3.  **CRITICAL**: You MUST end every response with at least one question. Never just recap or summarize without asking something. If you recap what the user said, you MUST follow it with a question to keep the conversation moving. BUT make sure your question is about missing goals or goal confirmation, NOT about prioritization.
#         3.  You MUST include a progress bar at the end of your response in this format:
#            [Progress: ||||||....] {progress_pct}%
#            (Use exactly 20 characters for the bar.)
#         4.  If the Critic provides feedback on a vague quest, you must relay that to the user and ask for clarification.
#         5.  **CRITICAL - Check Current Sheet State First**: 
#             - **BEFORE** determining what's missing, ALWAYS check the "Current Sheet State" in the System Context above.
#             - The Current Sheet State shows ALL goals that have been extracted so far - use this as the source of truth.
#             - The "Missing Pillars" field is calculated from the Current Sheet State - trust this field.
#             - **ABSOLUTE RULE**: If a pillar has a goal in the Current Sheet State, that pillar is NOT missing. Do NOT ask about it again.
#             - **EXAMPLE**: If Current Sheet State shows "Be Calm Under Pressure" with pillar MENTAL, then MENTAL is NOT missing. Do NOT think "Missing: Mental pillar".
#             - **ABSOLUTE RULE**: Do NOT infer problems (like "stress and anxiety") when the user just mentions wanting a "better method" or "better way". Only mention problems if the user explicitly stated them.
#             - Do NOT ask about goals that are already in the Current Sheet State, even if you don't see them in the recent conversation.
#             - Only use conversation history to understand the user's latest response, not to determine what goals exist.
#             - **IN YOUR THINKING**: First list what goals exist in Current Sheet State, THEN determine what's missing. Example: "Current Sheet State shows: [list goals]. Missing: [only pillars not in Current Sheet State]."
#         6.  **CRITICAL - ABSOLUTE NO INFERENCE RULE**: 
#             - **ONLY reference things the user has EXPLICITLY stated in the conversation history provided to you.**
#             - **ABSOLUTE RULE - NO INFERENCE**: Do NOT infer, assume, or mention ANYTHING the user hasn't directly said.
#             - **EXAMPLES OF WHAT NOT TO DO**:
#               * User says "data analysis" → DO NOT mention "anxiety" or "how they manage anxiety" (they never said it)
#               * User says "vocal practice" → DO NOT mention "social anxiety" or "anxiety when talking to people" (they never said it)
#               * User says "journaling" → DO NOT mention "stress management" or "anxiety" (they never said it)
#               * User says "volleyball is just fun and cardio" → DO NOT mention "anxiety" or "how they manage anxiety" (they never said it)
#               * User says "volleyball is just fun and cardio" → DO NOT think "Missing: Mental pillar - specifically how they manage anxiety" (they never mentioned anxiety)
#               * User says "I would do X, Y, Z" → DO NOT infer they have problems, anxiety, or issues (they're just describing activities)
#             - **ABSOLUTE RULE**: Do NOT use information from few-shot examples - those are just examples of how to ask questions, NOT facts about this user. If an example mentions "teacher" or "anxiety", that does NOT mean this user is a teacher or has anxiety.
#             - **ABSOLUTE RULE**: Do NOT mention jobs, careers, hobbies, or activities unless the user explicitly mentioned them.
#             - **ABSOLUTE RULE**: If the user mentions specific activities (like journaling, exercise, vocal practice, volleyball, coding, family), ONLY ask about those. Do NOT assume they have a job, are a teacher, have anxiety, or do anything else they haven't mentioned.
#             - **ABSOLUTE RULE**: If the user says "I would do X, Y, Z" - they are describing activities/goals, NOT their current job or problems. Do NOT assume they have a job, anxiety, or any issues unless they explicitly say "I work as...", "I am a...", "I have anxiety", "I'm anxious", etc.
#             - **ABSOLUTE RULE**: Do NOT mention anxiety, stress, mental health issues, or any problems unless the user EXPLICITLY mentions them using words like "I have anxiety", "I'm anxious", "I'm stressed", "I struggle with X", etc.
#             - **ABSOLUTE RULE**: In your thinking block, ONLY state what the user explicitly said. Do NOT add inferences like "they mentioned anxiety" or "specifically related to their anxiety" if they didn't say it.
#             - **ABSOLUTE RULE**: When a pillar is missing, ONLY think "Missing: [Pillar name]" and plan to ask about goals. Do NOT think "Missing: [Pillar] - specifically how they manage [problem]" or "specifically related to [problem]" unless the user explicitly mentioned that problem.
#             - **ABSOLUTE RULE**: Track each user response separately. If they talk about productivity in one message and social connections in another, don't mix them up. Keep responses about different topics separate.
#         7.  **Focus on Goals, Not Implementation Details** (Phase 1) / **Focus on Current Actions** (Phase 2):
#             - **Phase 1 - GOALS ONLY**: 
#               * Ask ONLY about WHAT the user wants to achieve (their goals), not HOW to achieve it.
#               * Do NOT ask about current habits, routines, actions, or what they're doing now.
#               * Do NOT ask about implementation details, steps, methods, costs, budgets, skills to learn, or tools needed.
#               * Example (GOOD): "What's a major goal you have for your career?" 
#               * Example (BAD): "What's your current exercise routine?" or "How often do you go to the gym?" (these are Phase 2 questions)
#             - **Phase 2 - CURRENT ACTIONS ONLY**: 
#               * Ask about WHAT the user is CURRENTLY doing or HAS DONE, NOT what they need to learn or will do in the future.
#               * Focus on specific, measurable actions they're already taking.
#               * Do NOT ask about future skills or technologies to learn - the system will generate needed_quests later.
#               * Example (GOOD): "What are you currently doing to work toward that goal? Are you taking any courses, practicing, or working on projects?"
#               * Example (BAD): "What skills do you need to learn?" (this is not Phase 2 - system handles this later)
#         8.  **Suggest Solutions, Don't Ask for Them** (Phase 1 and Phase 3 only - NOT Phase 2):
#             - **CRITICAL**: This rule does NOT apply in Phase 2. Phase 2 is ONLY about data collection - asking what they're currently doing, not suggesting solutions.
#             - **Phase 2**: If the user mentions a problem, just ask "What are you currently doing about that?" - DO NOT suggest solutions.
#             - **Phase 1 and Phase 3**: When the user mentions a problem or challenge, SUGGEST a solution rather than asking them what they should do.
#             - Instead of "What's one thing you could do *right now*?" say "Here's something you could try: [specific suggestion]."
#             - Instead of "How do you think you'll handle that?" say "When you face [challenge], try [suggestion]."
#             - Example: If they say "I need more discipline," suggest "Try setting a specific time each day for [activity]. That builds structure."
#         9.  **Smooth Transitions**:
#             - When moving between topics, reference what the user just said.
#             - Use simple, direct language. Avoid idioms like "spinning your wheels."
#             - Example: "You mentioned [X]. Now let's talk about [Y]."
#         """

#         if ask_for_prioritization:
#             system_prompt_with_context += """
            
#             [PRIORITIZATION INSTRUCTION]
#             All four pillars now have goals. Your next task is to ask the user to rank them.
#             Present the four goals clearly to the user.
#             Ask them to rank these goals from most to least important.
#             Make it clear that their ranking will determine the focus of their journey.
#             Example: "We've set goals for all four pillars of your life. Now, let's prioritize. Please rank the following from most to least important for you right now: [Goal 1], [Goal 2], [Goal 3], [Goal 4]."
#             """
#         else:
#             # This is for the final turn after prioritization is done (phase3.5 or later).
#             # Only provide final summary if we're in phase3.5 or later AND all pillars have goals
#             if phase in ["phase3.5", "phase4", "phase5"] and not missing_pillars:
#                  system_prompt_with_context += """
                
#                 [FINAL TURN INSTRUCTION]
#                 All pillars have goals and they have been prioritized. Do NOT ask any more questions.
#                 Provide a grand, encouraging summary of the user's profile.
#                 Welcome them to their journey.
#                 """

#         messages = [{"role": "system", "content": system_prompt_with_context}]
        
#         # Add few-shot examples with a warning
#         # IMPORTANT: These are ONLY examples of how to ask questions. They are NOT facts about the current user.
#         messages.append({"role": "system", "content": "[IMPORTANT] The following examples are ONLY demonstrations of question style. Do NOT use any information from them (like jobs, activities, or problems) unless the user explicitly mentions those same things."})
#         messages.extend(FEW_SHOT_EXAMPLES)
        
#         # Add history
#         messages.extend(history)
        
#         # Inject feedback if present
#         if feedback:
#             messages.append({"role": "system", "content": f"[Critic's Feedback]: {feedback}"})

#         response = llm_client.chat_completion(messages)
        
#         # Extract and log thinking block before stripping
#         thinking_content = ""
#         thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL | re.IGNORECASE)
#         if thinking_match:
#             thinking_content = thinking_match.group(1).strip()
#             print(f"[Architect Thinking]\n{thinking_content}\n")
        
#         # Hide internal thinking traces from the user-facing chat
#         visible_response = _strip_thinking_block(response)
#         return visible_response, thinking_content


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
        """
        
        last_architect_msg = "None"
        if len(history) >= 2 and history[-2]['role'] == 'assistant':
            last_architect_msg = history[-2]['content']
        
        # Phase-specific instructions
        phase_instructions = ""
        if phase == "phase1":
            phase_instructions = """
        <phase_context>
            <phase>PHASE 1 - GOAL IDENTIFICATION</phase>
            <objective>Identify WHAT the user wants to achieve (Outcomes).</objective>
            <restriction>Do NOT extract `current_quests` (Habits/Actions) in this phase. Leave the array empty.</restriction>
            <distinction>
                "I want to lose weight" -> GOAL (Outcome).
                "I go to the gym" -> HABIT (Ignore for now, or extract as Goal "Improve Physical Fitness").
            </distinction>
            <feedback_restriction>
                **CRITICAL - FEEDBACK RESTRICTION FOR PHASE 1**:
                In `feedback_for_architect`, DO NOT suggest asking about:
                - Current activities (e.g., "Ask about their current volleyball skill level")
                - What they're currently doing (e.g., "Ask what they're currently doing to achieve this")
                - Skill levels (e.g., "Ask about their experience level")
                - Types of activities (e.g., "Ask about the type of networking they're interested in")
                These are Phase 2 questions. In Phase 1, ONLY suggest asking for more specific goals or clarifying vague goals.
                Example (CORRECT for Phase 1): "The user's goal is vague. Ask them to specify what they want to achieve."
                Example (WRONG for Phase 1): "Ask about their current volleyball skill level" or "Ask about the type of networking they're interested in"
            </feedback_restriction>
        </phase_context>
        """
        elif phase == "phase2":
            phase_instructions = """
        <phase_context>
            <phase>PHASE 2 - CURRENT QUESTS COLLECTION</phase>
            <objective>**PRIMARY OBJECTIVE**: Extract `current_quests` (what the user is CURRENTLY doing) for goals that ALREADY EXIST in the `Current Character Sheet`. If user has limited or no current activities, extract their skill level self-assessment instead.</objective>
            <restriction>ONLY extract `current_quests` for goals that ALREADY EXIST in the `Current Character Sheet`.</restriction>
            <new_goals>If the user mentions a BRAND NEW goal (e.g., "I want to spike a volleyball"), extract it as a new goal, but DO NOT attach quests to it yet.</new_goals>
            <critical_distinction>
                **CRITICAL - GOAL vs QUEST in Phase 2**:
                - "I want to spike a volleyball" -> GOAL (desired outcome), NOT a quest
                - "I spike volleyballs twice a week" -> QUEST (current action)
                - "I want to network" -> GOAL (desired outcome), NOT a quest
                - "I attend networking events monthly" -> QUEST (current action)
                - "I manage stress with breathing exercises" -> QUEST (current action for "Manage Stress" goal)
                - "I listen to music to calm down" -> QUEST (current action for "Manage Stress" goal)
                - "Currently I manage that stress with breathing exercises and listening to music" -> EXTRACT BOTH as quests: ["breathing exercises", "listening to music"]
                If the user says "I want to X" or "I want to be able to X", that's a GOAL, not a quest.
                If the user says "I do X", "I manage X with Y", "Currently I X", "I practice X", "I go to X", that's a QUEST (current action).
            </critical_distinction>
            <quest_extraction_rules>
                **MANDATORY - YOU MUST EXTRACT QUESTS WHEN USER DESCRIBES CURRENT ACTIONS**:
                1. If user says "I manage [goal] with [action]" -> Extract [action] as a quest for that goal
                2. If user says "Currently I [action]" -> Extract [action] as a quest for the relevant goal
                3. If user says "I do [action] to [goal]" -> Extract [action] as a quest for that goal
                4. If user lists multiple actions (e.g., "breathing exercises and listening to music"), extract ALL of them as separate quests
                5. **CRITICAL**: Match the quest to the correct goal based on context. If user mentions managing stress, match quests to the "Manage Stress" goal.
            </quest_extraction_rules>
            <limited_activity_detection>
                **CRITICAL - DETECT LIMITED ACTIVITY**:
                If the user indicates they have LIMITED or NO current activities, you MUST:
                1. Extract whatever quests they mentioned (even if 0 or 1)
                2. Extract their skill level self-assessment if they provide one
                3. Look for phrases like:
                   - "I only do X" / "I only [action]"
                   - "I don't really do anything" / "I don't do anything for that"
                   - "I'm just starting out" / "I haven't started yet"
                   - "I'm a beginner" / "I'm new to this"
                   - "I don't have any experience" / "I have no experience"
                4. If user provides a skill level (1-10 scale), extract it in the `skill_level` field
                5. If user says they have 0-1 quests, mark this in `feedback_for_architect` so Architect can ask for skill level
            </limited_activity_detection>
            <skill_level_extraction>
                **SKILL LEVEL EXTRACTION**:
                - If user provides a number 1-10 when asked about skill level, extract it as `skill_level`
                - Examples: "I'd say 3/10", "maybe a 5", "around 7", "I'm at level 2"
                - If user provides qualitative assessment, try to map it:
                  * "beginner" / "just starting" -> 1-3
                  * "some experience" / "intermediate" -> 4-6
                  * "experienced" / "advanced" -> 7-9
                  * "expert" -> 10
            </skill_level_extraction>
            <specificity>Quests must be specific actions (e.g., "Run 5km", "Study Python 1hr", "breathing exercises", "listening to music"). Avoid vague concepts.</specificity>
            <example>
                User says: "Currently I manage that stress with breathing exercises and listening to music"
                Goal exists: "Manage Stress" (MENTAL)
                You MUST extract: "current_quests": ["breathing exercises", "listening to music"]
                Do NOT leave current_quests empty!
            </example>
            <example_limited_activity>
                User says: "I don't really do anything for volleyball, I'm just starting out"
                Goal exists: "Spike a Volleyball" (PHYSICAL)
                You MUST extract: "current_quests": [] (empty, since they said they don't do anything)
                In feedback_for_architect: "User indicates they have no current activities for this goal. Ask them to self-assess their skill level (1-10)."
            </example_limited_activity>
            <example_skill_level>
                User says: "I'd say I'm at a 3 out of 10 for volleyball"
                Goal exists: "Spike a Volleyball" (PHYSICAL)
                You MUST extract: "skill_level": 3
            </example_skill_level>
        </phase_context>
        """
        else:
            phase_instructions = f"""
        <phase_context>
            <phase>{phase.upper()}</phase>
            <instruction>Follow standard extraction rules.</instruction>
        </phase_context>
        """
        
        system_prompt = """
        <role_definition>
        You are the "Critic" and "Data Extractor". Your task is to analyze conversation to build a structured JSON Character Sheet.
        </role_definition>
        
        <onboarding_flow>
        The onboarding process has multiple phases that you will pass through:
        - PHASE 1: Goal Identification - Extract goals (what the user wants to achieve)
        - PHASE 2: Current Quests - Extract current_quests (what the user is currently doing)
        - PHASE 3: Debuff Confirmation - Confirm debuffs with the user
        - PHASE 3.5: Goal Prioritization - User ranks their goals
        - PHASE 4: Skill Tree Generation - System generates needed_quests and skill tree
        You are currently in: {phase}
        </onboarding_flow>
        
        <context_data>
        Current Character Sheet:
        {current_sheet_json}
        
        Last Architect Message: "{last_architect_msg}"
        </context_data>
        
        {phase_instructions}
        
        <output_schema>
        **OUTPUT FORMAT (JSON ONLY)**:
        {{
            "analysis_trace": "String. BRIEF reasoning. 1. What did user say? 2. Is it a Goal (Outcome) or Quest (Action)? 3. Does it imply a Problem (Debuff)? 4. Does user have limited activity (0-1 quests)?",
            "goals": [
                {{
                    "name": "string (concise title)",
                    "pillars": ["CAREER" | "PHYSICAL" | "MENTAL" | "SOCIAL"],
                    "current_quests": ["string"],
                    "description": "string (context)",
                    "skill_level": integer_1_to_10 (optional, only if user self-assessed)
                }}
            ],
            "stats_career": {{"StatName": integer_1_to_10}},
            "stats_physical": {{"StatName": integer_1_to_10}},
            "stats_mental": {{"StatName": integer_1_to_10}},
            "stats_social": {{"StatName": integer_1_to_10}},
            "debuffs_analysis": [
                {{"name": "string", "evidence": "exact user quote", "confidence": "high|medium|low"}}
            ],
            "feedback_for_architect": "String. Tell the Architect if the user was vague and needs follow-up questions. **CRITICAL - PHASE 1 ONLY**: In Phase 1, ONLY suggest asking for more specific goals or clarifying vague goals. DO NOT suggest asking about current activities, skill levels, or what they're currently doing - those are Phase 2 questions. **CRITICAL - PHASE 2 ONLY**: In Phase 2, ONLY suggest asking for more quests if the user has provided vague quests, or suggest asking for skill level if user has 0-1 quests. DO NOT suggest asking about goals, desired outcomes, or what they want to achieve - those are Phase 1 questions. If the user provides good, specific quests (like 'practicing knife skills' or 'making new recipes'), DO NOT suggest asking about goals. Example (Phase 1): 'The user's goal is vague. Ask them to specify what they want to achieve.' Example (Phase 2 - CORRECT): 'User indicates they have no current activities for this goal. Ask them to self-assess their skill level (1-10).' Example (Phase 2 - WRONG): 'Ask about the user's overall goal and desired level of expertise' - this is Phase 1, not Phase 2."
        }}
        </output_schema>
        
        <extraction_rules>
        1. **GOAL EXTRACTION (The "What")**:
           - Extract high-level outcomes (e.g., "Become a Senior Dev", "Run a Marathon").
           - **Duplicate Check**: If a goal is similar to an existing one, MERGE them.
           - **Pillar Logic**: Assign pillars based STRICTLY on context.
        
        2. **QUEST EXTRACTION (The "How" - Phase 2 Only)**:
           - Extract specific actions the user CURRENTLY does (e.g., "Gym 3x/week", "I practice coding daily").
           - **CRITICAL DISTINCTION**: "I want to X" or "I want to be able to X" is a GOAL, NOT a quest.
           - Only extract as quests if they describe CURRENT actions (e.g., "I do X", "I go to X", "I practice X").
           - Example (WRONG): User says "I want to spike a volleyball" → This is a GOAL, NOT a quest.
           - Example (CORRECT): User says "I spike volleyballs twice a week" → This is a QUEST (current action).
           - If a quest is VAGUE (e.g., "I try to be healthy"), do NOT extract it. Add note to `feedback_for_architect`.
        
        3. **DEBUFF EXTRACTION (Conservative Mode)**:
           - **DEFINITION**: A debuff is a SELF-IDENTIFIED PROBLEM or BLOCKER.
           - **RULE**: ONLY extract if the user uses negative self-language ("I struggle with...", "I can't...", "I have anxiety").
           - **FALSE POSITIVES**: Coping mechanisms ("I listen to music to calm down") are NOT debuffs.
           - **EVIDENCE**: You MUST quote the user in the `evidence` field.
        
        4. **STAT INFERENCE**:
           - Infer stats (1-10) only if the user provides evidence of skill level.
        </extraction_rules>
        """
        
        messages = [
            {"role": "system", "content": system_prompt.format(
                current_sheet_json=current_sheet.model_dump_json(), 
                last_architect_msg=last_architect_msg,
                phase_instructions=phase_instructions,
                phase=phase
            )},
            {"role": "user", "content": user_input}
        ]
        
        # Store pending debuffs to return
        pending_debuffs = []
        
        # Call LLM in JSON mode
        response_str = llm_client.chat_completion(messages, json_mode=True)
        
        print(f"[Critic Analysis]\n{response_str}\n")
        
        try:
            data = json.loads(response_str)

            # Process goals and quests based on phase
            if "goals" in data:
                if phase == "phase1":
                    # PHASE 1: Extract all goals, duplicate handling
                    for goal_data in data["goals"]:
                        pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
                        if not pillars_data: continue
                        
                        pillar_enums = []
                        for p in pillars_data:
                            try:
                                pillar_enums.append(Pillar(p.upper()))
                            except ValueError: continue
                        
                        if not pillar_enums: continue
                        
                        goal_name = goal_data.get("name", "")
                        
                        # Check for duplicate/overlapping goals
                        existing_goal = None
                        for existing in current_sheet.goals:
                            if existing.name.lower() == goal_name.lower():
                                existing_goal = existing
                                break
                            similarity = difflib.SequenceMatcher(None, existing.name.lower(), goal_name.lower()).ratio()
                            if similarity > 0.6 and any(p in existing.pillars for p in pillar_enums):
                                if len(goal_name) > len(existing.name) or "data" in goal_name.lower() or "analysis" in goal_name.lower():
                                    existing.name = goal_name
                                    existing.description = goal_data.get("description", existing.description)
                                    for p in pillar_enums:
                                        if p not in existing.pillars:
                                            existing.pillars.append(p)
                                existing_goal = existing
                                break
                        
                        if not existing_goal:
                            new_goal = Goal(
                                name=goal_name,
                                pillars=pillar_enums,
                                description=goal_data.get("description"),
                                current_quests=[] 
                            )
                            current_sheet.goals.append(new_goal)
                        else:
                            existing_goal.pillars = list(set(existing_goal.pillars + pillar_enums))
                            if goal_data.get("description"):
                                existing_goal.description = goal_data.get("description")
                
                elif phase == "phase2":
                    # PHASE 2: New goals okay, but Quests only for existing goals
                    # CRITICAL: Store all existing goals by name to ensure we don't lose any
                    existing_goal_names_before = {g.name.lower(): g for g in current_sheet.goals}
                    
                    # First, process new goals (if any) with duplicate detection
                    for goal_data in data["goals"]:
                        pillars_data = goal_data.get("pillars") or ([goal_data.get("pillar")] if goal_data.get("pillar") else [])
                        if not pillars_data: continue
                        
                        pillar_enums = []
                        for p in pillars_data:
                            try:
                                pillar_enums.append(Pillar(p.upper()))
                            except ValueError: continue

                        if not pillar_enums: continue

                        goal_name = goal_data.get("name", "")
                        goal_name_lower = goal_name.lower()
                        
                        existing_goal = None
                        # Check exact match first
                        if goal_name_lower in existing_goal_names_before:
                            existing_goal = existing_goal_names_before[goal_name_lower]
                        else:
                            # Check similarity with existing goals
                            for existing in current_sheet.goals:
                                similarity = difflib.SequenceMatcher(None, existing.name.lower(), goal_name_lower).ratio()
                                if similarity > 0.6 and any(p in existing.pillars for p in pillar_enums):
                                    if len(goal_name) > len(existing.name) or "data" in goal_name_lower or "analysis" in goal_name_lower:
                                        existing.name = goal_name
                                        existing.description = goal_data.get("description", existing.description)
                                    for p in pillar_enums:
                                        if p not in existing.pillars:
                                            existing.pillars.append(p)
                                    existing_goal = existing
                                    break
                        
                        if not existing_goal:
                            # New goal - add it
                            new_goal = Goal(
                                name=goal_name,
                                pillars=pillar_enums,
                                description=goal_data.get("description"),
                                current_quests=[]
                            )
                            current_sheet.goals.append(new_goal)
                            existing_goal_names_before[goal_name_lower] = new_goal
                    
                    # Then, add current_quests and skill_level to goals (both existing and newly added)
                    for goal_data in data["goals"]:
                        goal_name = goal_data.get("name", "")
                        goal_name_lower = goal_name.lower()
                        
                        # Find goal by name (case-insensitive)
                        goal_obj = None
                        for g in current_sheet.goals:
                            if g.name.lower() == goal_name_lower:
                                goal_obj = g
                                break
                        
                        if goal_obj:
                            # Add current_quests
                            if "current_quests" in goal_data:
                                for quest in goal_data["current_quests"]:
                                    if quest and quest not in goal_obj.current_quests:
                                        goal_obj.current_quests.append(quest)
                            
                            # Add skill_level if provided
                            if "skill_level" in goal_data and goal_data["skill_level"] is not None:
                                skill_level = goal_data["skill_level"]
                                # Ensure it's between 1-10
                                if isinstance(skill_level, (int, float)):
                                    goal_obj.skill_level = max(1, min(10, int(skill_level)))
                                elif isinstance(skill_level, str):
                                    try:
                                        goal_obj.skill_level = max(1, min(10, int(float(skill_level))))
                                    except (ValueError, TypeError):
                                        pass
            
            if "stats_career" in data: current_sheet.stats_career.update(data["stats_career"])
            if "stats_physical" in data: current_sheet.stats_physical.update(data["stats_physical"])
            if "stats_mental" in data: current_sheet.stats_mental.update(data["stats_mental"])
            if "stats_social" in data: current_sheet.stats_social.update(data["stats_social"])
                
            if "debuffs_analysis" in data:
                for item in data["debuffs_analysis"]:
                    name = item.get("name")
                    evidence = item.get("evidence", "")
                    confidence = item.get("confidence", "medium")
                    if name and name not in current_sheet.debuffs:
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
        if pending_debuffs is None: pending_debuffs = []
        if queued_goals is None: queued_goals = []
        
        # Phase 2 uses a completely separate, focused agent
        if phase == "phase2":
            return self._generate_phase2_response(history, current_sheet, feedback, current_pillar)
        
        # Calculate progress and determine missing pillars
        all_pillars_in_goals = set()
        for goal in current_sheet.goals:
            all_pillars_in_goals.update(goal.pillars)
        pillars_with_goals = list(all_pillars_in_goals)
        defined_pillars = len(pillars_with_goals)
        total_pillars = len(Pillar)
        
        # DEBUG: Log goals for debugging
        print(f"[DEBUG Architect] Current sheet has {len(current_sheet.goals)} goals:")
        for goal in current_sheet.goals:
            print(f"  - {goal.name}: {[p.value for p in goal.pillars]}")
        print(f"[DEBUG Architect] Pillars covered: {[p.value for p in all_pillars_in_goals]}")
        print(f"[DEBUG Architect] Missing pillars: {[p.value for p in Pillar if p not in all_pillars_in_goals]}")
        
        progress_pct = 0
        if phase == "phase1":
            progress_pct = min(int((defined_pillars / total_pillars) * 100), 75)
        elif phase == "phase2":
            total_goals = len(current_sheet.goals)
            total_quests = sum(len(g.current_quests) for g in current_sheet.goals)
            target_quests = max(total_goals, 1) * 2
            quest_progress = min(total_quests / target_quests * 25, 25) if target_quests > 0 else 0
            progress_pct = 75 + int(quest_progress)
        elif phase == "phase3" or phase == "phase3.5":
            progress_pct = 85
        elif phase == "phase4":
            progress_pct = 95
        else:
            progress_pct = 100

        missing_pillars = [p.value for p in Pillar if p not in all_pillars_in_goals]
        
        phase_instruction = ""
        
        # ------------------- PHASE 1: GOAL IDENTIFICATION -------------------
        if phase == "phase1":
            # Helper function to check if pillar has pure goal
            def has_pure_goal_for_pillar(goals, pillar):
                return any(len(g.pillars) == 1 and pillar in g.pillars for g in goals)
            
            pillars_needing_pure_goals = []
            for p in Pillar:
                if p in all_pillars_in_goals and not has_pure_goal_for_pillar(current_sheet.goals, p):
                    pillars_needing_pure_goals.append(p.value)
            
            queued_goals_text = ""
            if queued_goals:
                queued_list = "\n".join([f"- {g['name']} ({', '.join(g['pillars'])})" for g in queued_goals])
                queued_goals_text = f"\n- **Queued Goals for Current Pillar**: The user mentioned these goals earlier for {current_pillar if current_pillar else 'this pillar'}. Present them first:\n{queued_list}\n"
            
            current_pillar_text = f"Current Pillar Being Asked About: {current_pillar if current_pillar else 'None (all pillars have goals)'}"
            
            pure_goal_requirement = ""
            if current_pillar and current_pillar in pillars_needing_pure_goals:
                pure_goal_requirement = f"\n- **CRITICAL - PURE GOAL REQUIRED**: The {current_pillar} pillar currently has goals, but NONE of them are pure goals. You MUST ask the user for at least one pure goal for {current_pillar}."
            
            phase_instruction = f"""
        <system_phase_control>
            <current_phase>PHASE 1 - GOAL IDENTIFICATION</current_phase>
            <objective>Identify WHAT the user wants to achieve (goals) for each of the 4 pillars. Do not discuss "how", "when", or "ranking".</objective>
        </system_phase_control>

        <dynamic_context_data>
            <pure_goal_requirement>{pure_goal_requirement}</pure_goal_requirement>
            <current_pillar_text>{current_pillar_text}</current_pillar_text>
            <queued_goals_text>{queued_goals_text}</queued_goals_text>
            <missing_pillars_list>{', '.join(missing_pillars) if missing_pillars else 'None'}</missing_pillars_list>
        </dynamic_context_data>

        <critical_prohibitions>
            <ban_severity="CRITICAL">
                <rule>NEVER ASK ABOUT PRIORITIZATION.</rule>
                <description>Do not ask "Which is most important?", "Should we rank these?", or "What is your priority?". Prioritization is exclusively for Phase 3.5.</description>
            </ban_severity>
            <ban_severity="HIGH">
                <rule>NO IMPLEMENTATION TALK.</rule>
                <description>Do not ask about habits, routines, specific actions, costs, skills to learn, or "how" to achieve the goal. Stick strictly to the "What".</description>
            </ban_severity>
            <ban_severity="HIGH">
                <rule>NO PROBLEM INFERENCE.</rule>
                <description>Do not assume negative states (anxiety, stress, bad health) unless explicitly stated by the user. If a user has a goal like "Be calm," treat it as a goal, not a symptom of an anxiety disorder.</description>
            </ban_severity>
            <ban_severity="MEDIUM">
                <rule>ONE PILLAR ONLY.</rule>
                <description>Never ask about multiple missing pillars in a single message. Process them one by one.</description>
            </ban_severity>
        </critical_prohibitions>

        <execution_logic>
            <step_1_audit_state>
                **CRITICAL - YOU MUST DO THIS FIRST - DO NOT SKIP THIS STEP**:
                1. Open the &lt;current_sheet_state&gt; section in the system context above.
                2. **UNDERSTAND WHAT THIS IS**: The Current Sheet State contains ALL goals from ALL previous messages, accumulated over the entire conversation. It is NOT just the current message.
                3. **PARSE THE JSON**: Look for the "goals" array in the JSON. Extract EVERY goal from that array, regardless of when it was mentioned.
                4. **LIST ALL GOALS**: In your thinking, you MUST write: "Current Sheet State shows: [list ALL goals with their pillars]"
                   - Example: "Current Sheet State shows: 'Spike Volleyball' (PHYSICAL), 'Become a Chef' (CAREER), 'Be Calm Under Pressure' (MENTAL)"
                   - **CRITICAL**: If you see "Spike Volleyball" (PHYSICAL) in the list, Physical is COVERED. Do NOT think "Missing: Physical pillar".
                   - **CRITICAL**: If you see "Become a Chef" (CAREER) in the list, Career is COVERED. Do NOT think "Missing: Career pillar".
                5. **IDENTIFY COVERED PILLARS**: For each goal, note which pillar(s) it belongs to. If a pillar appears in ANY goal, that pillar is COVERED.
                6. **CHECK MISSING PILLARS LIST**: The &lt;missing_pillars_list&gt; field shows which pillars are missing - this is calculated from the Current Sheet State and is the SOURCE OF TRUTH.
                7. **ABSOLUTE RULE**: If a pillar has ANY goal in the Current Sheet State, that pillar is NOT missing. Do NOT ask about it.
                8. **ABSOLUTE RULE**: Do NOT determine missing pillars from conversation history. ONLY use the Current Sheet State.
                9. **ABSOLUTE RULE**: Do NOT think "User just mentioned X, so Y must be missing" - this is WRONG. Check the Current Sheet State.
                10. IF <missing_pillars_list> is empty, simply confirm goals and stop.
            </step_1_audit_state>

            <step_2_select_pillar>
                **ONLY AFTER STEP 1**: Select ONE missing pillar from <missing_pillars_list>.
                **CRITICAL**: Do NOT select a pillar that has goals in the Current Sheet State, even if you don't see it mentioned in the recent conversation.
                If the current interaction focuses on a specific pillar, stay on that pillar until a "Pure Goal" is extracted.
            </step_2_select_pillar>

            <step_3_formulate_question>
                Draft a question that asks strictly for the GOAL ("What do you want to achieve?").
                Ensure the question does not imply a solution or a habit.
                Example Correct: "What is your goal for your mental wellbeing?"
                Example Incorrect: "How do you currently manage stress?"
            </step_3_formulate_question>
        </execution_logic>

        <response_instructions>
            <instruction>You MUST output an internal reasoning block named &lt;thinking&gt; or &lt;analysis&gt; before your final response.</instruction>
            <instruction>🚨 CRITICAL - MANDATORY FORMAT - YOU MUST FOLLOW THIS EXACTLY 🚨</instruction>
            <instruction>In your &lt;thinking&gt; or &lt;analysis&gt;, you MUST follow this EXACT format (copy this structure exactly):
                1. **FIRST LINE (MANDATORY)**: "Current Sheet State shows: [list ALL goals with their pillars from the &lt;current_sheet_state&gt; section]"
                2. **SECOND LINE**: "Missing pillars: [list ONLY pillars that are NOT in the Current Sheet State, or 'None' if all 4 pillars have goals]"
                3. **THIRD LINE**: "Plan: [what you will ask about]"
            </instruction>
            <mandatory_format>
                **🚨 ABSOLUTE REQUIREMENT - YOUR THINKING MUST START WITH THIS EXACT PHRASE 🚨**
                Your &lt;thinking&gt; or &lt;analysis&gt; MUST start with the EXACT phrase: "Current Sheet State shows:"
                You CANNOT skip this step. You CANNOT determine missing pillars without first listing all goals from Current Sheet State.
                **VALIDATION**: Before you write "Missing: [pillar]", you MUST have first written "Current Sheet State shows: [list of goals]".
                If you write "Missing: Mental pillar" but did NOT first list all goals from Current Sheet State, you are WRONG.
                **IF YOUR THINKING DOES NOT START WITH "Current Sheet State shows:", YOU ARE VIOLATING THE RULES.**
                **HOW TO READ THE JSON**: 
                - Look for the "goals" field in the JSON (it's an array)
                - Each goal has a "name" field and a "pillars" field (array of pillar names)
                - Extract ALL goals from this array, regardless of when they were mentioned
                - Example JSON structure: {{"goals": [{{"name": "Spike Volleyball", "pillars": ["PHYSICAL"]}}, {{"name": "Become a Chef", "pillars": ["CAREER"]}}]}}
                - If you see this, you MUST write: "Current Sheet State shows: 'Spike Volleyball' (PHYSICAL), 'Become a Chef' (CAREER)"
                - **ALSO CHECK THE GOALS SUMMARY** at the top of &lt;current_sheet_state&gt; - it lists all goals in a readable format
            </mandatory_format>
            <critical_reminder>
                **ABSOLUTE CRITICAL REMINDER**: The Current Sheet State contains ALL goals that have been extracted so far, including goals from ALL previous messages.
                - If the user mentioned "Spike Volleyball" in message 1, it should be in the Current Sheet State as a PHYSICAL goal.
                - If the user mentioned "Become a Chef" in message 1, it should be in the Current Sheet State as a CAREER goal.
                - If the user mentioned "Be Calm Under Pressure" in message 2, it should be in the Current Sheet State as a MENTAL goal.
                - **ABSOLUTE RULE**: You MUST check the Current Sheet State to see ALL accumulated goals, not just the most recent message.
                - **ABSOLUTE RULE**: If "Spike Volleyball" (PHYSICAL) is in the Current Sheet State, Physical is COVERED. Do NOT think "Missing: Physical pillar".
                - **ABSOLUTE RULE**: If "Become a Chef" (CAREER) is in the Current Sheet State, Career is COVERED. Do NOT think "Missing: Career pillar".
                - **ABSOLUTE RULE**: Do NOT determine missing pillars by looking at conversation history. ONLY use the Current Sheet State.
            </critical_reminder>
            <example_correct_thinking>
                &lt;analysis&gt;
                Current Sheet State shows: 'Be Calm Under Pressure' (MENTAL), 'Become a Chef' (CAREER), 'Improve Networking' (SOCIAL), 'Spike Volleyball' (PHYSICAL).
                Missing pillars: None.
                Plan: Confirm goals and wait for system transition.
                &lt;/analysis&gt;
            </example_correct_thinking>
            <example_correct_thinking_2>
                &lt;analysis&gt;
                Current Sheet State shows: 'Be Calm Under Pressure' (MENTAL), 'Become a Chef' (CAREER).
                Missing pillars: Physical, Social.
                Plan: Ask about Physical pillar goals.
                &lt;/analysis&gt;
            </example_correct_thinking_2>
            <example_wrong_thinking>
                &lt;thinking&gt;
                User stated they want to "spike a volleyball."
                This is a physical activity goal.
                Missing: Mental and Social pillars.
                Plan: Ask about their mental wellbeing goals.
                &lt;/thinking&gt;
                **🚨 WRONG 🚨** - Did not check Current Sheet State first! Must start with "Current Sheet State shows:"
                **This is EXACTLY what you are doing wrong. Do NOT do this.**
            </example_wrong_thinking>
            <example_correct_thinking_3>
                &lt;thinking&gt;
                Current Sheet State shows: 'Become a Chef' (CAREER), 'Manage Stress & Remain Calm' (MENTAL), 'Improve Physical Fitness' (PHYSICAL).
                Missing pillars: Social.
                Plan: Ask about Social pillar goals.
                &lt;/thinking&gt;
                **CORRECT** - Started with "Current Sheet State shows:" and listed ALL goals, then determined missing pillars.
            </example_correct_thinking_3>
        </response_instructions>
        """

        # ------------------- PHASE 2: QUEST MAPPING -------------------
        elif phase == "phase2":
            current_pillar_enum = None
            if current_pillar:
                try:
                    current_pillar_enum = Pillar(current_pillar.upper())
                except ValueError: pass
            
            # Helper function to check if goal is complete for Phase 2
            def is_goal_complete_for_phase2(goal):
                """A goal is complete if it has 2+ quests OR has skill_level assessed (for 0-1 quest cases)."""
                return len(goal.current_quests) >= 2 or goal.skill_level is not None
            
            goals_for_current_pillar = []
            if current_pillar_enum:
                goals_for_current_pillar = [
                    g for g in current_sheet.goals 
                    if current_pillar_enum in g.pillars and not is_goal_complete_for_phase2(g)
                ]
            
            goals_list_text = ""
            if goals_for_current_pillar:
                goals_list = "\n".join([
                    f"  - {g.name} ({len(g.current_quests)}/2 quests): {', '.join(g.current_quests) if g.current_quests else 'No quests yet'}"
                    for g in goals_for_current_pillar
                ])
                goals_list_text = goals_list
            else:
                goals_list_text = "None in this pillar."
            
            current_pillar_text = f"{current_pillar if current_pillar else 'None'}"
            
            phase_instruction = f"""
        <system_phase_control>
            <current_phase>PHASE 2 - CURRENT QUESTS COLLECTION</current_phase>
            <objective>**PRIMARY OBJECTIVE**: Collect `current_quests` (what the user is CURRENTLY doing) for each goal, OR collect their skill level self-assessment if they have limited/no activities. This is DATA COLLECTION ONLY - you are gathering information about their current actions or skill level, not giving advice.</objective>
            <completion_criteria>
                A goal is complete for Phase 2 if:
                - It has 2+ current_quests, OR
                - It has skill_level assessed (for cases where user has 0-1 quests)
            </completion_criteria>
        </system_phase_control>
        
        <dynamic_context_data>
            <current_pillar>{current_pillar_text}</current_pillar>
            <goals_needing_quests>\n{goals_list_text}\n</goals_needing_quests>
        </dynamic_context_data>

        <critical_prohibitions>
            <ban_severity="CRITICAL">
                <rule>NO ADVICE GIVING.</rule>
                <description>Do not suggest solutions, habits, or things they "could" do. Only ask what they are ALREADY doing. Phase 2 is for DATA COLLECTION ONLY.</description>
            </ban_severity>
            <ban_severity="CRITICAL">
                <rule>DO NOT END CONVERSATION.</rule>
                <description>Always end with a question. You must collect quests or skill levels for all goals. Phase 2 continues until all goals are complete (2+ quests OR skill_level assessed).</description>
            </ban_severity>
            <ban_severity="HIGH">
                <rule>ONE GOAL AT A TIME.</rule>
                <description>Do not ask about multiple goals in one message. Focus on the first incomplete goal.</description>
            </ban_severity>
        </critical_prohibitions>

        <execution_logic>
            <step_1_audit_state>
                **CRITICAL - YOU MUST DO THIS FIRST**:
                1. Open the &lt;current_sheet_state&gt; section in the system context above.
                2. **UNDERSTAND WHAT THIS IS**: The Current Sheet State contains ALL goals from ALL previous messages, accumulated over the entire conversation.
                3. **PARSE THE JSON**: Look for the "goals" array in the JSON. Extract EVERY goal from that array.
                4. **LIST ALL GOALS**: In your thinking, you MUST write: "Current Sheet State shows: [list ALL goals with their pillars, quest counts, and skill_level if assessed]"
                   - Example: "Current Sheet State shows: 'Spike Volleyball' (PHYSICAL, 0/2 quests, skill_level: not assessed), 'Become a Chef' (CAREER, 2/2 quests), 'Be Calm Under Pressure' (MENTAL, 1/2 quests, skill_level: 3)"
            </step_1_audit_state>
            <step_2_target>
                Target the FIRST goal in <goals_needing_quests> that is incomplete (has < 2 quests AND no skill_level).
            </step_2_target>
            <step_3_inquiry>
                **FIRST ATTEMPT**: Ask: "What are you currently doing to work on [Goal Name]?"
                If they have 1 quest already, ask: "What else do you do for [Goal Name]?"
                
                **IF USER INDICATES LIMITED ACTIVITY** (0-1 quests):
                - If user says "I only do X" or "I don't do anything" or "I'm just starting out":
                  - Accept their answer (don't push for more quests)
                  - Ask: "On a scale of 1-10, how would you rate your current skill level in [Goal Name]?"
                  - The Critic will extract their skill level response
            </step_3_inquiry>
            <step_4_skill_assessment>
                **IF USER PROVIDES SKILL LEVEL**:
                - The Critic will extract it automatically
                - Mark this goal as complete for Phase 2
                - Move to the next incomplete goal
            </step_4_skill_assessment>
            <step_5_clarification>
                If the Critic provided feedback about a vague quest, ask for specifics (frequency, duration, specific output).
            </step_5_clarification>
        </execution_logic>

        <response_instructions>
            <instruction>Output an internal reasoning block named &lt;analysis&gt;.</instruction>
            <instruction>**MANDATORY FORMAT - YOU MUST FOLLOW THIS EXACTLY**:</instruction>
            <instruction>Your &lt;analysis&gt; MUST follow this EXACT structure:</instruction>
            <instruction>1. **FIRST LINE (MANDATORY)**: "Current Sheet State shows: [list ALL goals with their pillars and quest counts]"</instruction>
            <instruction>   Example: "Current Sheet State shows: 'Manage Stress' (MENTAL, 2/2 quests), 'Become a Chef' (CAREER, 2/2 quests), 'Spike a Volleyball' (PHYSICAL, 0/2 quests), 'Network' (SOCIAL, 0/2 quests)"</instruction>
            <instruction>2. **SECOND LINE**: "Missing quests/skill level: [specify EXACTLY what's missing]"</instruction>
            <instruction>   Example: "Missing quests/skill level: We need 2 more current quests for 'Spike a Volleyball' (PHYSICAL)"</instruction>
            <instruction>   Example: "Missing quests/skill level: We need 1 more current quest for 'Network' (SOCIAL), 2 more for 'Spike a Volleyball' (PHYSICAL)"</instruction>
            <instruction>   Example: "Missing quests/skill level: User has 0 quests for 'Spike a Volleyball' (PHYSICAL). Need to ask for skill level assessment."</instruction>
            <instruction>3. **THIRD LINE**: "Plan: [what you will ask about]"</instruction>
            <instruction>   Example: "Plan: Ask about current activities for 'Spike a Volleyball' goal"</instruction>
            <instruction>   Example: "Plan: User indicated limited activity. Ask for skill level self-assessment (1-10) for 'Spike a Volleyball' goal"</instruction>
            <instruction>**CRITICAL**: Be SPECIFIC about quest counts. Say "We need X more current quests for [Goal Name]" OR "User has 0-1 quests, need skill level assessment" not just "Missing: [Pillar]".</instruction>
            <instruction>Verify that you are asking about exactly ONE goal.</instruction>
            <instruction>Always end with a question about current quests for that goal.</instruction>
        </response_instructions>
        """

        # ------------------- PHASE 3: DEBUFF CONFIRMATION -------------------
        elif phase == "phase3":
            debuff_list = "\n".join([
                f"- {d['name']} (evidence: '{d.get('evidence', 'N/A')}', confidence: {d.get('confidence', 'medium')})"
                for d in pending_debuffs
            ])
            phase_instruction = f"""
        <system_phase_control>
            <current_phase>PHASE 3 - DEBUFF CONFIRMATION</current_phase>
            <objective>Validate potential negative traits (debuffs) identified by the Critic.</objective>
        </system_phase_control>
        
        <dynamic_context_data>
            <pending_debuffs>
            {debuff_list}
            </pending_debuffs>
        </dynamic_context_data>

        <execution_logic>
            <step_1_select>
                Select the first debuff in the list.
            </step_1_select>
            <step_2_present>
                Cite the user's own words (evidence).
            </step_2_present>
            <step_3_verify>
                Ask if they consider this a recurring hurdle or problem they want to address.
            </step_3_verify>
        </execution_logic>

        <response_instructions>
            <instruction>Output an internal reasoning block named &lt;analysis&gt;.</instruction>
            <instruction>Be empathetic but direct. Do not assume the debuff is true until confirmed.</instruction>
        </response_instructions>
        """

        # ------------------- PHASE 3.5: PRIORITIZATION -------------------
        elif phase == "phase3.5":
            goal_list = []
            for goal in current_sheet.goals:
                pillars_str = ", ".join([p.value for p in goal.pillars])
                goal_list.append(f"- {goal.name} ({pillars_str})")
            goals_text = "\n".join(goal_list) if goal_list else "your goals"
            
            phase_instruction = f"""
        <system_phase_control>
            <current_phase>PHASE 3.5 - GOAL PRIORITIZATION</current_phase>
            <objective>Rank the identified goals by importance to the user.</objective>
        </system_phase_control>
        
        <dynamic_context_data>
            <identified_goals>
            {goals_text}
            </identified_goals>
        </dynamic_context_data>

        <critical_prohibitions>
            <ban_severity="HIGH">
                <rule>NO "WHY" QUESTIONS.</rule>
                <description>Do not ask why they are prioritizing specific goals. Just ask for the ranking order.</description>
            </ban_severity>
        </critical_prohibitions>

        <execution_logic>
            <step_1_present>
                List all the goals clearly to the user.
            </step_1_present>
            <step_2_ask_ranking>
                Ask the user to rank them from 1 (Most Important) to N (Least Important).
                Example: "Please rank these goals from most to least important to you right now."
            </step_2_ask_ranking>
        </execution_logic>

        <response_instructions>
            <instruction>Output an internal reasoning block named &lt;analysis&gt;.</instruction>
        </response_instructions>
        """

        # ------------------- PHASE 4: SKILL TREE GENERATION -------------------
        elif phase == "phase4":
            phase_instruction = """
        <system_phase_control>
            <current_phase>PHASE 4 - SKILL TREE GENERATION</current_phase>
            <objective>Finalize the onboarding and transition to generation.</objective>
        </system_phase_control>

        <critical_prohibitions>
            <ban_severity="CRITICAL">
                <rule>NO FURTHER QUESTIONS.</rule>
                <description>Do not ask about goals, quests, or anything else. The process is complete.</description>
            </ban_severity>
        </critical_prohibitions>

        <execution_logic>
            <step_1_acknowledge>
                Acknowledge the user's ranking/input.
            </step_1_acknowledge>
            <step_2_announce>
                State that their custom Skill Tree is being generated now.
            </step_2_announce>
        </execution_logic>

        <response_instructions>
            <instruction>Output an internal reasoning block named &lt;analysis&gt;.</instruction>
            <instruction>Keep the response brief and encouraging.</instruction>
        </response_instructions>
        """
        
        # Format Critic feedback for display
        critic_feedback_text = ""
        if feedback:
            critic_feedback_text = f"\n<critic_feedback>{feedback}</critic_feedback>\n"
        
        # Create a human-readable goals summary
        goals_summary_lines = []
        for goal in current_sheet.goals:
            pillars_str = ", ".join([p.value for p in goal.pillars])
            if phase == "phase2":
                quest_count = len(goal.current_quests)
                skill_status = f", skill_level: {goal.skill_level}" if goal.skill_level else ", skill_level: not assessed"
                goals_summary_lines.append(f"- {goal.name} ({pillars_str}, {quest_count}/2 quests{skill_status})")
            else:
                goals_summary_lines.append(f"- {goal.name} ({pillars_str})")
        goals_summary = "\n".join(goals_summary_lines) if goals_summary_lines else "No goals yet"
        
        # Create a super simple, impossible-to-miss goals list
        # For Phase 2, include quest counts and skill_level; for Phase 1, just pillars
        if phase == "phase2":
            goals_list_simple = ", ".join([
                f"{g.name} ({', '.join([p.value for p in g.pillars])}, {len(g.current_quests)}/2 quests, skill_level: {g.skill_level if g.skill_level else 'not assessed'})"
                for g in current_sheet.goals
            ]) if current_sheet.goals else "No goals yet"
            thinking_format_instruction = f"Current Sheet State shows: {goals_list_simple}. Missing quests/skill level: [check goals_needing_quests in phase instructions]."
        else:
            goals_list_simple = ", ".join([f"{g.name} ({', '.join([p.value for p in g.pillars])})" for g in current_sheet.goals]) if current_sheet.goals else "No goals yet"
            thinking_format_instruction = f"Current Sheet State shows: {goals_list_simple}. Missing pillars: {', '.join(missing_pillars) if missing_pillars else 'None - All 4 pillars have goals!'}."
        
        covered_pillars_simple = ", ".join([p.value for p in all_pillars_in_goals]) if all_pillars_in_goals else "None"
        missing_pillars_simple = ", ".join(missing_pillars) if missing_pillars else "None - All 4 pillars have goals!"
        
        system_prompt_with_context = f"""
        **🚨🚨🚨 READ THIS FIRST - THIS IS THE SOURCE OF TRUTH 🚨🚨🚨**
        
        **ALL GOALS IN SHEET (from ALL previous messages):**
        {goals_list_simple}
        
        **PILLARS COVERED: {covered_pillars_simple}**
        **MISSING PILLARS: {missing_pillars_simple}**
        
        **ABSOLUTE RULE**: If a pillar is in "PILLARS COVERED" above, it is NOT missing. Do NOT ask about it.
        **ABSOLUTE RULE**: Only ask about pillars listed in "MISSING PILLARS" above.
        **ABSOLUTE RULE**: In your thinking, you MUST start with: "{thinking_format_instruction}"
        
        {ARCHITECT_SYSTEM_PROMPT}

        <system_context>
        Current Phase: {phase.upper()}
        Current Profile Completion: {progress_pct}%
        Missing Pillars: {missing_pillars_simple}
        Pending Debuffs: {len(pending_debuffs)} waiting for confirmation
        </system_context>
        
        <current_sheet_state>
        **🚨🚨🚨 CRITICAL - READ THIS FIRST - THIS IS THE SOURCE OF TRUTH 🚨🚨🚨**
        **This contains ALL goals from ALL previous messages, not just the current one.**
        **You MUST check this before determining what's missing.**
        **YOU CANNOT DETERMINE MISSING PILLARS WITHOUT READING THIS SECTION.**
        
        **📋 ALL ACCUMULATED GOALS (READ THIS FIRST - THESE ARE ALL GOALS FROM ALL MESSAGES):**
        {goals_summary}
        
        **✅ PILLARS COVERED BY THESE GOALS:**
        {', '.join([p.value for p in all_pillars_in_goals]) if all_pillars_in_goals else 'None'}
        
        **❌ MISSING PILLARS (calculated from goals above):**
        {', '.join(missing_pillars) if missing_pillars else 'None - All 4 pillars have goals!'}
        
        **🚨 ABSOLUTE RULES - YOU MUST FOLLOW THESE:**
        - If a goal appears in the list above, its pillar(s) are COVERED. Do NOT think that pillar is missing.
        - If "Be Calm Under Pressure" (MENTAL) is in the list above, Mental is COVERED. Do NOT think "Missing: Mental pillar".
        - If "Become a Chef" (CAREER) is in the list above, Career is COVERED. Do NOT think "Missing: Career pillar".
        - If "Spike Volleyball" (PHYSICAL) is in the list above, Physical is COVERED. Do NOT think "Missing: Physical pillar".
        - If "Improve Physical Fitness" (PHYSICAL) is in the list above, Physical is COVERED. Do NOT think "Missing: Physical pillar".
        - **IN YOUR THINKING, YOU MUST START WITH: "Current Sheet State shows: [list all goals from above]"**
        
        **FULL JSON (for verification - parse the "goals" array):**
        {current_sheet.model_dump_json()}
        </current_sheet_state>

        {critic_feedback_text}
        
        {phase_instruction}
        
        <global_instructions>
        1. **THINK FIRST**: Output a &lt;thinking&gt; or &lt;analysis&gt; block before your response.
        2. **CRITICAL - AUDIT STATE FIRST**: 
           - **BEFORE** determining what's missing, you MUST read the &lt;current_sheet_state&gt; section above.
           - **ABSOLUTE PROHIBITION**: Do NOT determine missing pillars from conversation history. You MUST check the Current Sheet State.
           - **ABSOLUTE PROHIBITION**: Do NOT think "User mentioned X and Y, so Z must be missing" - this is WRONG.
           - **CORRECT PROCESS**: 
             1. Open &lt;current_sheet_state&gt; section
             2. Extract ALL goals and their pillars from the JSON
             3. List them in your thinking: "Current Sheet State shows: [list all goals]"
             4. THEN determine what's missing based on that list
           - **ABSOLUTE RULE**: If a pillar has ANY goal in the Current Sheet State, that pillar is NOT missing. Do NOT ask about it.
           - **ABSOLUTE RULE**: Trust the &lt;missing_pillars_list&gt; field - it's calculated from the Current Sheet State and is the source of truth.
           - **ABSOLUTE RULE**: If you see "Be Calm Under Pressure" (MENTAL) in Current Sheet State, Mental is COVERED. Do NOT think "Missing: Mental pillar".
           - **ABSOLUTE RULE**: If you see "Become a Chef" (CAREER) in Current Sheet State, Career is COVERED. Do NOT think "Missing: Career pillar".
        3. **NO HALLUCINATIONS**: Do not assume the user has a job, hobby, or anxiety unless explicitly in the history.
        4. **PROGRESS BAR**: Append `[Progress: ||||||....] {progress_pct}%` to the end.
        </global_instructions>
        """

        if ask_for_prioritization:
            system_prompt_with_context += """
            <override_instruction>
            All pillars are full. Ignore missing pillars list.
            Transition to Prioritization now.
            </override_instruction>
            """
        else:
            if phase in ["phase3.5", "phase4", "phase5"] and not missing_pillars:
                 system_prompt_with_context += """
                <final_instruction>
                All data collected. Provide a brief, encouraging closing statement.
                </final_instruction>
                """

        messages = [{"role": "system", "content": system_prompt_with_context}]
        
        # Add few-shot examples with a warning
        messages.append({"role": "system", "content": "[IMPORTANT] The following examples are for TONE and STYLE only. Do NOT copy the content (e.g., if example mentions 'teacher', do not assume current user is a teacher)."})
        messages.extend(FEW_SHOT_EXAMPLES)
        
        # Add history
        messages.extend(history)
        
        # Inject feedback if present
        if feedback:
            messages.append({"role": "system", "content": f"<critic_feedback_injection>{feedback}</critic_feedback_injection>"})

        response = llm_client.chat_completion(messages)
        
        # Extract and log thinking block before stripping
        thinking_content = ""
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL | re.IGNORECASE)
        # Also check for <analysis> since we updated the prompts
        if not thinking_match:
            thinking_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL | re.IGNORECASE)
            
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            print(f"[Architect Thinking]\n{thinking_content}\n")
            
            # Validate that thinking starts with "Current Sheet State shows:"
            if not thinking_content.strip().startswith("Current Sheet State shows:"):
                print(f"[WARNING] Architect thinking does NOT start with 'Current Sheet State shows:' - this violates the rules!")
                print(f"[WARNING] Thinking content: {thinking_content[:200]}...")
                
                # ALWAYS prepend the correct format, regardless of other issues
                # For Phase 2, use quest-focused format; for Phase 1, use pillar format
                if phase == "phase2":
                    # Phase 2 format: focus on quest status
                    goals_with_quests = []
                    for g in current_sheet.goals:
                        quest_count = len(g.current_quests)
                        skill_status = f"skill_level: {g.skill_level}" if g.skill_level else "skill_level: not assessed"
                        goals_with_quests.append(f"{g.name} ({', '.join([p.value for p in g.pillars])}, {quest_count}/2 quests, {skill_status})")
                    goals_list_phase2 = ", ".join(goals_with_quests)
                    correct_prefix = f"Current Sheet State shows: {goals_list_phase2}.\n\n[NOTE: Previous thinking was missing the required 'Current Sheet State shows:' prefix - corrected above]"
                else:
                    # Phase 1 format: focus on pillars
                    correct_prefix = f"Current Sheet State shows: {goals_list_simple}. Missing pillars: {missing_pillars_simple}.\n\n[NOTE: Previous thinking was missing the required 'Current Sheet State shows:' prefix - corrected above]"
                thinking_content = correct_prefix + "\n\n" + thinking_content
                
                # Check if the Architect is incorrectly saying pillars are missing when they're not
                # Extract what pillars the Architect thinks are missing
                missing_mentions = []
                for pillar in ["MENTAL", "PHYSICAL", "CAREER", "SOCIAL"]:
                    if f"Missing: {pillar}" in thinking_content or f"missing: {pillar}" in thinking_content or f"Missing: {pillar.lower()}" in thinking_content or f"missing: {pillar.lower()}" in thinking_content:
                        missing_mentions.append(pillar)
                    # Also check for "Career and Mental" or "Career, Mental" patterns
                    if f"Career" in thinking_content and f"Mental" in thinking_content and ("Missing" in thinking_content or "missing" in thinking_content):
                        if "Career" not in missing_mentions:
                            missing_mentions.append("CAREER")
                        if "Mental" not in missing_mentions:
                            missing_mentions.append("MENTAL")
                
                # Check if any of these are actually covered
                covered_pillar_values = [p.value for p in all_pillars_in_goals]
                incorrectly_missing = [p for p in missing_mentions if p in covered_pillar_values]
                
                if incorrectly_missing:
                    print(f"[ERROR] Architect incorrectly thinks these pillars are missing (but they're covered): {incorrectly_missing}")
                    print(f"[ERROR] Covered pillars: {covered_pillar_values}")
                    print(f"[ERROR] Actual missing pillars: {missing_pillars}")
                    # Correct the thinking content by removing the contradiction
                    # For Phase 2, replace with quest-focused format; for Phase 1, use pillar format
                    if phase == "phase2":
                        # Phase 2: Replace "Missing pillars" with "Missing quests/skill level" format
                        thinking_content = re.sub(
                            r"Missing.*?pillars.*?:.*?[\.\n]",
                            "Missing quests/skill level: [check goals_needing_quests above].",
                            thinking_content,
                            flags=re.IGNORECASE
                        )
                    else:
                        # Phase 1: Replace incorrect "Missing: X" statements with correct ones
                        for pillar in incorrectly_missing:
                            thinking_content = re.sub(
                                rf"Missing:.*?{pillar}.*?[\.\n]",
                                f"Missing pillars: {missing_pillars_simple}.",
                                thinking_content,
                                flags=re.IGNORECASE
                            )
                        # If all pillars are covered, ensure thinking says "Missing pillars: None"
                        if not missing_pillars:
                            thinking_content = re.sub(
                                r"Missing.*?:.*?[\.\n]",
                                "Missing pillars: None - All 4 pillars have goals!.",
                                thinking_content,
                                flags=re.IGNORECASE
                            )
                    print(f"[CORRECTED] Updated thinking content to remove contradiction")
        
        # Hide internal thinking traces from the user-facing chat
        visible_response = _strip_thinking_block(response)
        # Also strip analysis block if present
        visible_response = re.sub(r"<analysis>.*?</analysis>", "", visible_response, flags=re.DOTALL | re.IGNORECASE).strip()
        
        return visible_response, thinking_content
    
    def _generate_phase2_response(self, history: List[Dict[str, str]], current_sheet: CharacterSheet, feedback: str = "", current_pillar: str = None) -> Tuple[str, str]:
        """
        Dedicated Phase 2 agent - ONLY collects current quests and skill levels.
        NO goal questions, NO pillar questions, ONLY quest collection.
        """
        from src.llm import LLMClient
        llm_client = LLMClient()
        
        # Helper function to check if goal is complete for Phase 2
        def is_goal_complete_for_phase2(goal):
            return len(goal.current_quests) >= 2 or goal.skill_level is not None
        
        # Find the first incomplete goal
        current_pillar_enum = None
        if current_pillar:
            try:
                current_pillar_enum = Pillar(current_pillar.upper())
            except ValueError:
                pass
        
        incomplete_goals = []
        if current_pillar_enum:
            incomplete_goals = [
                g for g in current_sheet.goals 
                if current_pillar_enum in g.pillars and not is_goal_complete_for_phase2(g)
            ]
        else:
            # If no current pillar, find first incomplete goal across all pillars
            for p in Pillar:
                incomplete_goals = [
                    g for g in current_sheet.goals 
                    if p in g.pillars and not is_goal_complete_for_phase2(g)
                ]
                if incomplete_goals:
                    break
        
        if not incomplete_goals:
            return "Great! I've collected all the information I need about what you're currently doing. Let's move on.", "Phase 2 complete - all goals have quests or skill levels."
        
        target_goal = incomplete_goals[0]
        quest_count = len(target_goal.current_quests)
        
        # Build a super simple, focused prompt for Phase 2
        goals_status = "\n".join([
            f"- {g.name}: {len(g.current_quests)}/2 quests, skill_level: {g.skill_level if g.skill_level else 'not assessed'}"
            for g in current_sheet.goals
        ])
        
        system_prompt = f"""You are a data collector. Your ONLY job is to ask about what the user is CURRENTLY doing for their goals.

**CRITICAL RULES - YOU MUST FOLLOW THESE:**
1. **ONLY ASK ABOUT CURRENT QUESTS** - What are they ALREADY doing? NOT what they want to do.
2. **NEVER ASK ABOUT GOALS** - All goals are already identified. Do NOT ask "what is your goal" or "what do you want to achieve".
3. **NEVER ASK ABOUT MISSING PILLARS** - Do NOT mention pillars, missing areas, or what's not covered.
4. **ONE GOAL AT A TIME** - Focus on ONE goal per message.

**CURRENT STATUS:**
{goals_status}

**TARGET GOAL TO ASK ABOUT:**
Goal: "{target_goal.name}"
Current quests: {quest_count}/2
Skill level: {'Assessed: ' + str(target_goal.skill_level) if target_goal.skill_level else 'Not assessed'}

**YOUR TASK:**
Ask the user what they are CURRENTLY doing to work on "{target_goal.name}".

**EXAMPLES OF GOOD QUESTIONS:**
- "What are you currently doing to work on [Goal Name]?"
- "Tell me what you're already doing for [Goal Name]."
- "What activities are you doing right now for [Goal Name]?"

**EXAMPLES OF BAD QUESTIONS (DO NOT ASK THESE):**
- "What is your goal for [area]?" ❌ (This is Phase 1, not Phase 2)
- "What do you want to achieve?" ❌ (This is Phase 1, not Phase 2)
- "What about your [pillar] goals?" ❌ (Do not mention pillars or goals)
- "What else do you want to do?" ❌ (Focus on what they ARE doing, not what they WANT to do)

**IF USER HAS 0-1 QUESTS:**
If the user indicates they have limited or no current activities, ask: "On a scale of 1-10, how would you rate your current skill level in [Goal Name]?"

**OUTPUT FORMAT:**
Start with: "Current quest status: [Goal Name] has {quest_count}/2 quests."
Then ask your question.

Keep it simple and direct. No fluff, no goal questions, just quest collection."""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        
        if feedback:
            messages.append({"role": "system", "content": f"<critic_feedback>{feedback}</critic_feedback>"})
        
        response = llm_client.chat_completion(messages)
        
        # Extract thinking if present
        thinking_content = ""
        thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL | re.IGNORECASE)
        if not thinking_match:
            thinking_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL | re.IGNORECASE)
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            print(f"[Phase 2 Architect Thinking]\n{thinking_content}\n")
        
        # Strip thinking from response
        visible_response = re.sub(r"<thinking>.*?</thinking>", "", response, flags=re.DOTALL | re.IGNORECASE).strip()
        visible_response = re.sub(r"<analysis>.*?</analysis>", "", visible_response, flags=re.DOTALL | re.IGNORECASE).strip()
        
        return visible_response, thinking_content