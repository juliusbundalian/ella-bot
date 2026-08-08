# Strict Fluency Confidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lower the strict fluency confidence threshold for Levels 3 and 4 from 55% to 35%.

**Architecture:** Keep the threshold in `validators.py`, where strict-fluency matching is performed. Name the constant so the policy is visible, and cover its inclusive boundary with direct validator tests.

**Tech Stack:** Python 3, pytest.

## Global Constraints

- Only strict-fluency validation changes; Levels 1 and 2 remain unaffected.
- A confidence of exactly `0.35` is accepted; a lower confidence is rejected.

---

### Task 1: Lower and document the strict-fluency threshold

**Files:**
- Modify: `tests/test_validators.py`
- Modify: `src/ella_bot/validation/validators.py`

**Interfaces:**
- Produces: `STRICT_FLUENCY_CONFIDENCE: float` used by `align_words` for Levels 3 and 4.

- [ ] **Step 1: Write the failing tests**

```python
def test_strict_fluency_accepts_matching_word_at_35_percent_confidence():
    result = validate_spoken_text(
        "we waited", "we waited",
        spoken_confidences=[0.35, 0.9], strict_fluency=True,
    )
    assert result.accuracy == 1.0


def test_strict_fluency_rejects_matching_word_below_35_percent_confidence():
    result = validate_spoken_text(
        "we waited", "we waited",
        spoken_confidences=[0.34, 0.9], strict_fluency=True,
    )
    assert result.incorrect_words == [("we", "we")]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_validators.py -v -k "35_percent"`

Expected: the first test fails because the current 55% threshold rejects `0.35`.

- [ ] **Step 3: Implement the minimal change**

```python
STRICT_FLUENCY_CONFIDENCE = 0.35

# Enforce a 35% acoustic fluency requirement for higher levels.
if is_match and strict_fluency and spoken_confidences and j - 1 < len(spoken_confidences):
    if spoken_confidences[j - 1] < STRICT_FLUENCY_CONFIDENCE:
        is_match = False
```

- [ ] **Step 4: Run the validator tests**

Run: `.venv/bin/python -m pytest tests/test_validators.py -v`

Expected: PASS.

- [ ] **Step 5: Review the diff**

Run: `git diff -- src/ella_bot/validation/validators.py tests/test_validators.py`

Expected: only the named 35% threshold and its tests are added, apart from pre-existing user changes.
