"""Phase 2 Quest Extraction Test Script

Tests if the architect can extract specific quests from goals without warping the goal or being delusional.
Validates goal coverage, quest extraction accuracy, relevance checking, and duplicate detection.
"""

import sys
import os
import re
import json

# Add project root to path (go up one level from debug/ folder)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import CharacterSheet, ConversationState, Pillar, Goal
from src.onboarding.agent import ArchitectAgent, CriticAgent


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_initial_sheet():
    """Create a CharacterSheet with Phase 1 goals pre-populated."""
    sheet = CharacterSheet(user_id="test_user")
    
    # Pre-populate with the 4 goals from Phase 1
    goals = [
        Goal(
            name="Drop shipping business",
            pillars=[Pillar.CAREER],
            description="The user wants to start a drop shipping business.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Deadlift 200kg",
            pillars=[Pillar.PHYSICAL],
            description="The user wants to deadlift 200kg.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Have a lot of friend groups",
            pillars=[Pillar.SOCIAL],
            description="The user wants to have a lot of friend groups.",
            current_quests=[],
            skill_level=None
        ),
        Goal(
            name="Be calm under pressure",
            pillars=[Pillar.MENTAL],
            description="The user wants to be calm under pressure.",
            current_quests=[],
            skill_level=None
        ),
    ]
    
    sheet.goals = goals
    return sheet


def is_goal_complete_for_phase2(goal):
    """Check if a goal is complete for Phase 2 (has 2+ quests or skill_level)."""
    return len(goal.current_quests) >= 2 or goal.skill_level is not None


def get_current_pillar_for_phase2(sheet: CharacterSheet):
    """Determine which pillar to ask about next in Phase 2."""
    incomplete_pillars = set()
    for goal in sheet.goals:
        if not is_goal_complete_for_phase2(goal):
            incomplete_pillars.update(goal.pillars)
    
    for p in Pillar:
        if p in incomplete_pillars:
            return p.value
    return None


def extract_target_goal_from_architect_message(message: str, sheet: CharacterSheet) -> str:
    """Extract which goal the architect is asking about from its message."""
    if not message:
        return None
    
    # Look for patterns like "work on [goal name]" or "to work on [goal name]"
    match = re.search(r"work on ([^?\.]+)", message, re.IGNORECASE)
    if match:
        potential_goal = match.group(1).strip()
        # Check if this matches any existing goal
        for goal in sheet.goals:
            if goal.name.lower() in potential_goal.lower() or potential_goal.lower() in goal.name.lower():
                return goal.name
    
    # Also check if goal name appears directly in the message
    for goal in sheet.goals:
        if goal.name.lower() in message.lower():
            return goal.name
    
    return None


# ============================================================================
# THINKING VALIDATOR
# ============================================================================

