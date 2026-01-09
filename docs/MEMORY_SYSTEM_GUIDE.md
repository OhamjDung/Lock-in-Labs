# Semantic Memory System - Implementation Guide

## Overview

You now have a **professional-grade RAG (Retrieval-Augmented Generation)** system that transforms your Life OS from a chatbot into a true second brain with three advanced techniques:

1. **Time-Aware Retrieval**: Answer "Why do I fail on Tuesdays?" with metadata filtering
2. **Recursive Summarization**: "Zoom in/out" from daily summaries to detailed logs
3. **Memory Consolidation**: Nightly "dreaming" process that extracts patterns into procedural memory

## What Was Built

### Core Components

1. **`src/memory/schema.py`**: Structured metadata schema for time-aware queries
   - `MemoryMetadata`: Rich metadata with temporal, semantic, and hierarchical fields
   - `MemoryChunk`: Text content + metadata
   - `ChunkType`, `MemoryLevel`: Enums for categorization

2. **`src/memory/vector_store.py`**: ChromaDB wrapper with advanced features
   - `SemanticMemory`: Main class with time-aware search, zoom in/out, metadata filtering
   - Supports day-of-week queries, date ranges, sentiment filtering
   - Parent-child indexing for recursive summarization

3. **`src/memory/consolidation.py`**: The "nightly dreaming" agent
   - `ConsolidationAgent`: Reads raw logs, extracts patterns with LLM, updates `user_facts`
   - Daily and weekly consolidation
   - Pattern extraction (e.g., "User fails on Tuesdays")

4. **`src/memory/integration.py`**: Easy integration helpers
   - `sync_daily_report_to_memory()`: Auto-sync DailyReports
   - `query_user_memory()`: Simplified query interface
   - `analyze_day_of_week_pattern()`: Pattern analysis helper

## Installation

```bash
pip install chromadb sentence-transformers
```

The embedding model (`all-MiniLM-L6-v2`, ~80MB) will download automatically on first use.

## Quick Start: 3 Steps to Integration

### Step 1: Sync Existing Reports (One-Time Migration)

```python
from src.memory.vector_store import SemanticMemory
from src.memory.integration import sync_all_reports_to_memory
from src.storage import load_profile
from src.models import CharacterSheet

# Load existing profile
profile = load_profile("user_01")
sheet = CharacterSheet(**profile["character_sheet"])

# Initialize memory and sync
memory = SemanticMemory(user_id="user_01")
synced = sync_all_reports_to_memory(memory, sheet)
print(f"Migrated {synced} reports to memory")
```

### Step 2: Auto-Sync New Reports

In `src/reporting/agent.py`, modify `finalize_report()`:

```python
from src.memory.integration import sync_daily_report_to_memory
from src.memory.vector_store import SemanticMemory

def finalize_report(self, state, sheet, tree) -> DailyReport:
    # ... existing report generation code ...
    
    # NEW: Sync to semantic memory
    memory = SemanticMemory(user_id=sheet.user_id)
    sync_daily_report_to_memory(memory, report, sheet.user_id)
    
    return report
```

### Step 3: Use Memory in LLM Prompts

Enhance your reporting/onboarding prompts with relevant memory:

```python
from src.memory.integration import query_user_memory

# In your agent's prompt construction:
memory = SemanticMemory(user_id=sheet.user_id)

# Get relevant past experiences
relevant_memories = query_user_memory(
    memory,
    query="coding failures struggles",
    filters={"pillar": "CAREER"},
    n_results=3
)

# Inject into prompt
context = "\n".join([m["text"] for m in relevant_memories])
prompt = f"""
User's relevant past experiences:
{context}

Now respond to: {user_query}
"""
```

## Example Use Cases

### 1. "Why do I always fail on Tuesdays?"

```python
from src.memory.integration import analyze_day_of_week_pattern

pattern = analyze_day_of_week_pattern(memory, day_of_week=1, query="failure struggle")
# Returns: {
#   "day": "Tuesday",
#   "total_matches": 12,
#   "sentiment_breakdown": {"negative": 10, "neutral": 2},
#   "sample_entries": [...]
# }
```

