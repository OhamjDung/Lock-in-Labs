import json
from typing import List
from src.models import SkillNode, NodeType, Pillar
from src.llm import LLMClient


class BasePlanner:
    def __init__(self):
        self.llm_client = LLMClient()

    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str]) -> List[SkillNode]:
        raise NotImplementedError

    def _call_llm(self, prompt: str) -> List[SkillNode]:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.llm_client.chat_completion(messages, json_mode=True)
            data = json.loads(response)
            nodes: List[SkillNode] = []

            for raw in data.get("nodes", []):
                node_data = dict(raw)  # shallow copy so we can normalize

                # --- Normalize type ---
                t = node_data.get("type")
                if isinstance(t, str):
                    # If it's not one of the allowed enum values, fall back to Habit
                    if t not in {e.value for e in NodeType}:
                        node_data["type"] = NodeType.HABIT.value

                # --- Normalize pillar ---
                p = node_data.get("pillar")
                if isinstance(p, str):
                    # Map common title‑case forms to our enum values
                    pillar_map = {
                        "Career": Pillar.CAREER.value,
                        "Physical": Pillar.PHYSICAL.value,
                        "Mental": Pillar.MENTAL.value,
                        "Social": Pillar.SOCIAL.value,
                    }
                    if p in pillar_map:
                        node_data["pillar"] = pillar_map[p]
                    else:
                        up = p.upper()
                        if up in Pillar.__members__:
                            node_data["pillar"] = Pillar[up].value
                        else:
                            # Skip nodes with unrecognizable pillars
                            continue

                try:
                    nodes.append(SkillNode(**node_data))
                except Exception as node_err:
                    print(f"Planner Node Error: {node_err}")
                    continue

            return nodes
        except Exception as e:
            print(f"Planner Error: {e}")
            return []


class CareerPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str]) -> List[SkillNode]:
        prompt = f"""
        You are a Career Architect using the O*NET Database.
       
        **GOAL:** {north_star}
        **CURRENT SKILLS/HABITS:** {json.dumps(current_quests)}
        **DEBUFFS:** {json.dumps(debuffs)}

        **TASK:**
        Create a progressive roadmap of at least 7 steps to bridge the gap between the User's current state and their Goal.
        - Start from where they are (Current Quests).
        - End at the Goal.
        - If they have debuffs like 'Burnout' or 'Procrastination', include recovery steps.
        - STRICTLY use "Career" as the pillar for all nodes.
       
        **OUTPUT SCHEMA (JSON):**
        {{
            "nodes": [
                {{
                    "id": "skill_pandas",
                    "name": "Pandas Library",
                    "type": "Sub-Skill",
                    "pillar": "Career",
                    "prerequisites": ["prev_node_id"],
                    "xp_reward": 100,
                    "description": "Data manipulation mastery (O*NET 15-2051.00)."
                }}
            ]
        }}
        """
        return self._call_llm(prompt)


class PhysicalPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str]) -> List[SkillNode]:
        prompt = f"""
        You are a Strength & Conditioning Coach using the ExerciseDB ontology.
       
        **GOAL:** {north_star}
        **CURRENT HABITS:** {json.dumps(current_quests)}
        **DEBUFFS:** {json.dumps(debuffs)}

        **TASK:**
        Create a progressive overload roadmap (at least 7 steps).
        - If debuffs like 'Sleep Deprivation' exist, start with 'Recovery' or 'Sleep Hygiene'.
        - Use specific exercises (e.g., 'Knee Pushup' -> 'Pushup').
        - STRICTLY use "Physical" as the pillar for all nodes.
       
        **OUTPUT SCHEMA (JSON):**
        {{
            "nodes": [
                {{
                    "id": "skill_pushup_progression",
                    "name": "Pushup Progression",
                    "type": "Sub-Skill",
                    "pillar": "Physical",
                    "prerequisites": ["prev_node_id"],
                    "xp_reward": 100,
                    "description": "Upper body strength development."
                }}
            ]
        }}
        """
        return self._call_llm(prompt)


class MentalPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str]) -> List[SkillNode]:
        prompt = f"""
        You are a Cognitive Behavioral Therapist (CBT) and High-Performance Coach using VIA Character Strengths.
       
        **GOAL:** {north_star}
        **CURRENT HABITS:** {json.dumps(current_quests)}
        **DEBUFFS:** {json.dumps(debuffs)}

        **TASK:**
        Create a roadmap (7+ steps) to build mental resilience and clarity.
        - Address debuffs immediately (e.g., 'Anxiety' -> 'Box Breathing').
        - Progress from simple habits to complex mental models.
        - STRICTLY use "Mental" as the pillar for all nodes.
       
        **OUTPUT SCHEMA (JSON):**
        {{
            "nodes": [
                {{
                    "id": "skill_mindfulness",
                    "name": "Mindfulness Practice",
                    "type": "Sub-Skill",
                    "pillar": "Mental",
                    "prerequisites": ["prev_node_id"],
                    "xp_reward": 100,
                    "description": "Cultivating present-moment awareness."
                }}
            ]
        }}
        """
        return self._call_llm(prompt)


class ConnectionPlanner(BasePlanner):
    def generate_roadmap(self, north_star: str, current_quests: List[str], debuffs: List[str]) -> List[SkillNode]:
        prompt = f"""
        You are a Social Dynamics Coach using NVC (Nonviolent Communication) principles.
       
        **GOAL:** {north_star}
        **CURRENT HABITS:** {json.dumps(current_quests)}
        **DEBUFFS:** {json.dumps(debuffs)}

        **TASK:**
        Create a roadmap (7+ steps) to improve social connection and leadership.
        - Address social anxiety or isolation first.
        - Use terms like 'Active Listening', 'Empathy', 'Conflict Resolution'.
        - STRICTLY use "Social" as the pillar for all nodes.
       
        **OUTPUT SCHEMA (JSON):**
        {{
            "nodes": [
                {{
                    "id": "skill_active_listening",
                    "name": "Active Listening",
                    "type": "Sub-Skill",
                    "pillar": "Social",
                    "prerequisites": ["prev_node_id"],
                    "xp_reward": 100,
                    "description": "Fully concentrating on what is being said."
                }}
            ]
        }}
        """
        return self._call_llm(prompt)
