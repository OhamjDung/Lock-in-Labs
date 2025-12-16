from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class SkillNode(BaseModel):
    skill_name: str = Field(..., description="Name of the skill")
    parent_stat: str = Field(..., description="The core stat this skill belongs to (e.g., Intelligence, Vitality)")
    current_level: int = Field(default=1, description="Starting level of the skill")
    xp_to_next_level: int = Field(default=100, description="XP required to level up")
    linked_habits: List[str] = Field(default_factory=list, description="Daily habits associated with this skill")

class CharacterSheet(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user")
    north_star_goals: List[str] = Field(default_factory=list, description="Abstract, long-term goals (e.g., 'Change the world of AI')")
    main_quests: List[str] = Field(default_factory=list, description="Concrete, achievable milestones")
    core_stats: Dict[str, int] = Field(default_factory=lambda: {"Intelligence": 0, "Vitality": 0, "Discipline": 0}, description="Base attributes")
    debuffs: List[str] = Field(default_factory=list, description="Current obstacles or constraints")
    skill_tree: List[SkillNode] = Field(default_factory=list, description="The graph of skills and habits")

class ConversationState(BaseModel):
    missing_fields: List[str] = Field(..., description="List of fields in the CharacterSheet that still need to be populated")
    current_topic: str = Field(..., description="The specific topic the Architect is currently asking about")
    user_sentiment: str = Field(default="neutral", description="The detected emotional state of the user (e.g., engaged, bored, confused)")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="History of the chat")
