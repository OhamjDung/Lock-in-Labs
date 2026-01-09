# Memory System Verification Suite

**"Don't paint the car before you build the engine."**

This suite verifies that the memory system backend logic works correctly **before** building any frontend UI. It proves:

1. ✅ **Significance Gate**: Filters routine logs, keeps strategic memories
2. ✅ **Vector DB Filtering**: Actually enforces significance threshold
3. ✅ **Decision Explainability**: Agent can cite sources and make verifiable decisions

## Quick Start

```bash
# Step 1: Generate synthetic 30-day history
python debug/generate_mock_history.py

# Step 2: Test significance gate
python debug/test_significance.py

# Step 3: Test decision explainability
python debug/test_decision_logic.py
```

## Test 1: Significance Gate

**Purpose**: Verify that routine logs ("Ate oatmeal") are filtered out, while strategic memories ("Sharp pain in knee") are kept.

**What it tests**:
- Significance scoring (1-10 scale)
- Threshold filtering (default: 7/10)
- Key phrase verification
- Routine entry filtering

**Expected output**:
```
✅ EMBEDDING (Score 8): AMAZING run today! Hit 5km for the first time!
✅ EMBEDDING (Score 9): Sharp pain in right knee at mile 1. Had to walk home.
❌ SKIPPING (Score 2): Ate oatmeal. Ran 3km. Felt easy.
```

**Success criteria**:
- High-significance entries: ~10-15 (milestones, injuries, insights)
- Low-significance entries: ~15-20 (routine activities)
- Filter rate: ~60-70% filtered out
- All key phrases captured

## Test 2: Vector DB Filtering

**Purpose**: Verify that `SemanticMemory.add_chunk()` actually filters by significance threshold.

**What it tests**:
- Chunks with score >= threshold are added
- Chunks with score < threshold are skipped
- Vector DB count matches filtered count
- Search works on filtered results

**Success criteria**:
- Only 2 chunks added (score 8 and 9)
- 2 chunks skipped (score 1 and 2)
- Search returns relevant high-significance results

## Test 3: Decision Explainability

**Purpose**: Verify that the agent can make decisions with proper citations.

**What it tests**:
- Agent queries Vector DB for relevant memories
- Agent makes structured decision (JSON)
- Decision includes `contributing_factors` with citations
- Citations reference actual dates and quotes from memory

**Expected output structure**:
```json
{
  "target": "running_distance",
  "old_value": "5km",
  "new_value": "3km",
  "decision_type": "DECREASE",
  "confidence_score": 0.95,
  "contributing_factors": [
    {
      "factor": "Injury Risk",
      "weight": "negative",
      "description": "User reported sharp knee pain on 2025-01-15",
      "citation_date": "2025-01-15",
      "citation_text": "Sharp pain in right knee at mile 1"
    }
  ],
  "explanation": "We are decreasing distance because..."
}
```

**Success criteria**:
- All `contributing_factors` have `citation_date` and `citation_text`
- Citations can be verified against actual memories
- Explanation cites specific dates
- Decision is structured and parseable

## Narrative Arc: "The Runner's Knee Injury"

The mock data tells a realistic story:

**Week 1 (Days 0-6)**: High motivation, good progress
- Milestone: First 5km run
- Positive sentiment, building momentum

**Week 2 (Days 7-13)**: Warning signs ignored
- Shin splints, weird knee feeling
- Overconfidence leads to pushing through pain

**Week 3 (Days 14-20)**: Injury crash
- Sharp knee pain, can't run
- Demotivation, frustration
- Doctor diagnosis: Runner's Knee

**Week 4 (Days 21-29)**: Recovery and lesson learned
- Root cause identified: Too much, too fast
- Glute strengthening work
- Gradual return plan

## Using the Results

### For Backend Development

If all tests pass:
- ✅ Memory system is working correctly
- ✅ Significance gate filters appropriately
- ✅ Decisions are explainable and verifiable
- **You can now build the frontend UI with confidence**

### For Frontend Development

The test outputs provide the exact JSON structure you need:

1. **`debug/mock_history.json`**: Raw log entries (for audit trail UI)
2. **`debug/decision_output.json`**: Decision structure (for React FactorCard component)

Use these as TypeScript interfaces:

```typescript
interface ContributingFactor {
  factor: string;
  weight: "positive" | "negative";
  description: string;
  citation_date: string;
  citation_text: string;
}

interface Decision {
  target: string;
  old_value: string;
  new_value: string;
  decision_type: "INCREASE" | "DECREASE" | "MAINTAIN";
  confidence_score: number;
  contributing_factors: ContributingFactor[];
  explanation: string;
}
```

## Troubleshooting

### Test 1 fails: Significance scoring
- **Issue**: Key phrases not captured
- **Fix**: Adjust significance threshold or improve scorer prompts

### Test 2 fails: Vector DB filtering
- **Issue**: Wrong count in Vector DB
- **Fix**: Check `significance_threshold` parameter, verify `add_chunk()` logic

### Test 3 fails: Missing citations
- **Issue**: LLM response missing `citation_date` or `citation_text`
- **Fix**: Strengthen prompt requirements, add JSON schema validation

## Next Steps

Once all tests pass:

1. ✅ **Backend verified** - Memory system works
2. 📦 **Build React FactorCard** - Component to display `contributing_factors`
3. 📦 **Build Diff View** - Show `old_value → new_value` changes
4. 📦 **Build Citation Links** - Click citation to see source memory

The JSON structure is **locked in** - you won't need to rewrite the frontend when the backend changes.
