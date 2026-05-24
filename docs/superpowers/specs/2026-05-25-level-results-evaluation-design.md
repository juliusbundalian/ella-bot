# Level Results & Evaluation Feature

**Date:** 2026-05-25
**Branch:** temp/main
**Goal:** Add per-sub-level and per-tier completion/results screens, an A–F performance evaluation, and durable on-disk session logging for the E.L.L.A. reading tutor (runs on a Raspberry Pi 5).

## Overview

Today, level progression happens silently inside `ReadingPromptScene`/`AttemptRunner`: when `try_level_up` succeeds, the app speaks a "Level up!" line and continues to the next item in the same scene. This feature inserts **results screens** at every sub-level and tier boundary, computes performance stats (fluency %, A–F rating), gates advancement, and writes a durable per-session log that survives power-off.

### Level model

The 13 sub-levels group into 4 **tiers**:

| Tier | Sub-levels |
|------|------------|
| 1 | `1a 1b 1c 1d 1e 1f 1g` |
| 2 | `2a 2b 2c 2d` |
| 3 | `3` |
| 4 | `4` |

### Flow

```
complete 1a → ResultsScene "Sub-Level 1A Complete!"   → [Next] 1b / [Retry] / [Main Menu]
complete 1b → ResultsScene "Sub-Level 1B Complete!"   → [Next] 1c / ...
   ...
complete 1f → ResultsScene "Sub-Level 1F Complete!"   → [Next] 1g
complete 1g → ResultsScene "Level 1 Complete — Level Up!" → [Next] 2a / [Retry Tier] / [Main Menu]
   ...
complete 3  → ResultsScene "Level 3 Complete — Level Up!"  → [Next] 4
complete 4  → FinalEvaluationScene                         → [Play Again] / [Main Menu]
```

