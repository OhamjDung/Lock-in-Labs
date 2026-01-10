import json
from typing import Dict
from src.models import CharacterSheet
from src.llm import LLMClient


class StatRollerAgent:
    def __init__(self):
        self.llm = LLMClient()

    def calculate_initial_xp(self, character_sheet: CharacterSheet) -> Dict[str, int]:
        """
        Analyzes user's current quests and self-reported skill level
        to award initial 'Legacy XP' based on past experience.
        
        Args:
            character_sheet: CharacterSheet with goals, current_quests, and skill_levels
            
        Returns:
            Dict with xp_career, xp_physical, xp_mental, xp_social, and justification
        """
        # Build goals summary with skill levels and quests
        goals_summary = []
        for goal in character_sheet.goals:
            goals_summary.append({
                "name": goal.name,
                "pillars": [p.value for p in goal.pillars],
                "skill_level": goal.skill_level or 1,
                "current_quests": goal.current_quests
            })
        
        prompt = f"""
You are the StatRoller Agent. Your job is to award initial "Legacy XP" based on what the user has already accomplished in their life.

USER'S PROFILE:
{json.dumps(goals_summary, indent=2)}

RULES FOR XP AWARDING:
1. Skill Level 1-3 (Beginner): Award 0-200 XP total. These users are true beginners and should start from scratch.
2. Skill Level 4-7 (Intermediate): Award 300-1000 XP per relevant pillar. These users have some experience and deserve recognition.
3. Skill Level 8-10 (Advanced): Award 1000-2500 XP per relevant pillar. These users are experienced and should not start at Level 1.

XP DISTRIBUTION LOGIC:
- Distribute XP across pillars based on which pillars each goal belongs to
- If a goal has multiple pillars, split XP proportionally across those pillars
- Consider the current_quests when determining which pillars should get more XP
- A goal with skill_level 8 in CAREER should give significant xp_career
- A goal with skill_level 5 in PHYSICAL should give moderate xp_physical

OUTPUT JSON (ONLY JSON, NO MARKDOWN):
{{
    "xp_career": <int>,
    "xp_physical": <int>,
    "xp_mental": <int>,
    "xp_social": <int>,
    "justification": "Brief explanation of the XP allocation (1-2 sentences)"
}}
"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.llm.chat_completion(messages, json_mode=True)
        
        try:
            data = json.loads(response)
            return {
                "xp_career": max(0, data.get("xp_career", 0)),
                "xp_physical": max(0, data.get("xp_physical", 0)),
                "xp_mental": max(0, data.get("xp_mental", 0)),
                "xp_social": max(0, data.get("xp_social", 0)),
                "justification": data.get("justification", "Initial XP awarded based on past experience.")
            }
        except json.JSONDecodeError as e:
            print(f"[StatRoller] Failed to parse LLM response: {e}")
            print(f"[StatRoller] Response was: {response}")
            # Fallback: return zeros
            return {
                "xp_career": 0,
                "xp_physical": 0,
                "xp_mental": 0,
                "xp_social": 0,
                "justification": "Failed to parse response. Starting from zero."
            }
