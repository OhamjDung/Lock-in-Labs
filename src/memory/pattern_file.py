"""Rolling Pattern File - maintains verified patterns across time, not extracted fresh each night."""

import json
import os
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Pattern(BaseModel):
    """A verified pattern with confidence scoring."""
    pattern_id: str = Field(..., description="Unique pattern identifier")
    description: str = Field(..., description="Human-readable pattern description")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    evidence_count: int = Field(default=0, description="Number of times this pattern was observed")
    first_observed: str = Field(..., description="ISO date when pattern was first identified")
    last_verified: str = Field(..., description="ISO date when pattern was last verified")
    category: str = Field(default="general", description="Pattern category (e.g., 'day_of_week', 'habit_failure', 'mood_pattern')")
    metadata: Dict = Field(default_factory=dict, description="Additional pattern metadata")


class PatternFile:
    """Manages rolling pattern state - patterns are verified/updated, not extracted fresh.
    
    This solves the "Consolidation Hallucination" problem:
    - Don't ask LLM to find new patterns every night (it can't see long-term trends)
    - Instead: Maintain a pattern file that gets UPDATED based on new data
    - LLM's job: Verify existing patterns against new data, update confidence scores
    """
    
    def __init__(self, user_id: str, file_path: Optional[str] = None):
        """Initialize pattern file for a user.
        
        Args:
            user_id: User identifier
            file_path: Path to pattern file (default: data/patterns/{user_id}_patterns.json)
        """
        self.user_id = user_id
        self.file_path = file_path or os.path.join("data", "patterns", f"{user_id}_patterns.json")
        self.patterns: Dict[str, Pattern] = {}
        self.load()
    
    def load(self):
        """Load patterns from disk."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    self.patterns = {
                        pid: Pattern(**pattern_data)
                        for pid, pattern_data in data.get("patterns", {}).items()
                    }
            except Exception as e:
                print(f"[PatternFile] Error loading patterns: {e}")
                self.patterns = {}
        else:
            self.patterns = {}
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
    
    def save(self):
        """Save patterns to disk."""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'w') as f:
            json.dump({
                "user_id": self.user_id,
                "last_updated": datetime.now().isoformat(),
                "patterns": {pid: pattern.model_dump() for pid, pattern in self.patterns.items()}
            }, f, indent=2)
    
    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get a specific pattern by ID."""
        return self.patterns.get(pattern_id)
    
    def get_patterns_by_category(self, category: str) -> List[Pattern]:
        """Get all patterns in a category."""
        return [p for p in self.patterns.values() if p.category == category]
    
    def add_pattern(self, pattern: Pattern):
        """Add or update a pattern."""
        self.patterns[pattern.pattern_id] = pattern
        self.save()
    
    def verify_pattern(
        self,
        pattern_id: str,
        new_evidence: bool,
        llm_feedback: Optional[str] = None,
    ) -> bool:
        """Verify/update a pattern based on new evidence.
        
        Args:
            pattern_id: Pattern to verify
            new_evidence: True if new data supports this pattern, False if it contradicts
            llm_feedback: Optional LLM analysis of the evidence
            
        Returns:
            True if pattern was updated, False if pattern doesn't exist
        """
        if pattern_id not in self.patterns:
            return False
        
        pattern = self.patterns[pattern_id]
        
        if new_evidence:
            # Strengthen pattern: increase evidence count and confidence
            pattern.evidence_count += 1
            # Confidence increases but with diminishing returns
            pattern.confidence = min(1.0, pattern.confidence + (1.0 - pattern.confidence) * 0.1)
        else:
            # Weaken pattern: decrease confidence
            pattern.confidence = max(0.0, pattern.confidence * 0.9)
        
        pattern.last_verified = datetime.now().isoformat()
        
        # Auto-delete very low confidence patterns
        if pattern.confidence < 0.1:
            del self.patterns[pattern_id]
            self.save()
            return True
        
        self.save()
        return True
    
    def create_pattern_from_insight(
        self,
        insight: str,
        category: str = "general",
        initial_confidence: float = 0.5,
    ) -> Pattern:
        """Create a new pattern from an LLM-generated insight.
        
        Only call this when LLM identifies a NEW pattern (not just verifying existing ones).
        """
        pattern_id = f"pattern_{len(self.patterns)}_{datetime.now().strftime('%Y%m%d')}"
        
        pattern = Pattern(
            pattern_id=pattern_id,
            description=insight,
            confidence=initial_confidence,
            evidence_count=1,
            first_observed=datetime.now().isoformat(),
            last_verified=datetime.now().isoformat(),
            category=category,
        )
        
        self.add_pattern(pattern)
        return pattern
    
    def get_all_patterns(self) -> List[Pattern]:
        """Get all patterns sorted by confidence (highest first)."""
        return sorted(self.patterns.values(), key=lambda p: p.confidence, reverse=True)
    
    def to_user_facts(self) -> List[str]:
        """Convert high-confidence patterns to user_facts format for CharacterSheet."""
        high_confidence = [p for p in self.patterns.values() if p.confidence >= 0.7]
        return [p.description for p in sorted(high_confidence, key=lambda p: p.confidence, reverse=True)]
