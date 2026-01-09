"""Utility functions for reporting agent - citation verification and grounding."""

from difflib import SequenceMatcher
from typing import Dict, List, Any


def verify_citations(decision_json: Dict[str, Any], user_logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Scans the LLM's 'evidence' and finds the REAL log entry that matches it.
    Fixes the date if the LLM hallucinated it.
    
    Uses multiple matching strategies:
    1. Exact substring match (highest confidence)
    2. Citation contained in log (reverse substring)
    3. Sequence matcher on full text
    4. Keyword overlap (for partial citations)
    
    Args:
        decision_json: The decision object from LLM (may have wrong dates)
        user_logs: List of actual log entries with correct dates
        
    Returns:
        decision_json with verified citations added:
        - verified_date: Corrected date from actual log
        - is_verified: True if citation was verified
        - verification_score: Match confidence (0.0-1.0)
        - date_corrected: True if date was wrong and got fixed
    """
    for factor in decision_json.get("contributing_factors", []):
        cited_text = factor.get("citation_text", "").lower().strip()
        cited_date = factor.get("citation_date", "")
        
        # Extract key phrases from citation (remove common words)
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        citation_words = set(word for word in cited_text.split() if word not in stop_words and len(word) > 3)
        
        best_match = None
        best_score = 0.0
        best_match_type = None
        
        for log in user_logs:
            log_content = log.get("content", "").lower()
            log_date = log.get("date", "")
            
            # Strategy 1: Exact substring match (highest confidence)
            if cited_text in log_content:
                score = 1.0
                match_type = "exact_substring"
            # Strategy 2: Citation is contained in log (reverse substring)
            elif log_content in cited_text and len(cited_text) < len(log_content) * 2:
                score = 0.95
                match_type = "contains_substring"
            # Strategy 3: Sequence matcher on full text
            else:
                score = SequenceMatcher(None, cited_text, log_content).ratio()
                match_type = "sequence_match"
                
                # Strategy 4: Keyword overlap (boost score if key words match)
                log_words = set(word for word in log_content.split() if word not in stop_words and len(word) > 3)
                if citation_words and log_words:
                    overlap = len(citation_words & log_words) / len(citation_words)
                    # Boost score by overlap ratio (but cap at 0.9)
                    score = min(0.9, score + (overlap * 0.3))
            
            if score > best_score:
                best_score = score
                best_match = log
                best_match_type = match_type
        
        # Lower threshold for verification (0.5 instead of 0.7) since citations are often partial
        # But require at least some meaningful overlap
        if best_match and best_score >= 0.5:
            # FORCE correct the date/id
            factor["verified_date"] = best_match["date"]
            factor["verified_id"] = best_match.get("id")
            factor["original_citation_date"] = cited_date  # Keep original for comparison
            factor["verification_score"] = best_score
            factor["verification_type"] = best_match_type
            factor["is_verified"] = True
            factor["verified_content"] = best_match.get("content", "")[:150]  # First 150 chars for reference
            
            # Check if date was wrong
            if cited_date and cited_date != best_match["date"]:
                factor["date_corrected"] = True
            else:
                factor["date_corrected"] = False
        else:
            factor["is_verified"] = False
            factor["verification_score"] = best_score
            factor["verification_type"] = best_match_type
            if best_match:
                factor["closest_match_date"] = best_match["date"]
                factor["closest_match_score"] = best_score
                factor["closest_match_content"] = best_match.get("content", "")[:100]
            
    return decision_json
