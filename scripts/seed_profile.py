from datetime import datetime, timedelta
import uuid
import json
import os
import sys

# Ensure repo root is on sys.path so `from src...` imports work when running
# the script directly (python scripts/seed_profile.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.storage import load_profile, save_profile

USER_ID = "user_01"

now = datetime.utcnow()

# Helper to iso format
def iso(dt):
    return dt.replace(microsecond=0).isoformat() + "Z"

# Load existing profile if present
profile = load_profile(USER_ID) or {}

# Ensure top-level structure
if "character_sheet" not in profile:
    profile["character_sheet"] = {"user_id": USER_ID}

cs = profile["character_sheet"]

# Add sample calendar events (mix of HARD_DEADLINE, HABIT_SLOT, MEETING)
cs["calendar_events"] = [
    {
        "id": str(uuid.uuid4()),
        "title": "Project planning",
        "start_time": iso(now + timedelta(days=1, hours=9)),
        "end_time": iso(now + timedelta(days=1, hours=10)),
        "type": "MEETING",
        "node_id": None,
        "description": "Discuss milestones and assign tasks",
        "is_completed": False,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Submit taxes (deadline)",
        "start_time": iso(now + timedelta(days=7, hours=12)),
        "end_time": iso(now + timedelta(days=7, hours=13)),
        "type": "HARD_DEADLINE",
        "node_id": None,
        "description": "Final tax filing deadline",
        "is_completed": False,
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Morning Pomodoro",
        "start_time": iso(now + timedelta(days=0, hours=8)),
        "end_time": iso(now + timedelta(days=0, hours=8, minutes=25)),
        "type": "HABIT_SLOT",
        "node_id": None,
        "description": "Daily focused work slot",
        "is_completed": False,
    },
]

# Add sample pomodoro sessions
cs["pomodoro_history"] = [
    {
        "id": str(uuid.uuid4()),
        "start_time": iso(now - timedelta(days=1, hours=3)),
        "duration_minutes": 25,
        "task_id": None,
        "notes": "Worked on project outline",
        "completed": True,
    },
    {
        "id": str(uuid.uuid4()),
        "start_time": iso(now - timedelta(hours=5)),
        "duration_minutes": 25,
        "task_id": None,
        "notes": "Code kata",
        "completed": True,
    },
]
cs["pomodoros_total"] = len(cs["pomodoro_history"])

# Add sample lock-in sessions
cs["lockin_history"] = [
    {
        "id": str(uuid.uuid4()),
        "start_time": iso(now - timedelta(days=2, hours=2)),
        "end_time": iso(now - timedelta(days=2, hours=1, minutes=30)),
        "duration_seconds": 30 * 60,
        "distractions_detected": 1,
        "distraction_events": [{"ts": iso(now - timedelta(days=2, hours=1, minutes=50)), "type": "phone"}],
    },
    {
        "id": str(uuid.uuid4()),
        "start_time": iso(now - timedelta(days=1, hours=4)),
        "end_time": iso(now - timedelta(days=1, hours=3, minutes=20)),
        "duration_seconds": 40 * 60,
        "distractions_detected": 0,
        "distraction_events": [],
    },
]
cs["lockin_total_time_seconds"] = sum(s["duration_seconds"] for s in cs["lockin_history"])
cs["phone_distractions_total"] = sum(s["distractions_detected"] for s in cs["lockin_history"])

# Add a few user_facts
cs.setdefault("user_facts", [])
cs["user_facts"].extend([
    "Prefers morning focused sessions",
    "Enjoys short coding challenges",
])

# Save back
save_profile(profile, USER_ID)
print(f"Seeded profile for {USER_ID} and saved via storage.save_profile()")
