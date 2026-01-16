# FIXES IMPLEMENTATION GUIDE

## FIX #1: Make Critic Stricter About Unrelated Input

**File**: `src/onboarding/agent.py`  
**Class**: `CriticAgent`  
**Method**: `analyze()`  
**Priority**: CRITICAL

### Problem
Critic accepts completely unrelated input as valid quests. Example:
```
Q: "What are you doing for your CAREER goal?"
A: "I like pizza and watch movies"
Result: Critic adds "Watch movies on weekends" as a quest ✗ WRONG
```

### Current Behavior
The Critic's LLM is too permissive - it treats ANY statement from the user as potentially relevant.

### Required Change
Add validation that rejects input that doesn't relate to the active goal.

### Implementation

**Location**: Around line 160-210 in the `analyze()` method, in the system prompt

**Add this rule to the system prompt**:

```python
        <unrelated_response_detection>
        CRITICAL: If the user's response is completely UNRELATED to the active goal or the question asked, 
        you MUST reject it and return NO deltas.
        
        Examples of UNRELATED responses (return empty deltas):
        - Q: "What are you doing for your CAREER goal?"
          A: "I like pizza and watch movies" → UNRELATED (about personal preferences, not career)
        - Q: "What exercises are you doing?"
          A: "My favorite color is blue" → UNRELATED (about preferences, not exercise)
        - Q: "Tell me about your current quests for this goal"
          A: "The weather is nice today" → UNRELATED (about weather, not goal-related)
        
        Examples of RELATED responses (create deltas):
        - Q: "What are you doing for your CAREER goal?"
          A: "I'm taking online courses in Python" → RELATED (learning for career)
        - Q: "What exercises are you doing?"
          A: "I go to the gym 3x per week" → RELATED (exercise activity)
        
        Check: Is the user's response about the ACTIVE GOAL topic?
        - If YES → Extract normally (add_quest or update_skill)
        - If NO → Return STOP_SIGNAL or intent: "UNCLEAR" with empty deltas
        </unrelated_response_detection>
```

### Testing
After implementing, run: `python debug/onboarding_test_suite.py`
Then type: `3`

Expected result:
```
Test 3 verification should show:
✓ PASS: No quest from unrelated input
✓ PASS: Architect mentions career topic
✓ PASS: Architect response is question
✓ PASS: Response shows firmness
```

---

## FIX #2: Remove Phantom Acknowledgments

**File**: `src/onboarding/agent.py`  
**Class**: `ArchitectAgent`  
**Method**: `generate_response()`  
**Priority**: HIGH

### Problem
Architect adds acknowledgments even when the directive doesn't include one. Examples:
```
Directive: "Ask about their career goal"
Response: "Okay, a 1. What are you doing professionally..." ✗ WRONG
- "Okay, a 1" is a phantom acknowledgment (user didn't say "1")
```

### Current Behavior
The Architect's system prompt tells it to "Acknowledge" but doesn't validate whether there's actually something to acknowledge. The LLM defaults to a filler acknowledgment like "Okay, a 1".

### Required Change
Update the prompt to ONLY add acknowledgments when there's real content to acknowledge.

### Implementation

**Location**: Around line 265-290 in the `generate_response()` method, in the system prompt

**Find this section**:
```python
        4. **Acknowledgement Rules**:
           - NEVER put a question mark in the acknowledgement
           - Keep it 1 sentence max
           - Examples: "Got it.", "Okay, a 1 out of 10.", "That's okay, we all start somewhere."
           - WRONG: "Okay, a 1. What are you doing?" (question in acknowledgement)
           - RIGHT: "Okay, a 1. Now let's move on to [goal]. What are you doing for this?"
           - ⚠️ MOST IMPORTANT: DO NOT add an acknowledgement if the directive does NOT start with "Acknowledge"
```

**Update to**:
```python
        4. **Acknowledgement Rules**:
           - ONLY add an acknowledgement if:
             a) The directive explicitly says "Acknowledge X"
             b) The user provided specific information (like a number, activity, or clear statement)
           - If NEITHER of these is true, go directly to the question with NO acknowledgement
           - NEVER invent acknowledgements like "Okay, a 1" when user didn't provide a rating
           - NEVER put a question mark in the acknowledgement
           - Keep it 1 sentence max
           - Examples: "Got it.", "Okay, a 1 out of 10.", "That's okay, we all start somewhere."
           - WRONG: "Okay, a 1. What are you doing?" (phantom acknowledgement)
           - RIGHT (when acknowledging): "Okay, a 1. Now let's move on to [goal]. What are you doing for this?"
           - RIGHT (when not acknowledging): "What are you doing professionally to become a software engineer?"
           - ⚠️ CRITICAL: If directive only says "Ask X", respond ONLY with the question. NO acknowledgement.
```

### Testing
After implementing, run: `python debug/onboarding_test_suite.py`
Then type: `2`

Expected result:
```
Test 2 should show Architect response like:
"Alright, we've covered goals for all 4 areas. Let me dig deeper..."
NOT:
"Okay, a 1. Now let's move on..."
```

---

## FIX #3: Add Phase Transition Celebration

**File**: `backend/api.py`  
**Location**: Look for phase transition logic (search for "phase2" or "all_4_pillars")  
**Priority**: MEDIUM

### Problem
When user provides all 4 pillars, the system doesn't celebrate before moving to Phase 2.