class ThinkingValidator:
    """Validates architect thinking/reasoning output for correctness."""
    
    @staticmethod
    def validate_goal_understanding(thinking: str, expected_goal_name: str, sheet: CharacterSheet) -> tuple[bool, str]:
        """
        Validate that architect thinking shows correct understanding of the goal.
        Returns (is_valid, error_message)
        """
        if not thinking:
            return False, "No thinking output provided"
        
        thinking_lower = thinking.lower()
        expected_goal_lower = expected_goal_name.lower()
        
        # Check if the expected goal name appears in thinking (full name or substring)
        goal_mentioned = expected_goal_lower in thinking_lower
        
        # If not full name, check for meaningful words (matching post-processing logic)
        if not goal_mentioned:
            goal_words = set(expected_goal_lower.split())
            
            # Remove common words that don't add meaning
            common_words = {"a", "an", "the", "of", "to", "for", "in", "on", "at", "by", "lot"}
            goal_words_meaningful = {w for w in goal_words if w not in common_words}
            
            # If no meaningful words (all were common), use all words
            if not goal_words_meaningful:
                goal_words_meaningful = goal_words
            
            thinking_words = set(thinking_lower.split())
            
            # Check if meaningful words appear together
            if goal_words_meaningful:
                meaningful_intersection = goal_words_meaningful & thinking_words
                # Check if meaningful words appear - for multi-word goals, require at least 2 words or 60% match
                # For "Have a lot of friend groups" (3 meaningful words), require at least 2 words
                if len(goal_words_meaningful) >= 3:
                    min_words_needed = 2  # At least 2 out of 3+ words
                elif len(goal_words_meaningful) == 2:
                    min_words_needed = 2  # Both words required
                else:
                    min_words_needed = 1  # Single word required
                if len(meaningful_intersection) >= min_words_needed:
                    goal_mentioned = True
                # Also check for key phrase patterns (e.g., "friend groups" for "Have a lot of friend groups")
                elif len(goal_words_meaningful) >= 2:
                    meaningful_words_list = sorted(goal_words_meaningful, key=lambda x: expected_goal_lower.find(x))
                    if len(meaningful_words_list) >= 2:
                        # Check if last two meaningful words appear together
                        last_two = " ".join(meaningful_words_list[-2:])
                        if last_two in thinking_lower:
                            goal_mentioned = True
                        # Also check if any two meaningful words appear together
                        for i in range(len(meaningful_words_list) - 1):
                            pair = f"{meaningful_words_list[i]} {meaningful_words_list[i+1]}"
                            if pair in thinking_lower:
                                goal_mentioned = True
                                break
        
        if not goal_mentioned:
            return False, f"Thinking does not mention expected goal '{expected_goal_name}'"
        
        # Check for confusion - should not mention wrong goals prominently without mentioning correct one
        for goal in sheet.goals:
            if goal.name != expected_goal_name:
                # If another goal is mentioned prominently, that might be confusion
                other_goal_lower = goal.name.lower()
                if other_goal_lower in thinking_lower and expected_goal_lower not in thinking_lower:
                    # But only flag as confusion if the wrong goal name is mentioned fully
                    # (not just partial matches)
                    return False, f"Thinking mentions wrong goal '{goal.name}' instead of '{expected_goal_name}'"
        
        return True, ""
    
    @staticmethod
    def validate_quest_count_understanding(thinking: str, expected_quest_count: int, goal_name: str) -> tuple[bool, str]:
        """
        Validate that architect thinking shows correct understanding of quest count.
        Returns (is_valid, error_message)
        """
        if not thinking:
            return False, "No thinking output provided"
        
        thinking_lower = thinking.lower()
        
        # Check if quest count is mentioned (e.g., "1/2", "0/2", "2 quests", etc.)
        quest_count_patterns = [
            rf"{expected_quest_count}/2",
            rf"{expected_quest_count} quest",
            rf"quest.*{expected_quest_count}",
        ]
        
        found_count = False
        for pattern in quest_count_patterns:
            if re.search(pattern, thinking_lower):
                found_count = True
                break
        
        # Also check for qualitative understanding
        if expected_quest_count == 0:
            if "no quest" in thinking_lower or "0 quest" in thinking_lower or "no activit" in thinking_lower:
                found_count = True
        elif expected_quest_count == 1:
            if "one quest" in thinking_lower or "single quest" in thinking_lower or "only one" in thinking_lower:
                found_count = True
        
        if not found_count:
            return False, f"Thinking does not show understanding of quest count ({expected_quest_count}/2) for '{goal_name}'"
        
        return True, ""
    
    @staticmethod
    def validate_state_tracking(thinking: str, sheet: CharacterSheet) -> tuple[bool, str]:
        """
        Validate that architect thinking shows correct state tracking.
        Returns (is_valid, error_message)
        """
        if not thinking:
            return False, "No thinking output provided"
        
        thinking_lower = thinking.lower()
        
        # Check that thinking shows awareness of which goals are complete/incomplete
        # This is a softer check - just verify it's not completely confused
        
        # Should not show confusion about goal names
        goal_names = [g.name.lower() for g in sheet.goals]
        mentioned_goals = [name for name in goal_names if name in thinking_lower]
        
        if len(mentioned_goals) > 3:  # Might be confusing multiple goals
            return False, "Thinking shows confusion - mentions too many goals at once"
        
        return True, ""
    
    @staticmethod
    def validate_skill_level_reasoning(thinking: str, should_ask_skill: bool, goal_name: str) -> tuple[bool, str]:
        """
        Validate that architect thinking shows correct reasoning about skill level.
        Returns (is_valid, error_message)
        """
        if not thinking:
            return False, "No thinking output provided"
        
        thinking_lower = thinking.lower()
        
        if should_ask_skill:
            # Should mention skill level, no activities, or similar reasoning
            skill_indicators = ["skill", "level", "no activit", "don't do", "doesn't do", "no quest"]
            if not any(indicator in thinking_lower for indicator in skill_indicators):
                return False, f"Thinking should mention skill level reasoning for '{goal_name}' but doesn't"
        else:
            # Should NOT ask for skill level yet
            if "skill level" in thinking_lower and "no activit" not in thinking_lower:
                # This might be okay if it's just acknowledging, but check context
                pass
        
        return True, ""


# ============================================================================
# ASSERTION FUNCTIONS
# ============================================================================

