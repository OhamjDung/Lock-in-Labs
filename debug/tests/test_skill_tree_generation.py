import json
import os
import sys

# Add project root to sys.path to allow imports from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import CharacterSheet
from src.skill_tree.generator import SkillTreeGenerator


def main():
    """Runs a focused test on the SkillTreeGenerator using data/user_01.json."""
    print("--- Running Skill Tree Generation Test ---")

    # Load the existing user profile, including goals, stats, and debuffs
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    user_path = os.path.join(project_root, "data", "user_01.json")

    with open(user_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    character_sheet_data = payload["character_sheet"]
    character_sheet = CharacterSheet(**character_sheet_data)
    print("Character Sheet loaded for test from data/user_01.json.")

    # Initialize the generator and create the skill tree
    skill_tree_generator = SkillTreeGenerator()
    print("Generating skill tree...")
    skill_tree = skill_tree_generator.generate_skill_tree(character_sheet)
    print("Skill tree generated.")

    # Define the output path for the debug file
    output_dir = os.path.join(project_root, "data")
    output_file = "skill_tree_debug_output.json"
    output_path = os.path.join(output_dir, output_file)

    # Ensure the data directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Save the generated skill tree to the debug file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(skill_tree.model_dump(), f, indent=4)

    print(f"--- Skill tree debug output saved to {output_path} ---")


if __name__ == "__main__":
    main()
