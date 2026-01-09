import json
import os
import uuid

DATA_DIR = "data"

def migrate():
    print(f"Starting migration for files in {DATA_DIR}...")
    
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} not found.")
        return

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".json"): continue
        
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Skipping invalid JSON file: {filename}")
            continue
        
        # Check if this is a profile file (has "character_sheet" or direct fields)
        # The structure seems to vary based on previous logs, let's inspect structure
        # Standard structure from previous logs seems to be the root object IS the sheet/data
        # Let's check if it has "goals"
        
        sheet = data
        if "goals" not in sheet:
            # Maybe it's nested?
            if "character_sheet" in data:
                sheet = data["character_sheet"]
            else:
                # print(f"ℹ️ Skipping {filename} (no goals found)")
                continue
        
        changed = False

        # FIX: Backfill IDs for existing goals
        if "goals" in sheet and isinstance(sheet["goals"], list):
            for goal in sheet["goals"]:
                if "id" not in goal:
                    goal["id"] = f"goal_{str(uuid.uuid4())[:8]}"
                    print(f"[+] Added ID {goal['id']} to goal '{goal.get('name', 'Unknown')}' in {filename}")
                    changed = True

        if changed:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"Migrated {filename}")
        else:
            print(f"No changes needed for {filename}")

if __name__ == "__main__":
    migrate()
