# Active Coach Workflow Test

This test script simulates the entire Active Coach lifecycle to verify the implementation works correctly.

## What It Tests

The test simulates a user who has completed 29/30 "Run 5k" sessions and is about to master the habit. It then walks through all 4 phases:

1. **REVIEW Phase**: User reports completing the 30th session → System detects mastery
2. **PROGRESSION Phase**: System presents level-up decision → User accepts → Unlocks "Run 10k"
3. **SCHEDULING Phase**: User provides availability → System generates tomorrow's schedule
4. **COMPLETED Phase**: User confirms → Schedule is persisted

## How to Run

```bash
# From project root
python debug/test_active_coach_workflow.py
```

## Prerequisites

- Python environment with dependencies installed (`pip install -r requirements.txt`)
- **Optional**: `GEMINI_API_KEY` in `.env` file (for LLM-based scheduling)
  - If not set, the scheduler will use a fallback schedule (basic time-blocking)
  - The test will still work, but scheduling will be more basic

## Expected Output

If everything works correctly, you should see:

```
🚀 STARTING ACTIVE COACH SIMULATION...
============================================================

🔹 [TURN 1] User: 'I ran 5k today. I'm done reporting.'
   Current Progress: 30/30
🤖 Agent: Great work today! You've mastered some skills! Review these upgrades:
   Phase: PROGRESSION
   ✅ SUCCESS: Entered PROGRESSION phase.
   🃏 Cards Generated: 1 decision(s)
      1. Run 5k → Run 10k
------------------------------------------------------------

🔹 [TURN 2] User: 'Accept all'
🤖 Agent: Upgrades applied! (1 upgrade accepted) Now, what does your availability look like for tomorrow?
   Phase: SCHEDULING
   ✅ SUCCESS: 'Run 5k' is now MASTERED (was ACTIVE)
   ✅ SUCCESS: 'Run 10k' is now ACTIVE (was LOCKED)
   ✅ SUCCESS: Transitioned to SCHEDULING phase.
------------------------------------------------------------

🔹 [TURN 3] User: 'I have work from 9-5, but I'm free afterwards.'
   ⏳ Generating schedule (this may take a moment if LLM is called)...
🤖 Agent: I've drafted your schedule for tomorrow:
   Phase: COMPLETED
   📅 Generated Schedule (1 items):
      - 18:00: Run 10k
   ✅ SUCCESS: Schedule generated.
   ✅ SUCCESS: Transitioned to COMPLETED phase.
------------------------------------------------------------

🔹 [TURN 4] User: 'Confirm' (Finalizing schedule)
🤖 Agent: Schedule saved! Reporting session complete.
   Phase: COMPLETED
```

## Troubleshooting

### If progression phase doesn't trigger:
- Check that `sheet.habit_progress["node_run_5k"].completed_total` is actually 30
- Verify `check_progression()` function is working correctly
- Check that `required_completions` is set correctly (should be 30)

### If decisions aren't generated:
- Verify that `run_10k` node has `prerequisites=["node_run_5k"]`
- Check that the progression logic correctly finds children nodes

### If scheduling fails:
- Check that `GEMINI_API_KEY` is set (if using LLM)
- Review fallback scheduler logs (should print warnings if fallback is used)
- Verify that `_get_active_nodes()` returns nodes correctly

### If schedule isn't persisted:
- Note: The test doesn't call `save_profile()` - this is expected
- The API endpoint handles persistence (see `backend/api.py`)
- Check that `state.tomorrow_schedule` is populated

## Key Test Points

✅ **Blind Acceptance Fix**: The test verifies that decisions are NOT auto-applied - the user must explicitly accept them

✅ **Partial Acceptance**: You can modify the test to try "accept 1" or "accept 2" to test partial acceptance

✅ **Timezone Safety**: The test uses `state.current_date` for date calculations, not server time

✅ **Scheduler Resilience**: If LLM fails, fallback schedule is used with a warning message

## Extending the Test

To test other scenarios, modify `create_ready_to_level_up_sheet()`:

- **Multiple mastery candidates**: Add more nodes with 30/30 completions
- **No mastery**: Set `completed_total = 25` to test the "no progression" path
- **Multiple next steps**: Create multiple nodes that depend on the same prerequisite
- **Rejection**: Change "Accept all" to "Skip" to test rejection flow
