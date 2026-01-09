# In-Depth Explanation: How the Skill Tree System Works

## 1. Core Data Structure

### SkillNode
Each node in the tree is a `SkillNode` with:

```python
SkillNode:
  - id: "skill_python" (unique identifier)
  - name: "Python Proficiency" (display name)
  - type: "Goal" | "Sub-Skill" | "Habit" (hierarchy level)
  - pillar: "CAREER" | "PHYSICAL" | "MENTAL" | "SOCIAL"
  - prerequisites: ["skill_basics", "habit_practice"] (list of node IDs)
  - xp_reward: 100 (XP gained on completion)
  - xp_multiplier: 1.0 (affected by debuffs)
  - required_completions: 30 (for habits, how many times to complete)
  - description: "Ability to write clean Python code..."
```

### SkillTree
A `SkillTree` is a collection of nodes that form a Directed Acyclic Graph (DAG):

```python
SkillTree:
  - nodes: List[SkillNode] (all nodes in the tree)
```

**Critical: Prerequisites Direction**
- The `prerequisites` field stores **dependencies** (what must be completed first)
- If node A has `prerequisites: ["node_b"]`, it means **A depends on B**
- In graph visualization: Edge points **B → A** (from prerequisite to dependent)
- Example: `Goal: "Learn Python"` has `prerequisites: ["skill_python_basics"]`
  - Visualization: `skill_python_basics` → `Goal: "Learn Python"`
  - Meaning: You must complete "Python Basics" before unlocking the Goal

## 2. The Generation Pipeline

The skill tree is built in stages:

### Phase 1: User Onboarding → Goals
During onboarding, users define goals per pillar:
- Career: "Become a Data Scientist"
- Physical: "Run a Marathon"
- Mental: "Reduce Anxiety"
- Social: "Build Stronger Friendships"

Each goal has:
- `current_quests`: What the user is already doing
- `needed_quests`: Generated roadmap (populated in Phase 2)

### Phase 2: Planner → Roadmap Generation (RAG-Enhanced)

For each goal, a pillar-specific planner generates a roadmap:

```
User Goal: "Become Data Scientist"
  ↓
CareerPlanner.generate_roadmap()
  ↓
RAG: Search Knowledge Base (TF-IDF)
  ↓
Retrieve: ["Python Proficiency", "Data Analysis with Pandas", ...]
  ↓
LLM Prompt: "Here are verified skills. Order them logically (Beginner → Advanced). Use them if relevant, or generate new ones."
  ↓
Output: ["Python Basics", "NumPy Arrays", "Pandas DataFrames", "Data Visualization", "Machine Learning Basics", "SQL Queries", "Project Portfolio"]
  ↓
These become goal.needed_quests
```

**Critical: LLM Ordering Responsibility**
- RAG returns an **unordered bag** of skills: `["Advanced ML", "Python Basics"]`
- The **LLM is responsible for ordering** these into a logical dependency chain
- The prompt explicitly instructs: "Order them logically from beginner to advanced"
- The LLM structures them with prerequisites: `"Advanced ML"` depends on `"Python Basics"`
- This ordering happens in the planner's prompt, not in the RAG retrieval

### Phase 3: Skill Tree Assembly

`SkillTreeGenerator.generate_skill_tree()` builds the final tree:

#### Step 1: Create Goal Nodes
```python
for goal in goals_list:
    goal_node = SkillNode(
        id="goal_become_data_scientist",
        name="Become a Data Scientist",
        type=NodeType.GOAL,
        pillar=Pillar.CAREER,
        prerequisites=[],  # Will be populated
        xp_reward=100
    )
```

#### Step 2: Create Sub-Skill Nodes from needed_quests
```python
for quest in goal.needed_quests:  # ["Python Basics", "NumPy Arrays", ...]
    skill_node = SkillNode(
        id="skill_python_basics",
        name="Python Basics",
        type=NodeType.SUB_SKILL,
        pillar=Pillar.CAREER,
        prerequisites=[],  # Will be populated with habits
        xp_reward=150
    )
    # Link skill to goal
    goal_node.prerequisites.append(skill_node.id)
```

