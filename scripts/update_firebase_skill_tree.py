#!/usr/bin/env python3
"""Script to update Firebase with skill tree data. Requires Firebase service account credentials."""

import json
import sys
import os

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.firebase_client import get_firestore_client

def main():
    user_id = "kK6R32MEZghS5HNMpijNevrRZfF2"
    
    # Load the skill tree from the local file
    print(f"Loading profile data from data/{user_id}.json...")
    profile_file = f"data/{user_id}.json"
    
    if not os.path.exists(profile_file):
        print(f"ERROR: Profile file not found: {profile_file}")
        return 1
    
    with open(profile_file, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    skill_tree = profile_data.get("skill_tree")
    if not skill_tree:
        print("ERROR: No skill_tree found in profile data")
        return 1
    
    print(f"[OK] Loaded skill tree with {len(skill_tree.get('nodes', []))} nodes")
    
    # Check for Firebase credentials
    cred_path = os.getenv("FIREBASE_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not cred_path:
        print("\n" + "="*70)
        print("ERROR: Firebase credentials not found!")
        print("="*70)
        print("\nTo update Firebase, you need to set up Firebase Admin credentials.")
        print("\nSteps to get Firebase service account credentials:")
        print("1. Go to https://console.firebase.google.com/")
        print("2. Select your project")
        print("3. Click the gear icon (Settings) > Project settings")
        print("4. Go to the 'Service accounts' tab")
        print("5. Click 'Generate new private key'")
        print("6. Save the JSON file (e.g., firebase-service-account.json)")
        print("7. Set the environment variable:")
        print("   Windows PowerShell: $env:FIREBASE_CREDENTIALS='path/to/firebase-service-account.json'")
        print("   Windows CMD: set FIREBASE_CREDENTIALS=path/to/firebase-service-account.json")
        print("   Linux/Mac: export FIREBASE_CREDENTIALS=path/to/firebase-service-account.json")
        print("\nOr set GOOGLE_APPLICATION_CREDENTIALS with the same path.")
        print("="*70 + "\n")
        return 1
    
    if not os.path.exists(cred_path):
        print(f"\nERROR: Credentials file not found: {cred_path}")
        print("Please check the path and try again.\n")
        return 1
    
    print(f"[OK] Using Firebase credentials from: {cred_path}")
    
    # Update Firebase
    try:
        print(f"\nConnecting to Firebase...")
        db = get_firestore_client()
        
        print(f"Updating profile for user {user_id} in Firebase...")
        doc_ref = db.collection("profiles").document(user_id)
        
        # Update only the skill_tree field using merge
        update_data = {
            "skill_tree": skill_tree
        }
        doc_ref.set(update_data, merge=True)
        
        print(f"\n[OK] Successfully updated Firebase!")
        print(f"  - Collection: profiles")
        print(f"  - Document ID: {user_id}")
        print(f"  - Skill tree nodes: {len(skill_tree.get('nodes', []))}")
        
        # Verify the update
        print(f"\nVerifying update...")
        snapshot = doc_ref.get()
        if snapshot.exists:
            data = snapshot.to_dict()
            if data.get("skill_tree") and len(data["skill_tree"].get("nodes", [])) == len(skill_tree.get("nodes", [])):
                print(f"[OK] Verification successful - skill tree is in Firebase!")
            else:
                print(f"[WARNING] Update may not have completed correctly")
        else:
            print(f"[WARNING] Document not found after update")
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: Failed to update Firebase: {e}")
        print(f"\nPlease check:")
        print(f"1. Your Firebase credentials are valid")
        print(f"2. The service account has Firestore write permissions")
        print(f"3. Your Firestore database is enabled")
        return 1

if __name__ == "__main__":
    sys.exit(main())

