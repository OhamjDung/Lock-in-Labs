"""Memory system for Life OS - RAG with advanced retrieval techniques."""

from .schema import MemoryChunk, MemoryMetadata, ChunkType, MemoryLevel
from .vector_store import SemanticMemory
from .consolidation import ConsolidationAgent
from .significance import SignificanceScorer, DEFAULT_SIGNIFICANCE_THRESHOLD
from .pattern_file import PatternFile, Pattern

__all__ = [
    "MemoryChunk",
    "MemoryMetadata", 
    "ChunkType",
    "MemoryLevel",
    "SemanticMemory",
    "ConsolidationAgent",
    "SignificanceScorer",
    "DEFAULT_SIGNIFICANCE_THRESHOLD",
    "PatternFile",
    "Pattern",
]