class TestAssertions:
    """Collection of assertion functions for testing."""
    
    @staticmethod
    def assert_all_goals_asked(goals_asked: list[str], sheet: CharacterSheet) -> tuple[bool, str]:
        """Assert that all goals were asked about."""
        expected_goals = {g.name for g in sheet.goals}
        asked_goals = set(goals_asked)
        
        if expected_goals != asked_goals:
            missing = expected_goals - asked_goals
            extra = asked_goals - expected_goals
            error = []
            if missing:
                error.append(f"Missing goals: {missing}")
            if extra:
                error.append(f"Extra goals asked: {extra}")
            return False, "; ".join(error)
        
        return True, ""
    
    @staticmethod
    def assert_no_goals_skipped(goals_asked: list[str], sheet: CharacterSheet) -> tuple[bool, str]:
        """Assert that no goals were skipped."""
        expected_goals = {g.name for g in sheet.goals}
        asked_goals = set(goals_asked)
        
        if expected_goals - asked_goals:
            missing = expected_goals - asked_goals
            return False, f"Skipped goals: {missing}"
        
        return True, ""
    
    @staticmethod
    def assert_no_goals_asked_twice(goals_asked: list[str]) -> tuple[bool, str]:
        """Assert that no goal was asked about twice."""
        seen = set()
        duplicates = []
        for goal in goals_asked:
            if goal in seen:
                duplicates.append(goal)
            seen.add(goal)
        
        if duplicates:
            return False, f"Goals asked twice: {duplicates}"
        
        return True, ""
    
    @staticmethod
    def assert_no_hallucinated_goals(initial_goal_count: int, current_goal_count: int, initial_goal_names: set[str], current_goal_names: set[str]) -> tuple[bool, str]:
        """Assert that no new goals were hallucinated."""
        if current_goal_count > initial_goal_count:
            new_goals = current_goal_names - initial_goal_names
            return False, f"Hallucinated new goals: {new_goals}"
        
        return True, ""
    
    @staticmethod
    def assert_no_duplicate_goals(sheet: CharacterSheet) -> tuple[bool, str]:
        """Assert that no duplicate goals exist."""
        goal_names = [g.name.lower() for g in sheet.goals]
        seen = set()
        duplicates = []
        for name in goal_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        
        if duplicates:
            return False, f"Duplicate goals found: {duplicates}"
        
        return True, ""
    
    @staticmethod
    def assert_quests_extracted_accurately(goal: Goal, expected_quests: list[str]) -> tuple[bool, str]:
        """Assert that quests were extracted accurately."""
        if len(goal.current_quests) != len(expected_quests):
            return False, f"Quest count mismatch: expected {len(expected_quests)}, got {len(goal.current_quests)}"
        
        # Check if quests match (allowing for minor variations)
        for expected_quest in expected_quests:
            found = False
            expected_lower = expected_quest.lower()
            for actual_quest in goal.current_quests:
                actual_lower = actual_quest.lower()
                # Check if key words match
                expected_words = set(expected_lower.split())
                actual_words = set(actual_lower.split())
                # Remove common words
                common_words = {"a", "an", "the", "to", "i", "do", "go", "am"}
                expected_words = expected_words - common_words
                actual_words = actual_words - common_words
                if expected_words & actual_words:  # Intersection
                    found = True
                    break
            
            if not found:
                return False, f"Missing expected quest: '{expected_quest}'"
        
        return True, ""
    
    @staticmethod
    def assert_no_hallucinated_quests(goal: Goal, user_input: str) -> tuple[bool, str]:
        """Assert that no quests were hallucinated (not mentioned by user)."""
        user_lower = user_input.lower()
        
        for quest in goal.current_quests:
            quest_lower = quest.lower()
            # Check if key words from quest appear in user input
            quest_words = set(quest_lower.split())
            user_words = set(user_lower.split())
            # Remove common words
            common_words = {"a", "an", "the", "to", "i", "do", "go", "am", "the", "and", "or"}
            quest_words = quest_words - common_words
            user_words = user_words - common_words
            
            if not (quest_words & user_words):  # No intersection
                return False, f"Hallucinated quest: '{quest}' (not mentioned in user input)"
        
        return True, ""
    
    @staticmethod
    def assert_followup_when_insufficient_quests(architect_response: str, quest_count: int) -> tuple[bool, str]:
        """Assert that architect asks for more quests when user provides < 2."""
        if quest_count >= 2:
            return True, ""  # Not applicable
        
        # Check if architect asks for more
        response_lower = architect_response.lower()
        followup_indicators = [
            "more", "else", "anything else", "other", "additional", "another"
        ]
        
        if not any(indicator in response_lower for indicator in followup_indicators):
            return False, "Architect did not ask for more quests when user provided < 2"
        
        return True, ""
    
    @staticmethod
    def assert_skill_level_requested(architect_response: str, user_confirmed_only_one: bool) -> tuple[bool, str]:
        """Assert that architect asks for skill level when user confirms they only do 1 quest."""
        if not user_confirmed_only_one:
            return True, ""  # Not applicable
        
        response_lower = architect_response.lower()
        skill_indicators = [
            "skill", "level", "rate", "scale", "1-10", "1 to 10", "out of 10"
        ]
        
        if not any(indicator in response_lower for indicator in skill_indicators):
            return False, "Architect did not ask for skill level when user confirmed only 1 quest"
        
        return True, ""
    
    @staticmethod
    def assert_correct_order(question_sequence: list[str]) -> tuple[bool, str]:
        """Assert that questions follow correct order."""
        # Expected order: ask for quests → ask more if missing → confirm if only 1 → ask skill level
        # This is a simplified check - we'll track the sequence in the test
        
        # Check that "ask for quests" comes before "ask for skill level"
        quest_asked = False
        skill_asked = False
        
        for question in question_sequence:
            question_lower = question.lower()
            if "work on" in question_lower or "currently doing" in question_lower:
                quest_asked = True
            if "skill" in question_lower or "level" in question_lower:
                skill_asked = True
                if not quest_asked:
                    return False, "Skill level asked before quests were asked"
        
        return True, ""
    
    @staticmethod
    def assert_relevance_detected(architect_response: str, wrong_goal_mentioned: bool) -> tuple[bool, str]:
        """Assert that architect detects when user provides quest for wrong goal."""
        if not wrong_goal_mentioned:
            return True, ""  # Not applicable
        
        response_lower = architect_response.lower()
        relevance_indicators = [
            "different", "wrong", "not related", "unrelated", "that's for", "that's about",
            "did you mean", "are you sure", "clarify", "confused"
        ]
        
        if not any(indicator in response_lower for indicator in relevance_indicators):
            return False, "Architect did not detect quest relevance mismatch"
        
        return True, ""
    
    @staticmethod
    def assert_duplicate_detected(architect_response: str, duplicate_quests_provided: bool) -> tuple[bool, str]:
        """Assert that architect detects duplicate/similar quests."""
        if not duplicate_quests_provided:
            return True, ""  # Not applicable
        
        response_lower = architect_response.lower()
        duplicate_indicators = [
            "similar", "duplicate", "same", "merge", "combine", "alike"
        ]
        
        if not any(indicator in response_lower for indicator in duplicate_indicators):
            return False, "Architect did not detect duplicate/similar quests"
        
        return True, ""
    
    @staticmethod
    def assert_merge_question_asked(architect_response: str, duplicate_quests_provided: bool) -> tuple[bool, str]:
        """Assert that architect asks to merge duplicate quests."""
        if not duplicate_quests_provided:
            return True, ""  # Not applicable
        
        response_lower = architect_response.lower()
        merge_indicators = [
            "merge", "combine", "want to merge", "merge them"
        ]
        
        if not any(indicator in response_lower for indicator in merge_indicators):
            return False, "Architect did not ask to merge duplicate quests"
        
        return True, ""


