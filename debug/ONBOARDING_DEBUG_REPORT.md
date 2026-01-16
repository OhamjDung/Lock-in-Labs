# ONBOARDING DEBUG REPORT
**Generated: January 15, 2026**

## EXECUTIVE SUMMARY

Comprehensive testing of the onboarding system revealed **3 CRITICAL ISSUES** that need fixing:

1. **Critic is too permissive** - Accepts unrelated inputs as quests (watches movies accepted as a career quest)
2. **Architect has phantom acknowledgments** - Says "Okay, a 1" even when no rating was provided
3. **Phase 1 doesn't acknowledge progress** - Missing celebration when all 4 pillars covered

---

## TEST RESULTS

### PASSING TESTS (3/5) ✓
- **Test 1: Phase 1 Insufficient Goals** - PASS
- **Test 4: Pillar Alignment** - PASS  
- **Test 5: Overall Stability** - PASS

### FAILING TESTS (2/5) ✗
- **Test 2: Phase 1 Excess Goals** - FAIL
- **Test 3: Phase 2 Unrelated Response** - FAIL

---

## DETAILED FINDINGS

### ISSUE #1: Critic Accepts Unrelated Input as Quest
**Test**: Phase 2 - Unrelated Response  
**Severity**: CRITICAL  
**Impact**: System will record meaningless quests

**What Happened**:
```
Question: "What are you doing for your CAREER goal?"
User Response: "I like pizza and watch movies on weekends"
Critic Result: "add_quest: Watch movies on weekends"
```

**Expected**: No quest should be extracted (input is completely unrelated)  
**Actual**: Critic added "Watch movies" as a career quest

**Root Cause**: The Critic's LLM is being too generous in interpreting input. The system needs to be told:
- Only accept responses that directly relate to the active goal
- If the user's input doesn't address the question, flag it as unrelated
- Don't infer connections between unrelated activities and goals

**Recommendation**: Update Critic prompt to be more strict about input validation.

---

### ISSUE #2: Architect Phantom Acknowledgments
**Test**: Phase 2 Tests  
**Severity**: HIGH  
**Impact**: Confuses users, suggests AI didn't listen

**What Happened**:
```
Directive: "Ask about their career goal"
Architect Response: "Okay, a 1. What are you doing professionally..."
```

Expected: No "Okay, a 1" (user never said a rating)  
Actual: Architect added phantom acknowledgment

**Root Cause**: The Architect prompt tells it to "Acknowledge" but the directive doesn't include an actual acknowledgment to make. The LLM is defaulting to a filler acknowledgment.

**Evidence**:
- Test 2: "Okay, a 1. Now let's move on to CAREER goals..."
- Test 3: "Okay, a 1. Now let's move on to becoming a software engineer..."
- Test 4: "Okay, a 1. What are you doing professionally..."

**Recommendation**: Only add acknowledgment when there's actually something to acknowledge. If directive doesn't start with "Acknowledge", don't add acknowledgment.

---

### ISSUE #3: Phase 1 Missing Progress Feedback
**Test**: Phase 1 - Excess Goals  
**Severity**: MEDIUM  
**Impact**: Users don't know they've completed phase 1

**What Happened**:
```
Directive: "User provided many goals covering all 4 pillars. Acknowledge and prepare for phase 2"
Architect Response: "Okay, a 1. Now let's move on to CAREER goals. What are you doing for this?"
```

Expected: "Great! I've got goals for all 4 areas now. Let's dig deeper into each one."  
Actual: Just moves to the next question without celebrating progress

**Root Cause**: Same issue as #2 - phantom acknowledgment overshadows the actual phase transition message.

**Recommendation**: 
1. Fix phantom acknowledgments first
2. Then add explicit phase transition messaging

---

## PASSING TESTS ANALYSIS

### TEST 1: Phase 1 Insufficient Goals ✓
**Result**: PASS (4/4 checks)

```
User Input: "I want to be a software engineer and run a marathon"
Critic Extracted: 2 goals (CAREER + PHYSICAL)
Missing: MENTAL + SOCIAL
Architect Response: "Let's move on to the MENTAL pillar. What are you doing for this?"
```

**What Works Well**:
- Critic correctly identifies the 2 new goals
- Architect correctly identifies missing pillars  
- Architect asks about missing pillar
- Response ends with question

**Verdict**: This part of the system is working as designed ✓

---

### TEST 4: Pillar Alignment ✓
**Result**: PASS (6/6 checks)

Tested 3 pillar contexts:

**CAREER Question**:
- ✓ Has career keywords: "engineer", "professionally", "learning"
- ✓ No unrelated keywords

**PHYSICAL Question**:
- ✓ Has physical keywords: "marathon", "exercise", "fitness"
- ✓ No unrelated keywords

**MENTAL Question**:
- ✓ Has mental keywords: "calm", "pressure", "wellbeing", "stress"
- ✓ No unrelated keywords

**Verdict**: Pillar alignment is working correctly - questions are topic-specific ✓

---

### TEST 5: Overall Stability ✓
**Result**: PASS (All edge cases handled)

**Edge Cases Tested**:
- Empty string → Skipped (handled)
- Only spaces → Skipped (handled)
- Random characters (???) → ✓ Handled
- Number only (5) → ✓ Handled
- Very long input (1000 chars) → ✓ Handled
- Special characters (😀🎉💯) → ✓ Handled
- SQL injection attempt → ✓ Handled

**Verdict**: System doesn't crash on edge cases ✓

---

## SUMMARY OF CRITICAL FIXES NEEDED

