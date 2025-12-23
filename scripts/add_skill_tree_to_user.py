#!/usr/bin/env python3
"""Script to add skill tree from user_01.json to a specific user's profile in Firebase."""

import json
import sys
import os

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.storage import load_profile, save_profile

def main():
    # User ID to update
    user_id = "kK6R32MEZghS5HNMpijNevrRZfF2"
    
    # Load the skill tree from user_01.json
    print(f"Loading skill tree from data/user_01.json...")
    with open("data/user_01.json", "r", encoding="utf-8") as f:
        user_01_data = json.load(f)
    
    skill_tree = user_01_data.get("skill_tree")
    if not skill_tree:
        print("ERROR: No skill_tree found in user_01.json")
        return 1
    
    print(f"[OK] Loaded skill tree with {len(skill_tree.get('nodes', []))} nodes")
    
    # Load the current user's profile
    print(f"\nLoading current profile for user {user_id}...")
    current_profile = load_profile(user_id)
    
    if not current_profile:
        print(f"ERROR: No profile found for user {user_id}")
        return 1
    
    print(f"[OK] Loaded existing profile")
    
    # Add the skill tree to the profile (at top level, not inside character_sheet)
    current_profile["skill_tree"] = skill_tree
    
    print(f"\nUpdating profile for user {user_id}...")
    print(f"  - Added skill_tree with {len(skill_tree.get('nodes', []))} nodes")
    
    # Save the profile (this updates both local JSON and Firebase)
    save_profile(current_profile, user_id)
    
    print(f"\n[OK] Successfully updated profile for user {user_id}")
    print(f"  - Local file: data/{user_id}.json")
    print(f"  - Firebase: profiles/{user_id}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

