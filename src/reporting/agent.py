from __future__ import annotations

from typing import List, Dict, Optional, Any
import json
import re

from src.llm import LLMClient
from src.models import (
    CharacterSheet,
    SkillTree,
    DailyTask,
    DailyReport,
    DailyTaskReport,
    ReportingState,
    ReportingPhase,
    DailyTaskStatus,
    StatsDelta,
    SkillNode,
    NodeType,
    DailyScheduleItem,
    Pillar,
    Decision,
    ContributingFactor,
    NodeStatus,
    HabitProgress,
)
from .prompts import REPORTING_CONVERSATION_PROMPT, REPORTING_JSON_PROMPT_TEMPLATE, DECISION_GENERATION_PROMPT_TEMPLATE, DECISION_LOGIC_RULES
from .utils import verify_citations
from .progression import check_progression
from .scheduler_agent import SchedulerAgent
from datetime import datetime, timedelta


class ReportingAgent:
    """Handles the daily reporting conversation and final JSON summarization.

    This initial implementation keeps things deliberately simple:
    - Conversational replies are template based (no LLM yet) so the flow is stable.
    - Final reports are generated in a naive way without calling the JSON LLM.

    Once the flow feels good, we can switch `finalize_report` to use
    `REPORTING_JSON_PROMPT_TEMPLATE` and the LLM in json_mode.
    """

    def __init__(self) -> None:
        self.llm_client = LLMClient()
        # Lazy initialization of memory components (only when needed)
        self._memory = None
        self._significance_scorer = None
        self.scheduler_agent = SchedulerAgent(self.llm_client)
    
    def _get_memory(self, user_id: str):
        """Lazy initialization of semantic memory."""
        if self._memory is None:
            from src.memory.vector_store import SemanticMemory
            self._memory = SemanticMemory(user_id=user_id, significance_threshold=7)
        return self._memory
    
    def _get_significance_scorer(self):
        """Lazy initialization of significance scorer."""
        if self._significance_scorer is None:
            from src.memory.significance import SignificanceScorer
            self._significance_scorer = SignificanceScorer()
        return self._significance_scorer

    @staticmethod
    def _format_tasks_for_display(tasks: List[DailyTask]) -> str:
        lines = []
        for t in tasks:
            lines.append(
                f"- [{t.pillar.value}] {t.name} (planned reps: {t.planned_repetitions})"
            )
        return "\n".join(lines) if lines else "(no tasks scheduled)"

    def initial_message(self, state: ReportingState, sheet: CharacterSheet) -> str:
        """Generate the first message explaining what to report on, using schedule status."""
        # Get today's schedule if it exists
        todays_schedule = sheet.daily_schedule.get(state.current_date, [])
        
        # Build a map of node_id -> schedule item for quick lookup
        schedule_by_node: Dict[str, DailyScheduleItem] = {
            item.node_id: item for item in todays_schedule if item.node_id
        }
        
        # Categorize tasks by their schedule status
        completed_tasks: List[str] = []
        skipped_tasks: List[str] = []
        pending_tasks: List[str] = []
        partial_tasks: List[str] = []
        
        for task in state.todays_tasks:
            schedule_item = schedule_by_node.get(task.node_id)
            if schedule_item:
                status = schedule_item.status
                time_str = schedule_item.time if schedule_item.time else ""
                task_display = f"{task.name}"
                if time_str:
                    task_display = f"{time_str} - {task_display}"
                
                if status == DailyTaskStatus.DONE:
                    completed_tasks.append(task_display)
                elif status == DailyTaskStatus.SKIPPED:
                    skipped_tasks.append(task_display)
                elif status == DailyTaskStatus.PARTIAL:
                    partial_tasks.append(task_display)
                else:  # PENDING or default
                    pending_tasks.append(task_display)
            else:
                # No schedule item found, assume pending
                pending_tasks.append(task.name)
        
        # Build context message
        intro = "Let's do a quick daily check-in. Here's what I see from your schedule:\n\n"
        
        context_parts = []
        
        if completed_tasks:
            context_parts.append(f"✅ Completed: {', '.join(completed_tasks)}")
        
        if partial_tasks:
            context_parts.append(f"⚠️ Partially done: {', '.join(partial_tasks)}")
        
        if skipped_tasks:
            context_parts.append(f"❌ Skipped: {', '.join(skipped_tasks)}")
        
        if pending_tasks:
            context_parts.append(f"⏳ Still pending: {', '.join(pending_tasks)}")
        
        if not context_parts:
            # Fallback if no schedule data
            tasks_block = self._format_tasks_for_display(state.todays_tasks)
            context_parts.append(tasks_block)
        
        context = "\n".join(context_parts)
        
        # Single question to invite feedback
        question = (
            "\n\nWhat worked well today, and what didn't? "
            "Feel free to share any adjustments you'd like to make to these habits or their timing."
        )
        
        return intro + context + question

    def generate_reply(
        self,
        state: ReportingState,
        sheet: CharacterSheet,
        tree: SkillTree,
        user_message: str,
    ) -> Dict[str, Any]:
        """Conversational reply that manages the reporting flow through state machine phases.

        Returns a dict with:
        - text: The reply message
        - decisions: Optional list of Decision objects (for PROGRESSION phase)
        - schedule_preview: Optional list of DailyScheduleItem (for SCHEDULING phase)
        - phase: Current phase after this turn
        """
        # Normalize phase to ReportingPhase enum if it's a string
        if isinstance(state.phase, str):
            try:
                state.phase = ReportingPhase(state.phase)
            except ValueError:
                # Default to REVIEW if phase string doesn't match
                state.phase = ReportingPhase.REVIEW
        
        lowered = user_message.strip().lower()

        # --- PHASE 1: REVIEW ---
        if state.phase == ReportingPhase.REVIEW:
            # Check exit condition
            if self._is_user_done(user_message):
                # TRANSITION -> PROGRESSION
                state.phase = ReportingPhase.PROGRESSION
                decisions = check_progression(sheet, tree)
                
                if decisions:
                    state.pending_decisions = decisions
                    return {
                        "text": "Great work today! You've mastered some skills! Review these upgrades:",
                        "decisions": [d.model_dump() for d in decisions],
                        "schedule_preview": None,
                        "phase": state.phase.value,
                    }
                else:
                    # Skip Progression if nothing to upgrade
                    state.phase = ReportingPhase.SCHEDULING
                    return {
                        "text": "Logged. Now, what does your availability look like tomorrow?",
                        "decisions": None,
                        "schedule_preview": None,
                        "phase": state.phase.value,
                    }
            
            # Regular review conversation
            reply_text = self._generate_review_response(state, sheet, tree, user_message)
            return {
                "text": reply_text,
                "decisions": None,
                "schedule_preview": None,
                "phase": state.phase.value,
            }

        # --- PHASE 2: PROGRESSION ---
        elif state.phase == ReportingPhase.PROGRESSION:
            # User should have accepted/reviewed decisions
            # Parse user input for decision acceptance/rejection
            
            # Check for rejection/skip keywords
            if any(keyword in lowered for keyword in ["skip", "reject", "not now", "later", "no thanks"]):
                # User wants to skip all decisions
                state.pending_decisions = []
                state.phase = ReportingPhase.SCHEDULING
                return {
                    "text": "Got it, skipping upgrades for now. What does your availability look like for tomorrow?",
                    "decisions": None,
                    "schedule_preview": None,
                    "phase": state.phase.value,
                }
            
            # Check for acceptance keywords
            if any(keyword in lowered for keyword in ["accept", "accepted", "yes", "ok", "apply", "done"]):
                # Parse which decisions to accept
                accepted_decisions = self._parse_decision_acceptance(
                    user_message, 
                    state.pending_decisions
                )
                
                if accepted_decisions:
                    # Apply only accepted decisions
                    self._apply_progression_decisions(sheet, tree, accepted_decisions)
                    
                    # Remove accepted decisions from pending
                    accepted_ids = {d.id for d in accepted_decisions}
                    state.pending_decisions = [
                        d for d in state.pending_decisions 
                        if d.id not in accepted_ids
                    ]
                    
                    # TRANSITION -> SCHEDULING
                    state.phase = ReportingPhase.SCHEDULING
                    state.pending_decisions = []
                    
                    accepted_count = len(accepted_decisions)
                    return {
                        "text": f"Upgrades applied! ({accepted_count} upgrade{'s' if accepted_count != 1 else ''} accepted) Now, what does your availability look like for tomorrow?",
                        "decisions": None,
                        "schedule_preview": None,
                        "phase": state.phase.value,
                    }
                else:
                    # User said "accept" but we couldn't parse which ones - accept all
                    self._apply_progression_decisions(sheet, tree, state.pending_decisions)
                    state.phase = ReportingPhase.SCHEDULING
                    state.pending_decisions = []
                    return {
                        "text": "All upgrades applied! Now, what does your availability look like for tomorrow?",
                        "decisions": None,
                        "schedule_preview": None,
                        "phase": state.phase.value,
                    }
            else:
                # Still in progression, waiting for acceptance
                # Show decisions again with clearer instructions
                decision_list = "\n".join([
                    f"  • {d.target} → {d.new_value}"
                    for d in state.pending_decisions
                ])
                return {
                    "text": f"I've found {len(state.pending_decisions)} upgrade{'s' if len(state.pending_decisions) != 1 else ''} available:\n\n{decision_list}\n\nType 'accept' to apply all, 'accept 1,2' to accept specific ones, or 'skip' to skip for now.",
                    "decisions": [d.model_dump() for d in state.pending_decisions],
                    "schedule_preview": None,
                    "phase": state.phase.value,
                }

        # --- PHASE 3: SCHEDULING ---
        elif state.phase == ReportingPhase.SCHEDULING:
            # User input is availability: "Busy 9-5, free evening"
            
            # 1. Get Active Tasks (Freshly updated from Phase 2)
            active_nodes = self._get_active_nodes(sheet, tree)
            
            if not active_nodes:
                # No active tasks to schedule
                state.phase = ReportingPhase.COMPLETED
                return {
                    "text": "No active tasks to schedule. Reporting session complete!",
                    "decisions": None,
                    "schedule_preview": None,
                    "phase": state.phase.value,
                }
            
            # 2. Run Scheduler (use current_date from state for timezone safety)
            tomorrow_date = self._get_tomorrow_date_str(state.current_date)
            schedule, is_fallback = self.scheduler_agent.generate_schedule(
                user_constraints=user_message,
                tasks=active_nodes,
                priorities=sheet.pillar_rankings if sheet.pillar_rankings else [Pillar.PHYSICAL, Pillar.CAREER, Pillar.MENTAL, Pillar.SOCIAL],
                date_str=tomorrow_date
            )
            
            state.tomorrow_schedule = schedule
            state.phase = ReportingPhase.COMPLETED
            
            # Format schedule preview message
            schedule_text = "\n".join([
                f"  {item.time} - {item.label}"
                for item in schedule[:5]  # Show first 5 items
            ])
            if len(schedule) > 5:
                schedule_text += f"\n  ... and {len(schedule) - 5} more"
            
            # Add warning if fallback was used
            warning_msg = ""
            if is_fallback:
                warning_msg = "\n\n⚠️ Note: I couldn't generate a smart schedule based on your constraints, so I've created a basic template. You may want to adjust the times based on your availability."
            
            return {
                "text": f"I've drafted your schedule for tomorrow:\n\n{schedule_text}{warning_msg}\n\nType 'confirm' to save this schedule.",
                "decisions": None,
                "schedule_preview": [item.model_dump() for item in schedule],
                "phase": state.phase.value,
            }

        # --- PHASE 4: COMPLETED ---
        elif state.phase == ReportingPhase.COMPLETED:
            # Finalize and save
            if "confirm" in lowered or "yes" in lowered or "done" in lowered:
                return {
                    "text": "Schedule saved! Reporting session complete.",
                    "decisions": None,
                    "schedule_preview": [item.model_dump() for item in state.tomorrow_schedule] if state.tomorrow_schedule else None,
                    "phase": state.phase.value,
                }
            else:
                return {
                    "text": "Type 'confirm' to save the schedule, or let me know if you'd like to adjust it.",
                    "decisions": None,
                    "schedule_preview": [item.model_dump() for item in state.tomorrow_schedule] if state.tomorrow_schedule else None,
                    "phase": state.phase.value,
                }
        
        # Fallback
        return {
            "text": "I'm not sure what phase we're in. Let's start over.",
            "decisions": None,
            "schedule_preview": None,
            "phase": ReportingPhase.REVIEW.value,
        }
    
    def _is_user_done(self, user_message: str) -> bool:
        """Check if user indicates they're done reporting."""
        lowered = user_message.strip().lower()
        return any(keyword in lowered for keyword in ["done", "confirm", "finished", "that's all", "that's it"])

    def _generate_review_response(
        self,
        state: ReportingState,
        sheet: CharacterSheet,
        tree: SkillTree,
        user_message: str,
    ) -> str:
        """Generate a conversational reply during the REVIEW phase."""
        lowered = user_message.strip().lower()

        # First reply after the initial prompt.
        if not state.conversation_history:
            return (
                "Got it. Tell me how today went for those tasks – what you did, "
                "roughly how long, and anything that felt easy or hard. When you're done, type 'confirm'."
            )

        # Very lightweight sentiment flags.
        negative_markers = [
            "hard",
            "difficult",
            "useless",
            "blocked",
            "confusing",
            "too many",
            "overwhelming",
            "stuck",
        ]
        positive_markers = [
            "went well",
            "pretty well",
            "great",
            "good",
            "smooth",
            "easy",
            "satisfying",
            "solid",
        ]

        has_negative = any(m in lowered for m in negative_markers)
        has_positive = any(m in lowered for m in positive_markers)

        # Try to match parts of the user's message to today's tasks by keyword.
        mentioned_tasks: List[DailyTask] = []
        for task in state.todays_tasks:
            # Use a few distinctive words from the task name as fuzzy anchors.
            name_words = [w.strip(".,-()") for w in task.name.split()]
            keywords = {w.lower() for w in name_words if len(w) >= 4}
            if not keywords:
                continue
            if any(kw in lowered for kw in keywords):
                mentioned_tasks.append(task)

        # Build a short, concrete response.
        if not mentioned_tasks:
            # Generic acknowledgement when we can't confidently map to a task.
            base = "Thanks, I noted that."

            # Special-case a couple of common phrases that may refer to tasks
            # from previous days or the wider skill tree.
            if "database schema" in lowered:
                follow = (
                    " It sounds like the database schema work had too many options, "
                    "so it was hard to know what to focus on. Next time, would it help "
                    "if we picked just one table or one concrete question to explore?"
                )
            elif "sensation of breath" in lowered or "focus on the breath" in lowered or "focusing on the sensation of breath" in lowered:
                follow = (
                    " Focusing on the sensation of breath sounded frustrating and maybe pointless. "
                    "If that style of mindfulness doesn't click for you, we can swap it for a "
                    "different grounding habit (like a short walk, stretching, or journaling). "
                    "What would feel more useful instead?"
                )
            elif has_negative and not has_positive:
                follow = (
                    " It sounds like some of this felt challenging – if there's a specific habit "
                    "you want to adjust or drop, tell me which one."
                )
            elif has_positive and not has_negative:
                follow = " Sounds like today went reasonably well. Feel free to walk me through a couple of tasks."
            else:
                follow = " Feel free to share a bit more detail for any tasks that stood out."

            return base + follow + " When you're ready, type 'confirm'."

        # Focus on at most a couple of tasks so the reply stays short.
        tasks_to_comment = mentioned_tasks[:2]
        task_summaries: List[str] = []
        for t in tasks_to_comment:
            if has_negative and not has_positive:
                task_summaries.append(f"For {t.name}, it sounds like it felt a bit tough today.")
            elif has_positive and not has_negative:
                task_summaries.append(f"Nice work on {t.name} – sounds like you made good progress.")
            else:
                task_summaries.append(f"Got your notes about {t.name}.")

        response = " ".join(task_summaries)

        # Ask one clarifying question if there was friction.
        if has_negative:
            # Check if user wants modifications
            modification_keywords = ["too hard", "easier", "replace", "instead", "change", "modify", "adjust"]
            if any(kw in lowered for kw in modification_keywords):
                # Propose skill tree modifications
                proposed_mods = self._propose_skill_tree_modifications(
                    state, sheet, tree, user_message
                )
                
                if proposed_mods:
                    # Store in state for later use in finalize_report
                    state.proposed_skill_modifications.extend(proposed_mods)
                    
                    mod_names = [m.name for m in proposed_mods]
                    response += f" I can create easier or alternative versions: {', '.join(mod_names)}. Should I add these to your skill tree?"
                    return response
            
            response += (
                " What, specifically, made those tricky – not knowing where to start, "
                "too many options, low energy, or something else?"
            )
        else:
            response += " If there are any habits you want to tweak or replace, tell me which ones."

        response += " When you're ready for me to summarize the day, type 'confirm'."
        return response
    
    def _apply_progression_decisions(
        self,
        sheet: CharacterSheet,
        tree: SkillTree,
        decisions: List[Decision],
    ) -> None:
        """Apply progression decisions by unlocking next nodes and marking current ones as mastered."""
        from src.reporting.scheduler import mark_newly_unlocked_nodes
        
        for decision in decisions:
            # Mark the current node as mastered
            if decision.target_habit_id and decision.target_habit_id in sheet.habit_progress:
                sheet.habit_progress[decision.target_habit_id].status = NodeStatus.MASTERED
            
            # The next node will be unlocked via mark_newly_unlocked_nodes
        
        # Unlock any nodes that now have all prerequisites mastered
        mark_newly_unlocked_nodes(sheet, tree)
    
    def _get_active_nodes(self, sheet: CharacterSheet, tree: SkillTree) -> List[SkillNode]:
        """Get all active SkillNodes from the tree."""
        active_nodes = []
        
        for node in tree.nodes:
            if node.type != NodeType.HABIT:
                continue
            
            # Ensure progress entry exists
            if node.id not in sheet.habit_progress:
                sheet.habit_progress[node.id] = HabitProgress(node_id=node.id)
            
            progress = sheet.habit_progress[node.id]
            
            # Only include ACTIVE nodes (not LOCKED or MASTERED)
            if progress.status == NodeStatus.ACTIVE:
                active_nodes.append(node)
        
        return active_nodes
    
    def _get_tomorrow_date_str(self, current_date: Optional[str] = None) -> str:
        """Get tomorrow's date as ISO string.
        
        Args:
            current_date: ISO date string (YYYY-MM-DD). If None, uses datetime.now()
        """
        if current_date:
            # Parse current_date and add 1 day
            try:
                date_obj = datetime.strptime(current_date, "%Y-%m-%d").date()
                tomorrow = date_obj + timedelta(days=1)
                return tomorrow.isoformat()
            except ValueError:
                # Fallback to datetime.now() if parsing fails
                pass
        
        # Fallback: use datetime.now() (should be avoided in production)
        tomorrow = datetime.now() + timedelta(days=1)
        return tomorrow.date().isoformat()
    
    def _parse_decision_acceptance(
        self,
        user_message: str,
        pending_decisions: List[Decision],
    ) -> List[Decision]:
        """
        Parse user message to determine which decisions to accept.
        
        Supports:
        - "accept all" or "accept" → all decisions
        - "accept 1,2,3" → decisions by index (1-indexed)
        - "accept first" → first decision
        - JSON format: {"accepted_ids": ["id1", "id2"]} → by decision ID
        
        Args:
            user_message: User's input message
            pending_decisions: List of pending Decision objects
            
        Returns:
            List of Decision objects to accept (empty if none)
        """
        if not pending_decisions:
            return []
        
        lowered = user_message.lower().strip()
        
        # Try to parse JSON format first (for future frontend integration)
        try:
            import json
            # Look for JSON in the message
            if "{" in user_message and "}" in user_message:
                json_start = user_message.find("{")
                json_end = user_message.rfind("}") + 1
                json_str = user_message[json_start:json_end]
                parsed = json.loads(json_str)
                
                if "accepted_ids" in parsed:
                    accepted_ids = set(parsed["accepted_ids"])
                    return [d for d in pending_decisions if d.id in accepted_ids]
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Check for "accept all" or just "accept" (accept all)
        if "accept all" in lowered or (lowered == "accept" or lowered.startswith("accept")):
            # Check if specific indices are mentioned
            # Look for patterns like "accept 1,2,3" or "accept 1 2 3"
            number_pattern = r'accept\s+(\d+(?:\s*[,\s]\s*\d+)*)'
            match = re.search(number_pattern, lowered)
            
            if match:
                # Parse indices (1-indexed)
                indices_str = match.group(1)
                indices = [
                    int(x.strip()) - 1  # Convert to 0-indexed
                    for x in re.split(r'[,\s]+', indices_str)
                    if x.strip().isdigit()
                ]
                # Filter valid indices
                valid_indices = [i for i in indices if 0 <= i < len(pending_decisions)]
                if valid_indices:
                    return [pending_decisions[i] for i in valid_indices]
            
            # Check for "first", "last", etc.
            if "first" in lowered:
                return [pending_decisions[0]] if pending_decisions else []
            if "last" in lowered:
                return [pending_decisions[-1]] if pending_decisions else []
            
            # Default: accept all
            return pending_decisions
        
        return []

    def _propose_skill_tree_modifications(
        self,
        state: ReportingState,
        sheet: CharacterSheet,
        tree: SkillTree,
        user_feedback: str,
    ) -> List[SkillNode]:
        """Analyze user feedback and propose skill tree modifications.
        
        Returns list of new/modified SkillNodes to add to the tree.
        """
        modifications: List[SkillNode] = []
        lowered_feedback = user_feedback.lower()
        
        # Pattern: Task is too hard → suggest easier variant
        if any(word in lowered_feedback for word in ["too hard", "too difficult", "overwhelming", "can't do"]):
            # Find mentioned tasks and create easier variants
            for task in state.todays_tasks:
                task_words = set(w.lower() for w in task.name.split() if len(w) >= 4)
                if any(word in lowered_feedback for word in task_words):
                    # Create an easier variant node
                    original_node = next((n for n in tree.nodes if n.id == task.node_id), None)
                    if original_node:
                        easier_id = f"{task.node_id}_easier_variant"
                        # Check if variant already exists
                        if not any(n.id == easier_id for n in tree.nodes):
                            modifications.append(
                                SkillNode(
                                    id=easier_id,
                                    name=f"{original_node.name} (Easier Variant)",
                                    type=NodeType.HABIT,
                                    pillar=original_node.pillar,
                                    prerequisites=[],  # Easier variant has no prerequisites
                                    xp_reward=max(1, original_node.xp_reward // 2),  # Half XP
                                    xp_multiplier=original_node.xp_multiplier,
                                    required_completions=original_node.required_completions,
                                    description=f"Simplified version of {original_node.name} based on user feedback.",
                                )
                            )
        
        # Pattern: Task conflicts with schedule → suggest alternative time variant
        if any(word in lowered_feedback for word in ["time", "schedule", "conflict", "can't fit"]):
            for task in state.todays_tasks:
                task_words = set(w.lower() for w in task.name.split() if len(w) >= 4)
                if any(word in lowered_feedback for word in task_words):
                    original_node = next((n for n in tree.nodes if n.id == task.node_id), None)
                    if original_node:
                        # Create a time-flexible variant
                        flexible_id = f"{task.node_id}_flexible_time"
                        if not any(n.id == flexible_id for n in tree.nodes):
                            modifications.append(
                                SkillNode(
                                    id=flexible_id,
                                    name=f"{original_node.name} (Flexible Time)",
                                    type=NodeType.HABIT,
                                    pillar=original_node.pillar,
                                    prerequisites=original_node.prerequisites,
                                    xp_reward=original_node.xp_reward,
                                    xp_multiplier=original_node.xp_multiplier,
                                    required_completions=original_node.required_completions,
                                    description=f"Time-flexible version of {original_node.name} based on scheduling feedback.",
                                )
                            )
        
        # Pattern: Task consistently skipped → suggest replacement
        if any(word in lowered_feedback for word in ["replace", "instead", "alternative", "different"]):
            for task in state.todays_tasks:
                task_words = set(w.lower() for w in task.name.split() if len(w) >= 4)
                if any(word in lowered_feedback for word in task_words):
                    original_node = next((n for n in tree.nodes if n.id == task.node_id), None)
                    if original_node:
                        # Extract what they want instead (simple heuristic)
                        replacement_id = f"{task.node_id}_replacement"
                        if not any(n.id == replacement_id for n in tree.nodes):
                            # Create a placeholder replacement node
                            # In a full implementation, you'd use LLM to generate the replacement
                            modifications.append(
                                SkillNode(
                                    id=replacement_id,
                                    name=f"Alternative to {original_node.name}",
                                    type=NodeType.HABIT,
                                    pillar=original_node.pillar,
                                    prerequisites=original_node.prerequisites,
                                    xp_reward=original_node.xp_reward,
                                    xp_multiplier=original_node.xp_multiplier,
                                    required_completions=original_node.required_completions,
                                    description=f"User-requested replacement for {original_node.name}.",
                                )
                            )
        
        return modifications

    def finalize_report(
        self,
        state: ReportingState,
        sheet: CharacterSheet,
        tree: SkillTree,
    ) -> DailyReport:
        """Create a naive DailyReport based on today's tasks and conversation.

        This avoids LLM JSON calls for now and gives us a stable skeleton the
        rest of the system can build on. Later we can replace the internals
        with an LLM-driven implementation.
        """
        # Simple heuristic: mark every task as DONE with 1 repetition unless
        # the user explicitly mentioned skipping (not yet parsed in detail).
        task_reports: List[DailyTaskReport] = []
        for t in state.todays_tasks:
            task_reports.append(
                DailyTaskReport(
                    task_id=t.id,
                    node_id=t.node_id,
                    status=DailyTaskStatus.DONE,
                    completed_repetitions=max(1, t.planned_repetitions),
                    user_comment="",
                )
            )

        # Build a crude free-text summary from the last few user messages
        user_messages: List[str] = [
            turn["content"]
            for turn in state.conversation_history
            if turn.get("role") == "user"
        ]
        free_text = " ".join(user_messages[-5:]) if user_messages else ""

        wins = [f"Made progress on {t.name}" for t in state.todays_tasks]

        # Compute XP gained from today's tasks so we can both persist it in
        # stats_delta and show it in the human-readable summary.
        node_index = {n.id: n for n in tree.nodes}
        xp_career = xp_physical = xp_mental = xp_social = 0
        for tr in task_reports:
            node = node_index.get(tr.node_id)
            if node is None or tr.completed_repetitions <= 0:
                continue

            reps = tr.completed_repetitions
            xp_gain = int(node.xp_reward * node.xp_multiplier * reps)
            if node.pillar.value == "CAREER":
                xp_career += xp_gain
            elif node.pillar.value == "PHYSICAL":
                xp_physical += xp_gain
            elif node.pillar.value == "MENTAL":
                xp_mental += xp_gain
            elif node.pillar.value == "SOCIAL":
                xp_social += xp_gain

        xp_total = xp_career + xp_physical + xp_mental + xp_social
        stats_delta = StatsDelta(
            xp_career=xp_career,
            xp_physical=xp_physical,
            xp_mental=xp_mental,
            xp_social=xp_social,
            xp_total=xp_total,
        )

        # Heuristically infer a couple of concrete "next actions" based on how
        # the user responded to suggestions during the conversation.
        decisions: List[str] = []
        new_tasks: List[DailyTask] = []

        history = state.conversation_history
        for i, turn in enumerate(history):
            if turn.get("role") != "user":
                continue

            content = (turn.get("content") or "").strip().lower()
            if not any(word in content for word in ["yes", "yeah", "yep", "sure", "ok", "okay"]):
                continue

            # Look at the immediately preceding assistant message to see what
            # the user said "yes" to.
            if i == 0 or history[i - 1].get("role") != "assistant":
                continue

            prev = (history[i - 1].get("content") or "").lower()

            # Case 1: narrowing overwhelming database schema work.
            if "one table or one concrete question to explore" in prev:
                decisions.append(
                    "Next time, focus on a single table and a single concrete "
                    "question when working with database schemas."
                )

                # Attach a concrete follow-up DailyTask to the existing
                # "Explore a database schema" habit node if present.
                db_habit_node = None
                for node in tree.nodes:
                    if "database schema" in node.name.lower():
                        db_habit_node = node
                        break

                if db_habit_node is not None:
                    new_tasks.append(
                        DailyTask(
                            id=f"plan_db_focus_{state.current_date}",
                            name="Pick one table and one concrete question to explore",
                            node_id=db_habit_node.id,
                            pillar=db_habit_node.pillar,
                            type=db_habit_node.type,
                            scheduled_date=state.current_date,
                            planned_repetitions=1,
                            notes=(
                                "Follow-up from reporting about being overwhelmed "
                                "by database schemas."
                            ),
                        )
                    )

            # Additional cases for other suggestions can be added here over time.
        
        # Collect skill tree modifications from conversation
        skill_modifications: List[SkillNode] = list(state.proposed_skill_modifications)
        
        # Also check conversation history for modification requests
        for turn in state.conversation_history:
            if turn.get("role") == "user":
                mods = self._propose_skill_tree_modifications(
                    state, sheet, tree, turn.get("content", "")
                )
                skill_modifications.extend(mods)
        
        # Deduplicate by node ID
        seen_ids = set()
        unique_mods = []
        for mod in skill_modifications:
            if mod.id not in seen_ids:
                seen_ids.add(mod.id)
                unique_mods.append(mod)
        
        base_summary = "Auto-generated daily report."
        summary_lines: List[str] = [base_summary, ""]

        # XP summary.
        summary_lines.append(
            f"XP gained today: total {xp_total} "
            f"(CAREER {xp_career}, PHYSICAL {xp_physical}, MENTAL {xp_mental}, SOCIAL {xp_social})."
        )

        # Simple pattern vs. recent history, if any.
        if sheet.daily_reports:
            recent = sheet.daily_reports[-3:]
            recent_total = sum(r.stats_delta.xp_total for r in recent)
            recent_avg = int(round(recent_total / len(recent))) if recent_total else 0

            if recent_avg > 0:
                if xp_total > recent_avg * 1.2:
                    pattern_line = (
                        f"Today was above your recent XP average (~{recent_avg} per day)."
                    )
                elif xp_total < recent_avg * 0.8:
                    pattern_line = (
                        f"Today was below your recent XP average (~{recent_avg} per day)."
                    )
                else:
                    pattern_line = (
                        f"Today was roughly in line with your recent XP average (~{recent_avg} per day)."
                    )
            else:
                pattern_line = "No meaningful XP pattern yet from recent days."

            summary_lines.append(pattern_line)
        else:
            summary_lines.append(
                "No past reports yet to compare XP patterns – this is your first one."
            )

        # Add a lightweight schedule / timetable suggestion so the user
        # can see when to do what at a glance.
        if state.todays_tasks:
            summary_lines.append("")
            summary_lines.append("Schedule / timetable suggestion (for this habit set):")

            morning: list[str] = []
            afternoon: list[str] = []
            evening: list[str] = []

            for t in state.todays_tasks:
                # Very simple heuristic: map pillars to rough time-of-day slots.
                if t.pillar.value == "PHYSICAL":
                    morning.append(t.name)
                elif t.pillar.value == "CAREER":
                    afternoon.append(t.name)
                elif t.pillar.value in {"MENTAL", "SOCIAL"}:
                    evening.append(t.name)
                else:
                    afternoon.append(t.name)

            def _slot(label: str, items: list[str]) -> None:
                if not items:
                    return
                summary_lines.append(f"- {label}: " + ", ".join(items))

            _slot("Morning", morning)
            _slot("Afternoon", afternoon)
            _slot("Evening", evening)

        # Lock-in session metrics for today
        if sheet.lockin_history:
            todays_sessions = [
                s for s in sheet.lockin_history
                if s.start_time.split("T")[0] == state.current_date
            ]
            
            if todays_sessions:
                total_duration_minutes = sum(s.duration_seconds for s in todays_sessions) // 60
                total_distractions = sum(s.distractions_detected for s in todays_sessions)
                sessions_with_rating = [s for s in todays_sessions if s.user_rating is not None]
                
                if sessions_with_rating:
                    avg_rating = sum(s.user_rating for s in sessions_with_rating) / len(sessions_with_rating)
                    summary_lines.append("")
                    summary_lines.append(
                        f"Focus sessions: {len(todays_sessions)} session(s), "
                        f"{total_duration_minutes} minutes total, "
                        f"avg rating {avg_rating:.1f}/10, "
                        f"{total_distractions} distraction(s)"
                    )
                    
                    # Add to wins if high rating
                    for session in sessions_with_rating:
                        if session.user_rating and session.user_rating >= 8:
                            wins.append(
                                f"Maintained high focus (rating {session.user_rating}/10) during lock-in session"
                            )
                else:
                    summary_lines.append("")
                    summary_lines.append(
                        f"Focus sessions: {len(todays_sessions)} session(s), "
                        f"{total_duration_minutes} minutes total, "
                        f"{total_distractions} distraction(s)"
                    )

        # Decisions and newly added tasks.
        if decisions:
            summary_lines.append("")
            summary_lines.append("Decisions / next steps:")
            for d in decisions:
                summary_lines.append(f"- {d}")

        if new_tasks:
            summary_lines.append("")
            summary_lines.append("New follow-up tasks:")
            for t in new_tasks:
                summary_lines.append(
                    f"- {t.name} (pillar: {t.pillar.value}, scheduled: {t.scheduled_date})"
                )

        summary_text = "\n".join(summary_lines)

        report = DailyReport(
            date=state.current_date,
            summary=summary_text,
            sentiment="unknown",
            wins=wins,
            struggles=[],
            reflections=[],
            free_text=free_text,
            tasks=task_reports,
            stats_delta=stats_delta,
            new_tasks=new_tasks,
            new_skill_nodes=unique_mods,  # Add skill tree modifications
        )

        state.finalized = True
        return report
    
    def sync_report_to_memory(
        self,
        report: DailyReport,
        sheet: CharacterSheet,
    ) -> Dict[str, Any]:
        """Sync a DailyReport to semantic memory with significance scoring.
        
        CRITICAL: Only high-significance memories (score >= 7) go to Vector DB.
        Low-significance entries are returned for audit trail storage (JSON).
        
        Also syncs lock-in sessions from the same day.
        
        Args:
            report: DailyReport to sync
            sheet: CharacterSheet for context
            
        Returns:
            Dict with:
                - vector_db_chunks: List of chunk IDs added to Vector DB
                - audit_trail_chunks: List of all chunks (for audit trail storage)
        """
        from src.memory.integration import sync_daily_report_to_memory, sync_lockin_sessions_to_memory
        from src.memory.significance import SignificanceScorer
        
        scorer = self._get_significance_scorer()
        memory = self._get_memory(sheet.user_id)
        
        # Sync daily report
        result = sync_daily_report_to_memory(
            memory=memory,
            report=report,
            user_id=sheet.user_id,
            significance_scorer=scorer,
            skip_significance_check=False,
        )
        
        # Also sync lock-in sessions from the same day
        if sheet.lockin_history:
            todays_sessions = [
                s for s in sheet.lockin_history
                if s.start_time.split("T")[0] == report.date
            ]
            
            if todays_sessions:
                lockin_result = sync_lockin_sessions_to_memory(
                    memory=memory,
                    sessions=todays_sessions,
                    user_id=sheet.user_id,
                    report_date=report.date,
                )
                
                # Merge results
                result["vector_db_chunks"].extend(lockin_result["vector_db_chunks"])
                result["audit_trail_chunks"].extend(lockin_result["audit_trail_chunks"])
        
        return result
    
    def generate_weekly_decision(
        self,
        goal: Any,  # Goal from CharacterSheet
        sheet: CharacterSheet,
        tree: SkillTree,
        recent_reports: Optional[List[DailyReport]] = None,
    ) -> Decision:
        """Generate a decision object with citations for adjusting a goal's plan.
        
        This creates a validated Decision object (Explainable AI) with:
        - target, old_value, new_value, decision_type
        - contributing_factors with verifiable citations
        - All citations verified/grounded against actual logs
        
        Args:
            goal: Goal object to generate decision for
            sheet: CharacterSheet for context
            tree: SkillTree for goal context
            recent_reports: Optional list of recent DailyReports (defaults to last 7 days)
            
        Returns:
            Decision: Validated Decision object with grounded citations (Pydantic model)
        """
        from src.memory.vector_store import SemanticMemory
        
        memory = self._get_memory(sheet.user_id)
        
        # Get recent reports if not provided
        if recent_reports is None:
            recent_reports = sheet.daily_reports[-7:] if len(sheet.daily_reports) >= 7 else sheet.daily_reports
        
        # Query Vector DB for relevant high-significance memories
        # (Low-significance already filtered out, so we only get strategic memories)
        query = f"struggles failures lessons insights regarding {goal.name}"
        relevant_results = memory.search(
            query=query,
            n_results=10,
            pillar=goal.pillars[0].value if goal.pillars else None,  # Use pillar parameter, not filters dict
            apply_recency_weighting=True,
        )
        
        # Convert to format for prompt
        relevant_memories = [
            {
                "date": r.chunk.metadata.date,
                "content": r.chunk.text,
                "significance_score": r.chunk.metadata.significance_score,
            }
            for r in relevant_results
        ]
        
        # Determine persona based on pillar
        persona_map = {
            Pillar.CAREER: "Fortune 500 Executive Mentor",
            Pillar.PHYSICAL: "Elite Strength and Conditioning Coach",
            Pillar.MENTAL: "Cognitive Behavioral Therapist",
            Pillar.SOCIAL: "Interpersonal Communication Expert",
        }
        primary_pillar = goal.pillars[0] if goal.pillars else Pillar.CAREER
        persona = persona_map.get(primary_pillar, "Expert Life Coach")
        
        # Get current plan from goal (roadmap nodes or needed_quests)
        current_plan = []
        if goal.roadmap:
            current_plan = [node.name for node in goal.roadmap[:5]]
        elif goal.needed_quests:
            current_plan = goal.needed_quests[:5]
        elif goal.current_quests:
            current_plan = goal.current_quests
        
        current_plan_str = "\n".join([f"- {item}" for item in current_plan]) if current_plan else "No specific plan yet"
        
        # --- CALCULATE HARD DATA (New Logic) ---
        target_node_ids = set()
        if goal.roadmap:
            target_node_ids = {n.id for n in goal.roadmap}
        
        # Optimization: Node lookup
        node_map = {n.id: n for n in tree.nodes}
        
        task_stats = {} # name -> {completed, total}
        
        for rep in recent_reports:
            for t_rep in rep.tasks:
                is_relevant = False
                if t_rep.node_id in target_node_ids:
                    is_relevant = True
                else:
                    # Check pillar match if node exists and roadmap didn't catch it
                    node = node_map.get(t_rep.node_id)
                    if node and node.pillar in goal.pillars:
                        # Loose match: same pillar
                        is_relevant = True
                
                if is_relevant:
                    node = node_map.get(t_rep.node_id)
                    t_name = node.name if node else t_rep.task_id
                    
                    if t_name not in task_stats:
                        task_stats[t_name] = {"completed": 0, "total": 0}
                    
                    task_stats[t_name]["total"] += 1
                    if t_rep.status in [DailyTaskStatus.DONE, DailyTaskStatus.PARTIAL]:
                         task_stats[t_name]["completed"] += 1

        hard_data_lines = []
        if task_stats:
            for name, stats in task_stats.items():
                pct = int((stats["completed"] / stats["total"]) * 100)
                hard_data_lines.append(f"- {name}: {stats['completed']}/{stats['total']} days ({pct}%)")
        else:
            hard_data_lines.append("No specific habit data recorded this week (0 logs found).")
        
        # Calculate trend data for visualization
        trend_data = []
        for rep in recent_reports:
            total_tasks = len(rep.tasks)
            completed_tasks = sum(
                1 for t in rep.tasks 
                if t.status in [DailyTaskStatus.DONE, DailyTaskStatus.PARTIAL]
            )
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            trend_data.append({
                "date": rep.date,
                "completion_rate": round(completion_rate, 1),
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks
            })
        
        # Add lock-in session metrics for the past 7 days
        if sheet.lockin_history:
            # Get sessions from the past 7 days
            from datetime import datetime, timedelta
            # Use the most recent report date or today
            if recent_reports:
                today = datetime.strptime(recent_reports[-1].date, "%Y-%m-%d")
            else:
                today = datetime.now()
            week_start = today - timedelta(days=7)
            
            week_sessions = [
                s for s in sheet.lockin_history
                if datetime.fromisoformat(s.start_time.replace("Z", "+00:00")) >= week_start
            ]
            
            if week_sessions:
                total_duration_hours = sum(s.duration_seconds for s in week_sessions) / 3600
                total_distractions = sum(s.distractions_detected for s in week_sessions)
                sessions_with_rating = [s for s in week_sessions if s.user_rating is not None]
                
                hard_data_lines.append("")
                hard_data_lines.append(f"- Lock-in sessions: {len(week_sessions)} sessions, {total_duration_hours:.1f} hours total")
                
                if sessions_with_rating:
                    avg_rating = sum(s.user_rating for s in sessions_with_rating) / len(sessions_with_rating)
                    # Calculate trend if we have previous week data
                    prev_week_sessions = [
                        s for s in sheet.lockin_history
                        if week_start - timedelta(days=7) <= datetime.fromisoformat(s.start_time.replace("Z", "+00:00")) < week_start
                    ]
                    trend_str = ""
                    if prev_week_sessions:
                        prev_ratings = [s.user_rating for s in prev_week_sessions if s.user_rating is not None]
                        if prev_ratings:
                            prev_avg = sum(prev_ratings) / len(prev_ratings)
                            if avg_rating > prev_avg + 0.2:
                                trend_str = f" (up from {prev_avg:.1f} last week)"
                            elif avg_rating < prev_avg - 0.2:
                                trend_str = f" (down from {prev_avg:.1f} last week)"
                            else:
                                trend_str = f" (stable from {prev_avg:.1f} last week)"
                    
                    hard_data_lines.append(f"- Average focus rating: {avg_rating:.1f}/10{trend_str}")
                
                distraction_rate = total_distractions / len(week_sessions) if week_sessions else 0
                hard_data_lines.append(f"- Distractions: {total_distractions} total ({distraction_rate:.2f} per session)")
        
        hard_data_str = "\n".join(hard_data_lines)

        # --- FORMAT USER DIARY ---
        if relevant_memories:
            user_diary_str = "\n".join([f"- [{m['date']}] {m['content']}" for m in relevant_memories[:10]])
        else:
            user_diary_str = "[NO ENTRIES]"
            
        # Updated Prompt Construction with strict logic rules 
        prompt = DECISION_GENERATION_PROMPT_TEMPLATE.format(
            persona=persona,
            goal_name=goal.name,
            pillar=primary_pillar.value,
            current_plan=current_plan_str,
            hard_data=hard_data_str,
            user_diary=user_diary_str,
            logic_rules=DECISION_LOGIC_RULES
        )

        # Generate decision from LLM
        try:
            response = self.llm_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are an expert {persona}. Always respond with valid JSON only, no markdown."
                    },
                    {"role": "user", "content": prompt}
                ],
                json_mode=True,
                model=self.llm_client.default_model,
            )
            
            # Clean up markdown if present
            response_clean = response.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            response_clean = response_clean.strip()
            
            decision_dict = json.loads(response_clean)
            
            # Validate and create Decision object (ensures schema compliance)
            # Convert contributing_factors dicts to ContributingFactor objects
            factors = []
            for factor_dict in decision_dict.get("contributing_factors", []):
                factors.append(ContributingFactor(**factor_dict))
            
            decision = Decision(
                target=decision_dict.get("target", goal.name.lower().replace(" ", "_")),
                target_habit_id=decision_dict.get("target_habit_id"),
                old_value=decision_dict.get("old_value", "current plan"),
                new_value=decision_dict.get("new_value", "current plan"),
                decision_type=decision_dict.get("decision_type", "MAINTAIN"),
                confidence_score=decision_dict.get("confidence_score", 0.5),
                explanation=decision_dict.get("explanation", ""),
                contributing_factors=factors,
                goal_id=goal.id,
                pillar=primary_pillar,
            )
            
        except json.JSONDecodeError as e:
            print(f"[ReportingAgent] Error parsing LLM decision JSON: {e}")
            print(f"[ReportingAgent] Response: {response[:200]}...")
            # Return a safe default decision (validated Decision object)
            decision = Decision(
                target=goal.name.lower().replace(" ", "_"),
                old_value="current plan",
                new_value="current plan",
                decision_type="MAINTAIN",
                confidence_score=0.5,
                contributing_factors=[],
                explanation="Unable to generate decision due to parsing error.",
                goal_id=goal.id,
                pillar=primary_pillar,
            )
        except Exception as e:
            print(f"[ReportingAgent] Error generating decision: {e}")
            import traceback
            traceback.print_exc()
            decision = Decision(
                target=goal.name.lower().replace(" ", "_"),
                old_value="current plan",
                new_value="current plan",
                decision_type="MAINTAIN",
                confidence_score=0.5,
                contributing_factors=[],
                explanation="Unable to generate decision due to error.",
                goal_id=goal.id,
                pillar=primary_pillar,
            )
        
        # GROUND THE CITATIONS: Fix hallucinated dates
        # Convert recent reports to log format for grounding
        user_logs = []
        for rep in recent_reports:
            # Add main summary
            user_logs.append({
                "date": rep.date,
                "content": rep.summary,
                "id": f"report_{rep.date}",
            })
            # Add wins, struggles, reflections as separate entries
            for win in rep.wins:
                user_logs.append({
                    "date": rep.date,
                    "content": f"Win: {win}",
                    "id": f"report_{rep.date}_win",
                })
            for struggle in rep.struggles:
                user_logs.append({
                    "date": rep.date,
                    "content": f"Struggle: {struggle}",
                    "id": f"report_{rep.date}_struggle",
                })
            for reflection in rep.reflections:
                user_logs.append({
                    "date": rep.date,
                    "content": f"Reflection: {reflection}",
                    "id": f"report_{rep.date}_reflection",
                })
        
        # Also add memories from Vector DB (they already have dates)
        for mem in relevant_memories:
            user_logs.append({
                "date": mem["date"],
                "content": mem["content"],
                "id": f"memory_{mem['date']}",
            })
        
        # GROUND THE CITATIONS: Fix hallucinated dates
        # Apply citation verification/grounding to Decision object
        # Convert Decision to dict for grounding function (which expects dict)
        decision_dict = decision.model_dump()
        verified_dict = verify_citations(decision_dict, user_logs)
        
        # Rebuild Decision object with verified citations
        verified_factors = []
        for factor_dict in verified_dict.get("contributing_factors", []):
            verified_factors.append(ContributingFactor(**factor_dict))
        
        # Update decision with verified factors
        decision.contributing_factors = verified_factors
        
        # Update citation dates in factors to use verified_date if available
        for factor in decision.contributing_factors:
            if factor.verified_date:
                # Use verified date (grounded/corrected)
                factor.citation_date = factor.verified_date
        
        # Attach metadata for visualization
        decision.metadata = {
            "task_stats": task_stats,
            "trend_data": trend_data,
            "recent_reports_count": len(recent_reports),
            "goal_name": goal.name,
            "analysis_period_days": 7
        }
        
        return decision