# Profile Selection and Per-Learner Progress Design

## Goal

Add up to five named learner profiles to the ELLA GUI. Each profile owns its
learning history and exact resumable state. The selected profile persists
across application restarts, and the Main Menu immediately identifies it with
`Welcome, <Name>!`.

Profiles use names only in this version. Avatars, PINs, cloud synchronization,
and profile import are outside this scope.

## Current Behavior

ELLA currently has one application-wide resumable checkpoint and one
append-only evaluation history. The Main Menu offers Start and Exit, while
Reset Progress is available in Settings. Start either opens level selection or
offers to continue the one saved session.

This model cannot distinguish learners. Selecting a profile must therefore
change both the checkpoint path and evaluation-history path rather than merely
changing the greeting.

## Selected Architecture

Introduce a `ProfileStore` that exclusively owns profile registry operations:

- list profiles;
- create, rename, and delete profiles;
- get and persist the active profile;
- enforce the five-profile limit;
- validate profile names; and
- derive each profile's data paths.

`ProfileStore` does not serialize curriculum progress. The existing
`SessionCheckpointStore`, `SessionManager`, and `EvaluationService` remain
responsible for exact session state and grading history. `EllaGUIApp` binds
those existing services to the active profile's paths.

Add a `ProfilesScene` for profile selection and management. `MainMenuScene`
will display the active learner, open the new scene, and prevent Start from
continuing without an active profile. `SettingsScene` will no longer manage
learner progress.

## Storage Layout

The profile registry lives beside the configured session-log path. Profile
data uses a sibling `profiles` directory, preserving custom data-location
configuration.

```text
<session-log-parent>/
|-- profiles.json
|-- active_session.json       # legacy; untouched and ignored
|-- sessions.jsonl            # legacy; untouched and ignored
`-- profiles/
    `-- <stable-profile-id>/
        |-- active_session.json
        `-- sessions.jsonl
```

The registry schema is:

```json
{
  "schema_version": 1,
  "active_profile_id": "stable-generated-id",
  "profiles": [
    {
      "id": "stable-generated-id",
      "name": "User",
      "created_at": "2026-07-28T12:00:00+08:00"
    }
  ]
}
```

Profile IDs are generated once and never derived from display names. Renaming
a profile therefore does not rename or relocate its data directory.

The registry is saved with the same atomic write pattern as session
checkpoints: write a temporary file in the destination directory, flush it,
call `os.fsync()`, and replace the destination using `os.replace()`.

Existing application-wide `active_session.json` and `sessions.jsonl` files are
not imported, modified, deleted, or exposed through a profile. New profiles
start with no progress.

## Profile Rules

- ELLA supports zero through five profiles.
- Each profile has a name, stable ID, and creation timestamp.
- Names are trimmed before validation and storage.
- Names must contain 1 through 20 printable characters after trimming.
- Control characters are rejected.
- Names must be unique using Unicode-aware case-insensitive comparison.
- The five-profile limit is enforced by both `ProfileStore` and the scene.
- A missing or invalid active profile ID resolves to no active profile.
- The active profile selection is persisted immediately.

On first launch, ELLA may have no profiles and no active selection. It remains
on the Main Menu and displays `Welcome!` rather than forcing profile creation.

## Main Menu

The Main Menu displays the active learner beneath the ELLA title:

- active profile: `Welcome, Maria!`;
- no active profile: `Welcome!`.

The centered actions are Start, Profiles, and Exit. Their dimensions and gaps
will be calculated from the available inner-card height so all three remain
fully visible without overlapping the title, greeting, bot, or borders at the
supported screen size. The Settings gear remains in the lower-left corner.

Pressing Profiles opens `ProfilesScene`.

Pressing Start without an active profile opens a blocking modal rather than
starting or resuming unowned progress:

- with no profiles: `Create a profile before starting.`;
- with profiles but no selection: `Choose a profile before starting.`.

The modal's primary action opens `ProfilesScene`; Cancel returns to the Main
Menu.

Pressing Start with an active profile preserves the existing behavior within
that profile:

```text
Start
|-- Valid checkpoint for active profile
|   `-- Continue / New Session / Cancel prompt
`-- No checkpoint for active profile
    `-- Level Selection
```

Choosing New Session replaces only the active profile's checkpoint. It does
not affect another profile or the active profile's append-only history.

## Profiles Page

The page title is `Who's Learning?` and the main area uses a two-column card
grid with no more than five learner cards.

Each existing profile card displays:

- profile name;
- `Selected` when it is active;
- `Level <level> - Item <number>` when a valid reading checkpoint exists;
- `Level <level> - Results` when the checkpoint is on results; or
- `Ready to begin` when no valid checkpoint exists.

Clicking the main area of an existing card selects that profile immediately,
persists the selection, binds the application to its storage paths, and
returns to the Main Menu. Clicking a management control must not also select
the card.

A Back action returns to the Main Menu without changing the selection.

While fewer than five profiles exist, an empty `+ Create Profile` card is
shown. At five profiles it is replaced by a clear `5 of 5 profiles` message,
and the service layer independently rejects any sixth creation attempt.

## Profile Creation

Clicking `+ Create Profile` opens a simple name-entry modal. The modal provides
Save and Cancel actions and displays validation or persistence failures inline
without discarding the entered name.

On successful Save:

1. Create the profile and its stable ID.
2. Persist it as the active profile.
3. Bind the app to the profile's checkpoint and history paths.
4. Open the existing Level Selection scene.
5. Let the learner choose any curriculum level.

Confirming a level creates the profile's first reading checkpoint and starts
the existing reading flow. If level selection is cancelled, the new profile
remains selected with `Ready to begin`; pressing Start later opens Level
Selection again.

