"""Metadata schema for memory chunks - ensures structured, time-aware data."""

from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator


class ChunkType(str, Enum):
    """Type of memory chunk - determines how it's processed and retrieved."""
    
    # Raw episodic memory (from daily reports, conversations, etc.)
    REPORT_SUMMARY = "report_summary"
    REPORT_TASK = "report_task"
    REPORT_WIN = "report_win"
    REPORT_STRUGGLE = "report_struggle"
    REPORT_REFLECTION = "report_reflection"
    
    # Conversation logs
    ONBOARDING_TURN = "onboarding_turn"
    REPORTING_TURN = "reporting_turn"
    GENERAL_CHAT = "general_chat"
    
    # Behavioral patterns
    HABIT_COMPLETION = "habit_completion"
    HABIT_SKIP = "habit_skip"
    TASK_FAILURE = "task_failure"
    TASK_SUCCESS = "task_success"
    
    # Semantic summaries (from consolidation)
    DAILY_SUMMARY = "daily_summary"  # Parent summary for a day
    WEEKLY_SUMMARY = "weekly_summary"  # Parent summary for a week
    PATTERN_INSIGHT = "pattern_insight"  # Procedural memory (e.g., "User fails on Tuesdays")


class MemoryLevel(str, Enum):
    """Hierarchy level - for recursive summarization."""
    
    RAW = "raw"  # Individual log entries, tasks, etc.
    DAY = "day"  # Daily summaries
    WEEK = "week"  # Weekly summaries
    MONTH = "month"  # Monthly summaries
    PATTERN = "pattern"  # Cross-cutting insights


class MemoryMetadata(BaseModel):
    """Structured metadata for a memory chunk.
    
    This enables time-aware retrieval and filtering without relying on vector similarity.
    """
    
    # Temporal metadata (CRITICAL for "Why do I fail on Tuesdays?" queries)
    date: str = Field(..., description="ISO date string (YYYY-MM-DD)")
    datetime: Optional[str] = Field(None, description="ISO datetime string (YYYY-MM-DDTHH:MM:SS)")
    day_of_week: int = Field(..., description="Day of week: 0=Monday, 6=Sunday")
    hour: Optional[int] = Field(None, description="Hour of day (0-23) if available")
    week_of_year: int = Field(..., description="ISO week number (1-53)")
    month: int = Field(..., description="Month (1-12)")
    year: int = Field(..., description="Year (e.g., 2025)")
    
    # Semantic categorization
    chunk_type: ChunkType = Field(..., description="Type of memory chunk")
    pillar: Optional[str] = Field(None, description="Life pillar: CAREER, PHYSICAL, MENTAL, SOCIAL")
    sentiment: Optional[str] = Field(None, description="Sentiment: positive, negative, neutral, mixed")
    mood_score: Optional[int] = Field(None, ge=1, le=10, description="User mood score 1-10")
    
    # Content tags (for filtering)
    tags: List[str] = Field(default_factory=list, description="Custom tags for filtering (e.g., 'failure', 'coding', 'sleep')")
    
    # Hierarchical linking (for recursive summarization)
    parent_id: Optional[str] = Field(None, description="ID of parent summary chunk (for zoom-in)")
    child_ids: List[str] = Field(default_factory=list, description="IDs of child raw chunks (for zoom-out)")
    level: MemoryLevel = Field(default=MemoryLevel.RAW, description="Hierarchy level")
    
    # Entity linking
    goal_id: Optional[str] = Field(None, description="Linked goal ID if applicable")
    node_id: Optional[str] = Field(None, description="Linked skill node ID if applicable")
    task_id: Optional[str] = Field(None, description="Linked task ID if applicable")
    
    # Session context
    session_id: Optional[str] = Field(None, description="Session identifier (onboarding, reporting, etc.)")
    user_id: str = Field(..., description="User ID")
    
    # Additional structured data
    xp_gained: Optional[int] = Field(None, description="XP gained in this chunk")
    stats_delta: Optional[Dict[str, int]] = Field(None, description="Stat changes if applicable")
    
    # Significance scoring (CRITICAL: Only high-significance chunks go to Vector DB)
    significance_score: Optional[int] = Field(None, ge=1, le=10, description="Long-term strategic value (1-10). Only score >= threshold stored in Vector DB. Lower scores stored in audit trail only.")
    
    @field_validator("day_of_week")
    @classmethod
    def validate_day_of_week(cls, v: int) -> int:
        """Ensure day_of_week is in valid range."""
        if not (0 <= v <= 6):
            raise ValueError("day_of_week must be 0-6 (Monday-Sunday)")
        return v
    
    @field_validator("hour")
    @classmethod
    def validate_hour(cls, v: Optional[int]) -> Optional[int]:
        """Ensure hour is in valid range."""
        if v is not None and not (0 <= v <= 23):
            raise ValueError("hour must be 0-23")
        return v
    
    @classmethod
    def from_date(cls, date_str: str, user_id: str, chunk_type: ChunkType, **kwargs) -> "MemoryMetadata":
        """Factory method to create metadata from a date string with auto-computed temporal fields."""
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if "T" in date_str else datetime.fromisoformat(date_str)
        except:
            # Fallback: try parsing as YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # Extract temporal fields
        day_of_week = dt.weekday()  # 0=Monday, 6=Sunday
        hour = dt.hour if "T" in date_str else None
        
        # ISO week number
        iso_calendar = dt.isocalendar()
        week_of_year = iso_calendar[1]
        
        return cls(
            date=date_str.split("T")[0] if "T" in date_str else date_str,
            datetime=date_str if "T" in date_str else None,
            day_of_week=day_of_week,
            hour=hour,
            week_of_year=week_of_year,
            month=dt.month,
            year=dt.year,
            chunk_type=chunk_type,
            user_id=user_id,
            **kwargs
        )


