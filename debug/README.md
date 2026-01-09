# Debug & Test Scripts

This folder contains all debugging and testing scripts for the onboarding system.

## Interactive Testing Scripts

- **`debug_onboarding.py`** - Interactive terminal chat for full onboarding flow (all phases)
- **`test_phase1.py`** - Interactive terminal chat for Phase 1 only (goal identification)

## Automated Test Scripts

- **`test_scenarios_phase1.py`** - Automated test scenarios for Phase 1:
  - Test 1: Missing goals detection (only 3 pillars mentioned)
  - Test 2: Misclassified goals detection (wrong pillar assignment)
  - Test 3: Extra goals detection (more than 4 goals)

- **`test_onboarding_comprehensive.py`** - Comprehensive onboarding test suite

- **`test_phase2_quest_extraction.py`** - Test Phase 2 quest extraction logic

## Utility Scripts

- **`debug_specific_response.py`** - Debug a specific user response to verify goal extraction
- **`quick_test.py`** - Quick test for misclassification detection
- **`debug_phase2.py`** - Debug Phase 2 specific functionality
- **`debug_thinking.py`** - Debug Architect thinking/reasoning output
- **`debug_viewer.py`** - Frontend debug viewer (moved from frontend folder)

## Other Tests

- **`test_email.py`** - Email functionality tests

## Usage

Run any script from the project root:
```bash
python debug/test_scenarios_phase1.py
python debug/debug_onboarding.py
python debug/test_phase1.py
python debug/test_phase2_quest_extraction.py
python debug/test_email.py
```

## Notes

- All scripts have been updated to correctly import from the project root (`src/`) from within the `debug/` folder
- Some scripts may have dependencies on other files in this folder (e.g., `debug_thinking.py` imports from `test_phase2_quest_extraction.py`)
- The `tests/` subdirectory contains additional test utilities
