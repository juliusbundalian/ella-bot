# Level Selection and Exact Session Resume Design

## Goal

Change the main-menu Start flow so every new GUI session begins with a choice
among all thirteen unlocked curriculum levels, while an unfinished saved
session can be resumed at its exact stable state. Preserve the current upward
progression and pass gates after the learner chooses a starting level.

## Current Behavior

The main-menu Start button currently opens `reading_prompt` immediately. Before
the GUI is created, the CLI scans the append-only `sessions.jsonl` evaluation
history and silently selects the level after the most recently passed
sublevel.

This is not exact session recovery:

- attempts are kept only in `EvaluationService` memory until a sublevel ends;
- the active item index and completion count are not persisted;
- randomized Level 2+ session pools are not persisted;
- retry state and pending result screens are not persisted;
- returning to the main menu resets the active level; and
- shutdown does not write a resumable checkpoint.

## Selected Architecture

Use a separate atomic checkpoint document for active state. Keep
`sessions.jsonl` unchanged as append-only grading history.

The checkpoint path is derived from the configured session-log directory and
uses the filename `active_session.json`. This keeps a custom session-log
location and its active checkpoint together without adding another user-facing
setting.

Introduce a `SessionCheckpointStore` with these responsibilities:

- detect and summarize a valid saved session;
- atomically save a complete stable checkpoint;
- validate and restore a checkpoint;
- archive an invalid checkpoint; and
- clear the active checkpoint after an explicit progress reset or completion.

`SessionManager` and `EvaluationService` will expose serialization and
restoration interfaces that use plain dictionaries. The checkpoint store
combines their payloads but does not own curriculum progression or grading
logic.

`EllaGUIApp` will expose the orchestration operations used by scenes:

- `has_saved_session() -> bool`
- `saved_session_summary() -> SavedSessionSummary | None`
- `continue_saved_session() -> str | None`, returning the stable phase to open
- `start_new_session(level: str) -> bool`
- `save_active_session(phase: str, latest_result: dict | None = None) -> bool`
- `clear_active_session() -> None`

Scenes request these operations rather than reading or writing checkpoint
files directly.

## Checkpoint Schema

The top-level document contains only JSON-compatible data:

```json
{
  "schema_version": 1,
  "saved_at": "2026-07-24T12:00:00+08:00",
  "selected_start_level": "2c",
  "phase": "reading",
  "session": {},
  "evaluation": {},
  "latest_result_kind": null,
  "latest_result": null
}
```

`phase` is restricted to `reading` or `results`.

The session payload preserves:

- current level;
- every level index;
- ordered active session pools, including randomized Level 2+ selections;
- expected sentence;
- completed-item count;
- level goal; and
- last announced sentence.

The evaluation payload preserves:

- evaluation session ID;
- original start timestamp;
- attempts grouped by level; and
- completed tier results.

Attempts already made for the current item are represented by the restored
evaluation attempts, which is also the current source used by
`AttemptRunner` to derive retry exhaustion. No duplicate attempt counter is
stored.

For the `results` phase, `latest_result_kind` and `latest_result` preserve the
pending `SubLevelResult` or `TierResult` so recovery opens the results scene
without repeating the last item or appending duplicate evaluation history.

## Main-Menu Start Flow

Clicking Start follows this decision tree:

```text
Start
├─ Valid checkpoint exists
│  └─ Saved Session Found modal
│     ├─ Continue → restore exact state → saved phase
│     ├─ New Session → Level Selection
│     └─ Cancel/close → Main Menu
└─ No valid checkpoint
   └─ Level Selection
```

The modal shows the saved level, one-based item number, and save timestamp.
Continue restores both session and evaluation state before navigating:

- `reading` opens `reading_prompt` and begins the saved item;
- `results` restores the saved result and opens `results`.

The GUI CLI path will no longer call `get_resume_level()` or silently derive a
starting level from `sessions.jsonl`. The existing `--start-level` value may
initialize the app's pre-navigation in-memory session for API compatibility,
but it does not bypass the Start flow or lock any level.

## Level Selection

Add a `LevelSelectionScene` registered as `level_selection`. It displays all
entries from `LEVEL_ORDER`, grouped as:

- Level 1: 1A through 1G;
- Level 2: 2A through 2D;
- Level 3; and
- Level 4.

Every entry is enabled. The scene derives choices from `LEVEL_ORDER` rather
than duplicating a second hard-coded list.

A Back button returns to the main menu without modifying the checkpoint.
Selecting a level opens a confirmation dialog. Confirming calls
`start_new_session(level)`, replaces the previous checkpoint, opens
`reading_prompt`, and begins the selected level. Canceling closes the dialog
without changing saved progress.

The confirmation copy states both the selected level and that previously
saved progress will be replaced.

## New-Session Semantics