# ============================================================================
# TEST CASES
# ============================================================================

class Phase2TestRunner:
    """Runs Phase 2 quest extraction tests."""
    
    def __init__(self):
        self.architect = ArchitectAgent()
        self.critic = CriticAgent()
        self.validator = ThinkingValidator()
        self.assertions = TestAssertions()
        self.results = {}
    
    def run_test_1(self) -> dict:
        """TEST 1: Basic Goal Functionality"""
        print("\n" + "=" * 70)
        print("TEST 1: Basic Goal Functionality")
        print("=" * 70)
        
        sheet = create_initial_sheet()
        state = ConversationState(
            missing_fields=["current_quests"],
            current_topic="Current Quests",
            phase="phase2",
        )
        
        initial_goal_count = len(sheet.goals)
        initial_goal_names = {g.name for g in sheet.goals}
        
        goal_state_tracker = {}
        for goal in sheet.goals:
            goal_state_tracker[goal.name] = {
                "asked_about_activities": False,
                "asked_about_skill": False,
                "last_question_was": None,
                "last_response_indicated_no_activities": False
            }
        
        goals_asked = []
        thinking_records = []
        all_goals_complete = False
        max_iterations = 30  # Safety limit (increased for follow-up questions and all 4 goals)
        iteration = 0
        goal_interaction_count = {}  # Track how many times we've interacted with each goal
        
        # Predefined user responses for each goal
        user_responses = {
            "Drop shipping business": "I'm currently researching products and setting up my Shopify store",
            "Deadlift 200kg": "I go to the gym 3 times a week and do deadlift training",
            "Have a lot of friend groups": "I attend social events and join new clubs regularly",
            "Be calm under pressure": "I practice breathing exercises and meditation daily"
        }
        
        # Follow-up responses when architect asks for more quests
        followup_responses = {
            "Drop shipping business": "That's all I'm doing right now",
            "Deadlift 200kg": "That's all I do for that",
            "Have a lot of friend groups": "That's everything",
            "Be calm under pressure": "That's all"
        }
        
        while not all_goals_complete and iteration < max_iterations:
            iteration += 1
            
            # Get current pillar
            current_pillar = get_current_pillar_for_phase2(sheet)
            
            # Generate architect response
            arch_response, arch_thinking = self.architect.generate_response(
                history=state.conversation_history,
                current_sheet=sheet,
                feedback=feedback if 'feedback' in locals() else "",
                phase="phase2",
                pending_debuffs=pending_debuffs if 'pending_debuffs' in locals() else [],
                current_pillar=current_pillar,
                goal_state_tracker=goal_state_tracker,
                should_ask_skill_level=False,
                target_goal_name=None,
            )
            
            # Extract which goal is being asked about
            target_goal_name = extract_target_goal_from_architect_message(arch_response, sheet)
            
            if not target_goal_name:
                # Try to find incomplete goal
                for goal in sheet.goals:
                    if not is_goal_complete_for_phase2(goal):
                        target_goal_name = goal.name
                        break
            
            if not target_goal_name:
                all_goals_complete = True
                break
            
            # Track interactions per goal to prevent infinite loops
            goal_interaction_count[target_goal_name] = goal_interaction_count.get(target_goal_name, 0) + 1
            if goal_interaction_count[target_goal_name] > 5:  # Max 5 interactions per goal
                print(f"[TEST] Warning: Too many interactions with goal '{target_goal_name}', skipping")
                # Mark goal as complete to move on
                goal = next((g for g in sheet.goals if g.name == target_goal_name), None)
                if goal and len(goal.current_quests) == 1:
                    goal.skill_level = 5  # Default skill level to complete the goal
                continue
            
            # Record goal being asked about (only first time)
            if target_goal_name not in goals_asked:
                goals_asked.append(target_goal_name)
            
            # Extract actual goal name from thinking or response (more reliable than extraction function)
            actual_goal_name = target_goal_name  # Default to extracted name
            if arch_thinking:
                # Try to find goal name in thinking
                for goal in sheet.goals:
                    if goal.name.lower() in arch_thinking.lower():
                        actual_goal_name = goal.name
                        break
            elif arch_response:
                # Fallback to response if thinking not available
                for goal in sheet.goals:
                    if goal.name.lower() in arch_response.lower():
                        actual_goal_name = goal.name
                        break
            
            # Record thinking with actual goal name
            thinking_records.append({
                "goal": actual_goal_name,
                "thinking": arch_thinking,
                "response": arch_response
            })
            
            # Add architect response to history
            state.conversation_history.append({"role": "assistant", "content": arch_response})
            
            # Get user response - check if this is a follow-up question
            goal = next((g for g in sheet.goals if g.name == target_goal_name), None)
            is_followup = goal and len(goal.current_quests) == 1 and goal_state_tracker.get(target_goal_name, {}).get("asked_about_activities", False)
            
            if is_followup and "more" in arch_response.lower():
                # Architect is asking for more quests
                user_response = followup_responses.get(target_goal_name, "That's all I do")
            elif "skill" in arch_response.lower() or "level" in arch_response.lower():
                # Architect is asking for skill level
                user_response = "5"  # Default skill level
            else:
                # Initial question
                user_response = user_responses.get(target_goal_name, "I don't do anything for that currently")
            
            state.conversation_history.append({"role": "user", "content": user_response})
            
            # Analyze with Critic
            sheet, feedback, analysis_json, pending_debuffs = self.critic.analyze(
                user_response,
                sheet,
                state.conversation_history,
                state.phase,
                target_goal_name=target_goal_name
            )
            
            # Update goal state tracker
            if target_goal_name in goal_state_tracker:
                goal = next((g for g in sheet.goals if g.name == target_goal_name), None)
                if goal:
                    # Mark as asked about activities immediately after user responds (regardless of quest count)
                    if not goal_state_tracker[target_goal_name]["asked_about_activities"]:
                        goal_state_tracker[target_goal_name]["asked_about_activities"] = True
                    
                    # Update quest count status
                    if len(goal.current_quests) >= 2:
                        # Goal is complete with 2+ quests
                        pass
                    elif len(goal.current_quests) == 1:
                        # Check if user confirmed that's all
                        if "that's all" in user_response.lower() or "that's everything" in user_response.lower() or "that's it" in user_response.lower():
                            goal_state_tracker[target_goal_name]["last_response_indicated_no_activities"] = True
                    elif len(goal.current_quests) == 0:
                        # User said they don't do anything
                        goal_state_tracker[target_goal_name]["last_response_indicated_no_activities"] = True
                    
                    # Check if skill level was set
                    if goal.skill_level is not None:
                        goal_state_tracker[target_goal_name]["asked_about_skill"] = True
            
            # Check if all goals are complete
            all_goals_complete = all(is_goal_complete_for_phase2(g) for g in sheet.goals)
        
        # Run assertions
        results = {}
        
        # Check all goals asked
        passed, error = self.assertions.assert_all_goals_asked(goals_asked, sheet)
        results["all_goals_asked"] = {"passed": passed, "error": error}
        
        # Check no goals skipped
        passed, error = self.assertions.assert_no_goals_skipped(goals_asked, sheet)
        results["no_goals_skipped"] = {"passed": passed, "error": error}
        
        # Check no goals asked twice
        passed, error = self.assertions.assert_no_goals_asked_twice(goals_asked)
        results["no_goals_asked_twice"] = {"passed": passed, "error": error}
        
        # Check no hallucinated goals
        current_goal_names = {g.name for g in sheet.goals}
        passed, error = self.assertions.assert_no_hallucinated_goals(
            initial_goal_count, len(sheet.goals), initial_goal_names, current_goal_names
        )
        results["no_hallucinated_goals"] = {"passed": passed, "error": error}
        
        # Check no duplicate goals
        passed, error = self.assertions.assert_no_duplicate_goals(sheet)
        results["no_duplicate_goals"] = {"passed": passed, "error": error}
        
        # Check quests extracted accurately
        all_quests_accurate = True
        quest_errors = []
        for goal_name, expected_response in user_responses.items():
            goal = next((g for g in sheet.goals if g.name == goal_name), None)
            if goal:
                # Extract expected quests from user response (simplified)
                expected_quests = []
                if "researching products" in expected_response.lower() or "shopify" in expected_response.lower():
                    expected_quests = ["researching products", "setting up Shopify store"]
                elif "gym" in expected_response.lower() or "deadlift" in expected_response.lower():
                    expected_quests = ["going to gym", "deadlift training"]
                elif "social events" in expected_response.lower() or "clubs" in expected_response.lower():
                    expected_quests = ["attending social events", "joining new clubs"]
                elif "breathing" in expected_response.lower() or "meditation" in expected_response.lower():
                    expected_quests = ["breathing exercises", "meditation"]
                
                if expected_quests:
                    passed, error = self.assertions.assert_quests_extracted_accurately(goal, expected_quests)
                    if not passed:
                        all_quests_accurate = False
                        quest_errors.append(f"{goal_name}: {error}")
        
        results["quests_extracted_accurately"] = {
            "passed": all_quests_accurate,
            "error": "; ".join(quest_errors) if quest_errors else ""
        }
        
        # Check thinking shows correct understanding
        thinking_valid = True
        thinking_errors = []
        for record in thinking_records:
            goal_name = record["goal"]
            thinking = record.get("thinking") or ""  # Handle None thinking
            goal = next((g for g in sheet.goals if g.name == goal_name), None)
            if goal:
                passed, error = self.validator.validate_goal_understanding(thinking, goal_name, sheet)
                if not passed:
                    thinking_valid = False
                    # Add actual thinking content to error for debugging
                    thinking_preview = thinking[:150] + "..." if len(thinking) > 150 else thinking
                    thinking_errors.append(f"{goal_name}: {error} (Actual thinking: '{thinking_preview}')")
                    print(f"[TEST DEBUG] Thinking validation failed for '{goal_name}':")
                    print(f"  Thinking content: {thinking[:300]}...")
                    print(f"  Error: {error}")
        
        results["thinking_shows_correct_understanding"] = {
            "passed": thinking_valid,
            "error": "; ".join(thinking_errors) if thinking_errors else ""
        }
        
        # Check reasoning matches behavior
        reasoning_valid = True
        reasoning_errors = []
        for record in thinking_records:
            goal_name = record["goal"]
            thinking = record.get("thinking") or ""  # Handle None thinking
            response = record.get("response") or ""  # Handle None response
            goal = next((g for g in sheet.goals if g.name == goal_name), None)
            if goal:
                # Check if thinking mentions the goal that's being asked about
                if goal_name.lower() not in thinking.lower() and goal_name.lower() not in response.lower():
                    reasoning_valid = False
                    reasoning_errors.append(f"{goal_name}: Thinking/response doesn't match goal being asked about")
        
        results["reasoning_matches_behavior"] = {
            "passed": reasoning_valid,
            "error": "; ".join(reasoning_errors) if reasoning_errors else ""
        }
        
        return results
    
    def run_test_2(self) -> dict:
        """TEST 2: Basic Current Quest Functionality"""
        print("\n" + "=" * 70)
        print("TEST 2: Basic Current Quest Functionality")
        print("=" * 70)
        
        sheet = create_initial_sheet()
        state = ConversationState(
            missing_fields=["current_quests"],
            current_topic="Current Quests",
            phase="phase2",
        )
        
        goal_state_tracker = {}
        for goal in sheet.goals:
            goal_state_tracker[goal.name] = {
                "asked_about_activities": False,
                "asked_about_skill": False,
                "last_question_was": None,
                "last_response_indicated_no_activities": False
            }
        
        # Test with first goal - user provides only 1 quest
        test_goal = sheet.goals[0]  # "Drop shipping business"
        question_sequence = []
        thinking_records = []
        
        # Step 1: Architect asks about quests
        current_pillar = get_current_pillar_for_phase2(sheet)
        arch_response, arch_thinking = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback="",
            phase="phase2",
            pending_debuffs=[],
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name,
        )
        
        question_sequence.append(arch_response)
        thinking_records.append({
            "step": "initial_question",
            "thinking": arch_thinking,
            "response": arch_response,
            "quest_count": 0
        })
        state.conversation_history.append({"role": "assistant", "content": arch_response})
        
        # Step 2: User provides only 1 quest
        user_response_1 = "I'm currently researching products for my drop shipping business"
        state.conversation_history.append({"role": "user", "content": user_response_1})
        
        sheet, feedback, analysis_json, pending_debuffs = self.critic.analyze(
            user_response_1,
            sheet,
            state.conversation_history,
            state.phase,
            target_goal_name=test_goal.name
        )
        
        # Update goal
        test_goal = next((g for g in sheet.goals if g.name == test_goal.name), None)
        quest_count_after_first = len(test_goal.current_quests) if test_goal else 0
        
        # Update goal state tracker after user provides quest
        if test_goal and test_goal.name in goal_state_tracker:
            goal_state_tracker[test_goal.name]["asked_about_activities"] = True
            # Don't set no_activities=True yet - user provided a quest, so they have activities
            goal_state_tracker[test_goal.name]["last_response_indicated_no_activities"] = False
            print(f"[TEST DEBUG] Updated goal_state_tracker for '{test_goal.name}': asked_about_activities=True, quest_count={quest_count_after_first}")
        
        # Step 3: Architect should ask for more quests
        current_pillar = get_current_pillar_for_phase2(sheet)
        arch_response_2, arch_thinking_2 = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback=feedback,
            phase="phase2",
            pending_debuffs=pending_debuffs,
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        question_sequence.append(arch_response_2)
        # Debug: print actual response
        print(f"[TEST DEBUG] Step 3 - Followup question response (FULL): '{arch_response_2}'")
        print(f"[TEST DEBUG] Step 3 - Followup question thinking (FULL): '{arch_thinking_2 if arch_thinking_2 else 'None'}'")
        print(f"[TEST DEBUG] Step 3 - quest_count_after_first: {quest_count_after_first}")
        thinking_records.append({
            "step": "followup_question",
            "thinking": arch_thinking_2,
            "response": arch_response_2,
            "quest_count": quest_count_after_first
        })
        state.conversation_history.append({"role": "assistant", "content": arch_response_2})
        
        # Step 4: User confirms that's all they do
        user_response_2 = "That's all I do for that, I'm just starting out"
        state.conversation_history.append({"role": "user", "content": user_response_2})
        
        sheet, feedback_2, analysis_json_2, pending_debuffs_2 = self.critic.analyze(
            user_response_2,
            sheet,
            state.conversation_history,
            state.phase,
            target_goal_name=test_goal.name if test_goal else None
        )
        
        # Update goal state tracker
        if test_goal and test_goal.name in goal_state_tracker:
            goal_state_tracker[test_goal.name]["last_response_indicated_no_activities"] = True
            goal_state_tracker[test_goal.name]["asked_about_activities"] = True
        
        # Step 5: Architect should ask for skill level
        current_pillar = get_current_pillar_for_phase2(sheet)
        arch_response_3, arch_thinking_3 = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback=feedback_2,
            phase="phase2",
            pending_debuffs=pending_debuffs_2,
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=True,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        question_sequence.append(arch_response_3)
        thinking_records.append({
            "step": "skill_level_question",
            "thinking": arch_thinking_3,
            "response": arch_response_3,
            "quest_count": quest_count_after_first
        })
        
        # Step 6: User provides skill level
        user_response_3 = "3"
        state.conversation_history.append({"role": "user", "content": user_response_3})
        
        sheet, feedback_3, analysis_json_3, pending_debuffs_3 = self.critic.analyze(
            user_response_3,
            sheet,
            state.conversation_history,
            state.phase,
            target_goal_name=test_goal.name if test_goal else None
        )
        
        # Update test_goal reference
        test_goal = next((g for g in sheet.goals if g.name == test_goal.name), None) if test_goal else None
        
        # Run assertions
        results = {}
        
        # Check no hallucinated quests
        if test_goal:
            passed, error = self.assertions.assert_no_hallucinated_quests(test_goal, user_response_1)
            results["no_hallucinated_quests"] = {"passed": passed, "error": error}
        else:
            results["no_hallucinated_quests"] = {"passed": False, "error": "Test goal not found"}
        
        # Check follow-up when < 2 quests
        passed, error = self.assertions.assert_followup_when_insufficient_quests(arch_response_2, quest_count_after_first)
        results["followup_when_insufficient_quests"] = {"passed": passed, "error": error}
        
        # Check skill level requested
        passed, error = self.assertions.assert_skill_level_requested(arch_response_3, True)
        results["skill_level_requested"] = {"passed": passed, "error": error}
        
        # Check correct order
        passed, error = self.assertions.assert_correct_order(question_sequence)
        results["correct_order"] = {"passed": passed, "error": error}
        
        # Check thinking shows correct reasoning
        thinking_valid = True
        thinking_errors = []
        for record in thinking_records:
            thinking = record.get("thinking") or ""  # Handle None thinking
            quest_count = record.get("quest_count", 0)
            step = record.get("step", "")
            
            if step == "followup_question":
                passed, error = self.validator.validate_quest_count_understanding(thinking, quest_count, test_goal.name if test_goal else "")
                if not passed:
                    thinking_valid = False
                    thinking_errors.append(f"{step}: {error}")
            elif step == "skill_level_question":
                passed, error = self.validator.validate_skill_level_reasoning(thinking, True, test_goal.name if test_goal else "")
                if not passed:
                    thinking_valid = False
                    thinking_errors.append(f"{step}: {error}")
        
        results["thinking_shows_correct_reasoning"] = {
            "passed": thinking_valid,
            "error": "; ".join(thinking_errors) if thinking_errors else ""
        }
        
        # Check reasoning matches behavior
        reasoning_valid = True
        reasoning_errors = []
        for record in thinking_records:
            thinking = record.get("thinking") or ""  # Handle None thinking
            response = record.get("response") or ""  # Handle None response
            step = record.get("step", "")
            
            # Check if thinking aligns with what architect is asking
            if step == "followup_question":
                # Check for various ways of asking for more quests
                followup_indicators = ["more", "anything else", "do you do anything else", "is there anything else", "else", "other", "additional"]
                response_lower = response.lower()
                thinking_lower = thinking.lower()
                has_followup = any(indicator in response_lower or indicator in thinking_lower for indicator in followup_indicators)
                if not has_followup:
                    reasoning_valid = False
                    reasoning_errors.append(f"{step}: Should ask for more but doesn't (response: '{response[:100]}...')")
            elif step == "skill_level_question":
                # Check for various ways of asking for skill level
                skill_indicators = ["skill", "level", "rate", "scale", "1-10", "1 to 10", "out of 10", "how would you rate"]
                response_lower = response.lower()
                thinking_lower = thinking.lower()
                has_skill_question = any(indicator in response_lower or indicator in thinking_lower for indicator in skill_indicators)
                if not has_skill_question:
                    reasoning_valid = False
                    reasoning_errors.append(f"{step}: Should ask for skill level but doesn't (response: '{response[:100]}...')")
        
        results["reasoning_matches_behavior"] = {
            "passed": reasoning_valid,
            "error": "; ".join(reasoning_errors) if reasoning_errors else ""
        }
        
        # Check skill level stored correctly
        if test_goal and test_goal.skill_level == 3:
            results["skill_level_stored"] = {"passed": True, "error": ""}
        else:
            actual_level = test_goal.skill_level if test_goal else None
            results["skill_level_stored"] = {
                "passed": False,
                "error": f"Expected skill level 3, got {actual_level}"
            }
        
        return results
    
    def run_test_3(self) -> dict:
        """TEST 3: Relevance Check"""
        print("\n" + "=" * 70)
        print("TEST 3: Relevance Check")
        print("=" * 70)
        
        sheet = create_initial_sheet()
        state = ConversationState(
            missing_fields=["current_quests"],
            current_topic="Current Quests",
            phase="phase2",
        )
        
        goal_state_tracker = {}
        for goal in sheet.goals:
            goal_state_tracker[goal.name] = {
                "asked_about_activities": False,
                "asked_about_skill": False,
                "last_question_was": None,
                "last_response_indicated_no_activities": False
            }
        
        # Architect asks about "Drop shipping business" (Career)
        test_goal = next((g for g in sheet.goals if g.name == "Drop shipping business"), None)
        current_pillar = get_current_pillar_for_phase2(sheet)
        
        arch_response, arch_thinking = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback="",
            phase="phase2",
            pending_debuffs=[],
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        state.conversation_history.append({"role": "assistant", "content": arch_response})
        
        # User responds with quest for wrong goal - "Deadlift 200kg" (Physical)
        user_response = "I go to the gym 3 times a week"
        state.conversation_history.append({"role": "user", "content": user_response})
        
        # Analyze with Critic
        sheet, feedback, analysis_json, pending_debuffs = self.critic.analyze(
            user_response,
            sheet,
            state.conversation_history,
            state.phase,
            target_goal_name=test_goal.name if test_goal else None
        )
        
        # Architect should detect mismatch and ask for clarification
        current_pillar = get_current_pillar_for_phase2(sheet)
        arch_response_2, arch_thinking_2 = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback=feedback,
            phase="phase2",
            pending_debuffs=pending_debuffs,
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        # Run assertions
        results = {}
        
        # Check relevance detected
        passed, error = self.assertions.assert_relevance_detected(arch_response_2, True)
        results["relevance_detected"] = {"passed": passed, "error": error}
        
        # Check clarification requested
        response_lower = arch_response_2.lower()
        clarification_indicators = ["clarify", "confused", "different", "wrong", "not related", "that's for"]
        clarification_requested = any(indicator in response_lower for indicator in clarification_indicators)
        results["clarification_requested"] = {
            "passed": clarification_requested,
            "error": "Architect did not request clarification" if not clarification_requested else ""
        }
        
        return results
    
    def run_test_4(self) -> dict:
        """TEST 4: Duplicate Quest Detection"""
        print("\n" + "=" * 70)
        print("TEST 4: Duplicate Quest Detection")
        print("=" * 70)
        
        sheet = create_initial_sheet()
        state = ConversationState(
            missing_fields=["current_quests"],
            current_topic="Current Quests",
            phase="phase2",
        )
        
        goal_state_tracker = {}
        for goal in sheet.goals:
            goal_state_tracker[goal.name] = {
                "asked_about_activities": False,
                "asked_about_skill": False,
                "last_question_was": None,
                "last_response_indicated_no_activities": False
            }
        
        # Architect asks about "Deadlift 200kg" (Physical)
        test_goal = next((g for g in sheet.goals if g.name == "Deadlift 200kg"), None)
        current_pillar = get_current_pillar_for_phase2(sheet)
        
        arch_response, arch_thinking = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback="",
            phase="phase2",
            pending_debuffs=[],
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        state.conversation_history.append({"role": "assistant", "content": arch_response})
        
        # User provides two similar quests
        user_response = "I go to the gym regularly and I work out at the gym 3 times a week"
        state.conversation_history.append({"role": "user", "content": user_response})
        
        # Analyze with Critic
        sheet, feedback, analysis_json, pending_debuffs = self.critic.analyze(
            user_response,
            sheet,
            state.conversation_history,
            state.phase,
            target_goal_name=test_goal.name if test_goal else None
        )
        
        # Architect should detect duplicates and ask to merge
        current_pillar = get_current_pillar_for_phase2(sheet)
        arch_response_2, arch_thinking_2 = self.architect.generate_response(
            history=state.conversation_history,
            current_sheet=sheet,
            feedback=feedback,
            phase="phase2",
            pending_debuffs=pending_debuffs,
            current_pillar=current_pillar,
            goal_state_tracker=goal_state_tracker,
            should_ask_skill_level=False,
            target_goal_name=test_goal.name if test_goal else None,
        )
        
        # Run assertions
        results = {}
        
        # Check duplicates detected
        passed, error = self.assertions.assert_duplicate_detected(arch_response_2, True)
        results["duplicates_detected"] = {"passed": passed, "error": error}
        
        # Check merge question asked
        passed, error = self.assertions.assert_merge_question_asked(arch_response_2, True)
        results["merge_question_asked"] = {"passed": passed, "error": error}
        
        return results
    
    def run_all_tests(self):
        """Run all tests and generate report."""
        print("\n" + "=" * 70)
        print("PHASE 2 QUEST EXTRACTION TEST SUITE")
        print("=" * 70)
        
        # Run all tests
        self.results["test_1"] = self.run_test_1()
        self.results["test_2"] = self.run_test_2()
        self.results["test_3"] = self.run_test_3()
        self.results["test_4"] = self.run_test_4()
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate summary pass/fail report."""
        print("\n" + "=" * 70)
        print("TEST RESULTS SUMMARY")
        print("=" * 70)
        
        test_names = {
            "test_1": "TEST 1: Basic Goal Functionality",
            "test_2": "TEST 2: Basic Current Quest Functionality",
            "test_3": "TEST 3: Relevance Check",
            "test_4": "TEST 4: Duplicate Quest Detection"
        }
        
        all_passed = True
        
        for test_key, test_name in test_names.items():
            print(f"\n{test_name}")
            print("-" * 70)
            
            if test_key not in self.results:
                print("  [FAIL] Test not run")
                all_passed = False
                continue
            
            test_results = self.results[test_key]
            test_passed = True
            
            for check_name, result in test_results.items():
                passed = result["passed"]
                error = result.get("error", "")
                
                status = "[PASS]" if passed else "[FAIL]"
                check_display = check_name.replace("_", " ").title()
                print(f"  {status} {check_display}: {'PASS' if passed else 'FAIL'}")
                
                if not passed and error:
                    print(f"      Error: {error}")
                
                if not passed:
                    test_passed = False
                    all_passed = False
            
            print(f"  Result: {'PASS' if test_passed else 'FAIL'}")
        
        print("\n" + "=" * 70)
        if all_passed:
            print("OVERALL: ALL TESTS PASSED")
        else:
            print("OVERALL: SOME TESTS FAILED")
        print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all Phase 2 quest extraction tests."""
    runner = Phase2TestRunner()
    runner.run_all_tests()


if __name__ == "__main__":
    main()
