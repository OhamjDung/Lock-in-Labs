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
    """Unlock nodes when all prerequisites are MASTERED.
    
    Rules:
    - Only unlock habits (Sub-Skills and Goals don't have progress tracking yet)
    - A habit is unlocked if ALL its prerequisite habits are MASTERED
    - Unlocking is recursive: after unlocking one node, check if others can now be unlocked
    - Only sets status to ACTIVE if currently LOCKED (doesn't overwrite ACTIVE or MASTERED)
    
    This is called after applying daily reports, so newly MASTERED prerequisites
    can trigger unlocking of dependent habits.
    """
    # Build a map of all nodes by ID for quick lookup
    node_map = {node.id: node for node in tree.nodes}
    
    # Get all habit nodes (only habits have progress tracking currently)
    habit_nodes = [node for node in tree.nodes if node.type == NodeType.HABIT]
    
    # Recursive unlocking: keep checking until no more unlocks happen
    max_iterations = len(habit_nodes)  # Safety limit to prevent infinite loops
    iteration = 0
    any_unlocked = True
    
    while any_unlocked and iteration < max_iterations:
        any_unlocked = False
        iteration += 1
        
        for habit_node in habit_nodes:
            # Skip if not LOCKED (already ACTIVE or MASTERED)
            if habit_node.id not in sheet.habit_progress:
                sheet.habit_progress[habit_node.id] = HabitProgress(node_id=habit_node.id)
            
            progress = sheet.habit_progress[habit_node.id]
            if progress.status != NodeStatus.LOCKED:
                continue
            
            # If no prerequisites, skip (handled by initial selection, not unlocking)
            if not habit_node.prerequisites or len(habit_node.prerequisites) == 0:
                continue
            
            # Check if ALL prerequisite habits are MASTERED
            # Only check prerequisites that are habits (skip Sub-Skills/Goals for now)
            habit_prereqs = [
                prereq_id for prereq_id in habit_node.prerequisites
                if node_map.get(prereq_id) and node_map[prereq_id].type == NodeType.HABIT
            ]
            
            # If no habit prerequisites, skip (Sub-Skill/Goal prerequisites not checked yet)
            if len(habit_prereqs) == 0:
                continue
            
            # Check if ALL habit prerequisites are MASTERED
            all_prereqs_mastered = True
            for prereq_id in habit_prereqs:
                prereq_progress = sheet.habit_progress.get(prereq_id)
                if not prereq_progress:
                    # Prerequisite doesn't have progress yet - not unlocked
                    all_prereqs_mastered = False
                    break
                
                if prereq_progress.status != NodeStatus.MASTERED:
                    # Prerequisite is not MASTERED - not all prerequisites met
                    all_prereqs_mastered = False
                    break
            
            # If all prerequisite habits are MASTERED, unlock this habit
            if all_prereqs_mastered:
                progress.status = NodeStatus.ACTIVE
                any_unlocked = True
