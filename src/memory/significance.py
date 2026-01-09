"""Significance scoring - determines which memories go to Vector DB vs audit trail."""

from src.llm import LLMClient


class SignificanceScorer:
    """Calculates long-term strategic value (1-10) for memory chunks.
    
    Only chunks with score >= threshold are stored in Vector DB.
    Lower scores go to audit trail (JSON/SQL) only.
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client or LLMClient()
    
    def calculate_significance(self, log_entry: str, context: str = "") -> int:
        """Rate the long-term strategic value of a log entry.
        
        Criteria:
        1-3: Routine maintenance (ate food, slept, did reps). NO new learning.
        4-6: Minor mood shifts or small observations.
        7-8: Strong emotional event, specific lesson learned, or clear cause-effect pattern identified.
        9-10: Major life milestone, breakthrough insight, or critical failure analysis.
        
        Args:
            log_entry: The text content to score
            context: Optional context (e.g., user facts, previous patterns)
            
        Returns:
            Integer score 1-10
        """
        prompt = f"""Analyze this daily log entry and rate its "Long-Term Strategic Value" on a scale of 1-10.

Log Entry:
"{log_entry}"

{context if context else ""}

Scoring Criteria:
- 1-3: Routine maintenance with NO new learning (ate food, slept, did reps, completed routine task)
- 4-6: Minor mood shifts or small observations (felt tired, had a good day, minor note)
- 7-8: Strong emotional event, specific lesson learned, or clear cause-effect pattern (e.g., "Skipped gym because I stayed up too late - need to prioritize sleep")
- 9-10: Major life milestone, breakthrough insight, or critical failure analysis (e.g., "Realized I've been avoiding social situations due to anxiety - need therapy")

Return ONLY the integer score (1-10). No explanation."""

        try:
            response = self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.llm_client.default_model,
            )
            
            # Extract integer from response
            score_str = response.strip()
            # Remove any non-numeric characters except digits
            score_str = ''.join(c for c in score_str if c.isdigit())
            
            if score_str:
                score = int(score_str)
                # Clamp to valid range
                score = max(1, min(10, score))
                return score
            else:
                # Default to mid-range if parsing fails
                return 5
        except Exception as e:
            print(f"[SignificanceScorer] Error calculating significance: {e}. Defaulting to 5.")
            return 5
    
    def batch_calculate(self, log_entries: list[str], context: str = "") -> list[int]:
        """Calculate significance for multiple entries (more efficient)."""
        # For now, just call individually. Could optimize with batch LLM call later.
        return [self.calculate_significance(entry, context) for entry in log_entries]


# Default threshold: Only store memories with significance >= 7 in Vector DB
DEFAULT_SIGNIFICANCE_THRESHOLD = 7
