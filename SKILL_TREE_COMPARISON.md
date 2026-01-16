# Skill Tree Comparison: Before vs After Deduplication

## Summary Statistics

| Metric | OLD (skill_tree_output.json) | NEW (skill_tree_deduped.json) | Improvement |
|--------|------------------------------|-------------------------------|-------------|
| **Total Nodes** | 74 | 58 | **-16 nodes (-22%)** |
| **Goals** | 8 | 8 | Same |
| **Sub-Skills** | 33 | 25 | **-8 skills (-24%)** |
| **Habits** | 33 | 25 | **-8 habits (-24%)** |
| **Duplicate Skills** | 6 types duplicated | 0 | **✅ All duplicates removed** |
| **Orphan Goals** | 1 | 1 | Same (fixable by running planner) |

---

## Duplicate Skill Elimination

### OLD Tree - Duplicated Skills (Parallel Lines Problem)

These skills appeared multiple times with different IDs:

1. **"Active Listening"** - 4 copies
   - `skill_active_listening` (SOCIAL)
   - `skill_active_listening_2` (CAREER) 
   - `skill_active_listening_3` (SOCIAL)
   - `skill_active_listening_4` (SOCIAL)

2. **"Conversation Starters"** - 3 copies
   - `skill_conversation_starters` (SOCIAL)
   - `skill_conversation_starters_2` (SOCIAL)
   - `skill_conversation_starters_3` (SOCIAL)

3. **"Basic Communication Skills"** - 2 copies
   - `skill_basic_communication_skills` (CAREER)
   - `skill_basic_communication_skills_2` (CAREER)

4. **"Complete First Project"** - 2 copies
   - `skill_complete_first_project` (CAREER)
   - `skill_complete_first_project_2` (CAREER)

5. **"Empathy"** - 2 copies
   - `skill_empathy` (SOCIAL)
   - `skill_empathy_2` (SOCIAL)

6. **"Rapport Building"** - 2 copies
   - `skill_rapport_building` (SOCIAL)
   - `skill_rapport_building_2` (SOCIAL)

**Result**: Each goal had its own isolated copy → Parallel vertical lines with no connections

---

### NEW Tree - Shared Skills (True Tree Structure)

Each skill appears **once** and is reused across goals:

1. **"Active Listening"** - 1 node
   - Used by: "Be more outgoing...", "Be more flexible" (connects SOCIAL + CAREER)

2. **"Conversation Starters"** - 1 node
   - Used by: "Be more outgoing...", "Social", "Connection" (connects 3 SOCIAL goals)

3. **"Basic Communication Skills"** - 1 node
   - Used by: "Be more flexible", "Career" (connects 2 CAREER goals)

4. **"Complete First Project"** - 1 node
   - Used by: "Be more flexible", "Career" (connects 2 CAREER goals)

5. **"Empathy"** - 1 node
   - Used by: "Social", "Connection" (connects 2 SOCIAL goals)

6. **"Rapport Building"** - 1 node
   - Used by: "Social", "Connection" (connects 2 SOCIAL goals)

**Result**: Shared nodes create an interconnected web → True tree structure with cross-pillar connections

---

## Visual Structure Comparison

### OLD Tree (Parallel Lines)
```
Goal 1 (SOCIAL)          Goal 2 (CAREER)          Goal 3 (SOCIAL)
    ↓                        ↓                        ↓
Active Listening       Active Listening_2       Active Listening_3
    ↓                        ↓                        ↓
  Habit 1                  Habit 2                  Habit 3

(No connections between pillars - isolated vertical chains)
```

### NEW Tree (Interconnected Graph)
```
Goal 1 (SOCIAL)     Goal 2 (CAREER)     Goal 3 (SOCIAL)
    ↓                   ↓                   ↓
    └─────── Active Listening ──────────────┘
                ↓
             Habit
             
(Single "Active Listening" node feeds multiple goals - web structure)
```

---

## Habit Deduplication

### OLD Tree
- 33 habits generated (one per skill, including duplicates)
- Example: 4 separate "Complete 1 Active Listening task" habits

### NEW Tree  
- 25 habits generated (one per unique skill)
- Example: 1 "Complete 1 Active Listening task" habit shared across goals

**Impact**: User sees cleaner habit list, no confusion about which "Active Listening" to work on

---

## Known Issues (Both Trees)

### 1. "Become a plumber" - Orphan Goal ⚠️
- **Cause**: No `needed_quests` or `roadmap` in profile data
- **Fix**: Re-run planner for this goal OR delete duplicate goals and re-onboard
- **Status**: Not fixed by deduplication logic (data issue, not code issue)

### 2. Duplicate Goals Created During Onboarding
Both trees have 4 extra single-word goals:
- "Fitness" (PHYSICAL)
- "Career" (CAREER)  
- "Social" (SOCIAL)
- "Connection" (SOCIAL)

**Cause**: Phase 3.5 pillar ranking responses were misinterpreted as new goals by Critic agent

**Fix**: Already addressed in previous onboarding fixes - these won't appear in new profiles

---

## Code Changes That Enabled This

### 1. Skill Deduplication (generator.py)
```python
skill_by_key: dict = {}  # Maps normalized name -> SkillNode

for raw_node in current_roadmap:
    skill_key = _slugify(raw_node.name)  # "Active Listening" → "active_listening"
    
    if skill_key in skill_by_key:
        # REUSE existing skill instead of creating duplicate
        existing_skill = skill_by_key[skill_key]
        planner_id_map[raw_node.id] = existing_skill.id
    else:
        # Create new skill and register in lookup
        new_node = SkillNode(...)
        skill_by_key[skill_key] = new_node
```

### 2. Roadmap Preservation (api.py)
```python
# BEFORE (only saved names, lost structure)
goal.needed_quests = [node.name for node in needed_skill_nodes]

# AFTER (saves full SkillNode objects with prerequisites)
goal.roadmap = needed_skill_nodes  
goal.needed_quests = [node.name for node in needed_skill_nodes]  # Legacy
```

---

## Visualization Impact

### OLD Tree in Dagre/D3
- **Width**: Very wide due to parallel columns for each duplicate
- **Whitespace**: Large gaps between disconnected subgraphs
- **Readability**: Hard to see relationships between goals
- **Structure**: Looks like 8 separate mini-trees, not one unified tree

### NEW Tree in Dagre/D3
- **Width**: Compact - skills flow into multiple goals
- **Whitespace**: Minimal - nodes are connected and grouped
- **Readability**: Clear prerequisite chains and cross-pillar synergies
- **Structure**: True DAG with shared foundation skills

---

## Files for Comparison

- **OLD**: `skill_tree_output.json` (74 nodes, 6 duplicate skill types)
- **NEW**: `skill_tree_deduped.json` (58 nodes, 0 duplicates)
- **Profile Source**: `data/8OgBJwxGgRc1No7mi6tbVwmOZE13.json` (same data for both)

---

## Recommendation

**Use the NEW tree** (`skill_tree_deduped.json`) for your frontend visualization. It will:

1. ✅ Render as a proper tree/web structure in Dagre
2. ✅ Show meaningful connections between different life pillars  
3. ✅ Reduce visual clutter (16 fewer nodes)
4. ✅ Make it clear which skills support multiple goals
5. ✅ Eliminate confusing duplicate skill names

The frontend can now visualize "Active Listening" as a **keystone skill** that bridges SOCIAL and CAREER goals, rather than displaying 4 isolated copies.
