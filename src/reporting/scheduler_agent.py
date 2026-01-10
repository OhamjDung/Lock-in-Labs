"""Scheduler Agent for converting natural language availability into structured daily schedules."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

from src.models import (
    DailyScheduleItem,
    DailyTaskStatus,
    CharacterSheet,
    SkillNode,
    Pillar,
)
from src.llm import LLMClient


class SchedulerAgent:
    """Agent that converts user availability constraints into a structured daily schedule."""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
    
    def generate_schedule(
        self,
        user_constraints: str,
        tasks: List[SkillNode],
        priorities: List[Pillar],
        date_str: str,
    ) -> tuple[List[DailyScheduleItem], bool]:
        """
        Returns:
            Tuple of (schedule_items, is_fallback)
            - schedule_items: List of DailyScheduleItem objects
            - is_fallback: True if fallback schedule was used (LLM failed)
        """
        """
        Uses LLM to map availability + habits -> DailySchedule.
        
        Args:
            user_constraints: Natural language description of availability (e.g., "Work 9-5, free evening")
            tasks: List of SkillNode objects to schedule
            priorities: List of Pillar enums in priority order (most to least important)
            date_str: ISO date string for the schedule (e.g., "2025-01-15")
            
        Returns:
            List of DailyScheduleItem objects representing the scheduled day
        """
        # 1. Format Task List for Prompt
        task_list_str = "\n".join([
            f"- {t.name} (Pillar: {t.pillar.value}, Priority: {'HIGH' if t.pillar in priorities[:2] else 'NORMAL'})"
            for t in tasks
        ])
        
        priorities_str = ", ".join([p.value for p in priorities])
        
        # 2. Construct Prompt
        prompt = f"""
        Act as an expert time-blocking coach.
        
        CONTEXT:
        Date: {date_str}
        User Availability: "{user_constraints}"
        User Priorities (most to least important): {priorities_str}
        
        TASKS TO SCHEDULE:
        {task_list_str}
        
        RULES:
        1. Respect User Availability strictly. Do not schedule during busy times.
        2. High Priority tasks (top 2 pillars) must get the best time slots (e.g., morning or immediately after work).
        3. Standard duration is 60 mins unless specified.
        4. If tasks don't fit, mark them as 'skipped' in the output.
        5. Physical/Mental tasks should be prioritized for high-energy times.
        6. Social tasks can be scheduled for evening/wind-down times.
        
        OUTPUT JSON (valid JSON only, no markdown):
        {{
            "schedule_items": [
                {{ "time": "07:00", "label": "Run 5k", "reason": "Morning slot for high priority physical task", "status": "PENDING" }},
                {{ "time": "19:00", "label": "Read Book", "reason": "Wind down activity", "status": "PENDING" }}
            ],
            "unassigned_tasks": []
        }}
        """
        
        # 3. Call LLM & Parse
        try:
            response = self.llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert time-blocking coach. Always respond with valid JSON only, no markdown."
                    },
                    {"role": "user", "content": prompt}
                ],
                json_mode=True,
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
            
            parsed = json.loads(response_clean)
            
            # 4. Convert to Models
            schedule_items = []
            for item in parsed.get("schedule_items", []):
                # Find matching task node
                task_node = next(
                    (t for t in tasks if t.name == item.get("label", "")),
                    None
                )
                
                # Map status string to enum
                status_str = item.get("status", "PENDING").upper()
                status = DailyTaskStatus.PENDING
                if status_str == "DONE":
                    status = DailyTaskStatus.DONE
                elif status_str == "SKIPPED":
                    status = DailyTaskStatus.SKIPPED
                elif status_str == "PARTIAL":
                    status = DailyTaskStatus.PARTIAL
                elif status_str == "CANCELLED":
                    status = DailyTaskStatus.CANCELLED
                
                schedule_items.append(
                    DailyScheduleItem(
                        time=item.get("time", "09:00"),
                        label=item.get("label", ""),
                        node_id=task_node.id if task_node else None,
                        pillar=task_node.pillar if task_node else None,
                        status=status,
                    )
                )
            
            return (schedule_items, False)  # False = not fallback
            
        except json.JSONDecodeError as e:
            print(f"[SchedulerAgent] Error parsing LLM response JSON: {e}")
            print(f"[SchedulerAgent] Response: {response[:200]}...")
            # Fallback: create a simple schedule
            # Note: This fallback doesn't respect user constraints - user should be informed
            print(f"[SchedulerAgent] WARNING: Using fallback schedule (does not respect user constraints)")
            fallback_schedule = self._create_fallback_schedule(tasks, priorities, date_str, user_constraints)
            return (fallback_schedule, True)  # True = is fallback
        except Exception as e:
            print(f"[SchedulerAgent] Error generating schedule: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: create a simple schedule
            print(f"[SchedulerAgent] WARNING: Using fallback schedule due to error (does not respect user constraints)")
            fallback_schedule = self._create_fallback_schedule(tasks, priorities, date_str, user_constraints)
            return (fallback_schedule, True)  # True = is fallback
    
    def _create_fallback_schedule(
        self,
        tasks: List[SkillNode],
        priorities: List[Pillar],
        date_str: str,
        user_constraints: str = "",
    ) -> List[DailyScheduleItem]:
        """Create a simple fallback schedule if LLM fails.
        
        WARNING: This fallback does NOT respect user_constraints.
        It's a basic time-blocking that should be clearly communicated to the user.
        """
        schedule_items = []
        
        # Try to extract a safe start time from constraints (very basic parsing)
        start_hour = 7
        start_minute = 0
        
        # Very basic constraint parsing: look for "after X" or "from X"
        import re
        if user_constraints:
            # Look for patterns like "after 5", "from 9", "after work" (assume 5pm)
            after_match = re.search(r'after\s+(\d+)', user_constraints.lower())
            from_match = re.search(r'from\s+(\d+)', user_constraints.lower())
            
            if after_match:
                hour = int(after_match.group(1))
                # If hour < 12, assume PM (e.g., "after 5" = 5pm = 17:00)
                if hour < 12:
                    start_hour = hour + 12
                else:
                    start_hour = hour
                start_minute = 0
            elif from_match:
                hour = int(from_match.group(1))
                if hour < 12:
                    start_hour = hour + 12
                else:
                    start_hour = hour
                start_minute = 0
        
        # Sort tasks by priority (high priority pillars first)
        sorted_tasks = sorted(
            tasks,
            key=lambda t: (
                priorities.index(t.pillar) if t.pillar in priorities else 999,
                t.name
            )
        )
        
        for task in sorted_tasks:
            time_str = f"{start_hour:02d}:{start_minute:02d}"
            schedule_items.append(
                DailyScheduleItem(
                    time=time_str,
                    label=task.name,
                    node_id=task.id,
                    pillar=task.pillar,
                    status=DailyTaskStatus.PENDING,
                )
            )
            
            # Increment time by 60 minutes
            start_minute += 60
            if start_minute >= 60:
                start_hour += start_minute // 60
                start_minute = start_minute % 60
            
            # Don't schedule past 22:00
            if start_hour >= 22:
                break
        
        return schedule_items
