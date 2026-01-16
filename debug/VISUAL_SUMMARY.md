# DEBUGGING FLOWCHART & QUICK REFERENCE

## Quick Summary

```
START → Run Test Suite → Identify 3 Issues → Fix Each Issue → Validate → DONE
                             ↓
                        Issue #1: Critic
                        Issue #2: Phantom ACKs
                        Issue #3: Celebration
```

## Test Results At a Glance

```
╔════════════════════════════════════════════════════════════════╗
║                    ONBOARDING TEST RESULTS                     ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  TEST 1: Phase 1 - Insufficient Goals        ✓ PASS (4/4)    ║
║  TEST 2: Phase 1 - Excess Goals              ✗ FAIL (3/4)    ║
║  TEST 3: Phase 2 - Unrelated Response        ✗ FAIL (2/4)    ║
║  TEST 4: Pillar Alignment                    ✓ PASS (6/6)    ║
║  TEST 5: Overall Stability                   ✓ PASS (1/1)    ║
║                                                                ║
║  OVERALL SCORE: 3/5 (60%)                                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

## Issue Severity & Impact

```
ISSUE #1: Critic Too Permissive
┌─────────────────────────────────────────┐
│ Severity: CRITICAL                      │
│ Impact: Data Quality                    │
│ Fix Time: 30 min                        │
│ Affects: Test 3                         │
│                                         │
│ Current: "pizza" → Career quest ✗       │
│ After:   "pizza" → Rejected ✓           │
└─────────────────────────────────────────┘

ISSUE #2: Phantom Acknowledgments
┌─────────────────────────────────────────┐
│ Severity: HIGH                          │
│ Impact: User Experience                 │
│ Fix Time: 20 min                        │
│ Affects: Tests 2, 3                     │
│                                         │
│ Current: "Okay, a 1" (phantom) ✗        │
│ After:   Clean response ✓               │
└─────────────────────────────────────────┘

ISSUE #3: Missing Celebration
┌─────────────────────────────────────────┐
│ Severity: MEDIUM                        │
│ Impact: User Engagement                 │
│ Fix Time: 15 min                        │
│ Affects: Test 2                         │
│                                         │
│ Current: Silent transition ✗            │
│ After:   Celebratory message ✓          │
└─────────────────────────────────────────┘
```

## What Each Test Checks

```
┌──────────────────────────────────────────────────────────┐
│ TEST 1: Phase 1 - Insufficient Goals                     │
├──────────────────────────────────────────────────────────┤
│ Scenario: User only mentions 2 pillars                   │
│ Expected: AI asks for other 2 pillars                    │
│ Status:   ✓ WORKING                                      │
│ Checks:   • Goals collected (2)                          │
│           • Missing pillars identified                   │
│           • Question asked about missing                 │
│           • Response is valid                            │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ TEST 2: Phase 1 - Excess Goals                           │
├──────────────────────────────────────────────────────────┤
│ Scenario: User lists many goals (8+) for all 4 pillars   │
│ Expected: AI recognizes completion & celebrates          │
│ Status:   ✗ NEEDS FIXES #2 & #3                          │
│ Checks:   • Multiple goals collected (8+)                │
│           • Response is coherent                         │
│           • No crashes                                   │
│           • Progress acknowledged ✗ MISSING              │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ TEST 3: Phase 2 - Unrelated Response                     │
├──────────────────────────────────────────────────────────┤
│ Scenario: User answers with irrelevant info              │
│ Expected: AI rejects and asks again                      │
│ Status:   ✗ NEEDS FIX #1                                 │
│ Checks:   • No unrelated quest added ✗ FAILING           │
│           • AI mentions goal topic                       │
│           • Response is question                         │
│           • Response shows firmness ✗ FAILING            │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ TEST 4: Pillar Alignment                                 │
├──────────────────────────────────────────────────────────┤
│ Scenario: Verify right question for right pillar         │
│ Expected: Career Q uses career words, Fitness Q uses     │
│           fitness words, etc.                            │
│ Status:   ✓ WORKING PERFECTLY                            │
│ Checks:   • CAREER: career keywords present              │
│           • CAREER: no unrelated keywords                │
│           • PHYSICAL: fitness keywords present           │
│           • PHYSICAL: no unrelated keywords              │
│           • MENTAL: wellbeing keywords present           │
│           • MENTAL: no unrelated keywords                │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ TEST 5: Overall Stability                                │
├──────────────────────────────────────────────────────────┤
│ Scenario: Feed system edge cases & malicious input       │
│ Expected: No crashes, graceful handling                  │
│ Status:   ✓ WORKING                                      │
│ Checks:   • Empty strings → handled                      │
│           • Random chars → handled                       │
│           • Very long input → handled                    │
│           • Special chars & emojis → handled             │
│           • SQL injection attempts → handled             │
└──────────────────────────────────────────────────────────┘
```

## Fix Implementation Sequence

```
FIX #1: Critic Strictness (30 min)
│
├─ Edit: src/onboarding/agent.py
├─ Add: Unrelated input detection rules
├─ Test: Run test 3
└─ Verify: "No quest from unrelated: PASS"
    ↓
