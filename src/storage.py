import json
import os
from src.models import CharacterSheet, SkillTree
from src.firebase_client import get_firestore_client

DATA_DIR = "data"

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_profile(profile_data: dict, user_id: str):
    """
    Saves the final character profile (sheet + tree) to a JSON file.
    
    Args:
        profile_data (dict): A dictionary containing the character sheet and skill tree.
        user_id (str): The ID of the user to create the filename.
    """
    ensure_data_dir()
    
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    
    # The data is already a dict, so we can just dump it.
    try:
        with open(file_path, 'w') as f:
            json.dump(profile_data, f, indent=4)
    except TypeError as e:
        print(f"Error serializing profile data: {e}")
        # Fallback for complex types if needed in the future
        # with open(file_path, 'w') as f:
        #     json.dump(profile_data, f, indent=4, default=str)

    # Also persist the profile into Firebase (Firestore) so other
    # services/frontends can read it without touching the local JSON file.
    try:
        db = get_firestore_client()
        doc_ref = db.collection("profiles").document(user_id)
        doc_ref.set(profile_data, merge=True)
    except Exception as e:  # pragma: no cover - best-effort remote write
        # Log but don't crash the app if Firebase is misconfigured.
        print(f"[Firebase] Failed to save profile for user '{user_id}': {e}")

def load_profile(user_id: str):
    """Load the profile for a user.

    Priority order:
    1. Firestore document in collection "profiles" with id == user_id.
    2. Local JSON file under data/{user_id}.json (legacy fallback).
    """

    # 1) Try Firestore first so the app uses the most recent cloud state.
    try:
        db = get_firestore_client()
        doc_ref = db.collection("profiles").document(user_id)
        snapshot = doc_ref.get()
        if snapshot.exists:
            data = snapshot.to_dict() or {}
            return data
    except Exception as e:  # pragma: no cover - best-effort remote read
        print(f"[Firebase] Failed to load profile for user '{user_id}': {e}")

    # 2) Fallback to the local JSON file on disk.
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
