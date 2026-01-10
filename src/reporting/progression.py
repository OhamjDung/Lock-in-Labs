"""Progression engine for detecting mastery and generating level-up decisions."""

from typing import List
from datetime import datetime
from src.models import (
    CharacterSheet,
    Decision,
    DecisionType,
    ContributingFactor,
    FactorType,
    SkillTree,
    SkillNode,
    NodeStatus,
)


def check_progression(sheet: CharacterSheet, tree: SkillTree) -> List[Decision]:
    """
    Analyze the SkillTree and HabitProgress to identify specific "Level Up" opportunities.
    
    Logic:
    1. Identify Mastery Candidates: Active nodes where completed_total >= required_completions
    2. Identify Unlocks: Search the SkillTree for nodes that list the Mastery Candidate as a prerequisite
    3. Generate Decision: Create a verifiable Decision object for each unlock
    
    Args:
        sheet: CharacterSheet with habit progress
        tree: SkillTree with all nodes
        
    Returns:
        List of Decision objects representing progression opportunities
    """
    decisions = []
    
    # Map node ID to Node object for fast lookup
    node_map = {n.id: n for n in tree.nodes}
    
    # 1. Iterate Active Habits
    for node_id, progress in sheet.habit_progress.items():
        if progress.status != NodeStatus.ACTIVE:
            continue
            
        # Check Mastery Criteria
        node = node_map.get(node_id)
        if not node:
            continue
            
        # Get required completions from node (default to 30 if not set)
        required = node.required_completions if node.required_completions > 0 else 30
        
        if progress.completed_total >= required:
            # 2. Find "Next Step" (Children in the DAG)
            # Find nodes where current_node.id is in their prerequisites
            next_steps = [
                n for n in tree.nodes 
                if node_id in n.prerequisites
            ]
            
            # If no direct next step, it's a "Maintenance" decision or End of Tree
            if not next_steps:
                # Mark as mastered and continue
                progress.status = NodeStatus.MASTERED
                continue

            # 3. Create Decision Objects for each unlock
            for next_node in next_steps:
                decision = Decision(
                    id=f"prog_{node_id}_{next_node.id}_{datetime.now().isoformat()}",
                    target=node.name,  # The context is the current node
                    target_habit_id=node_id,
                    decision_type=DecisionType.INCREASE_INTENSITY,
                    old_value=node.name,
                    new_value=next_node.name,
                    explanation=f"Mastery achieved: {progress.completed_total}/{required} completions. Consistency streak: {progress.streak_days} days.",
                    confidence_score=1.0,
                    contributing_factors=[
                        ContributingFactor(
                            factor=f"Consistency Streak: {progress.streak_days} days",
                            factor_type=FactorType.DATA,
                            weight="positive",
                            description=f"Completed {progress.completed_total} sessions over time",
                            is_verified=True,  # This is verified data from our tracking
                            citation_text=f"Log count: {progress.completed_total}",
                            verification_score=1.0,
                            verification_type="data_verified"
                        )
                    ],
                    pillar=node.pillar,
                    generated_at=datetime.now().isoformat(),
                )
                decisions.append(decision)
    
    return decisions