## Profile Selection and Application Binding

At startup, ELLA loads the registry and restores `active_profile_id`. It does
not restore or begin the learner's session until Start is pressed. The active
ID is used immediately for the greeting and for profile summaries.

Selecting a profile performs this sequence:

1. Validate that the profile is still registered.
2. Persist its ID as active.
3. Point checkpoint operations to
   `profiles/<id>/active_session.json`.
4. Point evaluation history to `profiles/<id>/sessions.jsonl`.
5. Return to the Main Menu and update the greeting.

Profiles can only be switched from the Main Menu. An active reading attempt
therefore cannot be reassigned to another learner. Existing save points,
including attempt completion, results, navigation, and graceful shutdown,
continue to use the current checkpoint orchestration after it is bound to the
profile-specific paths.

Each profile restores the complete state already supported by the checkpoint
system: current level, item, ordered session pools, completed count, attempts,
retry state, evaluation session metadata, and pending results.

## Profile Management

Each profile card provides Rename, Reset Progress, and Delete controls.

### Rename

Rename opens the same name-entry UI with the current name prefilled. On Save,
the new name is validated and the registry is atomically replaced. The stable
ID and profile data paths do not change. If the renamed profile is active, the
Main Menu uses the new name immediately.

### Reset Progress

Reset Progress is removed from Settings and placed only on the Profiles page.
Its confirmation names the affected learner and explains that learning
progress will be erased while the profile remains.

On confirmation, ELLA clears only that profile's checkpoint and evaluation
history. To avoid a half-reset state, the profile data directory is first
renamed to a same-volume staging name. ELLA then creates a fresh directory at
the original profile path. If fresh-directory creation fails, it restores the
staged directory. Once the empty directory is ready, staged-data deletion is
best-effort and an undeletable staged directory remains inaccessible to the
application. The profile remains selected if it was already active. Its card
then shows `Ready to begin`, and Start opens Level Selection. Other profile
folders and the legacy global files are unchanged.

### Delete Profile

Delete uses a stronger confirmation that states the profile and all of its
progress will be removed. On confirmation, ELLA removes the registry entry
atomically, then removes the corresponding profile data folder. If folder
cleanup fails, the unregistered orphan folder is ignored and an error is
logged; it cannot be selected or attached to a newly generated profile ID.

If the deleted profile was active, `active_profile_id` becomes null. ELLA
returns to the generic `Welcome!` state even when other profiles remain; the
user must explicitly choose another learner.

## Settings

The learner-specific Reset Progress button and its confirmation UI are removed
from `SettingsScene`. Settings retains application-wide preferences such as
audio volume and listening duration. No global control may clear every
profile's progress in this version.

## Failure Handling

- A missing registry is treated as an empty registry.
- A malformed or semantically invalid registry is archived with an
  `.invalid-<timestamp>` suffix when possible, then ELLA starts with no
  profiles and no active profile.
- A registry write failure preserves the prior valid file and keeps the scene
  open with an inline error.
- A failed profile selection does not navigate away or change the in-memory
  active profile.
- A missing profile data directory represents a profile with no progress and
  is created when the first checkpoint or history entry is written.
- Invalid per-profile checkpoints retain the existing checkpoint archival and
  recovery behavior and appear as `Ready to begin`.
- Reset and delete errors are reported on the Profiles page. A reset either
  exposes the complete prior data directory or a fresh empty directory, never
  a profile with only one of its two progress files cleared. Any surviving
  registered data is re-read before the scene reports its final state.
- No failure silently falls back to another learner's checkpoint or history.

## Testing

### ProfileStore unit tests

- missing registry produces zero profiles and no active selection;
- registry round-trip preserves profile order and active selection;
- create trims and stores a valid name;
- duplicate names are rejected case-insensitively;
- empty, overlength, non-printable, and control-character names are rejected;
- a sixth profile is rejected;
- rename preserves stable ID and data paths;
- selecting an unknown profile is rejected;
- deleting the active profile clears the active ID;
- reset affects only the target profile's checkpoint and history;
- deleting one profile does not modify another profile;
- atomic replacement preserves the previous registry after a failed save;
- malformed and semantically invalid registries are archived; and
- per-profile checkpoint and history paths are derived correctly beside a
  custom configured session-log location.

### Scene and application tests

- Main Menu shows the selected learner's greeting;
- Main Menu shows `Welcome!` with no active profile;
- Profiles opens the new scene;
- Start without a profile shows the correct create/select modal;
- the modal primary action opens Profiles and Cancel stays on Main Menu;
- Start with a profile uses only that profile's checkpoint summary;
- cards show Selected, Ready to begin, and saved-position states;
- clicking a card selects it and returns to Main Menu;
- management controls do not trigger card selection;
- create and rename modals display validation errors;
- profile creation selects the profile and opens Level Selection;
- cancelling Level Selection preserves a new empty profile;
- five profiles disable creation in the UI;
- Rename, Reset Progress, and Delete confirmations have the specified effects;
- Reset Progress is absent from Settings;
- switching between two profiles restores distinct exact checkpoints,
  attempts, and pending results;
- new-session replacement affects only the active profile;
- graceful shutdown retains the selected profile and its latest stable state;
  and
- the complete existing test suite continues to pass.

## Out of Scope

- More than five profiles
- Avatars or profile colors selected by the user
- PINs, passwords, or parental controls
- Cloud synchronization or sharing profiles between devices
- Importing or automatically assigning legacy global progress
- A global reset-all-profiles action
- Recovering deleted profiles through the user interface
- Changing curriculum levels, pass thresholds, or evaluation behavior
