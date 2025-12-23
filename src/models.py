from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    GOAL = "Goal"
    SUB_SKILL = "Sub-Skill"
    HABIT = "Habit"


class Pillar(str, Enum):
    CAREER = "CAREER"
    PHYSICAL = "PHYSICAL"
    MENTAL = "MENTAL"
    SOCIAL = "SOCIAL"


class NodeStatus(str, Enum):
    """Dynamic status of a node for progress tracking and unlocking logic."""

    LOCKED = "LOCKED"
    ACTIVE = "ACTIVE"
    MASTERED = "MASTERED"


class DailyTaskStatus(str, Enum):
    """Per-day status for a scheduled task/habit instance."""

    PENDING = "PENDING"
    DONE = "DONE"
    PARTIAL = "PARTIAL"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

class SkillNode(BaseModel):
    id: str = Field(..., description="Unique identifier for the node (e.g., 'skill_python')")
    name: str = Field(..., description="Display name of the skill or habit")
    type: NodeType = Field(..., description="Type of node: Goal, Sub-Skill, or Habit")
    pillar: Pillar = Field(..., description="The life pillar this belongs to")
    prerequisites: List[str] = Field(default_factory=list, description="List of Node IDs that must be completed/unlocked first")
    xp_reward: int = Field(default=100, description="XP gained upon completion")
    xp_multiplier: float = Field(default=1.0, description="Multiplier for XP, affected by debuffs")
    required_completions: int = Field(
        default=30,
        description="How many times this node (primarily habits) should be completed before it is considered mastered."
    )
    description: Optional[str] = Field(None, description="Short description of the node")

class SkillTree(BaseModel):
    nodes: List[SkillNode] = Field(default_factory=list)


class HabitProgress(BaseModel):
    """User-specific progress for a habit-like node (usually a Habit SkillNode)."""

    node_id: str
    status: NodeStatus = Field(default=NodeStatus.LOCKED)
    completed_total: int = Field(default=0, description="All-time number of completions for this habit.")
    completed_since_last_report: int = Field(default=0, description="Completions since the last reporting session.")
    last_completed_date: Optional[str] = Field(default=None, description="ISO date string of last completion.")
    streak_days: int = Field(default=0, description="Optional streak count in days for gamification.")

class Goal(BaseModel):
    name: str = Field(..., description="The user's high-level goal.")
    pillars: List[Pillar] = Field(..., description="The life pillars this goal belongs to (can be multiple).")
    current_quests: List[str] = Field(default_factory=list, description="Concrete habits the user is currently doing for this goal.")
    needed_quests: List[str] = Field(default_factory=list, description="AI-generated roadmap of habits to achieve this goal.")
    description: Optional[str] = Field(None, description="A brief description of the goal.")


# --- Time / Focus Models ---
class CalendarEventType(str, Enum):
    # Differentiate between hard deadlines and flexible habit slots
    HARD_DEADLINE = "HARD_DEADLINE"
    HABIT_SLOT = "HABIT_SLOT"
    MEETING = "MEETING"


class CalendarEvent(BaseModel):
    id: str
    title: str
    start_time: str  # ISO 8601 datetime
    end_time: str    # ISO 8601 datetime
    type: CalendarEventType
    category: Optional[str] = None  # User-defined category (can create new or use existing)
    node_id: Optional[str] = None  # Link to a SkillNode if relevant
    description: Optional[str] = None
    is_completed: bool = False


class PomodoroSession(BaseModel):
    id: str
    start_time: str
    duration_minutes: int  # e.g., 25
    task_id: Optional[str] = None # Link to the DailyTask worked on
    notes: Optional[str] = None
    completed: bool = True # False if interrupted/abandoned


class LockInSession(BaseModel):
    """Tracks a session where the user activated the 'Sentinel'."""
    id: str
    start_time: str
    end_time: str
    duration_seconds: int
    distractions_detected: int = 0 # Number of times phone/people were detected
    distraction_events: List[Dict[str, str]] = Field(default_factory=list) # Timestamps of distractions

class CharacterSheet(BaseModel):
    user_id: str
    
    # Store all goals in a list (goals can belong to multiple pillars)
    goals: List[Goal] = Field(default_factory=list, description="List of all user goals (a goal can belong to multiple pillars).")
    
    stats_career: Dict[str, int] = Field(default_factory=dict)
    stats_physical: Dict[str, int] = Field(default_factory=dict)
    stats_mental: Dict[str, int] = Field(default_factory=dict)
    stats_social: Dict[str, int] = Field(default_factory=dict)
    
    debuffs: List[str] = Field(default_factory=list, description="Obstacles or challenges the user is facing.")
    skill_tree: Optional[SkillTree] = None

    # XP and reporting-related fields
    xp_total: int = Field(default=0, description="Total XP accumulated across all pillars.")
    xp_career: int = Field(default=0, description="XP earned in the Career pillar.")
    xp_physical: int = Field(default=0, description="XP earned in the Physical pillar.")
    xp_mental: int = Field(default=0, description="XP earned in the Mental pillar.")
    xp_social: int = Field(default=0, description="XP earned in the Social pillar.")

    habit_progress: Dict[str, HabitProgress] = Field(
        default_factory=dict,
        description="Per-node habit progress, keyed by SkillNode.id.",
    )

    # 1. Calendar (For the Calendar View)
    calendar_events: List[CalendarEvent] = Field(default_factory=list)

    # 2. Pomodoro Stats (For XP calculation & productivity tracking)
    pomodoro_history: List[PomodoroSession] = Field(default_factory=list)
    pomodoros_total: int = Field(default=0)

    # 3. Lock-In / Focus Stats (For the 'Sentinel' view)
    lockin_history: List[LockInSession] = Field(default_factory=list)
    lockin_total_time_seconds: int = Field(default=0)
    phone_distractions_total: int = Field(default=0)

    # 4. MEMORY / KNOWLEDGE GRAPH (Crucial for the "Smart" AI)
    # This acts as the AI's notebook about the user.
    user_facts: List[str] = Field(default_factory=list, description="Persistent facts about the user (e.g., 'Dislikes morning workouts', 'Struggles with SQL joins').")

    # Per-day schedule the system has suggested or the user has accepted.
    # Keyed by ISO date (YYYY-MM-DD).
    daily_schedule: Dict[str, List["DailyScheduleItem"]] = Field(
        default_factory=dict,
        description="Per-day schedule suggestions keyed by ISO date.",
    )

    daily_reports: List["DailyReport"] = Field(
        default_factory=list,
        description="Historical list of daily reporting summaries.",
    )
    last_report_date: Optional[str] = Field(
        default=None,
        description="ISO date of the last completed reporting session.",
    )

    def get_goal_list(self) -> List[Goal]:
        """Returns a flat list of all goals."""
        return self.goals  # goals is already a List[Goal], not a dict

