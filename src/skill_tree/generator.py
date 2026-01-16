import json
import os
import difflib
from typing import List
from dotenv import load_dotenv
from src.models import CharacterSheet, SkillTree, SkillNode, NodeType, Pillar, DifficultyTier, REP_MAP
from src.llm import LLMClient
from src.knowledge_base import retrieve_relevant_habits

load_dotenv()

SKILL_TREE_PROMPT = """
You are the "System Architect" for a Life RPG. Your objective is to transform a user's goals and habits into a unified, directed acyclic graph (DAG) of skills.

**INPUT DATA:**
- Goals (Prioritized List): {goals_json}
- Career Stats: {stats_career}
- Physical Stats: {stats_physical}
- Mental Stats: {stats_mental}
- Social Stats: {stats_social}
- Debuffs: {debuffs}

**YOUR MISSION:**
Generate a single, unified JSON `SkillTree` that connects all goals. You must identify "Overlap Nodes" (skills that serve multiple goals from different pillars). The `prerequisites` field is how you build the graph.

**STRICT RULES:**
1.  **Unified Tree**: All goals, regardless of pillar, must be part of the *same* tree. Connect them by finding shared, underlying skills.
2.  **Atomic Habits**: The leaves of your tree (nodes with no prerequisites) MUST be small, daily, actionable habits (e.g., "Meditate for 10 mins," "Solve 1 LeetCode Problem").
3.  **No Vague Verbs**: Avoid "Practice Python." Use "Write 1 Python script to automate a task."
4.  **Connect Goals to Skills**: A `Goal` node cannot have an empty `prerequisites` list. It must be connected to underlying `Sub-Skill` nodes.
5.  **Identify Overlap (CRITICAL)**: Find skills that bridge pillars.
    *   `Grit` or `Resilience` is a classic example. It should be a prerequisite for a challenging `Career` goal AND a tough `Physical` goal.
    *   `Focus` could be required for both `Mental` clarity and `Career` productivity.
    *   You MUST create at least one such overlap node.
6.  **No Orphans**: Every `Sub-Skill` must be a prerequisite for at least one `Goal` or another `Sub-Skill`.
7.  **No Dead Ends**: Every `Sub-Skill` must have prerequisites. Skills don't appear from nowhere; they are built from habits.
8.  **Debuff Handling**: For each debuff, you MUST create a "Cure" branch. This should be a `Goal` to overcome the debuff, linked to skills and habits.
    *   Debuff: "Procrastination" -> Goal: "Overcome Procrastination" -> Skill: "Time Management" -> Habit: "Use the Pomodoro Technique."
9.  **No Cycles**: A `Habit` node's `prerequisites` list must ALWAYS be empty.

**OUTPUT SCHEMA (JSON):**
{{
  "nodes": [
    {{
      "id": "goal_career_advancement",
      "name": "Advance in Career",
      "type": "Goal",
            "pillar": "CAREER",
      "prerequisites": ["skill_python_programming", "skill_grit"],
      "xp_reward": 1000
    }},
    {{
      "id": "goal_run_marathon",
      "name": "Run a Marathon",
      "type": "Goal",
    "pillar": "PHYSICAL",
      "prerequisites": ["skill_endurance", "skill_grit"],
      "xp_reward": 1000
    }},
    {{
      "id": "skill_grit",
      "name": "Grit",
      "type": "Sub-Skill",
    "pillar": "MENTAL",
      "prerequisites": ["habit_cold_showers"],
      "xp_reward": 200,
      "description": "The ability to persevere through hardship."
    }},
    // ... other nodes
  ]
}}
"""

def _slugify(text: str) -> str:
    """Simple slug helper for stable node IDs."""
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in text)
    return cleaned.strip("_") or "node"


