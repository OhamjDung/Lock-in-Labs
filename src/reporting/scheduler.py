from __future__ import annotations

from datetime import date
from typing import List

from src.models import (
    CharacterSheet,
    SkillTree,
    SkillNode,
    NodeType,
    DailyTask,
    Pillar,
    HabitProgress,
    NodeStatus,
    DailyScheduleItem,
    DailyTaskStatus,
)


def get_todays_tasks(
    sheet: CharacterSheet,
    tree: SkillTree,
    current_date: str | None = None,
) -> List[DailyTask]:
    """Select a simple set of daily tasks based on the current SkillTree.

    For now we:
    - Take all Habit nodes that have no prerequisites (leaf habits).
    - Schedule each as a DailyTask for the given date.

    Later we can add smarter selection, priority, and per-pillar limits.
    """

    if current_date is None:
        current_date = date.today().isoformat()

    habit_nodes: List[SkillNode] = [
        n for n in tree.nodes if n.type == NodeType.HABIT
    ]

    tasks: List[DailyTask] = []
    for node in habit_nodes:
        # Ensure there's a progress entry, defaulting to LOCKED
        if node.id not in sheet.habit_progress:
            sheet.habit_progress[node.id] = HabitProgress(node_id=node.id)

        progress = sheet.habit_progress[node.id]

        # Only schedule tasks for ACTIVE, not yet MASTERED habits
        if progress.status != NodeStatus.ACTIVE or progress.status == NodeStatus.MASTERED:
            continue

        task_id = f"{current_date}_{node.id}"
        tasks.append(
            DailyTask(
                id=task_id,
                name=node.name,
                node_id=node.id,
                pillar=node.pillar,
                type=node.type,
                scheduled_date=current_date,
                planned_repetitions=1,
            )
        )

    return tasks


def ensure_daily_schedule_for_date(
    sheet: CharacterSheet,
    todays_tasks: List[DailyTask],
    current_date: str | None = None,
) -> List[DailyScheduleItem]:
    """Ensure there is a simple per-day schedule for the given date.

    - If `sheet.daily_schedule[current_date]` already exists and is non-empty,
      we return it as-is (the day has already been planned).
    - Otherwise we create a lightweight schedule derived from `todays_tasks`.

    This gives the frontend a stable, JSON-serialized structure it can use to
    render a per-day timeline on the homepage without re-running scheduling
    logic client-side.
    """

    if current_date is None:
        current_date = date.today().isoformat()

    # If we've already planned this day, keep the existing plan.
    existing = sheet.daily_schedule.get(current_date) or []
    if existing:
        return existing

    schedule: List[DailyScheduleItem] = []

    # Very simple heuristic: lay tasks out in 60-minute blocks starting at 07:00,
    # grouped by pillar order so the day feels structured but predictable.
    ordered_pillars = [Pillar.PHYSICAL, Pillar.CAREER, Pillar.MENTAL, Pillar.SOCIAL]
    tasks_by_pillar: dict[Pillar, List[DailyTask]] = {p: [] for p in ordered_pillars}

    for task in todays_tasks:
        # Fallback bucket if a new pillar type ever shows up.
        bucket_pillar = task.pillar if task.pillar in tasks_by_pillar else Pillar.CAREER
        tasks_by_pillar[bucket_pillar].append(task)

    # Start at 07:00 local time and increment in one‑hour blocks.
    start_minutes = 7 * 60
    minutes = start_minutes

    for pillar in ordered_pillars:
        for task in tasks_by_pillar[pillar]:
            hours = minutes // 60
            mins = minutes % 60
            time_str = f"{hours:02d}:{mins:02d}"

            schedule.append(
                DailyScheduleItem(
                    time=time_str,
                    label=task.name,
                    node_id=task.node_id,
                    pillar=task.pillar,
                    status=DailyTaskStatus.PENDING,
                )
            )

            minutes += 60

    sheet.daily_schedule[current_date] = schedule
    return schedule


def mark_newly_unlocked_nodes(sheet: CharacterSheet, tree: SkillTree) -> None:
    """Placeholder for unlocking logic.

    In a future iteration we can:
    - Inspect each node's prerequisites.
    - If all prerequisite habits are MASTERED, set this node's status to ACTIVE
      in a separate progress structure if desired.

    For now this is a no-op stub so the reporting flow can compile.
    """

    return None
