# Lock In Labs: AI Agent Instructions

**Lock In Labs** is a Life RPG system that transforms personal goals into gamified skill trees with habits, XP rewards, and AI-powered onboarding.

## Architecture Overview

### Core Components

1. **FastAPI Backend** (`backend/api.py`, port 8000)
   - Main REST API and WebSocket server
   - Routes: `/api/onboarding/*`, `/api/skill-tree/*`, `/api/profile/*`, `/api/reporting/*`
   - WebSocket endpoints: `/ws/phone-detect` (phone detection), `/ws/voice` (voice input)

2. **Fatigue Detection Server** (`fatigue_detection/app.py`, port 8001)
   - Real-time webcam monitoring with YOLOv11
   - Calibration pipeline: work phase → rating → break phase → baseline stats
   - Saves user profiles to `fatigue_detection/profiles/{user_id}.json`

3. **Skill Tree Generation** (`src/skill_tree/generator.py`)
   - Phase 1: User onboarding → goals per pillar (Career, Physical, Mental, Social)
   - Phase 2: Planner agents order skills via RAG + LLM (pillar-specific)
   - Phase 3: SkillTreeGenerator builds DAG: Goals → Sub-Skills → Habits
   - Includes debuff recovery branches and deduplication

4. **Onboarding Orchestration** (`src/onboarding/agent.py`, `director.py`)
   - **ArchitectAgent**: Directive-driven conversational guide ("Listen kid" opening)
   - **CriticAgent**: Extracts structured CharacterSheet from history
   - **DirectorAgent**: Selects starter habits using LLM ranking

5. **Knowledge Base (RAG)** (`src/knowledge_base.py`, `data/curriculum.json`)
   - TF-IDF vectorization for skill/habit retrieval
   - Retrieved habits injected into LLM prompts as verified context
   - Fallback logic when RAG or LLM fails (heuristic habit generation)

## Critical Design Patterns

### Skill Tree Structure
- **Data Model**: `SkillNode` (id, name, type, pillar, prerequisites, xp_reward, required_completions)
- **Prerequisites Direction**: `node.prerequisites` = list of IDs that must be completed first
  - Edge visualization: prerequisite → dependent
  - Example: Goal "Learn Python" has `prerequisites: ["skill_python_basics"]`
- **Node Types**: GOAL (top-level), SUB_SKILL (skill/quest), HABIT (daily atomic action)
- **Pillars**: CAREER, PHYSICAL, MENTAL, SOCIAL (all tracked independently)

### LLM Integration Patterns
- **Directives**: ArchitectAgent follows rigid directives from ConversationState
  - Enforces single-goal focus during skill level queries
  - Validates responses don't violate goal constraints (see `_strip_thinking_block`)
- **JSON Mode**: Habit generation uses structured LLM output with fallback parsing
- **Thinking Blocks**: Strip Claude thinking tags before frontend delivery

### Habit Generation Rules
- **Actionability**: Must start with verb (Run, Write, Code, etc.)
- **Specificity**: Number of repetitions code-enforced via `DifficultyTier` enum
  - EASY=7, MEDIUM=14, HARD=30, ONE_OFF=1 (milestone/setup tasks)
- **Fallback Heuristics**: If LLM fails, use pillar-specific patterns (e.g., "Meditate for 5 min" for mental)

### Data Flow: Onboarding → Profile
1. User conversation history accumulated in frontend
2. POST `/api/onboarding/extract-profile` → CriticAgent extracts goals
3. Planners generate `needed_quests` per goal (RAG-ordered by LLM)
4. SkillTreeGenerator creates full DAG with habits
5. Profile saved: `data/{user_id}.json` containing CharacterSheet + SkillTree

## Developer Workflows