class MemoryChunk(BaseModel):
    """A single memory chunk with text content and structured metadata."""
    
    id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="The text content to embed")
    metadata: MemoryMetadata = Field(..., description="Structured metadata")
    
    # For recursive summarization: raw chunks vs summaries
    is_summary: bool = Field(default=False, description="True if this is a summary of other chunks")
    raw_chunks: List[str] = Field(default_factory=list, description="Raw text of child chunks (if this is a summary)")
    
    @classmethod
    def from_daily_report(
        cls,
        report_id: str,
        report_date: str,
        user_id: str,
        summary: str,
        wins: List[str],
        struggles: List[str],
        reflections: List[str],
        tasks: List[Dict[str, Any]],
        sentiment: str,
        pillar_stats: Optional[Dict[str, int]] = None,
    ) -> List["MemoryChunk"]:
        """Convert a DailyReport into multiple MemoryChunks.
        
        Creates:
        - One summary chunk for the day
        - Individual chunks for wins, struggles, reflections
        - Task-level chunks
        """
        chunks = []
        
        # Main daily summary (parent chunk)
        summary_metadata = MemoryMetadata.from_date(
            report_date,
            user_id,
            ChunkType.DAILY_SUMMARY,
            level=MemoryLevel.DAY,
            sentiment=sentiment.lower() if sentiment else None,
        )
        
        summary_text = f"Daily Report Summary ({report_date}): {summary}"
        if wins:
            summary_text += f" Wins: {', '.join(wins)}"
        if struggles:
            summary_text += f" Struggles: {', '.join(struggles)}"
        
        summary_chunk = cls(
            id=f"report_{report_id}_summary",
            text=summary_text,
            metadata=summary_metadata,
            is_summary=True,
        )
        chunks.append(summary_chunk)
        
        # Individual win chunks
        for i, win in enumerate(wins):
            win_metadata = MemoryMetadata.from_date(
                report_date,
                user_id,
                ChunkType.REPORT_WIN,
                parent_id=summary_chunk.id,
                sentiment="positive",
            )
            chunks.append(cls(
                id=f"report_{report_id}_win_{i}",
                text=f"Win: {win}",
                metadata=win_metadata,
            ))
        
        # Individual struggle chunks
        for i, struggle in enumerate(struggles):
            struggle_metadata = MemoryMetadata.from_date(
                report_date,
                user_id,
                ChunkType.REPORT_STRUGGLE,
                parent_id=summary_chunk.id,
                sentiment="negative",
            )
            chunks.append(cls(
                id=f"report_{report_id}_struggle_{i}",
                text=f"Struggle: {struggle}",
                metadata=struggle_metadata,
            ))
        
        # Individual reflection chunks
        for i, reflection in enumerate(reflections):
            reflection_metadata = MemoryMetadata.from_date(
                report_date,
                user_id,
                ChunkType.REPORT_REFLECTION,
                parent_id=summary_chunk.id,
            )
            chunks.append(cls(
                id=f"report_{report_id}_reflection_{i}",
                text=f"Reflection: {reflection}",
                metadata=reflection_metadata,
            ))
        
        # Task chunks
        for task in tasks:
            task_metadata = MemoryMetadata.from_date(
                report_date,
                user_id,
                ChunkType.REPORT_TASK,
                parent_id=summary_chunk.id,
                task_id=task.get("task_id"),
                node_id=task.get("node_id"),
                sentiment="positive" if task.get("status") == "DONE" else "negative",
            )
            
            status_emoji = "✅" if task.get("status") == "DONE" else "❌"
            task_text = f"{status_emoji} Task: {task.get('name', 'Unknown')} - Status: {task.get('status')}"
            if task.get("user_comment"):
                task_text += f" - Comment: {task['user_comment']}"
            
            chunks.append(cls(
                id=f"report_{report_id}_task_{task.get('task_id', i)}",
                text=task_text,
                metadata=task_metadata,
            ))
        
        # Update parent chunk's child_ids
        summary_chunk.metadata.child_ids = [c.id for c in chunks if c.id != summary_chunk.id]
        
        return chunks
