"""Integration helpers to connect semantic memory with existing Life OS components."""

from typing import List, Optional, Dict
from datetime import datetime, timedelta

from .vector_store import SemanticMemory
from .schema import MemoryChunk, MemoryMetadata
from .consolidation import ConsolidationAgent
from .significance import SignificanceScorer, DEFAULT_SIGNIFICANCE_THRESHOLD
from .pattern_file import PatternFile
from src.models import CharacterSheet, DailyReport


def sync_daily_report_to_memory(
    memory: SemanticMemory,
    report: DailyReport,
    user_id: str,
    significance_scorer: Optional[SignificanceScorer] = None,
    skip_significance_check: bool = False,
) -> Dict[str, any]:
    """Convert a DailyReport into memory chunks with significance scoring.
    
    CRITICAL: Only high-significance chunks (>= threshold) go to Vector DB.
    Low-significance chunks are returned for audit trail storage (JSON/SQL).
    
    This is the main integration point: call this after saving a DailyReport.
    
    Args:
        memory: SemanticMemory instance
        report: DailyReport to sync
        user_id: User ID
        significance_scorer: SignificanceScorer instance (creates new if None)
        skip_significance_check: Skip significance scoring (use with caution)
        
    Returns:
        Dict with:
            - vector_db_chunks: List of chunk IDs added to Vector DB (high significance)
            - audit_trail_chunks: List of chunks for audit trail (all chunks, low + high sig)
    """
    scorer = significance_scorer or SignificanceScorer()
    
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
    
    # Calculate significance scores for each chunk
    if not skip_significance_check:
        # Get context (existing user facts) for better scoring
        from src.storage import load_profile
        try:
            profile = load_profile(user_id)
            if profile and "character_sheet" in profile:
                sheet = CharacterSheet(**profile["character_sheet"])
                context = "\n".join(sheet.user_facts[-10:])  # Last 10 facts
            else:
                context = ""
        except:
            context = ""
        
        # Score each chunk
        for chunk in chunks:
            score = scorer.calculate_significance(chunk.text, context=context)
            # Update metadata with significance score
            chunk.metadata.significance_score = score
    
    # Add chunks to Vector DB (only high-significance ones will be added)
    vector_db_chunk_ids = memory.add_chunks(chunks, skip_significance_check=skip_significance_check)
    
    # All chunks (including low-significance) should be stored in audit trail
    # Return them for caller to store in JSON/SQL
    audit_trail_chunks = [
        {
            "id": chunk.id,
            "text": chunk.text,
            "date": chunk.metadata.date,
            "significance_score": chunk.metadata.significance_score,
            "metadata": chunk.metadata.model_dump(),
        }
        for chunk in chunks
    ]
    
    return {
        "vector_db_chunks": vector_db_chunk_ids,
        "audit_trail_chunks": audit_trail_chunks,
    }


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
    pattern_file: Optional[PatternFile] = None,
) -> Dict[str, any]:
    """Run the nightly consolidation process for a specific date.
    
    CRITICAL FIX: This is pattern VERIFICATION, not pattern extraction.
    - Verifies existing patterns against new data
    - Updates confidence scores
    - Only creates new patterns if LLM identifies something completely novel
    
    Args:
        memory: SemanticMemory instance
        sheet: CharacterSheet to update
        date: Date to consolidate (default: yesterday)
        pattern_file: PatternFile instance (creates new if None)
        
    Returns:
        Dict with verified_patterns, new_patterns, updated_facts
    """
    if date is None:
        # Default to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        date = yesterday.strftime("%Y-%m-%d")
    
    if pattern_file is None:
        pattern_file = PatternFile(user_id=sheet.user_id)
    
    consolidator = ConsolidationAgent()
    result = consolidator.consolidate_daily(memory, sheet, date, pattern_file)
    
    return result


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