### 2. "Show me my coding struggles this month"

```python
from datetime import datetime

start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
end = datetime.now().strftime("%Y-%m-%d")

results = memory.search(
    query="coding struggle difficulty",
    filters={"pillar": "CAREER", "sentiment": "negative"},
    date_range=(start, end),
    n_results=20
)
```

### 3. "How was my November?" (Zoom Effect)

```python
# Get daily summaries (zoom out)
november_summaries = memory.search(
    query="",
    filters={"month": 11, "level": "day", "chunk_type": "daily_summary"},
    date_range=("2024-11-01", "2024-11-30"),
    n_results=31
)

# Zoom into an interesting day
interesting = november_summaries[0].chunk
details = memory.zoom_in(interesting)  # Get all raw chunks for that day
```

## Memory Consolidation (Background Job)

Set up a cron job or scheduled task to run nightly consolidation:

```python
# nightly_consolidation.py
from src.memory.integration import run_nightly_consolidation, run_weekly_consolidation
from src.memory.vector_store import SemanticMemory
from src.storage import load_profile
from src.models import CharacterSheet
from src.storage import save_profile

def consolidate_user(user_id: str):
    # Load profile
    profile = load_profile(user_id)
    sheet = CharacterSheet(**profile["character_sheet"])
    
    # Initialize memory
    memory = SemanticMemory(user_id=user_id)
    
    # Run daily consolidation (for yesterday)
    new_insights = run_nightly_consolidation(memory, sheet)
    print(f"Extracted {len(new_insights)} insights for {user_id}")
    
    # Save updated profile
    profile["character_sheet"] = sheet.model_dump()
    save_profile(profile, user_id)
    
    # Weekly consolidation (every Sunday)
    if datetime.now().weekday() == 6:  # Sunday
        weekly_insights = run_weekly_consolidation(memory, sheet)
        print(f"Extracted {len(weekly_insights)} weekly insights")

# Schedule with cron: 0 2 * * * python nightly_consolidation.py
```

## Architecture Decision: Why ChromaDB?

- **Local-first**: All data stays on your machine (privacy)
- **Python-native**: No external services required
- **Metadata filtering**: Built-in support for time-aware queries
- **Lightweight**: ~50MB footprint, fast queries

## Next Steps

1. **Test the system**: Run `python debug/test_memory_system.py`
2. **Integrate with reporting**: Add sync call after DailyReport creation
3. **Enhance prompts**: Inject relevant memories into LLM context
4. **Build UI**: Create "Patterns" view showing day-of-week analysis
5. **Set up consolidation**: Schedule nightly/weekly jobs

## Advanced: Custom Embedding Models

For better quality (multilingual, larger context):

```python
memory = SemanticMemory(
    user_id="user_01",
    embedding_model="bge-m3"  # State-of-the-art, ~600MB
)
```

## Troubleshooting

**Issue**: "No module named 'chromadb'"
- **Fix**: `pip install chromadb sentence-transformers`

**Issue**: "Embedding model download slow"
- **Fix**: First run downloads ~80MB model. Subsequent runs are instant.

**Issue**: "Memory usage growing"
- **Fix**: Consider periodic cleanup or archival of old chunks. ChromaDB supports deletion by metadata filters.

## Files Created

```
src/memory/
├── __init__.py           # Module exports
├── schema.py             # Metadata schema definitions
├── vector_store.py       # ChromaDB wrapper with advanced features
├── consolidation.py      # Nightly consolidation agent
├── integration.py        # Easy integration helpers
└── README.md            # Detailed documentation

docs/
└── MEMORY_SYSTEM_GUIDE.md  # This file

debug/
└── test_memory_system.py   # Test suite

requirements.txt           # Updated with chromadb, sentence-transformers
```

## Questions?

See `src/memory/README.md` for detailed API documentation and examples.