`start_new_session(level)` validates the level against `LEVEL_ORDER`, creates
fresh `SessionManager` and `EvaluationService` instances, records the selected
starting level, and prepares a `reading` checkpoint before navigation begins.
It swaps the application to the fresh objects only after that checkpoint is
saved successfully. If saving fails, the old in-memory state and previous
checkpoint remain intact and the level-selection dialog reports the failure.
Starting a new session never deletes the append-only evaluation history.

Starting at any level preserves the existing progression order. For example,
a learner starting at 2C can progress through 2D, 3, and 4. Existing pass
checks remain authoritative: a failing sublevel or tier cannot advance and
continues through the retry or menu path.

## Checkpoint Lifecycle

The checkpoint represents the last stable application phase. It is written:

- after confirming a new starting level;
- after every scored reading attempt;
- after every silent reading attempt;
- after retrying or advancing from results;
- after restarting a level;
- before returning to the main menu;
- and during graceful application shutdown.

The settings Reset Progress action clears both the active checkpoint and the
evaluation history, preserving its existing full-reset meaning. Volume and
listening-duration changes do not touch session checkpoints.

For each reading attempt, saving occurs only after the attempt has been added
to `EvaluationService` and `_advance_after_attempt()` has resolved whether the
learner remains on the item, advances, or finishes the sublevel. This creates
one coherent snapshot. If the application closes during capture, validation,
or speech, recovery returns to the last fully completed attempt and ignores
partial audio.

Checkpoint creation is serialized with a lock inside `SessionCheckpointStore`.
Normal attempt checkpoints are written by the attempt worker only after its
state mutation finishes; result actions run after that worker has exited. On a
graceful quit, the reading scene aborts and joins any active attempt worker
before the app saves the last stable checkpoint. The shutdown path never
snapshots state while an attempt is being mutated.

When a sublevel or tier ends, save `phase = "results"` with its serialized
result. Result actions then update the checkpoint as follows:

- Passed Next: advance, save `reading`, then begin the higher level.
- Failed Retry: reset the failed unit, save `reading`, then begin it.
- Menu after failure: reset the failed unit, save `reading`, then navigate.
- Menu after success with Continue: advance, save `reading`, then navigate.
- Restart from the success confirmation: start a fresh Level 1A session and
  save `reading` before navigating.

`MainMenuScene.on_enter()` must stop resetting the current level, because that
would destroy the position represented by the checkpoint.

After full Level 4 completion, `finish_session()` first appends the final
evaluation history. The application then clears `active_session.json` and
shows `final_eval`. A completed session is not offered as resumable.

The existing Play Again action starts a fresh Level 1A session and creates its
checkpoint before opening the reading prompt.

## Atomicity and Validation

Saving writes a temporary file in the checkpoint directory, flushes it,
calls `os.fsync()`, and replaces the destination with `os.replace()`. A save
failure removes the temporary file when possible and leaves the previous
valid checkpoint untouched.

Restoration validates the complete document before mutating live application
state. Validation includes:

- supported schema version;
- allowed stable phase;
- selected and current levels in `LEVEL_ORDER`;
- item indices within their corresponding ordered pools;
- expected sentence matching the current pool and index;
- nonnegative completion counts and valid level goal;
- attempts containing the required fields and valid primitive types;
- tier results using recognized tier numbers; and
- a compatible pending result for the `results` phase.

If JSON parsing or semantic validation fails, rename the checkpoint using an
`.invalid-<timestamp>` suffix, log the reason, and behave as if no checkpoint
exists. Failure to archive must not prevent startup.

A failed continuation leaves the current in-memory session unchanged, shows
a non-blocking error, and remains on the main menu. A failed save logs the
error, keeps the prior checkpoint, and shows `Progress could not be saved`
without ending the reading session.

## Testing

Persistence unit tests cover:

- `SessionManager` round-trip with exact Level 1 and randomized Level 2+
  ordered pools;
- `EvaluationService` round-trip with attempts, tier results, session ID, and
  start time;
- reading and results checkpoint round-trips;
- atomic replacement;
- previous-checkpoint preservation after a write failure;
- missing checkpoints;
- malformed JSON;
- unsupported schema versions; and
- each semantic validation failure class.

Application and scene tests cover:

- Start without a checkpoint opening level selection;
- Start with a checkpoint opening the resume modal;
- modal summary content;
- Continue restoring the exact item and retry history;
- Continue restoring a pending results screen;
- New Session preserving the checkpoint until confirmation;
- Back and Cancel preserving the checkpoint;
- all thirteen `LEVEL_ORDER` entries rendered and enabled;
- confirmation creating the selected session;
- scored and silent attempts triggering saves after progression;
- pass, fail, retry, next, menu, restart, and Play Again checkpoint updates;
- full completion clearing the checkpoint; and
- GUI startup no longer silently deriving progress from evaluation history.

The complete `tests/` suite must pass after the focused tests.

## Out of Scope

- Multiple named learners or multiple save slots
- Cloud synchronization
- Manual checkpoint management
- Locking levels based on prior performance
- Changing thresholds, grades, item limits, or curriculum content
- Migrating historical `sessions.jsonl` records into exact checkpoints
