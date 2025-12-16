from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

class NodeType(str, Enum):
    GOAL = "Goal"
    SUB_SKILL = "Sub-Skill"
    HABIT = "Habit"

class Pillar(str, Enum):
    CAREER = "Career"
    PHYSICAL = "Physical"
    MENTAL = "Mental"
    SOCIAL = "Social"

class SkillNode(BaseModel):
    id: str = Field(..., description="Unique identifier for the node (e.g., 'skill_python')")
    name: str = Field(..., description="Display name of the skill or habit")
    type: NodeType = Field(..., description="Type of node: Goal, Sub-Skill, or Habit")
    pillar: Pillar = Field(..., description="The life pillar this belongs to")
    prerequisites: List[str] = Field(default_factory=list, description="List of Node IDs that must be completed/unlocked first")
    xp_reward: int = Field(default=100, description="XP gained upon completion")
    description: Optional[str] = Field(None, description="Short description of the node")

class SkillTree(BaseModel):
    nodes: List[SkillNode] = Field(default_factory=list, description="All nodes in the skill graph")

class CharacterSheet(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user")
    north_star_goals: List[str] = Field(default_factory=list, description="Abstract, long-term goals")
    main_quests: List[str] = Field(default_factory=list, description="Concrete, achievable milestones")
    
    # The 4 Pillars of Life
    stats_career: Dict[str, int] = Field(default_factory=lambda: {"Focus": 0, "Strategy": 0}, description="Career & Wealth stats")
    stats_physical: Dict[str, int] = Field(default_factory=lambda: {"Strength": 0, "Endurance": 0}, description="Physical Health stats")
    stats_mental: Dict[str, int] = Field(default_factory=lambda: {"Clarity": 0, "Resilience": 0}, description="Mental Health stats")
    stats_social: Dict[str, int] = Field(default_factory=lambda: {"Charisma": 0, "Empathy": 0}, description="Social Connection stats")
    
    debuffs: List[str] = Field(default_factory=list, description="Current obstacles or constraints")
    skill_tree: SkillTree = Field(default_factory=SkillTree, description="The graph of skills and habits")

class ConversationState(BaseModel):
    missing_fields: List[str] = Field(..., description="List of fields in the CharacterSheet that still need to be populated")
    current_topic: str = Field(..., description="The specific topic the Architect is currently asking about")
    user_sentiment: str = Field(default="neutral", description="The detected emotional state of the user (e.g., engaged, bored, confused)")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="History of the chat")
