"""Memory consolidation agent - transforms episodic memory into semantic/procedural memory."""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .vector_store import SemanticMemory
from .schema import MemoryChunk, MemoryMetadata, ChunkType, MemoryLevel
from src.models import CharacterSheet, DailyReport
from src.llm import LLMClient


class ConsolidationAgent:
    """Consolidation Agent: Reads raw logs and updates user profile with insights.
    
    This is the "nightly dreaming" process that:
    1. Reads today's logs from vector DB
    2. Analyzes patterns with LLM
    3. Updates CharacterSheet.user_facts (semantic/procedural memory)
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def consolidate_daily(
        self,
        memory: SemanticMemory,
        sheet: CharacterSheet,
        date: str,
    ) -> List[str]:
        """Consolidate a single day's memories into semantic insights.
        
        Args:
            memory: SemanticMemory instance
            sheet: CharacterSheet to update
            date: Date to consolidate (YYYY-MM-DD)
            
        Returns:
            List of new insights added to user_facts
        """
        # Get all chunks for this day
        daily_chunks = memory.get_daily_details(date)
        
        if not daily_chunks:
            return []
        
        # Get or create daily summary
        summary_chunk = memory.get_daily_summary(date)
        if not summary_chunk:
            # If no summary exists, create one from raw chunks
            summary_chunk = self._create_daily_summary(memory, date, daily_chunks)
        
        # Analyze patterns using LLM
        insights = self._extract_insights(daily_chunks, sheet)
        
        # Update user_facts with new insights
        new_facts = []
        for insight in insights:
            if insight not in sheet.user_facts:
                sheet.user_facts.append(insight)
                new_facts.append(insight)
        
        return new_facts
    
    def consolidate_weekly(
        self,
        memory: SemanticMemory,
        sheet: CharacterSheet,
        week_start_date: str,
    ) -> List[str]:
        """Consolidate a week's memories into higher-level insights.
        
        Creates weekly summary chunks and extracts cross-day patterns.
        """
        from datetime import datetime, timedelta
        
        dt = datetime.fromisoformat(week_start_date)
        week_num = dt.isocalendar()[1]
        year = dt.year
        
        # Get all chunks for the week
        week_results = memory.get_weekly_pattern(week_num, year)
        
        if not week_results:
            return []
        
        # Extract weekly patterns (week_results is List[SearchResult])
        week_chunks = [r.chunk for r in week_results]
        insights = self._extract_weekly_patterns(week_chunks, sheet)
        
        # Create weekly summary chunk
        weekly_summary = self._create_weekly_summary(
            memory,
            week_start_date,
            week_results,
            insights
        )
        
        # Update user_facts
        new_facts = []
        for insight in insights:
            if insight not in sheet.user_facts:
                sheet.user_facts.append(insight)
                new_facts.append(insight)
        
        return new_facts
    
    def _create_daily_summary(
        self,
        memory: SemanticMemory,
        date: str,
        raw_chunks: List[MemoryChunk],
    ) -> MemoryChunk:
        """Create a daily summary chunk from raw chunks."""
        # Combine all raw chunk texts
        raw_texts = [chunk.text for chunk in raw_chunks]
        combined_text = "\n".join(raw_texts)
        
        # Use LLM to create a concise summary
        prompt = f"""Summarize this day's activities and events in 2-3 sentences:

{combined_text}

Provide a concise summary focusing on:
- Main activities accomplished
- Challenges or struggles
- Overall mood/sentiment
"""
        
        summary_text = self.llm_client.complete(prompt, max_tokens=150)
        
        # Create summary metadata
        summary_metadata = MemoryMetadata.from_date(
            date,
            memory.user_id,
            ChunkType.DAILY_SUMMARY,
            level=MemoryLevel.DAY,
            child_ids=[chunk.id for chunk in raw_chunks]
        )
        
        summary_chunk = MemoryChunk(
            id=f"daily_summary_{date}",
            text=f"Daily Summary ({date}): {summary_text}",
            metadata=summary_metadata,
            is_summary=True,
            raw_chunks=raw_texts
        )
        
        memory.add_chunk(summary_chunk)
        
        # Update raw chunks to point to parent
        for chunk in raw_chunks:
            chunk.metadata.parent_id = summary_chunk.id
            # Re-add with updated metadata
            memory.add_chunk(chunk)
        
        return summary_chunk
    
    def _create_weekly_summary(
        self,
        memory: SemanticMemory,
        week_start: str,
        week_results: List,
        insights: List[str],
    ) -> MemoryChunk:
        """Create a weekly summary chunk."""
        from datetime import datetime, timedelta
        
        dt = datetime.fromisoformat(week_start)
        week_num = dt.isocalendar()[1]
        
        # Combine insights and chunk summaries
        insights_text = "\n".join([f"- {insight}" for insight in insights])
        
        summary_text = f"""Weekly Summary (Week {week_num} of {dt.year}):