### Starting Servers
```bash
# Recommended: Use startup script
.\start_servers.ps1  # Windows PowerShell

# Manual: Terminal 1 - Backend API
uvicorn backend.api:app --reload --port 8000

# Manual: Terminal 2 - Fatigue Detection (Windows PowerShell)
$env:FATIGUE_PORT=8001; python fatigue_detection/app.py
```

### Running Calibration (Fatigue Baseline)
```bash
# Basic: 30 min work, 5 min break
python fatigue_detection/calibration_cli.py --user your_user_id

# Quick test: 1 min work, 1 min break
python fatigue_detection/calibration_cli.py --user test_user --work-duration 1 --break-duration 1
```

### Testing Skill Tree Endpoints
- **Test viewer**: `frontend/test/skill_tree_viewer.html` (interactive visualization)
- **Difficulty adjustment**: POST with `{user_id, node_id, direction, amount, reason}`
- **Quiz generation**: GET `/api/skill-tree/generate-quiz/{skill_id}` (lazy loading, stores rubric)

### Debugging Logs
- Agent orchestration: `.cursor/debug.log` (structured JSON with location/hypothesis/timestamp)
- Test data: `data/test_skill_tree_demo*.json` for pipeline validation

## Project-Specific Conventions

### Node ID Convention
- Format: `{type}_{pillar}_{slug}` or `{type}_{rank_slug}`
- Example: `goal_career_become_accountant`, `skill_mental_stress_management`
- Used for deduplication by normalized name matching

### Deduplication Strategy
- Pillar-scoped: Skills merged within same pillar only
- Difflib-based: Normalized name comparison (case-insensitive, remove symbols)
- Cycle detection: Skip planner nodes if they'd create prerequisites cycle

### Profile Storage
- Location: `data/{user_id}.json`
- Schema: `{character_sheet, skill_tree}` (both Pydantic models serialized)
- Habit progress tracked in CharacterSheet's `habit_progress` dict per node_id

### Error Handling Philosophy
- **Graceful degradation**: LLM failures trigger pillar-specific fallback habits
- **Constraint validation**: Directives enforced post-LLM (logged if violated)
- **Empty tree prevention**: Always returns minimal valid tree, never raises on generation

## Key Files to Know

| Path | Purpose |
|------|---------|
| `src/models.py` | Core data models (SkillNode, SkillTree, CharacterSheet, Pillar enums) |
| `src/skill_tree/generator.py` | DAG generation, habit creation, debuff mechanics |
| `src/onboarding/agent.py` | ArchitectAgent directive-following, CriticAgent extraction |
| `src/knowledge_base.py` | RAG retrieval via TF-IDF, curriculum loading |
| `src/planners.py` | Pillar-specific roadmap generators (Career, Physical, Mental, Social) |
| `backend/api.py` | All REST/WebSocket routes, profile I/O, avatar dithering |
| `data/curriculum.json` | Knowledge base (verified skills/habits per pillar) |
| `frontend/test/skill_tree_viewer.html` | Interactive tree visualization, API testing |

## Common Workflows

### Adding a New API Endpoint
1. Define request/response Pydantic models near endpoint
2. Use `load_profile(user_id)` to fetch, `save_profile(data, user_id)` to persist
3. WebSocket: inherit from `ConnectionManager` pattern (see phone-detect)
4. Return proper HTTP status (404 for missing profile, 400 for validation)

### Debugging Habit Generation Issues
1. Check `curriculum.json` for pillar-specific habit examples
2. Verify RAG retrieval with `retrieve_relevant_habits(query, pillar, top_k=3)`
3. If LLM fails, check fallback heuristic matches skill name keywords
4. Enable debug logs: search for `.cursor/debug.log` writes in generator

### Understanding Prerequisite Chains
1. Read `docs/SKILL_TREE_EXPLANATION.md` sections 1-2 for mental model
2. Prerequisites are **inbound dependencies**: node must complete its prerequisites first
3. Visualization: draw arrows FROM prerequisite TO dependent
4. Deduplication: merge nodes with same normalized name within pillar scope
