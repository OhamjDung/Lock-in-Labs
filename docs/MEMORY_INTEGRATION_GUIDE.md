# Memory System Integration Guide

## ✅ Verification Complete

All tests passed:
- ✅ Significance gate: Filters routine logs correctly
- ✅ Vector DB filtering: Enforces threshold properly  
- ✅ Citation grounding: Fixes LLM date hallucinations
- ✅ Decision explainability: Generates structured JSON with verifiable citations

## Integration Steps

### Step 1: Update Reporting Flow to Sync Memory

After `apply_daily_report()` is called, sync the report to memory:

**In `backend/api.py` or wherever reporting is finalized:**

```python
from src.reporting.agent import ReportingAgent
from src.reporting.apply_updates import apply_daily_report

# After generating and applying report
report = agent.finalize_report(state, sheet, tree)
apply_daily_report(sheet, tree, report)

# NEW: Sync to semantic memory (with significance filtering)
sync_result = agent.sync_report_to_memory(report, sheet)
# sync_result["vector_db_chunks"]: High-significance only (goes to ChromaDB)
# sync_result["audit_trail_chunks"]: All chunks (save to JSON/SQL for factual queries)

# Save profile as usual
final_profile = {
    "character_sheet": sheet.model_dump(),
    "skill_tree": tree.model_dump(),
}
save_profile(final_profile, user_id)
```

### Step 2: Generate Weekly Decisions with Citations

When you need to adjust goals based on memory:

```python
from src.reporting.agent import ReportingAgent

agent = ReportingAgent()

# Generate decision for a specific goal
decision = agent.generate_weekly_decision(
    goal=sheet.goals[0],  # Target goal
    sheet=sheet,
    tree=tree,
    recent_reports=None,  # Uses last 7 days if None
)

# Decision structure:
# {
#   "target": "running_distance",
#   "old_value": "5km",
#   "new_value": "3km",
#   "decision_type": "DECREASE",
#   "confidence_score": 0.95,
#   "contributing_factors": [
#     {
#       "factor": "Injury Risk",
#       "weight": "negative",
#       "description": "...",
#       "citation_date": "2025-12-24",  # Original (may be wrong)
#       "citation_text": "Sharp pain in right knee...",
#       "verified_date": "2025-12-24",  # Corrected by grounding
#       "is_verified": true,
#       "date_corrected": false,
#       "verification_score": 1.0
#     }
#   ],
#   "explanation": "..."
# }

# Use verified_date (not citation_date) for UI display
# Show "date_corrected: true" indicator if date was wrong
```

### Step 3: Two-Tier Storage Pattern

**High-Significance (Vector DB):**
- Automatic: Handled by `sync_report_to_memory()`
- Only strategic memories (significance >= 7)
- Used for: "How do I usually handle failure?" queries

**Low-Significance (Audit Trail):**
- Store in CharacterSheet or separate JSON/SQL
- All routine activities
- Used for: "Did I run on Tuesday?" factual queries

```python
# Example: Store audit trail in CharacterSheet
if not hasattr(sheet, "audit_trail"):
    sheet.audit_trail = []

sync_result = agent.sync_report_to_memory(report, sheet)
sheet.audit_trail.extend(sync_result["audit_trail_chunks"])

# Query audit trail for factual queries
def did_user_run_on_date(user_id: str, date: str) -> bool:
    profile = load_profile(user_id)
    sheet = CharacterSheet(**profile["character_sheet"])
    for entry in sheet.audit_trail:
        if entry["date"] == date and "run" in entry["text"].lower():
            return True
    return False
```

## API Endpoints to Add

### 1. Sync Report to Memory

```python
@app.post("/api/reporting/sync-memory")
def sync_report_memory(payload: SyncMemoryRequest):
    """Sync a DailyReport to semantic memory."""
    agent = ReportingAgent()
    # ... load report and sheet ...
    result = agent.sync_report_to_memory(report, sheet)
    return {"synced": len(result["vector_db_chunks"]), "audit_trail": len(result["audit_trail_chunks"])}
```

### 2. Generate Weekly Decision

```python
@app.post("/api/reporting/generate-decision")
def generate_decision(payload: DecisionRequest):
    """Generate a decision object for goal adjustment."""
    agent = ReportingAgent()
    # ... load goal, sheet, tree ...
    decision = agent.generate_weekly_decision(goal, sheet, tree)
    return decision  # Already grounded/verified
```

### 3. Query Memory

```python
@app.post("/api/memory/query")
def query_memory(payload: MemoryQueryRequest):
    """Query semantic memory with filters."""
    from src.memory.vector_store import SemanticMemory
    memory = SemanticMemory(user_id=payload.user_id)
    results = memory.search(
        query=payload.query,
        n_results=payload.n_results,
        day_of_week=payload.day_of_week,  # Optional: "Why do I fail on Tuesdays?"
        date_range=payload.date_range,     # Optional: "Show me last month"
    )
    return [{"text": r.chunk.text, "date": r.chunk.metadata.date, "score": r.score} for r in results]
```

## Testing the Integration

### Manual Test

```python
# 1. Create a report
report = DailyReport(...)

# 2. Apply it
apply_daily_report(sheet, tree, report)

# 3. Sync to memory
agent = ReportingAgent()
sync_result = agent.sync_report_to_memory(report, sheet)
print(f"Synced {len(sync_result['vector_db_chunks'])} high-significance chunks")

# 4. Query memory
memory = agent._get_memory(sheet.user_id)
results = memory.search("struggles failures", n_results=5)
print(f"Found {len(results)} relevant memories")

# 5. Generate decision
decision = agent.generate_weekly_decision(sheet.goals[0], sheet, tree)
print(f"Decision: {decision['decision_type']}")
print(f"Verified citations: {sum(1 for f in decision['contributing_factors'] if f.get('is_verified'))}")
```

## What Changed in Codebase

### New Files
- `src/memory/utils.py` - Citation verification/grounding
- `src/reporting/utils.py` - Citation verification (same as above, consolidated)

### Updated Files
- `src/reporting/agent.py` - Added:
  - `sync_report_to_memory()` - Syncs reports with significance filtering
  - `generate_weekly_decision()` - Generates decisions with grounded citations
  - Lazy initialization of memory components

### New Dependencies
- `chromadb` - Vector database (already installed)
- `sentence-transformers` - Embeddings (already installed)

## Next Steps

1. ✅ **Backend verified** - All tests pass
2. ✅ **Grounding verified** - Citation verification works
3. ✅ **Integration code written** - Ready to wire up
4. 📦 **Wire up API endpoints** - Add the 3 endpoints above
5. 📦 **Build React UI** - Use `decision_output.json` structure
6. 📦 **Test end-to-end** - Full flow from report → memory → decision

The JSON structure is **locked in** - safe to build frontend now!