#### Step 3: Generate Habits (RAG-Enhanced)

For each Sub-Skill, generate concrete daily habits:

```python
# RAG: Search for verified habits
habits = retrieve_relevant_habits(
    query="Python Basics coding practice",
    pillar=Pillar.CAREER,
    top_k=3
)
# Finds: "Solve 1 LeetCode Easy", "Code for 30 Minutes"

# LLM generates 2-3 habits per skill using verified habits as context
# Creates habit nodes and links them to skills
```

Result structure:
```
Goal: "Become Data Scientist"
  └─ Sub-Skill: "Python Basics"
      ├─ Habit: "Solve 1 LeetCode Easy" (30 completions)
      ├─ Habit: "Code for 30 Minutes" (30 completions)
      └─ Habit: "Read Python Documentation" (30 completions)
```

#### Step 4: Debuff Recovery Branches

For each debuff (e.g., "Procrastination"), create a recovery branch:

```python
debuff_goal = SkillNode(
    id="goal_overcome_procrastination",
    name="Overcome Procrastination",
    type=NodeType.GOAL,
    prerequisites=["skill_time_management"]
)

recovery_skill = SkillNode(
    id="skill_time_management",
    name="Time Management",
    type=NodeType.SUB_SKILL,
    prerequisites=["habit_pomodoro_technique"]
)

habit = SkillNode(
    id="habit_pomodoro_technique",
    name="Use Pomodoro Technique",
    type=NodeType.HABIT,
    prerequisites=[],  # Habits are leaves
    required_completions=30
)
```

## 3. Graph Structure: The DAG

The tree is a Directed Acyclic Graph (DAG) where:

- **Direction**: Edges point from prerequisites → dependents
- **Acyclic**: No circular dependencies
- **Hierarchy**: Goals → Sub-Skills → Habits

Example structure:

```
Goal: "Run Marathon" (PHYSICAL)
  └─ Sub-Skill: "Endurance Training"
      ├─ Habit: "Run 3 miles" (30x)
      └─ Habit: "Zone 2 Cardio" (30x)

Goal: "Advance Career" (CAREER)
  └─ Sub-Skill: "Python Proficiency"
      ├─ Habit: "Code 30 mins" (30x)
      └─ Habit: "Solve 1 LeetCode" (30x)

Overlap Node (bridges pillars):
Sub-Skill: "Grit" (MENTAL)
  ├─ Prerequisite for: "Run Marathon" goal
  ├─ Prerequisite for: "Advance Career" goal
  └─ Habit: "Cold Showers" (30x)
```

**Critical: Shared State & Overlap Nodes**
- Nodes are **unique by ID** - there is only one `habit_cold_showers` node
- When you complete `habit_cold_showers`, it contributes progress to **all parent trees simultaneously**
- Example: Completing "Cold Showers" (30x) unlocks "Grit", which unlocks both "Run Marathon" AND "Advance Career"
- This is a **feature, not a bug** - it rewards efficiency and recognizes that skills transfer across pillars
- XP is awarded **once per completion**, but the progress counts toward all dependent nodes

## 4. Post-Processing Steps

After initial generation, three cleanup steps run:

### A. Deduplicate Goals
Merges similar goals (e.g., "Code Daily" and "Dedicate time to coding"):
```python
# Uses SequenceMatcher to find 75%+ similar goals
# Merges prerequisites and removes duplicates
```

### B. Sanitize Tree
Fixes common issues:

1. **Orphaned Skills**: Skills with no prerequisites get a generic habit
   ```python
   if not skill.prerequisites:
       # Add "Practice {skill_name}" habit
   ```

2. **Grit Bottleneck**: If a skill only depends on generic "grit", add a specific habit
   ```python
   if skill.prerequisites == ["habit_grit"]:
       # Add pillar-specific habit (e.g., "Study Python Drills")
   ```