Key patterns and insights from this week:
{insights_text}
"""
        
        summary_metadata = MemoryMetadata.from_date(
            week_start,
            memory.user_id,
            ChunkType.WEEKLY_SUMMARY,
            level=MemoryLevel.WEEK,
        )
        
        summary_chunk = MemoryChunk(
            id=f"weekly_summary_{week_start}",
            text=summary_text,
            metadata=summary_metadata,
            is_summary=True
        )
        
        memory.add_chunk(summary_chunk)
        return summary_chunk
    
    def _extract_insights(
        self,
        chunks: List[MemoryChunk],
        sheet: CharacterSheet,
    ) -> List[str]:
        """Use LLM to extract actionable insights from daily chunks."""
        if not chunks:
            return []
        
        # Combine chunk texts
        chunk_texts = [chunk.text for chunk in chunks]
        combined_text = "\n\n".join(chunk_texts)
        
        # Get existing user facts for context
        existing_facts = "\n".join([f"- {fact}" for fact in sheet.user_facts[-10:]])  # Last 10 facts
        
        prompt = f"""You are analyzing a user's daily log entries to extract actionable insights about their behavior patterns, weaknesses, and tendencies.

Existing user facts (context):
{existing_facts if existing_facts else "None yet"}

Today's log entries:
{combined_text}

Analyze these logs and extract 1-3 concise insights in the format:
- "Pattern: [observable pattern]"
- "Weakness: [specific weakness identified]"
- "Strength: [specific strength identified]"
- "Tendency: [behavioral tendency]"

Examples:
- "Weakness: Sleep deprivation causes coding task failures"
- "Tendency: Skips gym on Tuesdays when workload is high"
- "Strength: Consistent morning meditation improves focus"
- "Pattern: Fails to complete database tasks when given too many options"

Return ONLY the insights, one per line, starting with the category (Pattern/Weakness/Strength/Tendency). If no significant insights, return "None".
"""
        
        response = self.llm_client.complete(prompt, max_tokens=200)
        
        # Parse insights
        insights = []
        for line in response.split("\n"):
            line = line.strip()
            if line and line != "None" and (line.startswith("Pattern:") or 
                                            line.startswith("Weakness:") or
                                            line.startswith("Strength:") or
                                            line.startswith("Tendency:")):
                insights.append(line)
        
        return insights
    
    def _extract_weekly_patterns(
        self,
        chunks: List[MemoryChunk],
        sheet: CharacterSheet,
    ) -> List[str]:
        """Extract cross-day patterns from a week's worth of chunks."""
        if not chunks:
            return []
        
        # Group by day of week to find patterns
        by_day = {}
        for chunk in chunks:
            day = chunk.metadata.day_of_week
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(chunk)
        
        # Analyze day-of-week patterns
        patterns = []
        
        # Check for failure patterns by day
        failure_days = {}
        for day, day_chunks in by_day.items():
            failures = [c for c in day_chunks if "struggle" in c.text.lower() or 
                       c.metadata.chunk_type == ChunkType.REPORT_STRUGGLE or
                       c.metadata.sentiment == "negative"]
            if len(failures) >= 2:  # At least 2 failures on this day
                failure_days[day] = len(failures)
        
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day, count in failure_days.items():
            patterns.append(f"Pattern: Frequent failures on {day_names[day]} ({count} instances this week)")
        
        # Use LLM for more complex pattern analysis
        chunk_summaries = "\n".join([f"Day {day_names[c.metadata.day_of_week]}: {c.text[:100]}..." 
                                     for c in chunks[:20]])  # Sample
        
        existing_facts = "\n".join([f"- {fact}" for fact in sheet.user_facts[-10:]])
        
        prompt = f"""Analyze weekly patterns from these log entries:

Existing user facts:
{existing_facts if existing_facts else "None yet"}

Week's log entries (sample):
{chunk_summaries}

Extract 1-3 high-level patterns or insights that span multiple days. Focus on:
- Day-of-week patterns (e.g., "User consistently struggles on Tuesdays")
- Weekly trends (e.g., "Productivity decreases mid-week")
- Recurring obstacles (e.g., "Sleep issues affect all morning tasks")

Return insights in format:
- "Pattern: [description]"

If no clear patterns, return "None".
"""
        
        response = self.llm_client.complete(prompt, max_tokens=250)
        
        for line in response.split("\n"):
            line = line.strip()
            if line and line.startswith("Pattern:") and line not in patterns:
                patterns.append(line)
        
        return patterns
