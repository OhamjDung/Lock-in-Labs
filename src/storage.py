import json
import os
from src.models import CharacterSheet, SkillTree

DATA_DIR = "data"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_profile(character_sheet: CharacterSheet, skill_tree: SkillTree):
    ensure_data_dir()
    
    # Convert Pydantic models to dict
    # CharacterSheet might need a custom encoder if it has complex types, 
    # but Pydantic's .dict() or .model_dump() (v2) usually works well.
    # Assuming Pydantic v1 or v2, .dict() is safer for now or .model_dump() if v2.
    # Let's try standard dict() first.
    
    try:
        sheet_data = character_sheet.dict()
    except AttributeError:
        sheet_data = character_sheet.model_dump()
        
    try:
        tree_data = skill_tree.dict()
    except AttributeError:
        tree_data = skill_tree.model_dump()

    # Combine into one profile object
    profile_data = {
        "user_id": character_sheet.user_id,
        "character_sheet": sheet_data,
        "skill_tree": tree_data
    }
    
    file_path = os.path.join(DATA_DIR, f"{character_sheet.user_id}.json")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2)
        
    print(f"[System]: Profile saved to {file_path}")

def load_profile(user_id: str):
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
