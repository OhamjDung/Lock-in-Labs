# Semantic Memory System for Life OS

This module implements **professional-grade RAG (Retrieval-Augmented Generation)** for your Life OS, transforming it from a simple chatbot into a true second brain.

## 🧠 Memory Hierarchy

The system implements a three-tier memory architecture:

1. **Short-Term (Context Window)**: The active chat conversation
2. **Long-Term Episodic Memory (Vector DB)**: All historical logs, reports, and conversations
3. **Semantic/Procedural Memory (User Profile)**: Consolidated insights and patterns extracted from episodic memory

## ✨ Advanced Features

### 1. Time-Aware Retrieval (Metadata Filtering)

**Problem**: Vectors are terrible at math and dates. If you embed "I failed on Tuesday," the vector emphasizes "failed," not the specific day.

**Solution**: Metadata filtering allows queries like "Why do I always fail on Tuesdays?" by:
- Pre-filtering chunks by `day_of_week == 1` (Tuesday)
- Then performing semantic search within that subset

```python
from src.memory.vector_store import SemanticMemory

memory = SemanticMemory(user_id="user_01")

# Search for Tuesday failures
tuesday_failures = memory.search_by_day(
    day_of_week=1,  # Tuesday
    query="failure struggle difficulty",
    n_results=10
)
```

### 2. Recursive Summarization (The "Zoom" Effect)

**Problem**: Standard RAG retrieves the top 5 most "intense" moments, but misses overall trends.

**Solution**: Parent-child indexing:
- **Parent chunks**: Daily/weekly summaries (the "gist")
- **Child chunks**: Raw log entries (details)

Search against summaries first, then "zoom in" to read detailed raw chunks.

```python
# Get daily summary (zoom out view)
summary = memory.get_daily_summary("2025-01-15")

# Zoom in to see detailed entries
details = memory.get_daily_details("2025-01-15")
# or
details = memory.zoom_in(summary)
```

### 3. Memory Consolidation (The "Dreaming" Process)

**Concept**: Instead of searching for "What did I do last time I failed?", the system should *already know* your tendencies.

**Implementation**: A consolidation agent that:
- Runs nightly/weekly (background job)
- Reads raw logs from vector DB
- Uses LLM to extract patterns
- Updates `CharacterSheet.user_facts` (semantic/procedural memory)

**Example Output**:
- Raw Log: "Failed coding task because I didn't sleep."
- Vector DB: Stores the incident
- Profile Update: Adds rule: `"Weakness: Sleep deprivation causes coding failure"`

## 📊 Data Schema

Every memory chunk has structured metadata:

```python
{
    # Temporal (for time-aware queries)
    "date": "2025-01-15",
    "day_of_week": 1,  # Tuesday
    "hour": 22,
    "week_of_year": 3,
    "month": 1,
    "year": 2025,
    
    # Semantic
    "chunk_type": "report_struggle",
    "pillar": "CAREER",
    "sentiment": "negative",
    "mood_score": 3,
    "tags": ["coding", "failure", "sleep"],
    
    # Hierarchical
    "parent_id": "daily_summary_2025-01-15",
    "child_ids": ["chunk_1", "chunk_2"],
    "level": "raw",  # or "day", "week", "pattern"
    
    # Entity linking
    "goal_id": "goal_123",
    "node_id": "skill_python",
    "task_id": "task_456",
    
    # Context
    "user_id": "user_01",
    "session_id": "onboarding_session_1",
    "xp_gained": 50
}
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install chromadb sentence-transformers
```

### 2. Sync Existing DailyReports to Memory

```python
from src.memory.vector_store import SemanticMemory
from src.memory.integration import sync_all_reports_to_memory
from src.storage import load_profile

# Load user profile
profile = load_profile("user_01")
sheet = CharacterSheet(**profile["character_sheet"])

# Initialize memory
memory = SemanticMemory(user_id="user_01")

# Sync all existing reports
synced_count = sync_all_reports_to_memory(memory, sheet)
print(f"Synced {synced_count} reports to memory")
```

### 3. Add New DailyReports Automatically

In your reporting agent, after finalizing a DailyReport:

```python
from src.memory.integration import sync_daily_report_to_memory

# After creating DailyReport
chunk_ids = sync_daily_report_to_memory(memory, report, sheet.user_id)
```

### 4. Query Memory

```python
from src.memory.integration import query_user_memory, analyze_day_of_week_pattern

# Semantic search
results = query_user_memory(
    memory,
    query="coding failures",
    filters={"pillar": "CAREER", "sentiment": "negative"},
    n_results=5
)

# Day-of-week pattern analysis
pattern = analyze_day_of_week_pattern(
    memory,
    day_of_week=1,  # Tuesday
    query="failure struggle"
)
print(f"Found {pattern['total_matches']} Tuesday failures")
```

### 5. Run Consolidation (Nightly Job)

```python
from src.memory.integration import run_nightly_consolidation

# Run for yesterday
new_insights = run_nightly_consolidation(memory, sheet)
print(f"Extracted {len(new_insights)} new insights:")
for insight in new_insights:
    print(f"  - {insight}")
```

## 🔄 Integration with Reporting Agent

Modify `src/reporting/agent.py`:

```python
from src.memory.integration import sync_daily_report_to_memory
from src.memory.vector_store import SemanticMemory

class ReportingAgent:
    def finalize_report(self, state, sheet, tree) -> DailyReport:
        report = ...  # Your existing report generation
        
        # NEW: Sync to semantic memory
        memory = SemanticMemory(user_id=sheet.user_id)
        sync_daily_report_to_memory(memory, report, sheet.user_id)
        
        return report
```

## 🎯 Example Use Cases

### "Why do I always fail on Tuesdays?"

```python
pattern = analyze_day_of_week_pattern(memory, day_of_week=1)
print(f"Tuesday pattern: {pattern['sentiment_breakdown']}")
```

### "Show me all my coding struggles this month"

```python
from datetime import datetime, timedelta

start_date = datetime.now().replace(day=1).strftime("%Y-%m-%d")
end_date = datetime.now().strftime("%Y-%m-%d")

results = memory.search(
    query="coding struggle difficulty",
    filters={"pillar": "CAREER", "sentiment": "negative"},
    date_range=(start_date, end_date),
    n_results=20
)
```

### "How was my November?"

```python
november_summaries = memory.search(
    query="",
    filters={"month": 11, "level": "day", "chunk_type": "daily_summary"},
    date_range=("2024-11-01", "2024-11-30"),
    n_results=31
)

# Then zoom into interesting days
interesting_day = november_summaries[0].chunk
details = memory.zoom_in(interesting_day)
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CharacterSheet                            │
│  - user_facts: ["Sleep deprivation causes failures"]        │
│  - daily_reports: [DailyReport, ...]                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼────────┐          ┌───────────▼──────────┐
│  SemanticMemory│          │ ConsolidationAgent   │
│  (ChromaDB)    │◄─────────┤ (Nightly Process)    │
│                │          │                      │
│  - Raw chunks  │          │  - Reads raw logs    │
│  - Summaries   │          │  - Extracts patterns │
│  - Metadata    │          │  - Updates user_facts│
└────────────────┘          └──────────────────────┘
```

## 🔧 Advanced Configuration

### Custom Embedding Model

For better quality (but slower), use a larger model:

```python
memory = SemanticMemory(
    user_id="user_01",
    embedding_model="bge-m3"  # State-of-the-art, multilingual
)
```

### Custom Persistence Directory

```python
memory = SemanticMemory(
    user_id="user_01",
    persist_directory="./custom/path/chroma"
)
```

## 📝 Notes

- **ChromaDB is local**: All data stays on your machine (privacy-first)
- **First run is slow**: The embedding model downloads on first use (~80MB)
- **Batch operations**: Use `add_chunks()` instead of multiple `add_chunk()` calls for better performance
- **Memory consolidation**: Run as a background cron job (e.g., every Sunday night)

## 🎓 Next Steps

1. **Integrate with reporting agent**: Auto-sync DailyReports
2. **Add to LLM prompts**: Inject `user_facts` and relevant memory chunks into system prompts
3. **Build UI**: Show "Patterns" view in frontend (e.g., "You tend to skip gym on Tuesdays")
4. **Weekly reports**: Generate weekly summaries automatically
