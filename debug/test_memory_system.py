"""Test script for the semantic memory system."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory.vector_store import SemanticMemory
from src.memory.schema import MemoryChunk, MemoryMetadata, ChunkType, MemoryLevel
from src.memory.integration import (
    sync_daily_report_to_memory,
    query_user_memory,
    analyze_day_of_week_pattern,
)
from src.models import DailyReport, DailyTaskReport, StatsDelta, DailyTaskStatus


def test_basic_operations():
    """Test basic memory operations."""
    print("=" * 60)
    print("TEST 1: Basic Memory Operations")
    print("=" * 60)
    
    user_id = "test_memory_user"
    memory = SemanticMemory(user_id=user_id)
    
    # Clear any existing data
    memory.clear()
    
    # Create test chunks
    chunk1 = MemoryChunk(
        id="test_chunk_1",
        text="I failed to complete my coding task because I was tired from lack of sleep.",
        metadata=MemoryMetadata.from_date(
            "2025-01-14",  # Tuesday
            user_id,
            ChunkType.REPORT_STRUGGLE,
            sentiment="negative",
            pillar="CAREER",
            tags=["coding", "failure", "sleep"],
        )
    )
    
    chunk2 = MemoryChunk(
        id="test_chunk_2",
        text="Skipped gym workout today. Feeling unmotivated.",
        metadata=MemoryMetadata.from_date(
            "2025-01-14",  # Tuesday
            user_id,
            ChunkType.HABIT_SKIP,
            sentiment="negative",
            pillar="PHYSICAL",
            tags=["gym", "skip"],
        )
    )
    
    chunk3 = MemoryChunk(
        id="test_chunk_3",
        text="Completed morning meditation. Feeling focused and calm.",
        metadata=MemoryMetadata.from_date(
            "2025-01-15",  # Wednesday
            user_id,
            ChunkType.REPORT_WIN,
            sentiment="positive",
            pillar="MENTAL",
            tags=["meditation", "focus"],
        )
    )
    
    # Add chunks
    memory.add_chunks([chunk1, chunk2, chunk3])
    print(f"✓ Added 3 test chunks")
    
    # Test search
    results = memory.search("coding failure", n_results=5)
    print(f"✓ Search for 'coding failure' returned {len(results)} results")
    if results:
        print(f"  Top result: {results[0].chunk.text[:80]}...")
        print(f"  Score: {results[0].score:.3f}")
    
    # Test metadata filtering
    tuesday_results = memory.search(
        query="failure struggle",
        day_of_week=1,  # Tuesday
        sentiment="negative",
        n_results=10
    )
    print(f"✓ Tuesday failures search returned {len(tuesday_results)} results")
    
    return memory


def test_daily_report_integration():
    """Test integration with DailyReport."""
    print("\n" + "=" * 60)
    print("TEST 2: DailyReport Integration")
    print("=" * 60)
    
    user_id = "test_memory_user"
    memory = SemanticMemory(user_id=user_id)
    
    # Create a mock DailyReport
    report = DailyReport(
        date="2025-01-16",
        summary="Had a productive day. Finished coding project but skipped gym.",
        sentiment="mixed",
        wins=["Completed coding project", "Felt focused"],
        struggles=["Skipped gym workout", "Feeling tired"],
        reflections=["Need to prioritize sleep"],
        tasks=[
            DailyTaskReport(
                task_id="task_1",
                node_id="skill_python",
                status=DailyTaskStatus.DONE,
                completed_repetitions=1,
                user_comment="Great progress!"
            ),
            DailyTaskReport(
                task_id="task_2",
                node_id="habit_gym",
                status=DailyTaskStatus.SKIPPED,
                completed_repetitions=0,
                user_comment="Too tired"
            ),
        ],
        stats_delta=StatsDelta(xp_career=100, xp_total=100),
        new_tasks=[],
        new_skill_nodes=[],
    )
    
    # Sync to memory
    chunk_ids = sync_daily_report_to_memory(memory, report, user_id)
    print(f"✓ Synced DailyReport to memory: {len(chunk_ids)} chunks created")
    
    # Search for gym skip
    results = query_user_memory(
        memory,
        query="skipped gym workout",
        n_results=5
    )
    print(f"✓ Found {len(results)} results about gym skipping")
    if results:
        print(f"  Top result: {results[0]['text'][:80]}...")
    
    return memory


def test_day_of_week_analysis():
    """Test day-of-week pattern analysis."""
    print("\n" + "=" * 60)
    print("TEST 3: Day-of-Week Pattern Analysis")
    print("=" * 60)
    
    user_id = "test_memory_user"
    memory = SemanticMemory(user_id=user_id)
    
    # Add multiple Tuesday failures
    for i in range(3):
        chunk = MemoryChunk(
            id=f"tuesday_failure_{i}",
            text=f"Tuesday failure #{i+1}: Couldn't focus, skipped tasks",
            metadata=MemoryMetadata.from_date(
                f"2025-01-{14+i*7}",  # Multiple Tuesdays
                user_id,
                ChunkType.REPORT_STRUGGLE,
                sentiment="negative",
                tags=["failure", "focus"],
            )
        )
        memory.add_chunk(chunk)
    
    # Analyze Tuesday pattern
    pattern = analyze_day_of_week_pattern(memory, day_of_week=1, query="failure struggle")
    print(f"✓ Tuesday pattern analysis:")
    print(f"  Total matches: {pattern['total_matches']}")
    print(f"  Type breakdown: {pattern['type_breakdown']}")
    print(f"  Sentiment breakdown: {pattern['sentiment_breakdown']}")


def test_hierarchical_summarization():
    """Test recursive summarization (zoom in/out)."""
    print("\n" + "=" * 60)
    print("TEST 4: Hierarchical Summarization")
    print("=" * 60)
    
    user_id = "test_memory_user"
    memory = SemanticMemory(user_id=user_id)
    
    # Create a daily summary with child chunks
    date = "2025-01-20"
    
    # Create child chunks first (we'll update parent_id later)
    child_chunks = []
    for i in range(3):
        chunk = MemoryChunk(
            id=f"child_{i}",
            text=f"Activity {i+1}: Worked on project, felt productive",
            metadata=MemoryMetadata.from_date(
                date,
                user_id,
                ChunkType.REPORT_TASK,
            )
        )
        child_chunks.append(chunk)
    
    # Create parent summary
    summary_chunk = MemoryChunk(
        id=f"daily_summary_{date}",
        text=f"Daily Summary ({date}): Productive day with good progress on project work.",
        metadata=MemoryMetadata.from_date(
            date,
            user_id,
            ChunkType.DAILY_SUMMARY,
            level=MemoryLevel.DAY,
            child_ids=[c.id for c in child_chunks],
        ),
        is_summary=True,
    )
    
    # Update child chunks to point to parent (create new metadata objects)
    updated_child_chunks = []
    for chunk in child_chunks:
        updated_metadata = chunk.metadata.model_copy(update={"parent_id": summary_chunk.id})
        updated_chunk = MemoryChunk(
            id=chunk.id,
            text=chunk.text,
            metadata=updated_metadata
        )
        updated_child_chunks.append(updated_chunk)
    child_chunks = updated_child_chunks
    
    # Add all chunks
    memory.add_chunks([summary_chunk] + child_chunks)
    print(f"✓ Created hierarchical structure: 1 summary + {len(child_chunks)} child chunks")
    
    # Test zoom in
    summary = memory.get_daily_summary(date)
    if summary:
        print(f"✓ Retrieved daily summary: {summary.text[:60]}...")
        details = memory.zoom_in(summary)
        print(f"✓ Zoomed in: Found {len(details)} child chunks")
    
    # Test zoom out
    if child_chunks:
        parent = memory.zoom_out(child_chunks[0])
        if parent:
            print(f"✓ Zoomed out: Found parent summary")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SEMANTIC MEMORY SYSTEM TEST SUITE")
    print("=" * 60)
    
    try:
        # Test 1: Basic operations
        memory = test_basic_operations()
        
        # Test 2: DailyReport integration
        test_daily_report_integration()
        
        # Test 3: Day-of-week analysis
        test_day_of_week_analysis()
        
        # Test 4: Hierarchical summarization
        test_hierarchical_summarization()
        
        # Get stats
        print("\n" + "=" * 60)
        print("MEMORY STATISTICS")
        print("=" * 60)
        stats = memory.get_stats()
        print(f"Total chunks: {stats['total_chunks']}")
        print(f"Chunk types: {stats['chunk_types']}")
        print(f"Levels: {stats['levels']}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
