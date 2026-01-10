import json
from typing import List, Tuple
from src.models import SkillTree, CharacterSheet, NodeType, NodeStatus, SkillNode, Pillar
from src.llm import LLMClient


class DirectorAgent:
    def __init__(self):
        self.llm = LLMClient()

    def _are_prereqs_met(self, node: SkillNode, sheet: CharacterSheet) -> bool:
        """Check if node's prerequisites are satisfied (all unlocked or mastered)."""
        if not node.prerequisites:
            return True
        
        for prereq_id in node.prerequisites:
            progress = sheet.habit_progress.get(prereq_id)
            if not progress or progress.status not in [NodeStatus.ACTIVE, NodeStatus.MASTERED]:
                return False
        return True

    def select_starter_directives(
        self, 
        tree: SkillTree, 
        sheet: CharacterSheet
    ) -> Tuple[List[str], str]:
        """
        Select 3-5 starter habits from top 2 prioritized pillars.
        
        Args:
            tree: Generated SkillTree
            sheet: CharacterSheet with pillar_rankings
            
        Returns:
            Tuple of (selected_node_ids, onboarding_message)
        """
        # 1. Filter Pillars: Get top 2 pillars from sheet.pillar_rankings
        top_pillars = sheet.pillar_rankings[:2] if len(sheet.pillar_rankings) >= 2 else sheet.pillar_rankings
        
        # Fallback: infer from goal priorities (first 2 unique pillars from goals)
        if not top_pillars:
            seen_pillars = []
            for goal in sheet.goals:
                for pillar in goal.pillars:
                    if pillar not in seen_pillars:
                        seen_pillars.append(pillar)
                        if len(seen_pillars) >= 2:
                            break
                if len(seen_pillars) >= 2:
                    break
            top_pillars = seen_pillars
        
        # 2. Find Candidates: Get all HABIT nodes in those pillars that have NO prerequisites (or only completed ones)
        candidates = []
        for node in tree.nodes:
            if (node.type == NodeType.HABIT and 
                node.pillar in top_pillars and 
                self._are_prereqs_met(node, sheet)):
                candidates.append(node)
        
        # If no candidates with met prerequisites, allow any habits from top pillars (for initial selection)
        if not candidates:
            for node in tree.nodes:
                if node.type == NodeType.HABIT and node.pillar in top_pillars:
                    if node.id not in [c.id for c in candidates]:
                        candidates.append(node)
        
        if not candidates:
            # No valid candidates - return empty list
            return [], "Welcome! Your skill tree is ready. You'll unlock habits as you progress."
        
        # 3. LLM Selection (The "Director"): Pick the best 3-5 from valid candidates
        if len(candidates) <= 5:
            selected = candidates
            onboarding_message = "Welcome! These are your starter habits. Let's begin your journey."
        else:
            # Ask LLM to select best 3-5
            candidates_json = [{
                "id": n.id,
                "name": n.name,
                "pillar": n.pillar.value if hasattr(n.pillar, 'value') else str(n.pillar),
                "description": n.description or ""
            } for n in candidates]
            
            prompt = f"""
You are the Director Agent. The user is starting their journey.
We need to pick max 5 Starter Directives (Habits) for them to focus on immediately.

USER PRIORITIES (Top 2 Pillars): {[p.value if hasattr(p, 'value') else str(p) for p in top_pillars]}

VALID CANDIDATES (Choose from these IDs only):
{json.dumps(candidates_json, indent=2)}

INSTRUCTIONS:
- Select exactly 3-5 habits (prefer 5 if possible)
- Ensure a mix of pillars if possible (don't ignore the 2nd priority pillar)
- Choose habits that give quick wins/momentum
- Prefer habits that are foundational and lead to bigger goals

OUTPUT JSON (ONLY JSON, NO MARKDOWN):
{{
    "selected_node_ids": ["id1", "id2", "id3", ...],
    "onboarding_message": "A short, hype message (2-3 sentences) telling them why these habits were chosen and encouraging them to start."
}}
"""
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat_completion(messages, json_mode=True)
            
            try:
                data = json.loads(response)
                selected_ids = data.get("selected_node_ids", [])
                # Cap at 5 and filter to valid candidates
                valid_ids = [n.id for n in candidates]
                selected_ids = [sid for sid in selected_ids[:5] if sid in valid_ids]
                selected = [n for n in candidates if n.id in selected_ids]
                
                if not selected:
                    # Fallback if LLM returned invalid IDs
                    selected = candidates[:5]
                    onboarding_message = "Welcome! These are your starter habits. Let's begin your journey."
                else:
                    onboarding_message = data.get("onboarding_message", "Welcome! These are your starter habits. Let's begin your journey.")
            except json.JSONDecodeError as e:
                print(f"[Director] Failed to parse LLM response: {e}")
                print(f"[Director] Response was: {response}")
                # Fallback: take first 5 candidates
                selected = candidates[:5]
                onboarding_message = "Welcome! These are your starter habits. Let's begin your journey."
        
        return [n.id for n in selected], onboarding_message
