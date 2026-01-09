"""Integration helpers to connect semantic memory with existing Life OS components."""

from typing import List, Optional
from datetime import datetime, timedelta

from .vector_store import SemanticMemory
from .schema import MemoryChunk
from .consolidation import ConsolidationAgent
from src.models import CharacterSheet, DailyReport


def sync_daily_report_to_memory(
    memory: SemanticMemory,
    report: DailyReport,
    user_id: str,
) -> List[str]:
    """Convert a DailyReport into memory chunks and add to vector store.
    
    This is the main integration point: call this after saving a DailyReport.
    
    Args:
        memory: SemanticMemory instance
        report: DailyReport to sync
        user_id: User ID
        
    Returns:
        List of chunk IDs that were added
    """
    # Convert DailyReport to MemoryChunks
    chunks = MemoryChunk.from_daily_report(
        report_id=f"report_{report.date}",
        report_date=report.date,
        user_id=user_id,
        summary=report.summary,
        wins=report.wins,
        struggles=report.struggles,
        reflections=report.reflections,
        tasks=[
            {
                "task_id": task.task_id,
                "node_id": task.node_id,
                "status": task.status.value,
                "name": f"Task {task.task_id}",  # You may want to map this from DailyTask
                "user_comment": task.user_comment or "",
            }
            for task in report.tasks
        ],
        sentiment=report.sentiment,
        pillar_stats=None,  # Could extract from stats_delta if needed
    )
    
    # Add all chunks to memory
    chunk_ids = memory.add_chunks(chunks)
    
    return chunk_ids


def sync_all_reports_to_memory(
    memory: SemanticMemory,
    sheet: CharacterSheet,
) -> int:
    """Sync all existing DailyReports from CharacterSheet to memory.
    
    Useful for one-time migration or initialization.
    
    Returns:
        Number of reports synced
    """
    synced_count = 0
    
    for report in sheet.daily_reports:
        try:
            sync_daily_report_to_memory(memory, report, sheet.user_id)
            synced_count += 1
        except Exception as e:
            print(f"[Memory Integration] Error syncing report {report.date}: {e}")
    
    return synced_count


def query_user_memory(
    memory: SemanticMemory,
    query: str,
    filters: Optional[dict] = None,
    n_results: int = 5,
) -> List[dict]:
    """Query user memory and return formatted results.
    
    Args:
        memory: SemanticMemory instance
        query: Search query
        filters: Optional metadata filters (e.g., {"day_of_week": 1} for Tuesdays)
        n_results: Number of results to return
        
    Returns:
        List of dicts with chunk info and metadata
    """
    results = memory.search(query=query, n_results=n_results, filters=filters)
    
    return [
        {
            "text": r.chunk.text,
            "score": r.score,
            "date": r.chunk.metadata.date,
            "type": r.chunk.metadata.chunk_type.value,
            "sentiment": r.chunk.metadata.sentiment,
            "pillar": r.chunk.metadata.pillar,
        }
        for r in results
    ]


def run_nightly_consolidation(
    memory: SemanticMemory,
    sheet: CharacterSheet,
    date: Optional[str] = None,
) -> List[str]:
    """Run the nightly consolidation process for a specific date.
    
    This is the "dreaming" process that:
    1. Consolidates the day's memories
    2. Extracts insights
    3. Updates CharacterSheet.user_facts
    
    Args:
        memory: SemanticMemory instance
        sheet: CharacterSheet to update
        date: Date to consolidate (default: yesterday)
        
    Returns:
        List of new insights added to user_facts
    """
    if date is None:
        # Default to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")
    
    consolidator = ConsolidationAgent()
    new_insights = consolidator.consolidate_daily(memory, sheet, date)
    
    return new_insights


def run_weekly_consolidation(
    memory: SemanticMemory,
    sheet: CharacterSheet,
    week_start_date: Optional[str] = None,
) -> List[str]:
    """Run weekly consolidation process.
    
    Args:
        memory: SemanticMemory instance
        sheet: CharacterSheet to update
        week_start_date: Start of week (YYYY-MM-DD), defaults to Monday of last week
        
    Returns:
        List of new insights added to user_facts
    """
    if week_start_date is None:
        # Default to Monday of last week
        today = datetime.now()
        days_since_monday = (today.weekday()) % 7
        last_monday = today - timedelta(days=days_since_monday + 7)
        week_start_date = last_monday.strftime("%Y-%m-%d")
    
    consolidator = ConsolidationAgent()
    new_insights = consolidator.consolidate_weekly(memory, sheet, week_start_date)
    
    return new_insights


def analyze_day_of_week_pattern(
    memory: SemanticMemory,
    day_of_week: int,
    query: str = "failure struggle difficulty skip",
) -> dict:
    """Analyze patterns for a specific day of week.
    
    Example: "Why do I always fail on Tuesdays?"
    
    Args:
        memory: SemanticMemory instance
        day_of_week: 0=Monday, 6=Sunday
        query: Search query for pattern analysis
        
    Returns:
        Dictionary with analysis results
    """
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_name = day_names[day_of_week]
    
    # Get all chunks for this day of week
    results = memory.search_by_day(day_of_week, query, n_results=20)
    
    # Count by type
    type_counts = {}
    sentiment_counts = {}
    
    for result in results:
        chunk_type = result.chunk.metadata.chunk_type.value
        type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
        
        sentiment = result.chunk.metadata.sentiment or "unknown"
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
    
    # Get sample texts
    sample_texts = [r.chunk.text[:100] for r in results[:5]]
    
    return {
        "day": day_name,
        "total_matches": len(results),
        "type_breakdown": type_counts,
        "sentiment_breakdown": sentiment_counts,
        "sample_entries": sample_texts,
    }


# Example usage in a reporting workflow:
"""
# After finalizing a DailyReport in reporting agent:

from src.memory.integration import sync_daily_report_to_memory, run_nightly_consolidation
from src.memory.vector_store import SemanticMemory

# Initialize memory (once per user)
memory = SemanticMemory(user_id=sheet.user_id)

# Sync the report
chunk_ids = sync_daily_report_to_memory(memory, report, sheet.user_id)

# Run nightly consolidation (could be a background job)
new_insights = run_nightly_consolidation(memory, sheet, date=report.date)

# Later, query memory:
from src.memory.integration import query_user_memory, analyze_day_of_week_pattern

# "Why do I fail on Tuesdays?"
pattern = analyze_day_of_week_pattern(memory, day_of_week=1, query="failure")

# General semantic search
results = query_user_memory(memory, "coding failures", filters={"pillar": "CAREER"})
"""
