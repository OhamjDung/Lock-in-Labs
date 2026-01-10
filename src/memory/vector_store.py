"""ChromaDB wrapper for semantic memory with advanced retrieval techniques."""

import os
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel

from .schema import MemoryChunk, MemoryMetadata, ChunkType, MemoryLevel
from .significance import DEFAULT_SIGNIFICANCE_THRESHOLD


class SearchResult(BaseModel):
    """Result from semantic search with metadata."""
    chunk: MemoryChunk
    score: float  # Final relevance score (similarity * recency)
    distance: float  # Raw cosine distance
    similarity: float  # 1 - distance (raw similarity score)
    recency_score: float  # Time decay multiplier (1.0 = today, 0.5 = 1 year ago)


class SemanticMemory:
    """Professional-grade semantic memory with RAG capabilities.
    
    Features:
    1. Time-aware retrieval (metadata filtering)
    2. Recursive summarization (parent-child indexing)
    3. Multi-level memory hierarchy
    """
    
    def __init__(
        self,
        user_id: str,
        persist_directory: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: Optional[str] = None,
        significance_threshold: int = DEFAULT_SIGNIFICANCE_THRESHOLD,
        use_openai_embeddings: bool = False,
        openai_api_key: Optional[str] = None,
        recency_decay_days: float = 365.0,  # Memories older than this have 0.5 weight
    ):
        """Initialize semantic memory for a user.
        
        Args:
            user_id: User identifier
            persist_directory: Where to persist ChromaDB data (default: ./data/chroma/{user_id})
            embedding_model: Sentence transformer model name (ignored if use_openai_embeddings=True)
            collection_name: Custom collection name (default: f"memory_{user_id}")
            significance_threshold: Only chunks with significance_score >= this go to Vector DB
            use_openai_embeddings: Use OpenAI API instead of local sentence-transformers
            openai_api_key: OpenAI API key (required if use_openai_embeddings=True)
            recency_decay_days: Number of days for recency score to decay to 0.5 (365 = 1 year)
        """
        self.user_id = user_id
        self.persist_directory = persist_directory or os.path.join("data", "chroma", user_id)
        self.collection_name = collection_name or f"memory_{user_id}"
        self.significance_threshold = significance_threshold
        self.recency_decay_days = recency_decay_days
        self.use_openai_embeddings = use_openai_embeddings
        
        # Initialize embedding model
        if use_openai_embeddings:
            if not openai_api_key:
                openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                raise ValueError("OpenAI API key required when use_openai_embeddings=True")
            print(f"[SemanticMemory] Using OpenAI embeddings (text-embedding-3-small)")
            self.openai_api_key = openai_api_key
            self.embedder = None
            self.embedding_dim = 1536  # OpenAI text-embedding-3-small dimension
        else:
            print(f"[SemanticMemory] Loading local embedding model: {embedding_model}")
            try:
                self.embedder = SentenceTransformer(embedding_model)
                self.embedding_dim = self.embedder.get_sentence_embedding_dimension()
            except Exception as e:
                print(f"[SemanticMemory] Error loading {embedding_model}: {e}")
                print("[SemanticMemory] Falling back to OpenAI embeddings (set OPENAI_API_KEY env var)")
                openai_api_key = os.getenv("OPENAI_API_KEY")
                if openai_api_key:
                    self.use_openai_embeddings = True
                    self.openai_api_key = openai_api_key
                    self.embedder = None
                    self.embedding_dim = 1536
                else:
                    raise ValueError(f"Could not load {embedding_model} and no OpenAI API key available")
        
        # Initialize ChromaDB client
        os.makedirs(self.persist_directory, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}  # Cosine similarity for semantic search
        )
        
        print(f"[SemanticMemory] Initialized for user {user_id} with {self.collection.count()} existing chunks")
        print(f"[SemanticMemory] Significance threshold: {significance_threshold} (only chunks >= threshold stored in Vector DB)")
    
    def _encode_text(self, text: str) -> List[float]:
        """Generate embedding for text using configured method."""
        if self.use_openai_embeddings:
            import openai
            client = openai.OpenAI(api_key=self.openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        else:
            embedding = self.embedder.encode(text, normalize_embeddings=True)
            return embedding.tolist()
    
    def add_chunk(self, chunk: MemoryChunk, skip_significance_check: bool = False) -> Optional[str]:
        """Add a single memory chunk to the vector store.
        
        CRITICAL: Only adds chunks with significance_score >= threshold.
        Lower significance chunks should be stored in audit trail (JSON/SQL) only.
        
        Args:
            chunk: MemoryChunk to add
            skip_significance_check: Skip significance threshold check (use with caution)
            
        Returns:
            The chunk ID if added, None if skipped due to low significance
        """
        # Significance gate: Only high-value memories go to Vector DB
        if not skip_significance_check:
            sig_score = chunk.metadata.significance_score
            if sig_score is None or sig_score < self.significance_threshold:
                print(f"[SemanticMemory] Skipping chunk {chunk.id}: significance_score={sig_score} < threshold={self.significance_threshold}")
                return None
        
        # Generate embedding
        embedding = self._encode_text(chunk.text)
        
        # Convert metadata to ChromaDB format (must be JSON-serializable)
        metadata_dict = self._metadata_to_dict(chunk.metadata)
        
        # Add to ChromaDB
        self.collection.add(
            ids=[chunk.id],
            embeddings=[embedding],
            documents=[chunk.text],
            metadatas=[metadata_dict]
        )
        
        return chunk.id
    
    def add_chunks(self, chunks: List[MemoryChunk], skip_significance_check: bool = False) -> List[str]:
        """Add multiple chunks in a batch with significance filtering.
        
        Args:
            chunks: List of chunks to add
            skip_significance_check: Skip significance threshold check
            
        Returns:
            List of chunk IDs that were actually added (may be fewer than input)
        """
        if not chunks:
            return []
        
        # Filter by significance threshold
        filtered_chunks = []
        if not skip_significance_check:
            for chunk in chunks:
                sig_score = chunk.metadata.significance_score
                if sig_score is not None and sig_score >= self.significance_threshold:
                    filtered_chunks.append(chunk)
                else:
                    print(f"[SemanticMemory] Skipping chunk {chunk.id}: significance_score={sig_score} < threshold={self.significance_threshold}")
        else:
            filtered_chunks = chunks
        
        if not filtered_chunks:
            return []
        
        # Generate embeddings (batch for efficiency)
        texts = [chunk.text for chunk in filtered_chunks]
        if self.use_openai_embeddings:
            import openai
            client = openai.OpenAI(api_key=self.openai_api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
        else:
            embeddings = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()
        
        ids = [chunk.id for chunk in filtered_chunks]
        metadatas = [self._metadata_to_dict(chunk.metadata) for chunk in filtered_chunks]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        return ids
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        level: Optional[MemoryLevel] = None,
        chunk_type: Optional[ChunkType] = None,
        pillar: Optional[str] = None,
        sentiment: Optional[str] = None,
        day_of_week: Optional[int] = None,
        date_range: Optional[Tuple[str, str]] = None,
        min_score: float = 0.0,
        apply_recency_weighting: bool = True,
    ) -> List[SearchResult]:
        """Search with time-aware metadata filtering and recency weighting.
        
        CRITICAL: Results are ranked by (similarity * recency), not just similarity.
        This prevents old but semantically similar memories from ranking higher.
        
        Args:
            query: Search query text
            n_results: Number of results to return (fetches 3x internally for reranking)
            filters: Raw ChromaDB where clause (advanced)
            level: Filter by memory level (RAW, DAY, WEEK, etc.)
            chunk_type: Filter by chunk type
            pillar: Filter by life pillar
            sentiment: Filter by sentiment
            day_of_week: Filter by day of week (0=Monday, 6=Sunday)
            date_range: Tuple of (start_date, end_date) in YYYY-MM-DD format
            min_score: Minimum similarity score threshold (applied to raw similarity, not final score)
            apply_recency_weighting: If False, skip recency weighting (pure semantic similarity)
            
        Returns:
            List of SearchResult objects sorted by final relevance (similarity * recency)
        """
        # Build where clause for metadata filtering
        # ChromaDB requires $and operator when multiple conditions are present
        conditions = [{"user_id": self.user_id}]  # Always filter by user
        
        if filters:
            # If filters is a dict, convert each key-value to a condition
            if isinstance(filters, dict):
                conditions.extend([{k: v} for k, v in filters.items() if v is not None])
        
        if level:
            conditions.append({"level": level.value})
        
        if chunk_type:
            conditions.append({"chunk_type": chunk_type.value})
        
        if pillar:
            conditions.append({"pillar": pillar})
        
        if sentiment:
            conditions.append({"sentiment": sentiment})
        
        if day_of_week is not None:
            conditions.append({"day_of_week": day_of_week})
        
        # Date range filtering (ChromaDB supports comparison operators)
        if date_range:
            start_date, end_date = date_range
            conditions.append({"date": {"$gte": start_date, "$lte": end_date}})
        
        # Build final where clause
        if len(conditions) == 1:
            where_clause = conditions[0]
        elif len(conditions) > 1:
            where_clause = {"$and": conditions}
        else:
            where_clause = None
        
        # Generate query embedding
        query_embedding = self._encode_text(query)
        
        # CRITICAL FIX: Fetch MORE results than requested if recency weighting enabled
        # This prevents old but semantically similar memories from ranking higher than recent ones
        if apply_recency_weighting:
            fetch_count = max(n_results * 3, 20)  # Fetch 3x requested, min 20
        else:
            fetch_count = n_results
        
        # Perform search with metadata filtering
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_count,
            where=where_clause if where_clause else None,
            include=["documents", "metadatas", "distances"]
        )
        
        # Convert to SearchResult objects with recency weighting
        search_results = []
        current_date = datetime.now().date()
        
        if results["ids"] and len(results["ids"][0]) > 0:
            for i, (chunk_id, doc, metadata_dict, distance) in enumerate(zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                # Convert distance to similarity score (cosine similarity: 1 - distance)
                similarity = 1.0 - distance
                
                if similarity >= min_score:
                    # Reconstruct MemoryMetadata from dict
                    metadata = self._dict_to_metadata(metadata_dict)
                    
                    # Calculate recency score (time decay)
                    try:
                        chunk_date = datetime.strptime(metadata.date, "%Y-%m-%d").date()
                        days_ago = (current_date - chunk_date).days
                        # Exponential decay: recent memories = 1.0, older = lower
                        # Formula: recency = 0.5 ^ (days_ago / decay_days)
                        # So if decay_days=365, a memory from 1 year ago has recency=0.5
                        recency_score = 0.5 ** (days_ago / self.recency_decay_days)
                        recency_score = max(0.1, min(1.0, recency_score))  # Clamp to [0.1, 1.0]
                    except Exception:
                        recency_score = 0.5  # Default if date parsing fails
                    
                    # FINAL SCORE: similarity * recency (recency-weighted relevance)
                    if apply_recency_weighting:
                        final_score = similarity * recency_score
                    else:
                        final_score = similarity
                        recency_score = 1.0  # No decay
                    
                    chunk = MemoryChunk(
                        id=chunk_id,
                        text=doc,
                        metadata=metadata
                    )
                    search_results.append(SearchResult(
                        chunk=chunk,
                        score=final_score,  # Final relevance score
                        distance=distance,
                        similarity=similarity,  # Raw semantic similarity
                        recency_score=recency_score  # Time decay multiplier
                    ))
            
            # Sort by final score (similarity * recency) descending
            search_results.sort(key=lambda x: x.score, reverse=True)
            
            # Return only top n_results
            search_results = search_results[:n_results]
        
        return search_results
    
    def search_by_day(self, day_of_week: int, query: str = "", n_results: int = 10) -> List[SearchResult]:
        """Convenience method: Search for patterns on a specific day of week.
        
        Example: "Why do I always fail on Tuesdays?"
        """
        return self.search(
            query=query or "failure struggle difficulty",
            day_of_week=day_of_week,
            n_results=n_results,
            sentiment="negative"
        )
    
    def get_daily_summary(self, date: str) -> Optional[MemoryChunk]:
        """Get the summary chunk for a specific day (parent chunk for zoom-in)."""
        results = self.search(
            query="daily summary",
            level=MemoryLevel.DAY,
            filters={"date": date, "chunk_type": ChunkType.DAILY_SUMMARY.value},
            n_results=1
        )
        return results[0].chunk if results else None
    
    def get_daily_details(self, date: str) -> List[MemoryChunk]:
        """Get all raw chunks for a specific day (children of daily summary)."""
        summary = self.get_daily_summary(date)
        if not summary or not summary.metadata.child_ids:
            return []
        
        # Fetch chunks by IDs
        results = self.collection.get(ids=summary.metadata.child_ids)
        
        chunks = []
        if results["ids"]:
            for chunk_id, doc, metadata_dict in zip(
                results["ids"],
                results["documents"],
                results["metadatas"]
            ):
                metadata = self._dict_to_metadata(metadata_dict)
                chunks.append(MemoryChunk(id=chunk_id, text=doc, metadata=metadata))
        
        return chunks
    
    def zoom_in(self, summary_chunk: MemoryChunk) -> List[MemoryChunk]:
        """Zoom into a summary: retrieve all child raw chunks."""
        if not summary_chunk.metadata.child_ids:
            return []
        
        results = self.collection.get(ids=summary_chunk.metadata.child_ids)
        chunks = []
        if results["ids"]:
            for chunk_id, doc, metadata_dict in zip(
                results["ids"],
                results["documents"],
                results["metadatas"]
            ):
                metadata = self._dict_to_metadata(metadata_dict)
                chunks.append(MemoryChunk(id=chunk_id, text=doc, metadata=metadata))
        
        return chunks
    
    def zoom_out(self, chunk: MemoryChunk) -> Optional[MemoryChunk]:
        """Zoom out from a raw chunk: retrieve parent summary."""
        if not chunk.metadata.parent_id:
            return None
        
        results = self.collection.get(ids=[chunk.metadata.parent_id])
        if not results["ids"] or not results["ids"][0]:
            return None
        
        metadata = self._dict_to_metadata(results["metadatas"][0])
        return MemoryChunk(
            id=results["ids"][0],
            text=results["documents"][0],
            metadata=metadata
        )
    
    def get_weekly_pattern(self, week_of_year: int, year: int) -> List[MemoryChunk]:
        """Get all chunks for a specific week."""
        return self.search(
            query="",
            filters={"week_of_year": week_of_year, "year": year},
            n_results=100  # Get all chunks for the week
        )
    
    def get_patterns_by_day(self, day_of_week: int, chunk_type: Optional[ChunkType] = None) -> List[SearchResult]:
        """Get all chunks of a specific type that occurred on a specific day of week.
        
        Useful for pattern analysis: "What happens every Tuesday?"
        """
        filters = {"day_of_week": day_of_week}
        if chunk_type:
            filters["chunk_type"] = chunk_type.value
        
        results = self.collection.get(
            where={"user_id": self.user_id, **filters},
            include=["documents", "metadatas"]
        )
        
        search_results = []
        if results["ids"]:
            for chunk_id, doc, metadata_dict in zip(
                results["ids"],
                results["documents"],
                results["metadatas"]
            ):
                metadata = self._dict_to_metadata(metadata_dict)
                chunk = MemoryChunk(id=chunk_id, text=doc, metadata=metadata)
                search_results.append(SearchResult(chunk=chunk, score=1.0, distance=0.0))
        
        return search_results
    
    def _metadata_to_dict(self, metadata: MemoryMetadata) -> Dict[str, Any]:
        """Convert MemoryMetadata to ChromaDB-compatible dict."""
        # ChromaDB metadata must be JSON-serializable
        # Lists are supported, but we need to handle enums and optional fields
        result = {
            "user_id": metadata.user_id,
            "date": metadata.date,
            "day_of_week": metadata.day_of_week,
            "week_of_year": metadata.week_of_year,
            "month": metadata.month,
            "year": metadata.year,
            "chunk_type": metadata.chunk_type.value,
            "level": metadata.level.value,
        }
        
        # Optional fields
        if metadata.datetime:
            result["datetime"] = metadata.datetime
        if metadata.hour is not None:
            result["hour"] = metadata.hour
        if metadata.pillar:
            result["pillar"] = metadata.pillar
        if metadata.sentiment:
            result["sentiment"] = metadata.sentiment
        if metadata.mood_score is not None:
            result["mood_score"] = metadata.mood_score
        if metadata.tags:
            result["tags"] = json.dumps(metadata.tags)  # ChromaDB doesn't support lists directly
        if metadata.parent_id:
            result["parent_id"] = metadata.parent_id
        if metadata.child_ids:
            result["child_ids"] = json.dumps(metadata.child_ids)
        if metadata.goal_id:
            result["goal_id"] = metadata.goal_id
        if metadata.node_id:
            result["node_id"] = metadata.node_id
        if metadata.task_id:
            result["task_id"] = metadata.task_id
        if metadata.session_id:
            result["session_id"] = metadata.session_id
        if metadata.xp_gained is not None:
            result["xp_gained"] = metadata.xp_gained
        if metadata.stats_delta:
            result["stats_delta"] = json.dumps(metadata.stats_delta)
        if metadata.significance_score is not None:
            result["significance_score"] = metadata.significance_score
        
        return result
    
    def _dict_to_metadata(self, metadata_dict: Dict[str, Any]) -> MemoryMetadata:
        """Convert ChromaDB metadata dict back to MemoryMetadata."""
        # Handle JSON-encoded lists
        tags = []
        if "tags" in metadata_dict:
            tags_str = metadata_dict["tags"]
            if isinstance(tags_str, str):
                try:
                    tags = json.loads(tags_str)
                except:
                    tags = []
            else:
                tags = tags_str
        
        child_ids = []
        if "child_ids" in metadata_dict:
            child_ids_str = metadata_dict["child_ids"]
            if isinstance(child_ids_str, str):
                try:
                    child_ids = json.loads(child_ids_str)
                except:
                    child_ids = []
            else:
                child_ids = child_ids_str
        
        stats_delta = None
        if "stats_delta" in metadata_dict:
            stats_str = metadata_dict["stats_delta"]
            if isinstance(stats_str, str):
                try:
                    stats_delta = json.loads(stats_str)
                except:
                    stats_delta = None
            else:
                stats_delta = stats_str
        
        return MemoryMetadata(
            user_id=metadata_dict["user_id"],
            date=metadata_dict["date"],
            datetime=metadata_dict.get("datetime"),
            day_of_week=metadata_dict["day_of_week"],
            hour=metadata_dict.get("hour"),
            week_of_year=metadata_dict["week_of_year"],
            month=metadata_dict["month"],
            year=metadata_dict["year"],
            chunk_type=ChunkType(metadata_dict["chunk_type"]),
            level=MemoryLevel(metadata_dict["level"]),
            pillar=metadata_dict.get("pillar"),
            sentiment=metadata_dict.get("sentiment"),
            mood_score=metadata_dict.get("mood_score"),
            tags=tags,
            parent_id=metadata_dict.get("parent_id"),
            child_ids=child_ids,
            goal_id=metadata_dict.get("goal_id"),
            node_id=metadata_dict.get("node_id"),
            task_id=metadata_dict.get("task_id"),
            session_id=metadata_dict.get("session_id"),
            xp_gained=metadata_dict.get("xp_gained"),
            stats_delta=stats_delta,
            significance_score=metadata_dict.get("significance_score"),
        )
    
    def clear(self):
        """Clear all memory for this user (use with caution!)."""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memory."""
        count = self.collection.count()
        
        # Get sample to analyze types
        sample = self.collection.get(limit=min(100, count), include=["metadatas"])
        
        type_counts = {}
        level_counts = {}
        if sample["metadatas"]:
            for meta in sample["metadatas"]:
                chunk_type = meta.get("chunk_type", "unknown")
                level = meta.get("level", "unknown")
                type_counts[chunk_type] = type_counts.get(chunk_type, 0) + 1
                level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "total_chunks": count,
            "chunk_types": type_counts,
            "levels": level_counts,
        }