class SkillTreeGenerator:
    def __init__(self):
        self.llm_client = LLMClient()

    def _make_unique_id(self, used_ids: set, prefix: str, name: str) -> str:
        base = f"{prefix}_{_slugify(name)}"
        if base not in used_ids:
            used_ids.add(base)
            return base
        i = 2
        while f"{base}_{i}" in used_ids:
            i += 1
        new_id = f"{base}_{i}"
        used_ids.add(new_id)
        return new_id

    def _generate_fallback_habit(self, skill_name: str, pillar: Pillar) -> str:
        """Generate a better fallback habit when LLM fails, using simple heuristics."""
        skill_lower = skill_name.lower()
        
        # Physical pillar patterns
        if pillar == Pillar.PHYSICAL:
            if "run" in skill_lower or "cardio" in skill_lower:
                return "Run 1 mile at easy pace"
            elif "strength" in skill_lower or "muscle" in skill_lower or "hypertrophy" in skill_lower:
                return "Perform 3 sets of 10 pushups"
            elif "squat" in skill_lower:
                return "Perform 3 sets of 5 bodyweight squats"
            elif "deadlift" in skill_lower:
                return "Perform 3 sets of 5 deadlifts with light weight"
            elif "stretch" in skill_lower or "flexibility" in skill_lower or "mobility" in skill_lower:
                return "Hold 5 stretches for 30 seconds each"
            elif "workout" in skill_lower:
                return "Complete a 20-minute workout"
            else:
                return "Exercise for 15 minutes"
        
        # Career pillar patterns
        elif pillar == Pillar.CAREER:
            if "communication" in skill_lower or "speaking" in skill_lower:
                return "Have 1 focused conversation with a colleague"
            elif "code" in skill_lower or "programming" in skill_lower or "python" in skill_lower:
                return "Write 10 lines of code"
            elif "time management" in skill_lower or "productivity" in skill_lower:
                return "Complete 1 Pomodoro session (25 mins)"
            elif "excel" in skill_lower or "spreadsheet" in skill_lower:
                return "Create 1 Excel formula or pivot table"
            elif "financial" in skill_lower or "accounting" in skill_lower:
                return "Analyze 1 financial statement"
            elif "project" in skill_lower:
                return "Work on project for 30 minutes"
            else:
                return "Work on 1 career skill for 20 minutes"
        
        # Mental pillar patterns
        elif pillar == Pillar.MENTAL:
            if "meditat" in skill_lower or "mindful" in skill_lower:
                return "Meditate for 5 minutes"
            elif "journal" in skill_lower or "writing" in skill_lower:
                return "Write 3 journal entries about emotions"
            elif "calm" in skill_lower or "stress" in skill_lower or "anxiety" in skill_lower:
                return "Take 10 deep breaths when stressed"
            elif "focus" in skill_lower or "concentration" in skill_lower:
                return "Focus on 1 task for 15 minutes without distractions"
            else:
                return "Practice mental wellness for 10 minutes"
        
        # Social pillar patterns (with variety to avoid redundant habit names)
        elif pillar == Pillar.SOCIAL:
            if "conversation" in skill_lower or "talk" in skill_lower:
                # Vary conversation habits to avoid "Start 1 conversation" × 4
                import random
                variations = [
                    "Ask someone for directions or recommendations",
                    "Compliment 1 person genuinely",
                    "Ask someone about their day or weekend plans",
                    "Start 1 conversation with someone new",
                    "Share 1 interesting fact or story with someone",
                    "Ask someone about their hobbies or interests"
                ]
                return random.choice(variations)
            elif "listening" in skill_lower or "listen" in skill_lower:
                return "Repeat back the last sentence someone said"
            elif "empathy" in skill_lower or "understanding" in skill_lower:
                return "Ask someone how they're feeling"
            elif "rapport" in skill_lower or "relationship" in skill_lower:
                return "Send 1 message to reconnect with a friend"
            elif "meetup" in skill_lower or "event" in skill_lower:
                return "Attend 1 social event"
            else:
                return "Have 1 meaningful social interaction"
        
        # Generic fallback
        return f"Practice {skill_name} for 15 minutes"

    def _generate_habits_for_skills(
        self,
        skills: List[SkillNode],
        used_ids: set,
    ) -> List[SkillNode]:
        """Use the LLM to generate concrete habit leaves for each skill node.

        If the LLM call fails or returns nothing usable, falls back to a simple
        deterministic habit for each skill.
        """

        if not skills:
            return []

        habit_nodes: List[SkillNode] = []

        # 1. RAG Retrieval for Habits
        # Pre-fetch habits for all skills to pass as context
        verified_habits_context = {}
        for skill in skills:
            # Search query combines skill name and description for better matching
            query = f"{skill.name} {skill.description or ''}"
            habits = retrieve_relevant_habits(query, pillar=skill.pillar, top_k=3)
            if habits:
                verified_habits_context[skill.id] = habits

        # 2. Build Prompt
        skills_payload = [
            {"id": s.id, "name": s.name, "pillar": s.pillar.value}
            for s in skills
        ]
        
        rag_text = json.dumps(verified_habits_context, indent=2)

        prompt = (
            "You are a Behavioral Scientist designing Atomic Habits for a Life RPG. "
            "Given this JSON list of skills, propose 1 SPECIFIC, PHYSICAL action for EACH skill.\n\n"
            f"**VERIFIED HABIT LIBRARY (Use these if they match the skill):**\n{rag_text}\n\n"
            
            "**STRICT ACTIONABILITY RULES (ENFORCED):**\n"
            "1. **START WITH A VERB**: Every habit MUST begin with an action verb (Run, Write, Read, Solve, Code, Build, Say, Do, Create, Analyze, etc.)\n"
            "2. **INCLUDE A NUMBER/DURATION**: Every habit MUST have a measurable quantity:\n"
            "   - Time: '10 mins', '2 minutes', '30 seconds'\n"
            "   - Quantity: '3 sets', '5 pages', '1 problem', '10 lines'\n"
            "   - Reps: '5 pushups', '1 conversation', '3 examples'\n"
            "3. **FORBIDDEN WORDS**: NEVER use 'Practice', 'Task', 'Complete', 'Do exercise', 'Work on'\n"
            "4. **BE STUPIDLY SIMPLE**: A 5-year-old should understand exactly what to do\n"
            "5. **CAREER CONTEXT CHECK**: If the skill is for a NON-CODING career (Accounting, Finance, Marketing), "
            "   FORBID coding habits (LeetCode, Git, Programming). Use domain tools instead (Excel, Reports, Spreadsheets).\n\n"
            
            "**FORBIDDEN EXAMPLES (DO NOT GENERATE THESE):**\n"
            "❌ 'Practice Active Listening' (No verb, uses 'Practice')\n"
            "❌ 'Complete 1 Active Listening task' (Uses 'Complete' and 'task')\n"
            "❌ 'Work on Hypertrophy Training' (Vague, no number)\n"
            "❌ 'Get better at running' (Not an action)\n\n"
            
            "**CORRECT EXAMPLES (GENERATE LIKE THESE):**\n"
            "✅ 'Repeat back the last sentence someone said' (Verb + specific action)\n"
            "✅ 'Perform 3 sets of 10 pushups' (Verb + number + specific exercise)\n"
            "✅ 'Run 1 mile at easy pace' (Verb + distance + constraint)\n"
            "✅ 'Write 5 lines of Python' (Verb + quantity + specific)\n"
            "✅ 'Read 10 pages of a finance book' (Verb + quantity + context)\n"
            "✅ 'Solve 1 LeetCode Easy problem' (Verb + quantity + specific)\n"
            "✅ 'Create 1 Excel pivot table' (Verb + quantity + tool)\n\n"
            
            "**DIFFICULTY TIERS:**\n"
            "For each habit, assign a 'difficulty_tier' (1, 2, 3, or 4):\n"
            "   - Tier 1 (Easy): Simple daily tasks (e.g. 'Drink water', 'Take vitamins')\n"
            "   - Tier 2 (Medium): Moderate effort (e.g. 'Code for 30 mins', 'Read 20 pages')\n"
            "   - Tier 3 (Hard): Deep work/training (e.g. 'Run 5k', 'Build full-stack app')\n"
            "   - Tier 4 (One-off): Milestones (e.g. 'Setup environment', 'Buy equipment')\n"
            "DO NOT assign 'required_completions' directly. Only provide 'difficulty_tier'.\n\n"
            
            "Return JSON ONLY in this format:\n"
            "{\n  \"habits\": [\n    {\n      \"skill_id\": \"skill_xyz\",\n"
            "      \"habits\": [\n        {\"name\": \"Actionable Verb + Noun\", \"description\": \"Why this works...\", \"difficulty_tier\": 2}\n      ]\n    }\n  ]\n}"
            "\n\nSkills JSON:\n" + json.dumps(skills_payload)
        )

        messages = [{"role": "user", "content": prompt}]

        habits_by_skill: dict = {}
        try:
            response_text = self.llm_client.chat_completion(messages, json_mode=True)
            data = json.loads(response_text)
            for entry in data.get("habits", []):
                sid = entry.get("skill_id")
                if not isinstance(sid, str):
                    continue
                habits_list = entry.get("habits", [])
                if isinstance(habits_list, list):
                    habits_by_skill.setdefault(sid, []).extend(habits_list)
        except Exception as e:
            print(f"Habit generation error, falling back to defaults: {e}")

        # Build habit nodes and wire them as leaves under each skill
        for skill in skills:
            raw_habits = habits_by_skill.get(skill.id)

            if not raw_habits:
                # Fallback: Generate actionable habit based on skill name
                habit_name = self._generate_fallback_habit(skill.name, skill.pillar)
                habit_id = self._make_unique_id(used_ids, "habit", habit_name)
                habit = SkillNode(
                    id=habit_id,
                    name=habit_name,
                    type=NodeType.HABIT,
                    pillar=skill.pillar,
                    prerequisites=[],
                    xp_reward=15,
                    required_completions=30,
                    description=f"Daily habit to improve {skill.name}.",
                )
                habit_nodes.append(habit)
                if habit_id not in skill.prerequisites:
                    skill.prerequisites.append(habit_id)
                continue

            for h in raw_habits:
                if not isinstance(h, dict):
                    continue
                # Remove "Practice" prefix if present and replace with action verb
                name = h.get("name") or f"Complete 1 {skill.name} task"
                # Clean up any "Practice" prefixes that might have slipped through
                if name.lower().startswith("practice "):
                    name = name[9:].strip()  # Remove "practice " prefix
                    # Try to add a better verb
                    if not any(name.lower().startswith(v) for v in ["run", "write", "read", "solve", "code", "build", "speak", "do", "complete", "create", "analyze"]):
                        name = f"Complete {name}"
                
                # Filter out coding-related habits for non-coding careers
                coding_keywords = ["leetcode", "git", "algorithm", "programming", "code commit", "pull request"]
                career_keywords = ["accountant", "accounting", "finance", "financial", "marketing", "sales", "hr", "human resources"]
                skill_name_lower = skill.name.lower()
                habit_name_lower = name.lower()
                
                # If this is a non-coding career skill and the habit contains coding keywords, replace it
                if any(ck in skill_name_lower for ck in career_keywords) and any(ckw in habit_name_lower for ckw in coding_keywords):
                    # Replace with appropriate career tool
                    if "account" in skill_name_lower or "finance" in skill_name_lower or "tax" in skill_name_lower:
                        name = f"Create 1 Excel Macro for {skill.name}"
                    elif "model" in skill_name_lower or "analysis" in skill_name_lower:
                        name = f"Analyze 1 {skill.name} report"
                    else:
                        name = f"Complete 1 {skill.name} task"
                desc = h.get("description") or f"Daily habit to improve {skill.name}."
                
                # Safe enum conversion with fallback
                try:
                    dt = int(h.get("difficulty_tier", 2))
                    if dt not in [1, 2, 3, 4]:
                        dt = 2  # Fallback to medium
                except (ValueError, TypeError):
                    dt = 2  # Fallback on any error
                
                reps = REP_MAP[DifficultyTier(dt)]
                
                habit_id = self._make_unique_id(used_ids, "habit", name)
                habit = SkillNode(
                    id=habit_id,
                    name=name,
                    type=NodeType.HABIT,
                    pillar=skill.pillar,
                    prerequisites=[],
                    xp_reward=15,
                    xp_multiplier=1.0,
                    required_completions=reps,  # Code-enforced, not LLM-generated
                    description=desc,
                )
                habit_nodes.append(habit)
                if habit_id not in skill.prerequisites:
                    skill.prerequisites.append(habit_id)

        return habit_nodes

    def generate_skill_tree(self, character_sheet: CharacterSheet) -> SkillTree:
        """Generate a tree where:

        - Each goal becomes a Goal node (one per pillar goal).
        - Each needed_quest under that goal becomes a Sub-Skill node (branch).
        - Each Sub-Skill gets concrete Habit leaf nodes (via LLM + fallback).
        - Each debuff gets its own "Overcome <Debuff>" Goal with a recovery skill
          branch and habits as leaves.
        """

        try:
            goals_list = character_sheet.get_goal_list()

            nodes: List[SkillNode] = []
            used_ids: set = set()

            # Map normalized skill name -> SkillNode to allow overlap across goals
            skill_by_key: dict = {}
            all_skills: List[SkillNode] = []

            # 1) Goals with structured roadmap (preserving prerequisite chains)
            for goal in goals_list:
                # Use the first pillar for the goal node (goals can have multiple pillars)
                goal_pillar = goal.pillars[0] if goal.pillars else Pillar.CAREER
                goal_id = self._make_unique_id(used_ids, "goal", goal.name)
                goal_node = SkillNode(
                    id=goal_id,
                    name=goal.name,
                    type=NodeType.GOAL,
                    pillar=goal_pillar,
                    prerequisites=[],
                    xp_reward=100,
                    xp_multiplier=1.0,
                    description=goal.description or "",
                )
                nodes.append(goal_node)

                current_roadmap = goal.roadmap
                
                # MIGRATION FALLBACK:
                # If no roadmap exists but needed_quests does, convert on the fly.
                if not current_roadmap and goal.needed_quests:
                    print(f"Migrating legacy goal: {goal.name}")
                    legacy_node_ids = []  # Track IDs to link to goal
                    
                    for q in goal.needed_quests:
                        # DEDUPLICATION: Check if this skill already exists
                        skill_key = _slugify(q)
                        
                        if skill_key in skill_by_key:
                            # Reuse existing skill node instead of creating duplicate
                            print(f"  Reusing existing skill: {q}")
                            existing_skill = skill_by_key[skill_key]
                            legacy_node_ids.append(existing_skill.id)
                        else:
                            # Create new skill node
                            id_candidate = _slugify(q)
                            # Check if progress exists under the raw name (old behavior)
                            if q in character_sheet.habit_progress:
                                final_id = q
                            # Check if progress exists under the slug (potential hybrid behavior)
                            elif id_candidate in character_sheet.habit_progress:
                                final_id = id_candidate
                            else:
                                # Default to skill_ prefix for clean IDs (not legacy_ anymore)
                                final_id = f"skill_{id_candidate}"
                            
                            new_skill = SkillNode(
                                id=final_id, 
                                name=q, 
                                type=NodeType.SUB_SKILL, 
                                pillar=goal_pillar, 
                                xp_reward=100,
                                prerequisites=[],
                                description=""  # Empty for clean display
                            )
                            skill_by_key[skill_key] = new_skill
                            nodes.append(new_skill)
                            all_skills.append(new_skill)
                            legacy_node_ids.append(final_id)
                    
                    # Link all legacy skills directly to goal (they have no prerequisites chain)
                    for skill_id in legacy_node_ids:
                        if skill_id not in goal_node.prerequisites:
                            goal_node.prerequisites.append(skill_id)
                    
                    # Skip the roadmap structure preservation logic for legacy goals
                    continue
                
                if not current_roadmap:
                    continue
                
                # --- Preserve Planner's Deep Structure ---
                
                # 1. Create ID mapping (planner IDs -> unique tree IDs) with deduplication
                planner_id_map = {}
                
                # First pass: Create or reuse planner nodes
                for raw_node in current_roadmap:
                    # DEDUPLICATION: Check if semantically identical skill exists
                    skill_key = _slugify(raw_node.name)
                    
                    if skill_key in skill_by_key:
                        # Reuse existing skill node
                        existing_skill = skill_by_key[skill_key]
                        planner_id_map[raw_node.id] = existing_skill.id
                        print(f"  Reusing skill '{raw_node.name}' (ID: {existing_skill.id}) for goal '{goal.name}'")
                    else:
                        # Create new skill node
                        unique_id = self._make_unique_id(used_ids, "skill", raw_node.name)
                        planner_id_map[raw_node.id] = unique_id
                        
                        new_node = SkillNode(
                            id=unique_id,
                            name=raw_node.name,
                            type=NodeType.SUB_SKILL,
                            pillar=goal_pillar,
                            prerequisites=[],  # Fill in Pass 2
                            xp_reward=raw_node.xp_reward,
                            xp_multiplier=raw_node.xp_multiplier,
                            description=raw_node.description
                        )
                        skill_by_key[skill_key] = new_node
                        nodes.append(new_node)
                        all_skills.append(new_node)
                
                # Second pass: Link prerequisites (preserve planner's chain)
                for raw_node in current_roadmap:
                    real_node_id = planner_id_map.get(raw_node.id)
                    if not real_node_id:
                        continue
                    real_node = next((n for n in nodes if n.id == real_node_id), None)
                    if not real_node:
                        continue
                    
                    for prereq_id in raw_node.prerequisites:
                        if prereq_id in planner_id_map:
                            mapped_id = planner_id_map[prereq_id]
                            if mapped_id not in real_node.prerequisites:
                                real_node.prerequisites.append(mapped_id)
                
                # Third pass: Find terminal nodes (top of chain) and link to Goal
                all_prereq_ids = set()
                for raw_node in current_roadmap:
                    all_prereq_ids.update(raw_node.prerequisites)
                
                terminal_node_ids = []
                for raw_node in current_roadmap:
                    if raw_node.id not in all_prereq_ids:
                        real_id = planner_id_map.get(raw_node.id)
                        if real_id:
                            terminal_node_ids.append(real_id)
                
                # Link terminal nodes to Goal
                for term_id in terminal_node_ids:
                    if term_id not in goal_node.prerequisites:
                        goal_node.prerequisites.append(term_id)
                
                # --- FALLBACK: If goal has 0 prerequisites, connect all sub-skills ---
                if not goal_node.prerequisites and terminal_node_ids:
                    # Graph fragmentation detected - fallback to flattening
                    for term_id in terminal_node_ids:
                        if term_id not in goal_node.prerequisites:
                            goal_node.prerequisites.append(term_id)
                
                # If still empty, connect ALL sub-skills as failsafe
                if not goal_node.prerequisites:
                    for raw_node in current_roadmap:
                        real_id = planner_id_map.get(raw_node.id)
                        if real_id and real_id not in goal_node.prerequisites:
                            goal_node.prerequisites.append(real_id)
                
                # --- End Deep Structure Preservation ---

            # 2) Debuff removal branches: goal -> recovery skill -> habits
            for debuff in character_sheet.debuffs:
                debuff_goal_name = f"Overcome {debuff}"
                goal_id = self._make_unique_id(used_ids, "goal_fix", debuff_goal_name)
                debuff_goal = SkillNode(
                    id=goal_id,
                    name=debuff_goal_name,
                    type=NodeType.GOAL,
                    pillar=Pillar.PHYSICAL,
                    prerequisites=[],
                    xp_reward=500,
                    xp_multiplier=1.0,
                    description="Recovery quest to remove debuff.",
                )
                nodes.append(debuff_goal)

                recovery_skill_name = f"Recovery Skills for {debuff}"
                key = _slugify(recovery_skill_name)
                if key in skill_by_key:
                    recovery_skill = skill_by_key[key]
                else:
                    skill_id = self._make_unique_id(used_ids, "skill_fix", recovery_skill_name)
                    recovery_skill = SkillNode(
                        id=skill_id,
                        name=recovery_skill_name,
                        type=NodeType.SUB_SKILL,
                        pillar=Pillar.PHYSICAL,
                        prerequisites=[],
                        xp_reward=200,
                        xp_multiplier=1.0,
                        description=f"Skills to overcome debuff '{debuff}'.",
                    )
                    skill_by_key[key] = recovery_skill
                    all_skills.append(recovery_skill)
                    nodes.append(recovery_skill)

                if recovery_skill.id not in debuff_goal.prerequisites:
                    debuff_goal.prerequisites.append(recovery_skill.id)

            # 3) Generate tangible habit leaves for every skill node
            habit_nodes = self._generate_habits_for_skills(all_skills, used_ids)
            nodes.extend(habit_nodes)

            tree = SkillTree(nodes=nodes)

            # 4) Post-processing
            self.deduplicate_goals(tree)
            self.sanitize_tree(tree)
            self.apply_debuff_mechanics(tree, character_sheet.debuffs)
            self.fix_milestone_completions(tree)  # Fix "Groundhog Day" bug

            return tree

        except Exception as e:
            print(f"Error generating skill tree: {e}")
            return SkillTree(nodes=[])

    def apply_debuff_mechanics(self, tree: SkillTree, debuffs: List[str]):
        """
        1. Applies XP penalties based on active debuffs.
        2. Generates 'Cure' branches for debuffs if missing.
        """
        for debuff in debuffs:
            # A. XP Penalty Logic
            if "Sleep" in debuff or "Fatigue" in debuff:
                # Penalty to Mental and Physical
                for node in tree.nodes:
                    if node.pillar in [Pillar.MENTAL, Pillar.PHYSICAL]:
                        node.xp_multiplier = 0.5 # 50% XP Gain
                        node.description += f" [DEBUFF: {debuff} (-50% XP)]"
            
            # B. Cure Branch Logic (Simple Heuristic)
            # Check if a goal to fix this exists
            has_cure = any(debuff.lower() in node.name.lower() for node in tree.nodes if node.type == NodeType.GOAL)
            
            if not has_cure:
                # Inject a Cure Branch
                goal_id = f"goal_fix_{debuff.lower().replace(' ', '_')}"
                habit_id = f"habit_fix_{debuff.lower().replace(' ', '_')}"
                
                goal = SkillNode(
                    id=goal_id, 
                    name=f"Overcome {debuff}", 
                    type=NodeType.GOAL, 
                    pillar=Pillar.PHYSICAL, # Or Mental, depending on debuff
                    xp_reward=500, 
                    description="Recovery quest to remove debuff."
                )
                habit = SkillNode(
                    id=habit_id, 
                    name=f"Fix {debuff} Action", 
                    type=NodeType.HABIT, 
                    pillar=Pillar.PHYSICAL, 
                    xp_reward=50,
                    required_completions=30,
                    description="Daily action to resolve issue."
                )
                goal.prerequisites.append(habit_id)
                
                tree.nodes.append(goal)
                tree.nodes.append(habit)

    def fix_milestone_completions(self, tree: SkillTree):
        """
        Fix "Groundhog Day" bug: Milestone/capstone nodes should have required_completions = 1.
        
        Detects milestone nodes by checking for keywords like "pass", "exam", "attend", 
        "run 5k", "complete", etc. These are one-time events, not repeating habits.
        """
        milestone_keywords = [
            "pass", "milestone", "exam", "certification", "certificate",
            "attend 3", "attend 1", "attend a", "host", "land",
            "run 5k", "run 10k", "run marathon", "deadlift", "bench press",
            "complete", "finish", "achieve", "earn", "obtain", "get first",
            "establish", "create first", "build first", "launch"
        ]
        
        for node in tree.nodes:
            lower_name = node.name.lower()
            
            # Check if node name contains milestone keywords
            is_milestone = any(keyword in lower_name for keyword in milestone_keywords)
            
            if is_milestone:
                # Milestones are one-time events, not repeating habits
                if node.required_completions != 1:
                    print(f"[Milestone Fix] Setting {node.name} to required_completions=1 (was {node.required_completions})")
                    node.required_completions = 1

    def deduplicate_goals(self, tree: SkillTree):
        """
        Merges goals that are too similar (e.g., 'Code Daily' and 'Dedicate time to coding').
        """
        goals = [n for n in tree.nodes if n.type == NodeType.GOAL]
        to_remove = set()
        
        for i in range(len(goals)):
            for j in range(i + 1, len(goals)):
                g1, g2 = goals[i], goals[j]
                if g1.id in to_remove or g2.id in to_remove:
                    continue
                
                # Similarity Ratio
                ratio = difflib.SequenceMatcher(None, g1.name.lower(), g2.name.lower()).ratio()
                
                if ratio > 0.75: # 75% similar
                    # Merge g2 into g1
                    # 1. Move g2's prerequisites to g1 and deduplicate
                    g1.prerequisites = list(set(g1.prerequisites + g2.prerequisites))
                    # 2. Mark g2 for deletion
                    to_remove.add(g2.id)
        
        # Filter out removed nodes
        tree.nodes = [n for n in tree.nodes if n.id not in to_remove]

    def sanitize_tree(self, tree: SkillTree):
        """
        Fixes common AI generation issues:
        1. Orphaned Skills (No prerequisites) -> Adds a generic habit.
        2. Grit Bottleneck (Only depends on Grit) -> Adds a specific habit.
        """
        new_nodes = []
        existing_ids = {n.id for n in tree.nodes}
        
        for node in tree.nodes:
            if node.type == NodeType.SUB_SKILL:
                # 1. Fix Orphans
                if not node.prerequisites:
                    habit_id = f"habit_practice_{node.id.replace('skill_', '')}"
                    # Avoid duplicates
                    if habit_id not in existing_ids:
                        new_habit = SkillNode(
                            id=habit_id,
                            name=f"Practice {node.name}",
                            type=NodeType.HABIT,
                            pillar=node.pillar,
                            prerequisites=[],
                            xp_reward=10,
                            required_completions=30,
                            description=f"Daily practice to improve {node.name}."
                        )
                        new_nodes.append(new_habit)
                        existing_ids.add(habit_id)
                    node.prerequisites.append(habit_id)
                
                # 2. Fix Grit Bottleneck
                # Check if the ONLY prerequisite is "habit_grit" (or similar generic ones)
                is_grit_only = (len(node.prerequisites) == 1 and 
                               any(term in node.prerequisites[0] for term in ["grit", "willpower", "focus"]))
                
                if is_grit_only:
                    # Create a specific habit based on the pillar
                    action_verb = "Perform"
                    if node.pillar == Pillar.PHYSICAL:
                        action_verb = "Train"
                    elif node.pillar == Pillar.SOCIAL:
                        action_verb = "Engage in"
                    elif node.pillar == Pillar.CAREER:
                        action_verb = "Study"
                        
                    habit_id = f"habit_specific_{node.id.replace('skill_', '')}"
                    
                    if habit_id not in existing_ids:
                        new_habit = SkillNode(
                            id=habit_id,
                            name=f"{action_verb} {node.name} Drills",
                            type=NodeType.HABIT,
                            pillar=node.pillar,
                            prerequisites=[],
                            xp_reward=15,
                            required_completions=30,
                            description=f"Specific exercises to build {node.name}."
                        )
                        new_nodes.append(new_habit)
                        existing_ids.add(habit_id)
                    
                    # Add the specific habit to the prerequisites
                    node.prerequisites.append(habit_id)
                    
        tree.nodes.extend(new_nodes)

