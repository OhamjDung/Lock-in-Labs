# Quick Start Guide - Onboarding Test Suite

## Start the Tests

```powershell
cd "d:\Noobcept\Lock In Labs"
python debug/onboarding_test_suite.py
```

## Commands

| Command | What It Does |
|---------|--------------|
| `all` | Run all 5 tests at once |
| `phase1` | Run Phase 1 tests (1-2) |
| `phase2` | Run Phase 2 tests (3-5) |
| `1` | Test Phase 1 - Insufficient Goals |
| `2` | Test Phase 1 - Excess Goals |
| `3` | Test Phase 2 - Unrelated Response |
| `4` | Test Pillar Alignment |
| `5` | Test Stability |
| `menu` | Show menu |
| `summary` | Show progress |
| `exit` | Quit |

## Current Status

### Passing Tests (3/5) ✓
- **Test 1**: Phase 1 correctly handles insufficient goals
- **Test 4**: Pillar alignment verified (right question for right pillar)
- **Test 5**: Stability verified (no crashes on edge cases)

### Failing Tests (2/5) ✗
- **Test 2**: Phase 1 Excess Goals
  - Issue: Missing progress acknowledgment when all 4 pillars covered
  - Fix Needed: #2 (Phantom acknowledgments) + #3 (Phase transition)

- **Test 3**: Phase 2 Unrelated Response
  - Issue: Critic accepts unrelated input ("pizza") as a quest
  - Fix Needed: #1 (Critic strictness)

## The 3 Fixes Needed

### Fix #1: Make Critic Stricter
**File**: `src/onboarding/agent.py` (CriticAgent)  
**Problem**: Accepts unrelated input as quests  
**Test It**: Run `3` - should see "No quest from unrelated input: PASS"

### Fix #2: Remove Phantom Acknowledgments
**File**: `src/onboarding/agent.py` (ArchitectAgent)  
**Problem**: Says "Okay, a 1" even when user didn't rate anything  
**Test It**: Run `2` or `3` - should NOT see "Okay, a 1"

### Fix #3: Add Phase Transition Celebration
**File**: Backend routing logic  
**Problem**: Doesn't celebrate when all 4 pillars covered  
**Test It**: Run `2` - should see celebratory language

## Test Flow

Each test:
1. Shows the scenario
2. Displays what the system does
3. Checks against expected behavior
4. Reports PASS or FAIL with details

## Debugging Tips

- Run individual tests with `1-5` to isolate issues
- Run `summary` to see what's been fixed
- Tests report every 5 fixes applied
- All issues are printed with [ISSUE FOUND] prefix

## Next Steps

1. Read the full report: `debug/ONBOARDING_DEBUG_REPORT.md`
2. Identify which fix to apply first (recommend: #1, then #2, then #3)
3. Make the fix in the code
4. Re-run the relevant test to verify
5. Continue until all 5 tests pass

## API Rate Limits

If you see rate limit errors:
- The system rotates between 5 API keys automatically
- Waits for cooldown periods
- Will pause and retry
- Just let it continue

---

**Created**: January 15, 2026  
**Test Suite Version**: 1.0  
**Status**: Ready for debugging
