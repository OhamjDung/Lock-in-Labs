"""Test script for Active Coach Workflow.

Simulates the entire lifecycle: Report → Level Up → Accept Decision → Schedule Tomorrow.
"""

import os
import sys
from datetime import datetime, date, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.models import (
    CharacterSheet, SkillTree, SkillNode, NodeType, 
    HabitProgress, NodeStatus, Pillar, ReportingState, ReportingPhase,
    DailyTask, DailyTaskStatus
)
from src.reporting.agent import ReportingAgent
from src.reporting.progression import check_progression


# --- 1. SETUP MOCK DATA ---
def create_ready_to_level_up_sheet():
    """Creates a user who is 1 rep away from mastering 'Run 5k'."""
    sheet = CharacterSheet(
        user_id="test_user"
    )
    
    # Create Nodes
    run_5k = SkillNode(
        id="node_run_5k", 
        name="Run 5k", 
        type=NodeType.HABIT, 
        pillar=Pillar.PHYSICAL,
        xp_reward=100,
        required_completions=30
    )
    
    run_10k = SkillNode(
        id="node_run_10k", 
        name="Run 10k", 
        type=NodeType.HABIT, 
        pillar=Pillar.PHYSICAL, 
        prerequisites=["node_run_5k"],  # Locked behind 5k
        xp_reward=200,
        required_completions=30
    )
    
    sheet.skill_tree = SkillTree(nodes=[run_5k, run_10k])
    
    # Set Progress (29/30 done for 5k)
    sheet.habit_progress["node_run_5k"] = HabitProgress(
        node_id="node_run_5k",
        status=NodeStatus.ACTIVE,
        completed_total=29,  # ONE AWAY FROM MASTERY
        required_completions=30,
        streak_days=5
    )
    
    # 10k is currently locked
    sheet.habit_progress["node_run_10k"] = HabitProgress(
        node_id="node_run_10k",
        status=NodeStatus.LOCKED,
        completed_total=0,
        required_completions=30
    )
    
    # Set pillar rankings for scheduler
    sheet.pillar_rankings = [Pillar.PHYSICAL, Pillar.CAREER, Pillar.MENTAL, Pillar.SOCIAL]
    
    return sheet