### Fix #1: Make Critic Stricter About Unrelated Input
**Priority**: CRITICAL  
**Location**: `src/onboarding/agent.py` - CriticAgent system prompt

**Change**: Add validation rules that reject unrelated input
```
Additional instruction for Critic:
"If the user's response does not address the active goal or question, 
return empty deltas with feedback 'User response is unrelated to the active goal.'"
```

**Estimated Impact**: Will prevent meaningless quests from being added

---

### Fix #2: Remove Phantom Acknowledgments
**Priority**: HIGH  
**Location**: `src/onboarding/agent.py` - ArchitectAgent system prompt

**Change**: Only acknowledge when there's actual content to acknowledge
```
Update: "Only add an acknowledgement if the user provided specific information 
(like a rating or activity). If the directive only asks a question, 
start directly with the question - no phantom acknowledgements."
```

**Estimated Impact**: Responses will be cleaner and less confusing

---

### Fix #3: Add Phase Transition Celebration
**Priority**: MEDIUM  
**Location**: Backend logic where phase transitions happen

**Change**: Add specific directive when all pillars are covered
```
If all_4_pillars_covered:
  directive = "Celebrate that we have goals for all 4 areas. 
              Then ask about specific activities for the first pillar."
```

**Estimated Impact**: Users will feel progress and understand phase transitions

---

## HOW TO USE THE TEST SUITE

The test script is at: `debug/onboarding_test_suite.py`

**Start the suite**:
```
python debug/onboarding_test_suite.py
```

**Available commands**:
```
all     - Run all 5 tests in sequence
phase1  - Run Phase 1 tests (1-2)
phase2  - Run Phase 2 tests (3-5)
1-5     - Run individual test
menu    - Show menu
summary - Show progress summary
exit    - Exit program
```

**The suite tracks**:
- Test pass/fail status
- Issues found
- Fixes applied (reports every 5 fixes)

---

## NEXT STEPS

1. **Implement Fix #1** (Critic strictness)
   - Test with: Command `3`
   - Should see "No quest from unrelated input: PASS"

2. **Implement Fix #2** (Remove phantom acknowledgments)
   - Test with: Commands `2`, `3`, `4`
   - Should no longer see "Okay, a 1" when user didn't say a rating

3. **Implement Fix #3** (Phase transition)
   - Test with: Command `2`
   - Should see celebration language

4. **Re-run all tests** with command `all`
   - Target: 5/5 passing

---

## TEST EXECUTION LOG

```
TEST 1: Phase 1 Insufficient Goals - PASS ✓
  • Collected 2 goals
  • Architect mentions missing pillar
  • Response is question
  • Response not empty

TEST 2: Phase 1 Excess Goals - FAIL ✗
  • Multiple goals collected ✓
  • Response is coherent ✓
  • No crash on excess input ✓
  • Response acknowledges progress ✗ (ISSUE)

TEST 3: Phase 2 Unrelated Response - FAIL ✗
  • No quest from unrelated input ✗ (ISSUE)
  • Architect mentions career topic ✓
  • Response is question ✓
  • Response shows firmness ✗ (ISSUE)

TEST 4: Pillar Alignment - PASS ✓
  • CAREER: Has career keywords ✓
  • CAREER: No unrelated keywords ✓
  • PHYSICAL: Has physical keywords ✓
  • PHYSICAL: No unrelated keywords ✓
  • MENTAL: Has mental keywords ✓
  • MENTAL: No unrelated keywords ✓

TEST 5: Overall Stability - PASS ✓
  • All edge cases handled ✓
```

---

## CONCLUSION

The onboarding system has a **solid foundation** but needs **3 key fixes**:

1. **Critic**: Be stricter about what counts as a quest
2. **Architect**: Stop adding phantom acknowledgments
3. **Phase Transitions**: Add celebration messaging

After these fixes, expect:
- 5/5 tests passing
- Users receive only relevant quests
- Clearer AI responses
- Better phase transition feedback

**Estimated time to fix**: 1-2 hours
**Estimated testing time**: 30 minutes

---

## APPENDIX: Full Test Scenarios

### Test Scenario 1: Insufficient Goals
```
User: "I want to become a software engineer and I want to run a marathon"
System should:
  1. Extract 2 goals (CAREER + PHYSICAL)
  2. Notice MENTAL + SOCIAL missing
  3. Ask about one of the missing pillars
Result: ✓ WORKING
```

### Test Scenario 2: Excess Goals
```
User: "I want to be a software engineer, start a business, run a marathon, 
       be flexible, make new friends, be more confident, be calm under 
       pressure, and meditate daily"
System should:
  1. Extract all 8 goals
  2. Recognize all 4 pillars covered
  3. Celebrate progress
  4. Transition to Phase 2
Result: ✗ NEEDS FIX #2 & #3
```

### Test Scenario 3: Unrelated Response
```
Question: "What are you doing for your CAREER goal: Become a software engineer?"
User: "I like pizza and watch movies on weekends"
System should:
  1. Recognize response is unrelated
  2. NOT add "watch movies" as a quest
  3. Ask again about the career goal
Result: ✗ NEEDS FIX #1
```

### Test Scenario 4: Pillar Alignment
```
Three separate tests verify that when asking about:
- CAREER: Uses career-specific language
- PHYSICAL: Uses fitness-specific language
- MENTAL: Uses wellbeing-specific language
Result: ✓ WORKING
```

### Test Scenario 5: Stability
```
System receives:
- Empty strings, spaces, random chars
- Very long input (1000+ chars)
- Special characters & emojis
- SQL injection attempts
System should: Handle all without crashing
Result: ✓ WORKING
```