Rules:
- **Advancement is user-triggered at every boundary.** Tapping **Next** advances to the next sub-level (or, at a tier boundary, the next tier's first sub-level). The previous silent auto-advance is removed.
- **Completion = every item in the sub-level read correctly** (`completed_in_level >= level_goal`). This is the existing read-loop behaviour: an item only advances on a correct read, so finishing a sub-level already means each item was read correctly. The per-attempt `LEVEL_THRESHOLDS` gate in `try_level_up` is **superseded** — completion no longer depends on it (this also unblocks tiers 3/4 whose threshold is `1.01`). Reading *quality* is now judged by the **fluency** stat at the results screen, not by a last-attempt threshold.
- **No double screen at a tier boundary.** Completing the last sub-level of a tier (`1g`, `2d`, `3`, `4`) shows the **tier** screen only (kind `tier`), not a separate sub-level screen. `3` and `4` are single-sub-level tiers, so they go straight to tier / final screens.
- **Retry** replays the just-completed unit: sub-level kind → replay that sub-level; tier kind → replay the whole tier from its first sub-level.

## Scoring

- **Fluency** = arithmetic mean of every attempt's `validation.accuracy` in scope (per sub-level, per tier, or whole session). Retries are included and pull the average down. This is the headline performance number.
- **"Correct" count.** Because completion requires every item to be read correctly, `items_correct == items_total` at any results screen — a raw "correct / total" would always read 100% and convey nothing. So the meaningful "how many did you get right" stat is **first-try correct**: items read correctly on the *first* attempt (no retry). This is what the results screen shows as the correct count, and it varies with performance.
- **A–F rating** from fluency×100, standard academic bands:
  | Rating | Fluency |
  |--------|---------|
  | A | ≥ 90 |
  | B | 80–89 |
  | C | 70–79 |
  | D | 60–69 |
  | F | < 60 |
- **Pass bar (gates "Next")** = fluency ≥ **0.70 (C)**, configurable. Rationale: tier/sub-level fluency averages in retries, so it runs below the 0.85–0.95 per-attempt progression thresholds; gating at those would mark mastered units as failures. Because sub-level gating already requires passing to reach the screen, in normal play "Next" is enabled and **Retry** is the practice option; the pass bar only ever disables Next on genuinely weak averages.

## Architecture

### New: `services/evaluation.py`

Single owner of attempt accumulation, scoring, and persistence. No pygame dependency (unit-testable).

**Data classes:**
```python
@dataclass
class ItemAttempt:
    item: int
    expected: str
    heard: str
    accuracy: float
    wer: float
    correct: bool
    ts: str

@dataclass
class SubLevelResult:
    tier: int
    level: str            # "1a"
    items_total: int
    first_try_correct: int   # items read correctly on the first attempt
    attempts: int            # total attempts incl. retries
    fluency: float        # 0..1
    rating: str           # "A".."F"
    passed: bool

@dataclass
class TierResult:
    tier: int
    fluency: float
    rating: str
    items_total: int
    first_try_correct: int
    passed: bool

@dataclass
class CumulativeResult:
    overall_fluency: float
    overall_rating: str
    items_total: int
    first_try_correct: int
    tiers: list[TierResult]
    duration_s: float
```

**`EvaluationService`:**
- `__init__(self, log_path: Path, pass_bar: float = 0.70)` — generates a `session_id` (ISO timestamp), records `started_ts`.
- `record_attempt(level, item, expected, heard, accuracy, wer, correct)` — buffers an `ItemAttempt` under the current sub-level.
- `finish_sublevel(level) -> SubLevelResult` — computes the sub-level summary (fluency = mean attempt accuracy; `first_try_correct` = items whose *first* buffered attempt was correct), appends a `sublevel` record (incl. per-item log) to the log, clears that sub-level's item buffer, returns the result.
- `finish_tier(tier) -> TierResult` — aggregates the tier's recorded attempts, appends a `tier` record, returns the result.
- `finish_session() -> CumulativeResult` — aggregates all tiers, appends a `session` record with `started_ts`/`ended_ts`/`duration_s`, returns the result.
- `reset_sublevel(level)` / `reset_tier(tier)` — drop buffered + (in-memory aggregate) stats for a Retry so the replay's numbers are used. (Already-written log records are append-only and remain as history.)
- `_rating(fluency) -> str` — band lookup.
- `_append(record: dict)` — `json.dumps` one line to `log_path` (create parent dirs, open in append mode, flush).

### `SessionManager` additions (`services/session_manager.py`)

Tier helpers; no scoring/IO here.
- `TIER_SUBLEVELS: dict[int, list[str]]` (or derive tier from the leading digit of the level name).
- `tier_of(level) -> int`
- `is_last_sublevel_of_tier(level) -> bool`
- `current_sublevel_complete() -> bool` — `completed_in_level >= level_goal` (all items correct). Does **not** depend on `LEVEL_THRESHOLDS` — this is the fix for tiers 3/4 whose threshold is `1.01` and otherwise never completes.
- `advance_to_next_sublevel_or_tier()` — used by **Next**: advance within tier, or cross into the next tier's first sub-level, resetting the new level.
- `retry_sublevel(level)` — reset that sub-level's index + `completed_in_level`.
- `retry_tier(tier)` — reset all of the tier's sub-level indices, set `current_level` to the tier's first sub-level.

`try_level_up` keeps deciding pass/complete for the *current* sub-level but **no longer performs the advance itself**; advancement moves to the Next button via the methods above.

### New events (`core/events.py`)

```python
@dataclass(frozen=True)
class SubLevelCompleted:
    result: Any        # SubLevelResult or TierResult
    kind: str          # "sublevel" | "tier"

@dataclass(frozen=True)
class SessionCompleted:
    result: Any        # CumulativeResult
```

### `AttemptRunner` changes (`services/attempt_runner.py`)

After scoring an attempt and speaking feedback:
1. `app.evaluation.record_attempt(...)` for every attempt (correct or not).
2. On a correct attempt, increment `completed_in_level` (existing behaviour).
3. Replace the `try_level_up`/auto-advance block with boundary detection:
   - If `session.current_sublevel_complete()`:
     - If `session.is_last_sublevel_of_tier(level)`:
       - If it is the **last tier** (`tier == 4`): `result = evaluation.finish_session()`; post `SessionCompleted(result)`.
       - Else: `evaluation.finish_sublevel(level)` (writes the sub-level record), `result = evaluation.finish_tier(tier)`; post `SubLevelCompleted(result, "tier")`.
     - Else (mid-tier sub-level): `result = evaluation.finish_sublevel(level)`; post `SubLevelCompleted(result, "sublevel")`.
   - Else: stay in the reading loop (next item) as today.
4. Keep the existing "Wow, you leveled up!" TTS line for the `tier` case; add a short congratulatory line for the `sublevel` case.

### `EllaGUIApp` changes (`ui/pygame_gui/app.py`)

- Construct `self.evaluation = EvaluationService(log_path=..., pass_bar=...)` (path + bar from config).
- Register two scenes: `"results"` and `"final_eval"`.
- Hold `self.latest_result` so the results scenes can read the data posted via the event.

### Event handling (`ReadingPromptScene._drain_event_queue`)

- `SubLevelCompleted` → store `app.latest_result` + `kind`, `switch_scene("results")`.
- `SessionCompleted` → store `app.latest_result`, `switch_scene("final_eval")`.

## Scenes

### `ResultsScene` (`ui/pygame_gui/scenes/results.py`)

Reusable for `sublevel` and `tier` kinds — identical layout, different copy. Matches existing card-frame style (black card → white inner → pink borders, pink shadow-rect buttons; constants reused from `main_menu.py`).

- **Headline** (`app.font_title`):
  - `sublevel`: `"Sub-Level {LEVEL} Complete!"`
  - `tier`: `"Level {TIER} Complete — Level Up!"`
- **Stats block** (centered):
  - Big A–F letter (large font, color-coded: A/B green-ish, C amber, D/F red — within existing palette).
  - `"Fluency: {pct}%"`
  - `"Read first try: {first_try_correct} / {items_total}"`
- **Buttons** (shadow-rect, reuse `_draw_button` pattern):
  - **Next** — label `"Next Level"` (tier) / `"Continue"` (sublevel); enabled when `result.passed`, else greyed/disabled.
  - **Retry** — `"Try Again"`; sublevel → `session.retry_sublevel` + `evaluation.reset_sublevel`; tier → `session.retry_tier` + `evaluation.reset_tier`; then `switch_scene("reading_prompt")` and start.
  - **Main Menu** — `switch_scene("main_menu")`.
- **Next handler:** `session.advance_to_next_sublevel_or_tier()`, then `switch_scene("reading_prompt")` and `_start_attempt()`.
- Encouraging subtext under the headline keyed off rating (e.g. A/B "Amazing reading!", C "Nice work!", D/F "Keep practicing — you've got this!").

### `FinalEvaluationScene` (`ui/pygame_gui/scenes/final_eval.py`)

Shown after tier 4. Same card frame.
- **Headline:** `"All Levels Complete!"`
- **Overall** big A–F letter + `"Overall Fluency: {pct}%"`.
- **Per-tier breakdown** — 4 rows: `Level {n}  ·  {RATING}  ·  {pct}%`.
- **Totals:** `"Read first try: {first_try_correct} / {items_total}"`.
- **Buttons:** **Play Again** (`session.reset_to_start()` + new `EvaluationService` session, `switch_scene("reading_prompt")`, start) and **Main Menu**.

## Persistence

**File:** `data/sessions.jsonl`, path overridable via `settings.ini` (`[System] session_log = ./data/sessions.jsonl`). Append-only; parent dir auto-created. On the Pi this lives on the SD card and survives power-off.

**Write timing (incremental):** a `sublevel` record is written when each sub-level finishes (when its results screen appears); a `tier` record at each tier screen; a `session` record after tier 4. An abrupt power-off only loses the sub-level in progress.

**Record shapes** (one JSON object per line; `session_id` ties one playthrough together):

```jsonc
{"type":"sublevel","session_id":"2026-05-25T15:30:45","tier":1,"level":"1a",
 "items_total":2,"first_try_correct":2,"attempts":3,"fluency":0.91,"rating":"A","passed":true,
 "items":[{"item":1,"expected":"a","heard":"a","accuracy":0.95,"wer":0.0,"correct":true,"ts":"..."}],
 "ts":"2026-05-25T15:31:10"}

{"type":"tier","session_id":"2026-05-25T15:30:45","tier":1,"fluency":0.88,"rating":"B",
 "items_total":172,"first_try_correct":150,"passed":true,"ts":"2026-05-25T15:55:02"}

{"type":"session","session_id":"2026-05-25T15:30:45","overall_fluency":0.86,"overall_rating":"B",
 "items_total":735,"first_try_correct":612,"tiers":[{"tier":1,"fluency":0.88,"rating":"B","passed":true}, ...],
 "started_ts":"2026-05-25T15:30:45","ended_ts":"2026-05-25T16:40:00","duration_s":4155,
 "ts":"2026-05-25T16:40:00"}
```

Retrying a unit appends fresh records under the same `session_id`; the log keeps the full journey (grouped/deduped by consumer if needed).

## Testing (TDD)

- `tests/test_evaluation.py` — fluency mean, rating-band boundaries (59/60/69/70/79/80/89/90), pass/fail at the bar, `first_try_correct` counting (first buffered attempt per item, retries don't count), sub-level/tier/session aggregation, per-item log shape, incremental append to a tmp file, reset on retry.
- Extend `tests/test_session_manager.py` — `tier_of`, `is_last_sublevel_of_tier`, `current_sublevel_complete` (incl. tiers 3/4 with `1.01` threshold), `advance_to_next_sublevel_or_tier` across a tier boundary, `retry_sublevel`, `retry_tier`.
- Scene wiring verified manually and via the existing scene-test pattern (`tests/test_settings_scene.py`).

## Files Changed

| File | Change |
|------|--------|
| `src/ella_bot/services/evaluation.py` | **New** — EvaluationService + result dataclasses + JSONL persistence |
| `src/ella_bot/services/session_manager.py` | Add tier helpers; stop `try_level_up` from auto-advancing |
| `src/ella_bot/core/events.py` | Add `SubLevelCompleted`, `SessionCompleted` |
| `src/ella_bot/services/attempt_runner.py` | Record attempts; detect boundaries; post new events |
| `src/ella_bot/ui/pygame_gui/app.py` | Construct EvaluationService; register `results` + `final_eval` scenes; hold `latest_result` |
| `src/ella_bot/ui/pygame_gui/scenes/results.py` | **New** — `ResultsScene` (sublevel + tier kinds) |
| `src/ella_bot/ui/pygame_gui/scenes/final_eval.py` | **New** — `FinalEvaluationScene` |
| `src/ella_bot/ui/pygame_gui/scenes/reading_prompt.py` | Handle new events in `_drain_event_queue` |
| `config/settings.ini` | Add `session_log` path under `[System]` |
| `tests/test_evaluation.py` | **New** |
| `tests/test_session_manager.py` | Add tier-helper tests |

## Out of Scope

- No changes to ASR/TTS engines, validation, or feedback/coaching logic.
- No parent/teacher report viewer or export UI (the JSONL is the data product for now).
- No "retry only weak sub-levels" targeting — Retry replays the whole unit.
- No cross-session trend/history screen inside the app.
- Pass bar and rating bands are constants/config, not a settings-screen UI control.
