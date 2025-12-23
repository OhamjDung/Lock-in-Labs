from __future__ import annotations

from typing import Dict
from datetime import date

from src.models import (
    CharacterSheet,
    SkillTree,
    DailyReport,
    NodeStatus,
    HabitProgress,
    StatsDelta,
    Pillar,
    NodeType,
)
from .scheduler import mark_newly_unlocked_nodes


def _index_nodes_by_id(tree: SkillTree) -> Dict[str, object]:
    return {n.id: n for n in tree.nodes}


def apply_daily_report(
    sheet: CharacterSheet,
    tree: SkillTree,
    report: DailyReport,
) -> None:
    """Apply a DailyReport to update stats and habit progress.

    This is a minimal first pass:
    - Updates HabitProgress.completed_total and last_completed_date for each
      reported task that has repetitions > 0.
    - Marks habits as MASTERED when completed_total >= required_completions.
    - Applies StatsDelta to the sheet's stats and XP fields.
    - Appends the report to sheet.daily_reports and updates last_report_date.
    """

    node_index = _index_nodes_by_id(tree)

    # Update habit progress and compute XP
    for task_report in report.tasks:
        node_id = task_report.node_id
        node = node_index.get(node_id)
        if node is None:
            continue

        if node_id not in sheet.habit_progress:
            sheet.habit_progress[node_id] = HabitProgress(node_id=node_id)

        progress = sheet.habit_progress[node_id]

        if task_report.completed_repetitions > 0:
            reps = task_report.completed_repetitions
            progress.completed_total += reps
            progress.completed_since_last_report += reps
            progress.last_completed_date = report.date

            # Check for mastery
            if progress.completed_total >= node.required_completions:
                progress.status = NodeStatus.MASTERED

    # Apply skill tree modifications
    if report.new_skill_nodes:
        for new_node in report.new_skill_nodes:
            # Check if node already exists (by ID)
            existing = next((n for n in tree.nodes if n.id == new_node.id), None)
            if existing:
                # Update existing node
                existing.name = new_node.name
                existing.description = new_node.description
                existing.xp_reward = new_node.xp_reward
                existing.xp_multiplier = new_node.xp_multiplier
                existing.required_completions = new_node.required_completions
            else:
                # Add new node to tree
                tree.nodes.append(new_node)
                
                # Initialize habit progress for new habit nodes
                if new_node.type == NodeType.HABIT:
                    sheet.habit_progress[new_node.id] = HabitProgress(
                        node_id=new_node.id,
                        status=NodeStatus.ACTIVE
                    )

    # Unlock any nodes whose prerequisites are now satisfied (stubbed for now)
    mark_newly_unlocked_nodes(sheet, tree)

    # Apply stats delta
    delta: StatsDelta = report.stats_delta

    for stat, change in delta.stats_career.items():
        sheet.stats_career[stat] = sheet.stats_career.get(stat, 0) + change
    for stat, change in delta.stats_physical.items():
        sheet.stats_physical[stat] = sheet.stats_physical.get(stat, 0) + change
    for stat, change in delta.stats_mental.items():
        sheet.stats_mental[stat] = sheet.stats_mental.get(stat, 0) + change
    for stat, change in delta.stats_social.items():
        sheet.stats_social[stat] = sheet.stats_social.get(stat, 0) + change

    # XP from structured deltas (includes XP from tasks if finalize_report populated it)
    sheet.xp_career += delta.xp_career
    sheet.xp_physical += delta.xp_physical
    sheet.xp_mental += delta.xp_mental
    sheet.xp_social += delta.xp_social
    sheet.xp_total += delta.xp_total

    # Append report and update last_report_date
    sheet.daily_reports.append(report)
    sheet.last_report_date = report.date or date.today().isoformat()
