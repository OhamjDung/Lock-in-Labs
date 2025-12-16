import json
import os
from typing import List
from dotenv import load_dotenv
from src.models import CharacterSheet, SkillTree, SkillNode, NodeType, Pillar
from src.llm import LLMClient

load_dotenv()

SKILL_TREE_PROMPT = """
You are the "System Architect" for a Life RPG. Your objective is to transform a user's abstract goals into a directed acyclic graph (DAG) of Skills, Habits, and Attributes.

**INPUT DATA:**
- Career Stats: {stats_career}
- Physical Stats: {stats_physical}
- Mental Stats: {stats_mental}
- Social Stats: {stats_social}
- Main Quests: {main_quests}

**YOUR MISSION:**
Generate a JSON `SkillTree` where nodes are connected by `prerequisites`. You must identify "Overlap Nodes" (skills that serve multiple goals).

**STRICT TERMINOLOGY RULES (The "Database" Check):**
1. **CAREER:** Use O*NET terminology (e.g., "Complex Problem Solving" instead of "Being smart", "Python (Programming Language)" instead of "Coding").
2. **PHYSICAL:** Use ExerciseDB/Standard Physiology terms (e.g., "VO2 Max", "Posterior Chain Strength").
3. **MENTAL:** Use 'VIA Character Strengths' for buffs (e.g., "Zest", "Prudence") and 'CBT Distortions' for debuffs (e.g., "All-or-Nothing Thinking").
4. **SOCIAL:** Use 'NVC Needs' or O*NET Social Skills (e.g., "Active Listening", "Social Perceptiveness").

**GRAPH LOGIC RULES:**
1. **The Root is the Goal:** The top nodes are the User's `Main Quests`.
2. **The Leaves are Habits:** The bottom nodes are small, daily actions (e.g., "Meditate 5 mins").
3. **MANDATORY WIRING:** 
   - You MUST link Goals to their relevant Skills. 
   - Example: "Play Volleyball" (Goal) MUST have "Physical Endurance" (Skill) and "Agility" (Skill) in its `prerequisites` list.
   - Do NOT leave Goal prerequisites empty.
4. **Identify Overlap:** Connect shared skills (like "Grit") to ALL goals that require them (e.g., Grit -> Coding AND Grit -> Volleyball).
5. **NO ORPHANS:** Every "Sub-Skill" MUST be listed as a prerequisite for at least one "Goal".
6. **MANDATORY OVERLAP:** The node "Grit" (or similar resilience skill) MUST be a prerequisite for at least TWO different Goals (e.g. Career Goal AND Physical Goal).
7. **NO DEAD ENDS:** Every "Sub-Skill" MUST have at least one "Habit" or another "Sub-Skill" as a prerequisite. Users cannot level up a skill without an action. **(CRITICAL: Do not leave prerequisites empty for Sub-Skills)**.
8. **NO GENERIC GATES:** A Sub-Skill cannot *only* depend on "Grit", "Focus", or "Willpower". It must have at least one **Action-Based Habit** as a prerequisite.
   - *Example:* To unlock "Endurance", "Practice Grit" is not enough. You must also add "Habit: Run 1 Mile".
9. **HABIT DENSITY:** You must generate enough unique Habits to ensure every Sub-Skill has a valid parent. Aim for a ratio of 1 Habit per 1-2 Sub-Skills. Do not reuse the same habit for every skill.
10. **HARD SKILLS MANDATE:**
   - If a Goal is "Career" or "Technical" (e.g., Coding, Volleyball), it MUST require a "Hard Skill" prerequisite (e.g., "Python", "Volleyball Technique").
   - It cannot rely ONLY on "Soft Skills" (like Focus, Logic, or Agility).
   - BAD: Goal: Coding <- [Focus, Logic]
   - GOOD: Goal: Coding <- [Focus, Logic, Skill: Python Programming]

**OUTPUT SCHEMA (JSON):**
{{
  "nodes": [
    {{
      "id": "skill_active_listening",
      "name": "Active Listening",
      "type": "Sub-Skill",
      "pillar": "Social",
      "prerequisites": ["habit_no_interrupting_practice"],
      "xp_reward": 100,
      "description": "The ability to give full attention to what other people are saying (O*NET 2.B.1.b)."
    }},
    {{
      "id": "habit_no_interrupting_practice",
      "name": "Practice 'Wait 2 Seconds'",
      "type": "Habit",
      "pillar": "Social",
      "prerequisites": [],
      "xp_reward": 10
    }}
  ]
}}
"""

class SkillTreeGenerator:
    def __init__(self):
        self.llm_client = LLMClient()

    def generate_skill_tree(self, character_sheet: CharacterSheet) -> SkillTree:
        """
        Generates a Skill Tree based on the completed Character Sheet.
        """
        
        # Serialize stats for the prompt
        stats_career_str = json.dumps(character_sheet.stats_career)
        stats_physical_str = json.dumps(character_sheet.stats_physical)
        stats_mental_str = json.dumps(character_sheet.stats_mental)
        stats_social_str = json.dumps(character_sheet.stats_social)
        main_quests_str = json.dumps(character_sheet.main_quests)
        
        prompt = SKILL_TREE_PROMPT.format(
            stats_career=stats_career_str,
            stats_physical=stats_physical_str,
            stats_mental=stats_mental_str,
            stats_social=stats_social_str,
            main_quests=main_quests_str
        )
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response_text = self.llm_client.chat_completion(messages, json_mode=True)
            data = json.loads(response_text)
            
            nodes = []
            for node_data in data.get("nodes", []):
                # Validate Pillar enum
                try:
                    pillar = Pillar(node_data["pillar"])
                except ValueError:
                    pillar = Pillar.CAREER # Default fallback
                
                # Validate NodeType enum
                try:
                    node_type = NodeType(node_data["type"])
                except ValueError:
                    node_type = NodeType.SUB_SKILL # Default fallback

                node = SkillNode(
                    id=node_data["id"],
                    name=node_data["name"],
                    type=node_type,
                    pillar=pillar,
                    prerequisites=node_data.get("prerequisites", []),
                    xp_reward=node_data.get("xp_reward", 100),
                    description=node_data.get("description", "")
                )
                nodes.append(node)
            
            # Sanitize the tree (Fix orphans and grit bottlenecks)
            nodes = self.sanitize_tree(nodes)

            return SkillTree(nodes=nodes)
            
        except Exception as e:
            print(f"Error generating skill tree: {e}")
            return SkillTree(nodes=[])

    def sanitize_tree(self, nodes: List[SkillNode]) -> List[SkillNode]:
        """
        Fixes common AI generation issues:
        1. Orphaned Skills (No prerequisites) -> Adds a generic habit.
        2. Grit Bottleneck (Only depends on Grit) -> Adds a specific habit.
        """
        new_nodes = []
        existing_ids = {n.id for n in nodes}
        
        for node in nodes:
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
                            description=f"Specific exercises to build {node.name}."
                        )
                        new_nodes.append(new_habit)
                        existing_ids.add(habit_id)
                    
                    # Add the specific habit to the prerequisites
                    node.prerequisites.append(habit_id)
                    
        return nodes + new_nodes

