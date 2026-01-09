import json
import os
from typing import List, Dict, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.models import Pillar

# Singleton State
_KNOWLEDGE_BASE: List[Dict] = []
_HABITS_KB: List[Dict] = []
_VECTORIZER: Optional[TfidfVectorizer] = None
_SKILL_VECTORS = None
_HABIT_VECTORS = None

def _safe_parse_pillar(pillar_str: str) -> Optional[Pillar]:
    """Safely convert a string to a Pillar enum, handling typos/case."""
    if not pillar_str:
        return None
    try:
        return Pillar(pillar_str.upper())
    except ValueError:
        # Fallback: return None to avoid crashing on typos
        return None

def init_knowledge_base():
    """Load knowledge base and create TF-IDF vectors. Idempotent."""
    global _KNOWLEDGE_BASE, _HABITS_KB, _VECTORIZER, _SKILL_VECTORS, _HABIT_VECTORS
    
    if _VECTORIZER is not None:
        return  # Already loaded

    kb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "curriculum.json")
    
    try:
        with open(kb_path, "r") as f:
            data = json.load(f)
        _KNOWLEDGE_BASE = data.get("skills", [])
        _HABITS_KB = data.get("habits", [])
        print(f"[RAG] Loaded {len(_KNOWLEDGE_BASE)} skills and {len(_HABITS_KB)} habits")
    except FileNotFoundError:
        print(f"[RAG] Warning: Knowledge base not found at {kb_path}. RAG disabled.")
        return
    except json.JSONDecodeError:
        print(f"[RAG] Error: {kb_path} is not valid JSON. RAG disabled.")
        return

    # Create searchable documents: Name + Tags + Description
    skill_docs = [
        f"{s.get('name', '')} {' '.join(s.get('tags', []))} {s.get('description', '')}"
        for s in _KNOWLEDGE_BASE
    ]
    
    habit_docs = [
        f"{h.get('name', '')} {' '.join(h.get('tags', []))} {h.get('description', '')}"
        for h in _HABITS_KB
    ]
    
    # Initialize TF-IDF vectorizer (lightweight)
    _VECTORIZER = TfidfVectorizer(stop_words='english', max_features=5000)
    
    # Fit on ALL documents (skills + habits) to share vocabulary
    all_docs = skill_docs + habit_docs
    if all_docs:
        _VECTORIZER.fit(all_docs)
        
        if skill_docs:
            _SKILL_VECTORS = _VECTORIZER.transform(skill_docs)
        if habit_docs:
            _HABIT_VECTORS = _VECTORIZER.transform(habit_docs)

def retrieve_relevant_skills(
    query: str, 
    top_k: int = 7, 
    pillar: Optional[Pillar] = None,
    similarity_threshold: float = 0.1
) -> List[Dict]:
    """Retrieve top K verified skills matching the query."""
    init_knowledge_base() # Ensure loaded
    
    if _SKILL_VECTORS is None or not _KNOWLEDGE_BASE:
        return []

    try:
        query_vec = _VECTORIZER.transform([query])
        scores = cosine_similarity(query_vec, _SKILL_VECTORS).flatten()
        
        sorted_indices = scores.argsort()[::-1]
        
        results = []
        for idx in sorted_indices:
            score = scores[idx]
            if score < similarity_threshold:
                break
            
            skill = _KNOWLEDGE_BASE[idx]
            
            # Filter by Pillar if provided (with safe parsing)
            if pillar:
                skill_pillar = _safe_parse_pillar(skill.get("pillar"))
                if skill_pillar and skill_pillar != pillar:
                    continue
            
            results.append(skill)
            if len(results) >= top_k:
                break
                
        return results
    except Exception as e:
        print(f"[RAG] Skill retrieval failed: {e}")
        return []

def retrieve_relevant_habits(
    query: str,
    pillar: Optional[Pillar] = None,
    top_k: int = 3,
    similarity_threshold: float = 0.1
) -> List[Dict]:
    """Retrieve verified habits."""
    init_knowledge_base()
    
    if _HABIT_VECTORS is None or not _HABITS_KB:
        return []

    try:
        query_vec = _VECTORIZER.transform([query])
        scores = cosine_similarity(query_vec, _HABIT_VECTORS).flatten()
        sorted_indices = scores.argsort()[::-1]
        
        results = []
        for idx in sorted_indices:
            if scores[idx] < similarity_threshold:
                break
            
            habit = _HABITS_KB[idx]
            
            if pillar:
                habit_pillar = _safe_parse_pillar(habit.get("pillar"))
                if habit_pillar and habit_pillar != pillar:
                    continue
            
            results.append(habit)
            if len(results) >= top_k:
                break
        
        return results
    except Exception as e:
        print(f"[RAG] Habit retrieval failed: {e}")
        return []