FIX #2: Remove Phantom ACKs (20 min)
│
├─ Edit: src/onboarding/agent.py
├─ Change: Only acknowledge when justified
├─ Test: Run test 2
└─ Verify: No "Okay, a 1" phantom responses
    ↓
FIX #3: Celebration Message (15 min)
│
├─ Edit: backend/api.py
├─ Add: Phase transition celebration
├─ Test: Run test 2
└─ Verify: Celebratory language present
    ↓
VALIDATE: All Tests (5 min)
│
├─ Run: all tests
├─ Target: 5/5 passing
└─ Confirm: No regressions
```

## Command Reference

```
┌─────────────────────────────────────────┐
│           COMMAND CHEAT SHEET           │
├─────────────────────────────────────────┤
│                                         │
│  START:        python debug/            │
│                 onboarding_test_suite.py │
│                                         │
│  RUN TESTS:                             │
│    all     → Run all 5 tests            │
│    phase1  → Run tests 1-2              │
│    phase2  → Run tests 3-5              │
│    1-5     → Run individual test        │
│                                         │
│  UTILITIES:                             │
│    menu    → Show menu                  │
│    summary → Show progress              │
│    exit    → Quit                       │
│                                         │
└─────────────────────────────────────────┘
```

## File Organization

```
debug/
├── onboarding_test_suite.py ← USE THIS TO RUN TESTS
│
├── README_ONBOARDING_DEBUG.md ← START HERE
│
├── ONBOARDING_DEBUG_REPORT.md ← FULL ANALYSIS
│   └─ Detailed findings
│   └─ Each issue explained
│   └─ Test results breakdown
│
├── FIXES_IMPLEMENTATION_GUIDE.md ← HOW TO FIX
│   └─ Exact locations
│   └─ Code examples
│   └─ Testing steps
│
└── TEST_SUITE_QUICK_START.md ← QUICK REF
    └─ Fast setup
    └─ Command reference
    └─ Status summary
```

## Problem → Solution Mapping

```
┌─────────────────────────────────────────────────────────┐
│              PROBLEM  →  SOLUTION                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ User: "I like pizza"                                    │
│ Q: "What are you doing for CAREER?"                     │
│                                                         │
│ PROBLEM: Critic adds "likes pizza" as quest ✗           │
│ SOLUTION: Detect unrelated input, reject ✓              │
│ FIX: #1 (Critic strictness)                             │
│                                                         │
│ ─────────────────────────────────────────              │
│                                                         │
│ User: "I want A, B, C, D..." [8 goals]                  │
│ AI Response: "Okay, a 1. Let's move to CAREER..."      │
│                                                         │
│ PROBLEM: Says "a 1" but user never rated ✗              │
│ SOLUTION: Only acknowledge real input ✓                 │
│ FIX: #2 (Remove phantom ACKs)                           │
│                                                         │
│ ─────────────────────────────────────────              │
│                                                         │
│ User: [provides all 4 pillars]                          │
│ AI Response: "Okay, a 1. Now let's talk..."            │
│                                                         │
│ PROBLEM: Doesn't celebrate completion ✗                 │
│ SOLUTION: Add phase transition celebration ✓            │
│ FIX: #3 (Celebration)                                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Success Criteria

```
After implementing all 3 fixes:

✓ Test 1 remains PASS (no regression)
✓ Test 2 becomes PASS (celebration + no phantom ACKs)
✓ Test 3 becomes PASS (strict critic)
✓ Test 4 remains PASS (pillar alignment)
✓ Test 5 remains PASS (stability)

RESULT: 5/5 PASSING (100%) ✓✓✓✓✓
```

## Estimated Timeline

```
┌──────────────────────────────┐
│  IMPLEMENTATION TIMELINE     │
├──────────────────────────────┤
│                              │
│ FIX #1:    ████ 30 minutes   │
│ FIX #2:    ███  20 minutes   │
│ FIX #3:    ██   15 minutes   │
│ Testing:   ██   10 minutes   │
│ Review:    █    5 minutes    │
│                              │
│ TOTAL:     ██████ ~80 min    │
│                              │
└──────────────────────────────┘
```

## What You'll Achieve

```
BEFORE                          AFTER
─────────────────────────────────────────────
❌ 60% tests passing            ✓ 100% tests passing
❌ Critic accepts garbage       ✓ Critic rejects unrelated
❌ Phantom acknowledgments      ✓ Clean responses
❌ No phase celebration         ✓ User feels progress
✓ Alignment perfect             ✓ Alignment stays perfect
✓ Stability good                ✓ Stability maintained
```

---

**Next Step**: Read `README_ONBOARDING_DEBUG.md` for full context

**Then**: Follow `FIXES_IMPLEMENTATION_GUIDE.md` to implement fixes

**Finally**: Use `onboarding_test_suite.py` to validate