class PendingDebuff(BaseModel):
    """A debuff waiting for user confirmation."""
    name: str
    evidence: str
    confidence: str  # "high", "medium", "low"

class PendingGoal(BaseModel):
    """A goal from a pillar that hasn't been asked about yet, waiting in queue."""
    name: str
    pillars: List[Pillar]  # Goals can have multiple pillars
    description: Optional[str] = None

class ConversationState(BaseModel):
    missing_fields: List[str] = Field(..., description="List of fields in the CharacterSheet that still need to be populated")
    current_topic: str = Field(..., description="The specific topic the Architect is currently asking about")
    user_sentiment: str = Field(default="neutral", description="The detected emotional state of the user (e.g., engaged, bored, confused)")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="History of the chat")
    goals_prioritized: bool = Field(default=False, description="Flag to check if the user has ranked their goals.")
    phase: str = Field(default="phase1", description="Current onboarding phase: phase1 (goals), phase2 (current_quests), phase3.5 (prioritization), phase4 (planners), phase5 (skill_tree)")
    pending_debuffs: List[PendingDebuff] = Field(default_factory=list, description="Debuffs waiting for user confirmation")
    pillars_asked_about: List[Pillar] = Field(default_factory=list, description="Pillars that have been asked about in Phase 1")
    pending_goals: List[PendingGoal] = Field(default_factory=list, description="Goals from pillars not yet asked about, waiting in queue")


class DailyTask(BaseModel):
    """A specific instance of a task or habit scheduled for a given date."""

    id: str
    name: str
    node_id: str
    pillar: Pillar
    type: NodeType
    scheduled_date: str
    status: DailyTaskStatus = Field(default=DailyTaskStatus.PENDING)
    planned_repetitions: int = Field(default=1)
    completed_repetitions: int = Field(default=0)
    xp_awarded: int = Field(default=0)
    notes: Optional[str] = None


class DailyScheduleItem(BaseModel):
    """Lightweight schedule entry for a specific time on a given day.

    Stored on the CharacterSheet so the frontend can render a per-day
    timeline (e.g., on the homepage) without re-running scheduling logic.
    """

    time: str = Field(..., description="Local time string like '07:30'.")
    label: str = Field(..., description="Human-readable label for this slot.")
    node_id: Optional[str] = Field(
        default=None,
        description="Optional SkillNode.id this schedule item is tied to.",
    )
    pillar: Optional[Pillar] = Field(
        default=None,
        description="Optional pillar classification for coloring/grouping.",
    )
    status: DailyTaskStatus = Field(
        default=DailyTaskStatus.PENDING,
        description="Lightweight status flag for the schedule row.",
    )


class DailyTaskReport(BaseModel):
    """Outcome of a scheduled task within a DailyReport."""

    task_id: str
    node_id: str
    status: DailyTaskStatus
    completed_repetitions: int = Field(default=0)
    user_comment: Optional[str] = None


class StatsDelta(BaseModel):
    """Changes to stats and XP computed for a given reporting session."""

    stats_career: Dict[str, int] = Field(default_factory=dict)
    stats_physical: Dict[str, int] = Field(default_factory=dict)
    stats_mental: Dict[str, int] = Field(default_factory=dict)
    stats_social: Dict[str, int] = Field(default_factory=dict)

    xp_career: int = Field(default=0)
    xp_physical: int = Field(default=0)
    xp_mental: int = Field(default=0)
    xp_social: int = Field(default=0)
    xp_total: int = Field(default=0)


class DailyReport(BaseModel):
    """Structured summary of a reporting session, used to update progress and stats."""

    date: str
    summary: str
    sentiment: str
    wins: List[str] = Field(default_factory=list)
    struggles: List[str] = Field(default_factory=list)
    reflections: List[str] = Field(default_factory=list)
    free_text: str = Field(default="")
    tasks: List[DailyTaskReport] = Field(default_factory=list)
    stats_delta: StatsDelta = Field(default_factory=StatsDelta)
    new_tasks: List[DailyTask] = Field(default_factory=list)
    new_skill_nodes: List[SkillNode] = Field(default_factory=list)


class ReportingState(BaseModel):
    """In-memory state for a reporting conversation/flow."""

    user_id: str
    current_date: str
    phase: str = Field(default="collecting")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    todays_tasks: List[DailyTask] = Field(default_factory=list)
    finalized: bool = Field(default=False)
    pending_report: Optional[DailyReport] = Field(
        default=None,
        description="Draft DailyReport awaiting user confirmation.",
    )
    review_feedback: List[str] = Field(
        default_factory=list,
        description="Free-text user feedback on the draft summary/schedule before final confirmation.",
    )