**Current behavior**:
```
User: [provides 8 goals covering all 4 pillars]
System: "Okay, a 1. Now let's move on to CAREER goals. What are you doing for this?"
Result: No celebration ✗ User doesn't know they've completed Phase 1
```

**Expected behavior**:
```
System: "Great! I've got your goals for career, fitness, mental, and social. 
Now let's dig into each one to see what you're already doing. 
Let's start with your career goal..."
```

### Implementation

**Location**: `backend/api.py` - Find where it checks "all_4_pillars_covered"

Search for: `if all_4_pillars_covered:` or similar

**Add special handling**:

```python
# When transitioning from Phase 1 to Phase 2
if state.phase == "phase1" and all_4_pillars_covered and not we_just_asked_about_phase1_completion:
    # First response: Celebrate and prepare for Phase 2
    directive = """Acknowledge that we now have goals for all 4 pillars:
Career, Physical, Mental, and Social. Express enthusiasm about what they've told you.
Then explain that now we'll dig into each one to understand what they're currently doing.
Ask about the first pillar's current activities."""
    we_just_asked_about_phase1_completion = True
else:
    # Normal Phase 2 flow
    directive = "[normal phase 2 directive]"
```

### Or Simpler Approach

Modify the directive passed to the Architect when all pillars are covered:

**Find this code**:
```python
if len(covered_pillars) == 4:
    # All pillars covered, move to phase 2
    state.phase = "phase2"
    directive = "Ask about current quests for the first goal"
```

**Change to**:
```python
if len(covered_pillars) == 4:
    if not state.phase_1_celebration_done:
        # First time all pillars covered: Celebrate
        directive = f"""Congratulate the user for providing clear goals across all 4 areas: Career, Physical, Mental, and Social.
Then explain we're moving to Phase 2 where we'll understand what they're currently doing.
Ask about current quests for the {current_goal_name} goal."""
        state.phase_1_celebration_done = True
    else:
        # Normal Phase 2 flow
        directive = "Ask about current quests for the next goal"
    
    state.phase = "phase2"
```

### Testing
After implementing, run: `python debug/onboarding_test_suite.py`
Then type: `2`

Expected result:
```
Test 2 Architect response should:
✓ Acknowledge multiple goals
✓ Mention all 4 pillars
✓ Show transition to Phase 2
✓ Use celebratory language (Great, Excellent, Perfect, etc.)
```

---

## Testing Each Fix

### After Fix #1 (Critic Strictness)
```
Run: python debug/onboarding_test_suite.py
Type: 3
Check: "No quest from unrelated input" → should PASS
```

### After Fix #2 (Phantom Acknowledgments)
```
Run: python debug/onboarding_test_suite.py
Type: 2, 3, 4
Check: No responses should start with "Okay, a 1" unless justified
```

### After Fix #3 (Phase Transition)
```
Run: python debug/onboarding_test_suite.py
Type: 2
Check: Response should acknowledge progress and mention moving to Phase 2
```

### All Fixed
```
Run: python debug/onboarding_test_suite.py
Type: all
Expected: 5/5 tests passing ✓✓✓✓✓
```

---

## Order of Implementation

**Recommended order**: 

1. **Fix #1 first** (Critic strictness)
   - Prevents bad data from entering system
   - Most impactful for data quality
   - Fixes Test 3

2. **Fix #2 second** (Phantom acknowledgments)
   - Improves UX immediately
   - Affects multiple responses
   - Fixes Test 2 and improves Test 3, 4

3. **Fix #3 last** (Phase transition)
   - Polish/nice-to-have
   - Only matters when all 4 pillars provided
   - Improves Test 2 final verification

---

## Validation Checklist

- [ ] Fix #1 implemented and Test 3 passes
- [ ] Fix #2 implemented and Tests 2, 3 pass
- [ ] Fix #3 implemented and all 5 tests pass
- [ ] No new issues appear in stability test (Test 5)
- [ ] Pillar alignment still correct (Test 4 still passes)
- [ ] Manual testing with backend confirms behavior

---

## Common Issues During Implementation

### Issue: Changes don't affect tests
**Solution**: Restart the Python process. Old module may still be cached.

### Issue: Tests still show "Okay, a 1"
**Solution**: Make sure you're updating the ArchitectAgent in the right place. Look for "MOST IMPORTANT" comment in the prompt.

### Issue: Critic rejects valid input
**Solution**: Make sure your "unrelated detection" logic is specific. Example:
```
✓ GOOD: "Does the response mention the goal topic?"
✗ BAD: "Does the response contain any noun?"
```

### Issue: Phase transition doesn't trigger
**Solution**: Verify that `all_4_pillars_covered` is being calculated correctly. Should check if all 4 Pillar enums are represented.

---

## Summary

| Fix | File | Issue | Test | Status |
|-----|------|-------|------|--------|
| #1 | agent.py (Critic) | Accepts unrelated input | 3 | ✗ FAIL |
| #2 | agent.py (Architect) | Phantom acknowledgments | 2 | ✗ FAIL |
| #3 | api.py (Backend) | No phase celebration | 2 | ✗ FAIL |

After all fixes: **Expected 5/5 passing** ✓

---

**Last Updated**: January 15, 2026  
**Created by**: GitHub Copilot  
**Status**: Ready for implementation