### C. Apply Debuff Mechanics
Applies XP penalties based on active debuffs:
```python
if "Sleep Deprivation" in debuffs:
    # Reduce XP multiplier to 0.5 for Mental/Physical nodes
    node.xp_multiplier = 0.5
```

## 5. RAG Integration Points

RAG is used at two points:

### Point 1: Planner Roadmap Generation
```python
# In CareerPlanner.generate_roadmap()
verified_skills = retrieve_relevant_skills(
    query="Become Data Scientist",
    top_k=5,
    pillar=Pillar.CAREER
)
# Returns: ["Python Proficiency", "Data Analysis with Pandas", ...]
# These are injected into LLM prompt as "Verified Skill Library"
# LLM orders them and structures prerequisites
```

**Critical: LLM Ordering**
- RAG returns unordered results: `["Advanced ML", "Python Basics"]`
- LLM prompt explicitly instructs: "Order them logically from beginner to advanced"
- LLM creates prerequisite chains: `"Advanced ML"` → `prerequisites: ["Python Basics"]`
- The LLM is responsible for **structuring** the retrieved skills into a logical dependency chain

### Point 2: Habit Generation
```python
# In SkillTreeGenerator._generate_habits_for_skills()
for skill in skills:
    habits = retrieve_relevant_habits(
        query=f"{skill.name} {skill.description}",
        pillar=skill.pillar,
        top_k=3
    )
    # Returns verified habits from curriculum.json
    # Injected into LLM prompt for habit generation
```

## 6. How It's Used in the System

### Storage
The skill tree is stored in:
- Local: `data/{user_id}.json`
- Firebase: `profiles/{user_id}/skill_tree`

### Progress Tracking
Each habit node tracks:
- `completed_total`: Total completions
- `streak_days`: Current streak
- `status`: LOCKED | ACTIVE | MASTERED

### Unlocking Logic
Nodes unlock when prerequisites are met:
```python
def can_unlock(node: SkillNode, completed_nodes: Set[str]) -> bool:
    return all(prereq in completed_nodes for prereq in node.prerequisites)
```

### XP System
- Completing a habit: `xp_reward * xp_multiplier` XP
- Mastering a habit (30 completions): Unlocks parent Sub-Skill
- Completing all Sub-Skills: Unlocks parent Goal

## 7. Key Design Principles

1. **Unified Tree**: All goals connect via overlap nodes (e.g., "Grit")
2. **Atomic Habits**: Leaves are concrete, daily actions
3. **Progressive Difficulty**: Roadmap goes from basics to advanced
4. **Pillar Integration**: Skills can bridge multiple pillars
5. **Debuff Handling**: Recovery branches for obstacles
6. **RAG Grounding**: Uses verified skills/habits when available, generates when needed
7. **LLM Ordering**: LLM structures retrieved skills into logical dependency chains

## 8. Example: Complete Flow

User input:
- Goal: "Learn Python for Data Science"
- Current quests: ["Reading Python tutorials"]
- Debuffs: ["Procrastination"]

Generated tree:
```
Goal: "Learn Python for Data Science" (CAREER)
  ├─ Sub-Skill: "Python Proficiency" [RAG: from curriculum.json]
  │   ├─ Habit: "Solve 1 LeetCode Easy" [RAG: verified habit]
  │   └─ Habit: "Code for 30 Minutes" [RAG: verified habit]
  ├─ Sub-Skill: "Data Analysis with Pandas" [RAG: from curriculum.json]
  │   └─ Habit: "Practice Pandas DataFrame operations" [Generated]
  └─ Sub-Skill: "NumPy Arrays" [Generated]
      └─ Habit: "Write NumPy array exercises" [Generated]

Goal: "Overcome Procrastination" (PHYSICAL)
  └─ Sub-Skill: "Time Management"
      └─ Habit: "Use Pomodoro Technique" (30x)
```

This system transforms high-level goals into actionable daily habits, grounded in verified knowledge while remaining flexible for niche goals.
