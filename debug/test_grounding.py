"""Test Citation Grounding - verify we can fix LLM date hallucinations."""

import sys
import os
import json
from pathlib import Path
from difflib import SequenceMatcher

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_citations(decision_json, user_logs):
    """
    Scans the LLM's 'evidence' and finds the REAL log entry that matches it.
    Fixes the date if the LLM hallucinated it.
    
    Uses multiple matching strategies:
    1. Exact substring match (highest confidence)
    2. Sequence matcher on full text
    3. Keyword overlap (for partial citations)
    
    Args:
        decision_json: The decision object from LLM (may have wrong dates)
        user_logs: List of actual log entries with correct dates
        
    Returns:
        decision_json with verified citations added
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


def test_grounding():
    """Test that grounding fixes hallucinated dates."""
    print("=" * 60)
    print("TEST: CITATION GROUNDING")
    print("=" * 60)
    
    # Load the decision output from previous test (has wrong dates)
    decision_path = Path("debug/decision_output.json")
    if not decision_path.exists():
        print("[X] Error: decision_output.json not found. Run test_decision_logic.py first.")
        return
    
    with open(decision_path, "r") as f:
        data = json.load(f)
    
    decision = data["decision"]
    user_logs = data["relevant_memories"]
    
    print(f"\nLoaded decision with {len(decision.get('contributing_factors', []))} contributing factors")
    print(f"Loaded {len(user_logs)} actual log entries")
    
    # Show original (potentially wrong) citations
    print("\n--- ORIGINAL CITATIONS (From LLM - May Have Wrong Dates) ---")
    for i, factor in enumerate(decision.get("contributing_factors", []), 1):
        print(f"\nFactor {i}: {factor.get('factor', 'N/A')}")
        print(f"  Citation Date: {factor.get('citation_date', 'N/A')}")
        print(f"  Citation Text: \"{factor.get('citation_text', 'N/A')[:60]}...\"")
    
    # Apply grounding
    print("\n" + "=" * 60)
    print("APPLYING GROUNDING LOGIC...")
    print("=" * 60)
    
    verified_decision = verify_citations(decision, user_logs)
    
    # Show verified citations
    print("\n--- VERIFIED CITATIONS (Grounding Applied) ---")
    all_verified = True
    date_corrections = []
    
    for i, factor in enumerate(verified_decision.get("contributing_factors", []), 1):
        is_verified = factor.get("is_verified", False)
        original_date = factor.get("citation_date", "N/A")
        verified_date = factor.get("verified_date", "N/A")
        score = factor.get("verification_score", 0.0)
        
        status = "[OK]" if is_verified else "[X]"
        print(f"\n{status} Factor {i}: {factor.get('factor', 'N/A')}")
        print(f"  Original Date (LLM): {original_date}")
        print(f"  Verified Date (Actual): {verified_date}")
        print(f"  Match Score: {score:.2%}")
        
        if is_verified:
            if original_date != verified_date:
                date_corrections.append({
                    "factor": factor.get("factor"),
                    "original": original_date,
                    "corrected": verified_date
                })
                print(f"  [CORRECTED] Date was wrong! Fixed: {original_date} -> {verified_date}")
            else:
                print(f"  [OK] Date was correct!")
        else:
            print(f"  [WARNING] Could not verify citation (score: {score:.2%})")
            all_verified = False
    
    # Verify the corrections make sense
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    if date_corrections:
        print(f"\n[OK] Found {len(date_corrections)} date corrections:")
        for correction in date_corrections:
            print(f"  - {correction['factor']}: {correction['original']} -> {correction['corrected']}")
    
    # Check if corrections are actually correct
    print("\n--- VALIDATION: Are Corrections Correct? ---")
    corrections_valid = True
    
    for factor in verified_decision.get("contributing_factors", []):
        if not factor.get("is_verified"):
            continue
            
        verified_date = factor.get("verified_date")
        citation_text = factor.get("citation_text", "").lower()
        
        # Find the log entry with that date
        matching_log = next((log for log in user_logs if log["date"] == verified_date), None)
        
        if matching_log:
            # Check if citation text actually appears in that log
            log_content = matching_log.get("content", "").lower()
            if citation_text in log_content or any(word in log_content for word in citation_text.split()[:3]):
                print(f"[OK] Verified citation for {verified_date}: Text matches log entry")
            else:
                print(f"[!] Warning: Verified date {verified_date} but citation text doesn't fully match")
                print(f"    Citation: \"{citation_text[:50]}...\"")
                print(f"    Log entry: \"{matching_log.get('content', '')[:50]}...\"")
                corrections_valid = False
        else:
            print(f"[X] ERROR: Verified date {verified_date} but no log entry found!")
            corrections_valid = False
    
    # Final summary
    print("\n" + "=" * 60)
    print("GROUNDING TEST SUMMARY")
    print("=" * 60)
    
    checks = {
        "All citations verified": all_verified,
        "Date corrections applied": len(date_corrections) > 0,
        "Corrections are valid": corrections_valid,
    }
    
    for check, passed in checks.items():
        status = "[OK]" if passed else "[X]"
        print(f"{status} {check}")
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("\n[OK] SUCCESS: Grounding logic works correctly!")
        print("   Date hallucinations can be automatically corrected.")
    else:
        print("\n[!] WARNING: Some checks failed. Review grounding logic.")
    
    # Export corrected decision
    output_path = Path("debug/decision_grounded.json")
    with open(output_path, "w") as f:
        json.dump({
            "original_decision": decision,
            "grounded_decision": verified_decision,
            "corrections": date_corrections,
            "verification": checks,
        }, f, indent=2)
    
    print(f"\n Grounded decision saved to: {output_path}")
    print("=" * 60)
    
    return verified_decision, date_corrections, checks


def test_edge_cases():
    """Test edge cases: partial matches, no matches, similar dates."""
    print("\n" + "=" * 60)
    print("TEST: GROUNDING EDGE CASES")
    print("=" * 60)
    
    # Edge case 1: Citation text is partial (should still match)
    print("\n--- Edge Case 1: Partial Citation Text ---")
    decision_partial = {
        "contributing_factors": [
            {
                "factor": "Test Factor",
                "citation_date": "2025-01-15",  # Wrong date
                "citation_text": "sharp pain in knee"  # Partial text
            }
        ]
    }
    
    logs = [
        {
            "date": "2025-12-24",
            "content": "FUCK. Sharp pain in right knee at mile 1. Had to walk home. Limping now. This is bad.",
            "id": "log_1"
        }
    ]
    
    grounded = verify_citations(decision_partial, logs)
    factor = grounded["contributing_factors"][0]
    
    if factor.get("is_verified") and factor.get("verified_date") == "2025-12-24":
        print("[OK] Partial citation text correctly matched")
    else:
        print(f"[X] Failed: Expected verified_date=2025-12-24, got {factor.get('verified_date')}")
    
    # Edge case 2: No matching log (should mark as unverified)
    print("\n--- Edge Case 2: No Matching Log ---")
    decision_no_match = {
        "contributing_factors": [
            {
                "factor": "Non-existent Factor",
                "citation_date": "2025-01-15",
                "citation_text": "This citation does not exist in any log"
            }
        ]
    }
    
    grounded = verify_citations(decision_no_match, logs)
    factor = grounded["contributing_factors"][0]
    
    if not factor.get("is_verified"):
        print("[OK] Non-existent citation correctly marked as unverified")
    else:
        print("[X] Failed: Should have marked as unverified")
    
    # Edge case 3: Multiple similar logs (should pick best match)
    print("\n--- Edge Case 3: Multiple Similar Logs ---")
    decision_multiple = {
        "contributing_factors": [
            {
                "factor": "Multiple Match Test",
                "citation_date": "2025-01-15",
                "citation_text": "knee pain"  # Appears in multiple logs
            }
        ]
    }
    
    logs_multiple = [
        {"date": "2025-12-24", "content": "Sharp pain in right knee at mile 1"},
        {"date": "2025-12-25", "content": "Knee pain is getting worse"},
        {"date": "2025-12-31", "content": "Knee pain is improving"}
    ]
    
    grounded = verify_citations(decision_multiple, logs_multiple)
    factor = grounded["contributing_factors"][0]
    
    if factor.get("is_verified"):
        print(f"[OK] Multiple matches: Selected best match (date: {factor.get('verified_date')}, score: {factor.get('verification_score', 0):.2%})")
    else:
        print("[X] Failed: Should have found a match")
    
    print("=" * 60)


if __name__ == "__main__":
    result = test_grounding()
    test_edge_cases()
    
    print("\n" + "=" * 60)
    print("OVERALL GROUNDING TEST STATUS")
    print("=" * 60)
    
    if result:
        verified_decision, corrections, checks = result
        if all(checks.values()):
            print("[OK] ALL TESTS PASSED: Grounding logic is production-ready!")
            print("\nNext: Integrate into src/reporting/agent.py")
        else:
            print("[!] SOME TESTS FAILED: Review grounding logic before integration")
    else:
        print("[X] TEST FAILED: Could not load decision output")
    
    print("=" * 60)
