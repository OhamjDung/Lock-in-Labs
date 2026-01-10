# Testing Decision Explainability with Running Mock Data

This guide shows how to test the Decision Explainability system using the running mock data we created.

## Overview

The Decision Explainability system generates explainable AI decisions with verifiable citations. Every decision includes:
- **Target**: What's being adjusted (e.g., `running_distance`)
- **Old Value → New Value**: The change (e.g., `5km → 3km`)
- **Contributing Factors**: List of factors with citations
- **Verification Status**: Whether citations were verified against actual logs

## Step 1: Generate Test Data

Run the test script to generate a Decision from the running mock history:

```bash
python debug/test_decision_with_running_data.py
```

This will:
1. Load or generate 30 days of mock running history (`debug/mock_history.json`)
2. Convert logs to `DailyReport` objects
3. Sync reports to SemanticMemory (with significance gate - only score >= 7)
4. Generate a Decision using `ReportingAgent.generate_weekly_decision()`
5. Export Decision JSON to `debug/test_decision_output.json`

## Step 2: View Decision JSON

The Decision JSON is saved to `debug/test_decision_output.json`. It includes:

```json
{
  "decision": {
    "target": "running_distance",
    "old_value": "7km",
    "new_value": "5km",
    "decision_type": "DECREASE_INTENSITY",
    "confidence_score": 0.85,
    "contributing_factors": [
      {
        "factor": "Consistency Streak",
        "weight": "positive",
        "citation_date": "2025-11-16",
        "citation_text": "Completed 7/7 days this week",
        "is_verified": false,
        "verification_score": 0.45
      }
    ],
    "explanation": "..."
  },
  "metadata": {
    "generated_at": "2026-01-09T18:10:57.856442",
    "goal_name": "Run 5km, 3x per week",
    "reports_count": 30
  }
}
```

## Step 3: Test in Frontend

### Option A: Copy JSON to Public Folder (Quick Test)

1. Copy the JSON file to the frontend public folder:
   ```bash
   # Windows
   copy debug\test_decision_output.json frontend\test\life-rpg\public\test_decision_output.json
   
   # Linux/Mac
   cp debug/test_decision_output.json frontend/test/life-rpg/public/test_decision_output.json
   ```

2. Start your frontend dev server
3. Navigate to the ReportView page
4. The DecisionCard component will automatically load and display the test decision

### Option B: Load via API (Production)

Once you wire up the API endpoints, the frontend will automatically fetch decisions from:
- `/api/reporting/generate-decision?goal_id={id}`

## Step 4: Verify the Decision

Check the Decision output:

1. **Decision Type**: Should be `DECREASE_INTENSITY` (knee injury recovery)
2. **Contributing Factors**: Should cite specific dates and events from mock history
3. **Citations**: Should reference:
   - Day 14 (Dec 23): Sharp knee pain
   - Day 21 (Dec 30): Realized mileage increase was too fast
   - Day 25 (Jan 3): Glute bridges helping recovery

4. **Verification Status**: Citations should be marked as `is_verified: true/false`

## Expected Decision

Based on the running mock data narrative:

- **Target**: `running_distance`
- **Old Value**: `5km` or `7km` (depending on current plan)
- **New Value**: `3km` (reduced due to injury recovery)
- **Decision Type**: `DECREASE_INTENSITY`
- **Key Factors**:
  1. **Injury Risk** (negative): "Sharp pain in right knee at mile 1" (Day 14)
  2. **User Insight** (positive): "Realized I increased mileage too fast" (Day 21)
  3. **Recovery Progress** (positive): "Did glute bridges today. Knee feels stable" (Day 25)

## Troubleshooting

### No Decision Generated
- Check that mock history exists: `debug/mock_history.json`
- Verify significance scores: Should see 15+ high-significance chunks synced
- Check LLM API keys: Decision generation requires LLM calls

### Citations Not Verified
- The verification system checks if `citation_text` matches actual log entries
- Low `verification_score` indicates partial matches (still useful)
- Check `date_corrected` field - shows if date was corrected by grounding

### Frontend Not Displaying
- Ensure `test_decision_output.json` is in `public/` folder
- Check browser console for fetch errors
- Verify DecisionCard component is imported correctly

## Next Steps

1. ✅ Decision generation works
2. ✅ Decision JSON exported
3. ✅ DecisionCard component created
4. ⏭️ Wire up API endpoints (`/api/reporting/generate-decision`)
5. ⏭️ Integrate with real user data (replace mock history)
6. ⏭️ Add modal for citation details (click to view full log entry)

## Files

- `debug/test_decision_with_running_data.py` - Test script
- `debug/mock_history.json` - 30 days of running data
- `debug/test_decision_output.json` - Generated Decision JSON
- `frontend/test/life-rpg/src/components/dashboard/DecisionCard.jsx` - UI component
- `frontend/test/life-rpg/src/components/dashboard/ReportView.jsx` - Integration point
