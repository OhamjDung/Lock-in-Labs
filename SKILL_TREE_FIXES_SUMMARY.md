# Skill Tree Fixes Summary

## Fixed Issues

### 1. ✅ Skill Deduplication (MAJOR FIX)
**Problem**: Skills like "Active Listening" appeared 4 times with suffixes `_2`, `_3`, `_4`, creating parallel vertical lines instead of a tree.

**Root Cause**: Generator created new nodes for each goal without checking if semantically identical skills existed.

**Solution**: 
- Added `skill_by_key` dictionary mapping normalized names (`_slugify()`) to SkillNode objects
- Before creating skill, check if normalized name exists in dictionary
- If exists, reuse the existing node ID instead of creating duplicate
- Applied to both roadmap generation and legacy fallback paths

**Files Modified**:
- [src/skill_tree/generator.py](src/skill_tree/generator.py#L310-L400)

**Result**: 
- **Before**: 74 nodes (33 sub-skills with 6 types duplicated)
- **After**: 58 nodes (25 unique sub-skills, 0 duplicates)
- **Impact**: 22% reduction in nodes, true tree structure with cross-pillar connections

---

### 2. ✅ Missing Roadmaps (CRITICAL FIX)
**Problem**: All goals had `roadmap: []` (empty array), causing generator to fall back to flat "legacy" skills.

**Root Cause**: In `backend/api.py:extract_profile()`, planners were called and returned SkillNode arrays, but only `needed_quests` (names only) were saved, not the full `roadmap` structure with prerequisites.

**Solution**:
```python
# BEFORE
goal.needed_quests = [node.name for node in needed_skill_nodes]

# AFTER
goal.roadmap = needed_skill_nodes  # Preserve full SkillNode structure
goal.needed_quests = [node.name for node in needed_skill_nodes]  # Legacy compat
```

**Files Modified**:
- [backend/api.py](backend/api.py#L1625)

**Result**: Skill trees now have proper depth (4-5 layers) with prerequisite chains instead of flat lists.

---

### 3. ✅ Habit Actionability (MAJOR UX FIX)
**Problem**: Habits used lazy templates like "Complete 1 Active Listening task" - not actionable.

**Root Cause**: LLM prompt was not strict enough, and fallback logic used `f"Complete 1 {skill.name} task"`.

**Solution**:

**A. Strengthened LLM Prompt**:
```python
"**STRICT ACTIONABILITY RULES (ENFORCED):**\n"
"1. **START WITH A VERB**: Every habit MUST begin with action verb\n"
"2. **INCLUDE A NUMBER/DURATION**: '10 mins', '5 pages', '3 sets'\n"
"3. **FORBIDDEN WORDS**: NEVER use 'Practice', 'Task', 'Complete'\n"
"4. **BE STUPIDLY SIMPLE**: A 5-year-old should understand what to do\n"
```

**B. Created Smart Fallback**:
```python
def _generate_fallback_habit(self, skill_name: str, pillar: Pillar) -> str:
    """Generate actionable habits using pillar-aware heuristics"""
    if "listening" in skill_lower:
        return "Repeat back the last sentence someone said"
    elif "hypertrophy" in skill_lower:
        return "Perform 3 sets of 10 pushups"
    # ... 60+ patterns
```

**Files Modified**:
- [src/skill_tree/generator.py](src/skill_tree/generator.py#L131-L160) - Prompt
- [src/skill_tree/generator.py](src/skill_tree/generator.py#L96-L160) - Fallback method

**Result**:
- **Before**: ❌ "Complete 1 Active Listening task"
- **After**: ✅ "Repeat back the last sentence someone said"
- **Test Score**: 5/5 habits actionable (100%)

---

### 4. ✅ Orphan Goals / RAG Fallback (COMPLETENESS FIX)
**Problem**: "Become a plumber" had `prerequisites: []` because RAG returned 0 skills.

**Root Cause**: When knowledge base has no data for a goal, planner returned empty array instead of using LLM's internal knowledge.

**Solution**: Added fallback warning in prompt when RAG returns nothing:
```python
if not verified_skills or len(verified_skills) == 0:
    rag_warning = (
        "\n**⚠️ WARNING: No verified skills found in knowledge base.**\n"
        "You MUST use your internal knowledge to generate a basic roadmap.\n"
        "Example: For 'Become a plumber', generate:\n"
        "  - Basic Plumbing Tools Knowledge\n"
        "  - Pipe Fitting Basics\n"
        # ... examples
    )
```

**Files Modified**:
- [src/planners.py](src/planners.py#L97-L117)

**Result**:
- **Before**: 0 skills generated for "Become a plumber"
- **After**: 5 skills with proper prerequisite chain
- **Test**: Both "plumber" and "professional bagpipe player" generated valid roadmaps

---

## Verification Tests

### Test 1: Deduplication
```bash
python debug/test_skill_tree_deduplication.py
```
**Result**: ✅ 0 duplicates, 25 unique skills, 8 shared skill connections

### Test 2: Habit Quality
```bash
python debug/test_habit_quality.py
```
**Result**: ✅ 100% actionable habits (5/5)
- "Write 5 lines of Python"
- "Solve 1 Python data type problem"
- "Code 3 if/else statements"
- "Create 2 Python functions"
- "Analyze 1 Pandas DataFrame"

### Test 3: RAG Fallback
```bash
python debug/test_plumber_fallback.py
```
**Result**: ✅ Both tests passed
- Plumber: 5 skills with 4-layer depth
- Bagpipe player: 5 skills generated

---

## Comparison: Before vs After

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Total Nodes** | 74 | 58 | -22% |
| **Sub-Skills** | 33 (6 types duplicated) | 25 (all unique) | -24% |
| **Duplicates** | 6 types | 0 | ✅ Eliminated |
| **Orphan Goals** | 1 ("Become a plumber") | 0 | ✅ Fixed |
| **Actionable Habits** | ~0% | 100% | ✅ Fixed |
| **Tree Structure** | Parallel lines (isolated) | Interconnected web | ✅ Fixed |
| **RAG Fallback** | None (fails on unknown goals) | LLM internal knowledge | ✅ Added |

---

## Visualization Impact

### Before (Parallel Lines)
```
Goal: Outgoing  Goal: Flexible  Goal: Social    Goal: Connection
    ↓               ↓               ↓               ↓
Active Listen_1  Active Listen_2  Active Listen_3  Active Listen_4
    ↓               ↓               ↓               ↓
  Habit 1         Habit 2         Habit 3         Habit 4

❌ 4 isolated vertical lines
❌ No cross-pillar connections
❌ Wide, sparse layout
```

### After (Interconnected Graph)
```
Goal: Outgoing    Goal: Flexible    Goal: Social    Goal: Connection
    ↓                 ↓                 ↓               ↓
    └──────── Active Listening (SHARED) ────────────────┘
                      ↓
            "Repeat back last sentence"

✅ Single shared node feeds 4 goals
✅ Cross-pillar synergy (SOCIAL + CAREER)
✅ Compact, connected layout
```

---

## Files Changed

1. **src/skill_tree/generator.py** (150 lines modified)
   - Skill deduplication logic
   - Habit prompt strengthening
   - Smart fallback habit generator

2. **backend/api.py** (3 lines modified)
   - Save `goal.roadmap` structure

3. **src/planners.py** (15 lines modified)
   - RAG fallback warning when no skills found

---

## Next Steps (Optional Enhancements)

### 1. Delete Duplicate Goals
The 4 single-word goals ("Fitness", "Career", "Social", "Connection") are artifacts from phase 3.5 pillar ranking. These can be:
- Automatically deleted during profile cleanup
- Prevented by improving Critic's phase 3.5 detection

### 2. Cross-Pillar Skill Suggestions
The system could proactively suggest shared skills:
- "Active Listening helps both SOCIAL and CAREER goals. Unlock synergy by leveling it up!"

### 3. Habit Variety
Current system generates 1 habit per skill. Could expand to:
- Multiple difficulty tiers (Easy: 5 mins, Medium: 20 mins, Hard: 1 hour)
- Time-of-day variations (Morning meditation vs Evening journaling)

---

## User-Facing Improvements

✅ **Cleaner Skill Tree**: 22% fewer nodes, easier to navigate  
✅ **Clear Progress Paths**: Shared skills show how different goals interconnect  
✅ **Actionable Daily Tasks**: Users know exactly what to do ("Run 1 mile" vs "Complete task")  
✅ **No More Orphans**: Every goal gets a roadmap, even obscure ones like "Become a plumber"  
✅ **Better Visualization**: Frontend can now render a true DAG instead of parallel lines
