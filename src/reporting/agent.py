from __future__ import annotations

from typing import List, Dict

from src.llm import LLMClient
from src.models import (
    CharacterSheet,
    SkillTree,
    DailyTask,
    DailyReport,
    DailyTaskReport,
    ReportingState,
    DailyTaskStatus,
    StatsDelta,
)
from .prompts import REPORTING_CONVERSATION_PROMPT, REPORTING_JSON_PROMPT_TEMPLATE


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

    @staticmethod
    def _format_tasks_for_display(tasks: List[DailyTask]) -> str:
        lines = []
        for t in tasks:
            lines.append(
                f"- [{t.pillar.value}] {t.name} (planned reps: {t.planned_repetitions})"
            )
        return "\n".join(lines) if lines else "(no tasks scheduled)"

    def initial_message(self, state: ReportingState) -> str:
        """Generate the first message explaining what to report on."""
        intro = (
            "Let's do a quick daily check-in. Here's what I'm tracking for you today:\n\n"
        )
        tasks_block = self._format_tasks_for_display(state.todays_tasks)
        guidance = (
            "\n\nFor each item, tell me:\n"
            "- Did you do it?\n"
            "- Roughly how many repetitions/minutes?\n"
            "- Anything notable (easy, hard, blocked, etc.)?\n\n"
            "You can also mention anything else that feels important, even if it's not on the list."
        )
        return intro + tasks_block + guidance

    def generate_reply(
        self,
        state: ReportingState,
        sheet: CharacterSheet,
        tree: SkillTree,
        user_message: str,
    ) -> str:
        """Conversational reply that reacts to what the user said.

        Still heuristic (no LLM call), but it:
        - Tries to recognize which of today's tasks the user is talking about.
        - Acknowledges wins vs. friction.
        - Asks a small clarifying question when something sounds hard or confusing.
        """
        lowered = user_message.strip().lower()

        # If the user indicates they're done, don't dig further.
        if "confirm" in lowered or "done" in lowered:
            return "Okay, I'll prepare your daily report next."

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
            response += (
                " What, specifically, made those tricky – not knowing where to start, "
                "too many options, low energy, or something else?"
            )
        else:
            response += " If there are any habits you want to tweak or replace, tell me which ones."

        response += " When you're ready for me to summarize the day, type 'confirm'."
        return response

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
        )

        state.finalized = True
        return report