# --- 2. THE TEST RUNNER ---
def run_simulation():
    """Run the Active Coach workflow simulation."""
    print("[TEST] STARTING ACTIVE COACH SIMULATION...\n")
    print("=" * 60)
    
    # Initialize
    sheet = create_ready_to_level_up_sheet()
    agent = ReportingAgent()
    
    # Create initial state
    current_date = date.today().isoformat()
    state = ReportingState(
        user_id="test_user",
        current_date=current_date,
        todays_tasks=[],  # Empty for this test
        phase=ReportingPhase.REVIEW,
        conversation_history=[]
    )
    
    tree = sheet.skill_tree
    
    # --- TURN 1: REPORTING (The Trigger) ---
    print(f"\n[TURN 1] User: 'I ran 5k today. I'm done reporting.'")
    print(f"   Current Progress: {sheet.habit_progress['node_run_5k'].completed_total}/30")
    
    # Manually increment progress to trigger mastery (simulating user completing the task)
    sheet.habit_progress["node_run_5k"].completed_total = 30
    
    # Add user message to history
    state.conversation_history.append({"role": "user", "content": "I ran 5k today. I'm done reporting."})
    
    # Generate reply (this should detect mastery and enter PROGRESSION phase)
    response = agent.generate_reply(state, sheet, tree, "I ran 5k today. I'm done reporting.")
    
    print(f"[AGENT] {response['text']}")
    print(f"   Phase: {response.get('phase', 'unknown')}")
    
    # Check if we entered PROGRESSION phase
    if response.get('phase') == ReportingPhase.PROGRESSION.value:
        print("   [OK] SUCCESS: Entered PROGRESSION phase.")
        decisions = response.get('decisions', [])
        if decisions:
            print(f"   [CARDS] Generated: {len(decisions)} decision(s)")
            for i, d in enumerate(decisions, 1):
                print(f"      {i}. {d.get('target', 'unknown')} -> {d.get('new_value', 'unknown')}")
        else:
            print("   [WARN] No decisions generated (check progression logic)")
    else:
        print(f"   [FAIL] Expected PROGRESSION phase, got {response.get('phase')}")
        print(f"   Returning early...")
        return
    
    state.conversation_history.append({"role": "assistant", "content": response['text']})
    
    print("-" * 60)
    
    # --- TURN 2: ACCEPTANCE (The Decision) ---
    print(f"\n[TURN 2] User: 'Accept all'")
    
    # Add user acceptance message
    state.conversation_history.append({"role": "user", "content": "Accept all"})
    
    response = agent.generate_reply(state, sheet, tree, "Accept all")
    
    print(f"[AGENT] {response['text']}")
    print(f"   Phase: {response.get('phase', 'unknown')}")
    
    # Check if 'Run 5k' is MASTERED and 'Run 10k' is UNLOCKED
    p_5k = sheet.habit_progress["node_run_5k"].status
    p_10k = sheet.habit_progress.get("node_run_10k", HabitProgress(node_id="node_run_10k")).status
    
    if p_5k == NodeStatus.MASTERED:
        print(f"   [OK] SUCCESS: 'Run 5k' is now MASTERED (was ACTIVE)")
    else:
        print(f"   [FAIL] 'Run 5k' status is {p_5k} (expected MASTERED)")
    
    if p_10k == NodeStatus.ACTIVE:
        print(f"   [OK] SUCCESS: 'Run 10k' is now ACTIVE (was LOCKED)")
    else:
        print(f"   [INFO] 'Run 10k' status is {p_10k} (may need unlocking logic)")
    
    # Check phase transition
    if response.get('phase') == ReportingPhase.SCHEDULING.value:
        print("   [OK] SUCCESS: Transitioned to SCHEDULING phase.")
    else:
        print(f"   [FAIL] Expected SCHEDULING phase, got {response.get('phase')}")
        return
    
    state.conversation_history.append({"role": "assistant", "content": response['text']})
    
    print("-" * 60)
    
    # --- TURN 3: SCHEDULING (The Plan) ---
    print(f"\n[TURN 3] User: 'I have work from 9-5, but I'm free afterwards.'")
    
    # Add user availability message
    state.conversation_history.append({"role": "user", "content": "I have work from 9-5, but I'm free afterwards."})
    
    # Note: Scheduler calls LLM, so this might take a moment
    print("   [WAIT] Generating schedule (this may take a moment if LLM is called)...")
    response = agent.generate_reply(
        state, 
        sheet, 
        tree, 
        "I have work from 9-5, but I'm free afterwards."
    )
    
    print(f"[AGENT] {response['text']}")
    print(f"   Phase: {response.get('phase', 'unknown')}")
    
    # Check if schedule was generated
    schedule_preview = response.get('schedule_preview')
    if schedule_preview:
        print(f"   [SCHEDULE] Generated ({len(schedule_preview)} items):")
        for item in schedule_preview[:5]:  # Show first 5 items
            time = item.get('time', 'unknown')
            label = item.get('label', 'unknown')
            print(f"      - {time}: {label}")
        if len(schedule_preview) > 5:
            print(f"      ... and {len(schedule_preview) - 5} more")
        print("   [OK] SUCCESS: Schedule generated.")
    else:
        print("   [WARN] No schedule_preview in response")
    
    # Check if state has tomorrow_schedule
    if state.tomorrow_schedule:
        print(f"   [OK] SUCCESS: tomorrow_schedule stored in state ({len(state.tomorrow_schedule)} items)")
    else:
        print("   [INFO] tomorrow_schedule not yet in state (may be set after confirmation)")
    
    # Check phase
    if response.get('phase') == ReportingPhase.COMPLETED.value:
        print("   [OK] SUCCESS: Transitioned to COMPLETED phase.")
    else:
        print(f"   [INFO] Phase is {response.get('phase')} (expected COMPLETED)")
    
    state.conversation_history.append({"role": "assistant", "content": response['text']})
    
    print("-" * 60)
    
    # --- TURN 4: FINALIZATION (Optional) ---
    print(f"\n[TURN 4] User: 'Confirm' (Finalizing schedule)")
    
    state.conversation_history.append({"role": "user", "content": "Confirm"})
    
    response = agent.generate_reply(state, sheet, tree, "Confirm")
    
    print(f"[AGENT] {response['text']}")
    print(f"   Phase: {response.get('phase', 'unknown')}")
    
    # Check if schedule is persisted
    tomorrow_date = (date.today() + timedelta(days=1)).isoformat()
    
    if tomorrow_date in sheet.daily_schedule:
        schedule = sheet.daily_schedule[tomorrow_date]
        print(f"   [OK] SUCCESS: Schedule persisted for {tomorrow_date} ({len(schedule)} items)")
    else:
        print(f"   [INFO] Schedule not yet persisted (may require API call to save_profile)")
    
    print("\n" + "=" * 60)
    print("[TEST] SIMULATION COMPLETE.\n")
    
    # Summary
    print("[SUMMARY]")
    print(f"   - Run 5k progress: {sheet.habit_progress['node_run_5k'].completed_total}/30")
    print(f"   - Run 5k status: {sheet.habit_progress['node_run_5k'].status}")
    print(f"   - Run 10k status: {sheet.habit_progress.get('node_run_10k', HabitProgress(node_id='node_run_10k')).status}")
    print(f"   - Final phase: {response.get('phase', 'unknown')}")
    print(f"   - Conversation turns: {len(state.conversation_history)}")
    print()


if __name__ == "__main__":
    try:
        run_simulation()
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
