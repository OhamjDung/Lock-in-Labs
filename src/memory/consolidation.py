"""Memory consolidation agent - verifies patterns against new data using rolling pattern file."""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .vector_store import SemanticMemory
from .pattern_file import PatternFile, Pattern
from .schema import MemoryChunk, MemoryMetadata, ChunkType, MemoryLevel
from src.models import CharacterSheet, DailyReport
from src.llm import LLMClient


class ConsolidationAgent:
    """Consolidation Agent: Verifies existing patterns against new data, updates confidence scores.
    
    CRITICAL FIX: This is NOT pattern extraction - it's pattern VERIFICATION.
    - Reads existing patterns from PatternFile
    - Compares them against yesterday's logs
    - Updates confidence scores (strengthens/weakens patterns)
    - Only creates NEW patterns if LLM identifies something completely novel
    
    This solves the "Consolidation Hallucination" - LLM can't find long-term patterns
    from one day's data, but it CAN verify if new data supports existing patterns.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def consolidate_daily(
        self,
        memory: SemanticMemory,
        sheet: CharacterSheet,
        date: str,
        pattern_file: Optional[PatternFile] = None,
    ) -> Dict[str, any]:
        """Verify existing patterns against a single day's memories.
        
        Args:
            memory: SemanticMemory instance
            sheet: CharacterSheet to update
            date: Date to consolidate (YYYY-MM-DD)
            pattern_file: PatternFile instance (creates new if None)
            
        Returns:
            Dict with:
                - verified_patterns: List of patterns that were verified/updated
                - new_patterns: List of newly created patterns (should be rare)
                - updated_facts: List of facts added to user_facts
        """
        if pattern_file is None:
            pattern_file = PatternFile(user_id=sheet.user_id)
        
        # Get all chunks for this day (from audit trail, not just Vector DB)
        daily_chunks = memory.get_daily_details(date)
        
        if not daily_chunks:
            return {
                "verified_patterns": [],
                "new_patterns": [],
                "updated_facts": []
            }
        
        # Combine day's content for pattern verification
        day_content = "\n".join([chunk.text for chunk in daily_chunks])
        
        # Get existing patterns
        existing_patterns = pattern_file.get_all_patterns()
        
        # Verify each existing pattern against today's data
        verified_patterns = []
        for pattern in existing_patterns:
            verified = self._verify_pattern_against_day(pattern, day_content, pattern_file)
            if verified:
                verified_patterns.append(pattern)
        
        # Check for completely new patterns (only if LLM identifies something novel)
        new_patterns = self._identify_new_patterns(day_content, existing_patterns, pattern_file)
        
        # Update user_facts from high-confidence patterns
        updated_facts = []
        high_confidence_patterns = pattern_file.to_user_facts()
        for fact in high_confidence_patterns:
            if fact not in sheet.user_facts:
                sheet.user_facts.append(fact)
                updated_facts.append(fact)
        
        return {
            "verified_patterns": verified_patterns,
            "new_patterns": new_patterns,
            "updated_facts": updated_facts
        }
    
    def _verify_pattern_against_day(
        self,
        pattern: Pattern,
        day_content: str,
        pattern_file: PatternFile,
    ) -> bool:
        """Verify if a single pattern is supported by today's data.
        
        Returns True if pattern was updated (strengthened or weakened).
        """
        prompt = f"""You are verifying a user behavior pattern against today's log entry.

Existing Pattern:
"{pattern.description}"
Current Confidence: {pattern.confidence:.2f}
Evidence Count: {pattern.evidence_count}

Today's Log Entry:
"{day_content}"

Does today's data SUPPORT or CONTRADICT this pattern?
- SUPPORT: The pattern is clearly visible in today's data
- CONTRADICT: Today's data goes against the pattern
- NEUTRAL: Today's data doesn't relate to this pattern

Respond with ONLY: SUPPORT, CONTRADICT, or NEUTRAL
"""
        
        try:
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_client.default_model,
            )
            response = response.strip().upper()
            
            if "SUPPORT" in response:
                pattern_file.verify_pattern(pattern.pattern_id, new_evidence=True)
                return True
            elif "CONTRADICT" in response:
                pattern_file.verify_pattern(pattern.pattern_id, new_evidence=False)
                return True
            # NEUTRAL: no update
            return False
        except Exception as e:
            print(f"[ConsolidationAgent] Error verifying pattern {pattern.pattern_id}: {e}")
            return False
    
    def _identify_new_patterns(
        self,
        day_content: str,
        existing_patterns: List[Pattern],
        pattern_file: PatternFile,
    ) -> List[Pattern]:
        """Identify completely new patterns (should be rare - most patterns already exist)."""
        existing_descriptions = "\n".join([f"- {p.description}" for p in existing_patterns[:20]])  # Sample
        
        prompt = f"""Analyze today's log entry for any NEW behavioral patterns that are NOT already in the existing patterns list.

Today's Log Entry:
"{day_content}"

Existing Patterns (do not repeat these):
{existing_descriptions if existing_descriptions else "None yet"}

Only identify patterns that are:
1. NOT already in the existing list above
2. Clear and observable (not vague)
3. Specific enough to verify in future days

Format: Return ONLY the pattern description, one per line. If no new patterns, return "NONE".

Example valid pattern: "Fails to complete coding tasks when sleep is less than 6 hours"
Example invalid (too vague): "Has bad days sometimes"
"""
        
        try:
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_client.default_model,
            )
            
            new_patterns = []
            for line in response.split("\n"):
                line = line.strip()
                if line and line.upper() != "NONE" and not line.startswith("-"):
                    # Clean up line
                    if line.startswith("Pattern:"):
                        line = line[8:].strip()
                    pattern = pattern_file.create_pattern_from_insight(
                        line,
                        category="general",
                        initial_confidence=0.5  # Start at medium confidence
                    )
                    new_patterns.append(pattern)
            
            return new_patterns
        except Exception as e:
            print(f"[ConsolidationAgent] Error identifying new patterns: {e}")
            return []
    
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
        
        response = self.llm_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.llm_client.default_model,
        )
        summary_text = response[:500]  # Limit length
        
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
    
