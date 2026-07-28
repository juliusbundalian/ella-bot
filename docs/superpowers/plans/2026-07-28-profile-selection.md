# Profile Selection and Per-Learner Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add up to five persistent name-only profiles, each with isolated exact session progress and learning history, plus profile-aware Main Menu, profile management, and level selection.

**Architecture:** A new `ProfileStore` atomically persists a small registry and derives stable-ID-based profile directories. `EllaGUIApp` remains the orchestration boundary: it binds the existing checkpoint and evaluation services to the active profile, while Pygame scenes call app methods instead of touching files. Existing global progress files remain untouched and ignored.

**Tech Stack:** Python 3.9+, pathlib, dataclasses, JSON, UUIDs, atomic `os.replace`, Pygame CE, pytest, unittest.mock.

## Global Constraints

- Support zero through five profiles; enforce the maximum in both service and UI layers.
- Accept trimmed names of 1–20 printable, non-control characters.
- Compare names with `str.casefold()` and reject duplicates.
- Persist profile selection across restarts.
- Give each profile its own `active_session.json` and `sessions.jsonl` under `profiles/<stable-id>/`.
- Restore the exact checkpoint state already supported by ELLA.
- Leave legacy global `active_session.json` and `sessions.jsonl` untouched and ignored.
- Create a new profile with no progress, select it, and open unrestricted level selection.
- Keep `Welcome!` when no profile is active and show `Welcome, <Name>!` otherwise.
- Remove Reset Progress from Settings; provide Rename, Reset Progress, and Delete on Profiles.
- Reset and delete only the targeted learner.
- Do not add avatars, PINs, cloud sync, migration, or a global reset-all action.
- Preserve unrelated working-tree changes; stage only files belonging to the current task.

---

## File Structure

**Create:**

- `src/ella_bot/services/profile_store.py` — profile models, validation, atomic registry persistence, stable paths, reset, and deletion.
- `src/ella_bot/ui/pygame_gui/scenes/profiles.py` — profile cards, name entry, selection, rename, reset, delete, and confirmations.
- `tests/test_profile_store.py` — pure persistence and filesystem behavior.
- `tests/test_profiles_scene.py` — scene state transitions and input behavior.

**Modify:**

- `src/ella_bot/ui/pygame_gui/app.py` — profile-store lifecycle and profile-scoped checkpoint/evaluation binding.
- `src/ella_bot/ui/pygame_gui/scenes/main_menu.py` — greeting, Profiles button, and guarded Start prompt.
- `src/ella_bot/ui/pygame_gui/scenes/settings.py` — remove global progress reset.
- `tests/test_app_session_flow.py` — require and verify active profiles in session flows.
- `tests/test_main_menu_scene.py` — greeting/navigation/guard tests.
- `tests/test_settings_scene.py` — remove obsolete reset behavior and assert Settings stays app-wide.

Do not modify `SessionManager`, `SessionCheckpointStore`, or the checkpoint schema. Profile isolation is achieved by constructing those services with profile-specific paths.

---

### Task 1: Atomic profile registry and validation

**Files:**
- Create: `src/ella_bot/services/profile_store.py`
- Create: `tests/test_profile_store.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `datetime.now().astimezone()`, `uuid.uuid4().hex`.
- Produces: `Profile`, `ProfileStore`, `ProfileStoreError`, `ProfileValidationError`, `ProfileLimitError`, and `ProfileNotFoundError`.
- Produces exact methods: `list_profiles() -> tuple[Profile, ...]`, `active_profile() -> Profile | None`, `create(name: str) -> Profile`, `rename(profile_id: str, name: str) -> Profile`, `select(profile_id: str) -> Profile`, `checkpoint_path(profile_id: str) -> Path`, and `history_path(profile_id: str) -> Path`.

- [ ] **Step 1: Write failing creation, persistence, and path tests**

```python
# tests/test_profile_store.py
import json

import pytest

from ella_bot.services.profile_store import (
    ProfileLimitError,
    ProfileNotFoundError,
    ProfileStore,
    ProfileValidationError,
)


def test_missing_registry_starts_empty(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    assert store.list_profiles() == ()
    assert store.active_profile() is None


def test_create_persists_profile_as_active(tmp_path):
    path = tmp_path / "profiles.json"
    created = ProfileStore(path).create("  Maria  ")
    restored = ProfileStore(path)

    assert created.name == "Maria"
    assert restored.list_profiles() == (created,)
    assert restored.active_profile() == created
    assert restored.checkpoint_path(created.id) == (
        tmp_path / "profiles" / created.id / "active_session.json"
    )
    assert restored.history_path(created.id) == (
        tmp_path / "profiles" / created.id / "sessions.jsonl"
    )


@pytest.mark.parametrize("name", ["", "   ", "x" * 21, "A\nB", "A\x00B"])
def test_invalid_names_are_rejected(tmp_path, name):
    store = ProfileStore(tmp_path / "profiles.json")
    with pytest.raises(ProfileValidationError):
        store.create(name)


def test_names_are_unique_by_casefold(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    store.create("Maria")
    with pytest.raises(ProfileValidationError):
        store.create("mARIA")


def test_sixth_profile_is_rejected(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    for index in range(5):
        store.create(f"Reader {index}")
    with pytest.raises(ProfileLimitError):
        store.create("Reader 6")


def test_rename_preserves_id_and_paths(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create("Old")
    before = store.checkpoint_path(profile.id)

    renamed = store.rename(profile.id, "New")

    assert renamed.id == profile.id
    assert renamed.name == "New"
    assert store.checkpoint_path(profile.id) == before


def test_select_unknown_profile_is_rejected(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    with pytest.raises(ProfileNotFoundError):
        store.select("missing")
```

- [ ] **Step 2: Run the focused tests and verify the import fails**

Run: `pytest -q tests/test_profile_store.py`

Expected: collection fails with `ModuleNotFoundError: No module named 'ella_bot.services.profile_store'`.

- [ ] **Step 3: Implement models, validation, registry loading, and atomic writes**

Create these public types and constants:

```python
# src/ella_bot/services/profile_store.py
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

SCHEMA_VERSION = 1
MAX_PROFILES = 5


class ProfileStoreError(Exception):
    pass


class ProfileValidationError(ProfileStoreError):
    pass


class ProfileLimitError(ProfileStoreError):
    pass


class ProfileNotFoundError(ProfileStoreError):
    pass


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    created_at: str
```

Implement `ProfileStore.__init__(registry_path)` so `profiles_root` is always
`registry_path.parent / "profiles"`. Validate loaded JSON before assigning
in-memory state:

```python
class ProfileStore:
    def __init__(self, registry_path: Path) -> None:
        self.registry_path = Path(registry_path)
        self.profiles_root = self.registry_path.parent / "profiles"
        self._profiles: tuple[Profile, ...] = ()
        self._active_profile_id: str | None = None
        self._load()

    def list_profiles(self) -> tuple[Profile, ...]:
        return self._profiles

    def active_profile(self) -> Profile | None:
        return next(
            (p for p in self._profiles if p.id == self._active_profile_id),
            None,
        )

    def checkpoint_path(self, profile_id: str) -> Path:
        self._require_profile(profile_id)
        return self.profiles_root / profile_id / "active_session.json"

    def history_path(self, profile_id: str) -> Path:
        self._require_profile(profile_id)
        return self.profiles_root / profile_id / "sessions.jsonl"
```

Name validation must use `trimmed = name.strip()`, reject non-strings,
lengths outside 1–20, and any `not character.isprintable()`. Compare
`trimmed.casefold()` against every other profile except the profile currently
being renamed.

`_write(profiles, active_profile_id)` must serialize exactly
`schema_version`, `active_profile_id`, and `profiles`; create the parent;
write through `tempfile.NamedTemporaryFile(delete=False, dir=parent,
encoding="utf-8", mode="w")`; call `json.dump`, `flush`, and `os.fsync`; then
call `os.replace`. Remove the temporary path on failure. Update `_profiles`
and `_active_profile_id` only after `_write` succeeds.

`create()` generates `uuid4().hex`, records
`datetime.now().astimezone().isoformat(timespec="seconds")`, appends the
profile, and makes it active in the same registry write. `rename()` uses
`dataclasses.replace`. `select()` writes the existing profile collection with
the new active ID.

`_load()` must validate exact top-level fields, schema version 1, a list of no
more than five exact profile objects, 32-character lowercase hexadecimal IDs,
unique IDs, valid unique names, timezone-aware ISO timestamps, and either a
null active ID or an ID in the registry. Archive invalid input using
`profiles.json.invalid-YYYYMMDDTHHMMSSffffff`; if archiving fails, log the
failure and still start empty.

- [ ] **Step 4: Add corruption and failed-write tests**

```python
def test_corrupt_registry_is_archived(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text("{broken", encoding="utf-8")

    store = ProfileStore(path)

    assert store.list_profiles() == ()
    assert not path.exists()
    assert len(list(tmp_path.glob("profiles.json.invalid-*"))) == 1


def test_failed_replace_preserves_registry_and_memory(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    store = ProfileStore(path)
    first = store.create("First")
    original = path.read_bytes()
    monkeypatch.setattr(
        "ella_bot.services.profile_store.os.replace",
        lambda *_: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError):
        store.create("Second")

    assert path.read_bytes() == original
    assert store.list_profiles() == (first,)
    assert store.active_profile() == first
```

- [ ] **Step 5: Run the profile-store tests**

Run: `pytest -q tests/test_profile_store.py`

Expected: all tests pass.

- [ ] **Step 6: Commit the registry unit**

```bash
git add src/ella_bot/services/profile_store.py tests/test_profile_store.py
git commit -m "feat: add persistent learner profile registry"
```

---

### Task 2: Profile-scoped reset and deletion

**Files:**
- Modify: `src/ella_bot/services/profile_store.py`
- Modify: `tests/test_profile_store.py`

**Interfaces:**
- Consumes: Task 1 `ProfileStore` registry and path methods.
- Produces: `reset_progress(profile_id: str) -> bool` and `delete(profile_id: str) -> bool`; the boolean reports whether stale-folder cleanup completed.

- [ ] **Step 1: Write failing isolation and active-deletion tests**

```python
def _write_progress(store, profile, checkpoint=b"checkpoint", history=b"history"):
    checkpoint_path = store.checkpoint_path(profile.id)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(checkpoint)
    store.history_path(profile.id).write_bytes(history)


def test_reset_progress_keeps_profile_and_other_profile_data(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    first = store.create("First")
    second = store.create("Second")
    _write_progress(store, first)
    _write_progress(store, second, b"other-checkpoint", b"other-history")

    assert store.reset_progress(first.id) is True

    assert store.checkpoint_path(first.id).exists() is False
    assert store.history_path(first.id).exists() is False
    assert store.history_path(second.id).read_bytes() == b"other-history"
    assert store.list_profiles() == (first, second)


def test_delete_active_profile_clears_selection_only(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    first = store.create("First")
    second = store.create("Second")
    _write_progress(store, second)

    assert store.delete(second.id) is True

    assert store.list_profiles() == (first,)
    assert store.active_profile() is None
    assert not (tmp_path / "profiles" / second.id).exists()
```

- [ ] **Step 2: Run both tests and verify missing-method failures**

Run: `pytest -q tests/test_profile_store.py -k "reset_progress or delete_active"`

Expected: FAIL with missing `reset_progress` and `delete` attributes.

- [ ] **Step 3: Implement an all-or-nothing visible reset**

```python
def reset_progress(self, profile_id: str) -> bool:
    self._require_profile(profile_id)
    profile_dir = self.profiles_root / profile_id
    if not profile_dir.exists():
        return True
    staged = self.profiles_root / (
        f".{profile_id}.reset-{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"
    )
    profile_dir.replace(staged)
    try:
        profile_dir.mkdir(parents=True, exist_ok=False)
    except Exception:
        staged.replace(profile_dir)
        raise
    try:
        shutil.rmtree(staged)
        return True
    except OSError as exc:
        logger.warning("Unable to remove staged profile reset data: %s", exc)
        return False
```

Import `shutil` and initialize a module logger through the existing
`ella_bot.utils.logging.get_logger` helper. Staged directories start with `.`
and are never considered registered profile directories.

- [ ] **Step 4: Implement registry-first deletion**

`delete()` must resolve the profile first, create the candidate tuple without
it, set the candidate active ID to `None` when deleting the active profile,
and atomically write that registry before touching the data directory. Then
call `shutil.rmtree(profile_dir)` when it exists. Log and return `False` if
cleanup fails; do not restore the registry entry.

- [ ] **Step 5: Test reset rollback and delete cleanup failure**

```python
def test_reset_restores_original_directory_when_recreation_fails(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create("Reader")
    _write_progress(store, profile)
    original_mkdir = Path.mkdir

    def fail_profile_recreation(path, *args, **kwargs):
        if path == tmp_path / "profiles" / profile.id:
            raise OSError("mkdir failed")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_profile_recreation)
    with pytest.raises(OSError):
        store.reset_progress(profile.id)
    assert store.checkpoint_path(profile.id).read_bytes() == b"checkpoint"


def test_delete_cleanup_failure_leaves_no_registered_profile(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path / "profiles.json")
    profile = store.create("Reader")
    _write_progress(store, profile)
    monkeypatch.setattr(
        "ella_bot.services.profile_store.shutil.rmtree",
        lambda *_: (_ for _ in ()).throw(OSError("busy")),
    )

    assert store.delete(profile.id) is False
    assert store.list_profiles() == ()
    assert store.active_profile() is None
```

- [ ] **Step 6: Run and commit**

Run: `pytest -q tests/test_profile_store.py`

Expected: all tests pass.

```bash
git add src/ella_bot/services/profile_store.py tests/test_profile_store.py
git commit -m "feat: isolate profile reset and deletion"
```

---

### Task 3: Bind application session services to the active profile

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/app.py:1-344`
- Modify: `tests/test_app_session_flow.py`

**Interfaces:**
- Consumes: Task 1 and 2 `ProfileStore`, `Profile`, and profile path methods.
- Produces app methods: `profiles()`, `active_profile()`, `create_profile(name)`, `rename_profile(profile_id, name)`, `select_profile(profile_id)`, `reset_profile_progress(profile_id)`, `delete_profile(profile_id)`, and `profile_session_summary(profile_id)`.
- Preserves existing `saved_session_summary()`, `start_new_session()`, `continue_saved_session()`, and `save_active_session()` signatures.

- [ ] **Step 1: Update the app test helper and write failing binding tests**

```python
# tests/test_app_session_flow.py
def _make_app(tmp_path, *, create_profile=False):
    app = EllaGUIApp(
        expected_sentence="",
        asr=MagicMock(),
        tts=None,
        audio_feedback=False,
        pronunciation_overrides={},
        config=GUIConfig(session_log_path=tmp_path / "sessions.jsonl"),
    )
    if create_profile and app.active_profile() is None:
        app.create_profile("Reader")
    return app


def test_new_session_requires_active_profile(tmp_path):
    app = _make_app(tmp_path)
    assert app.start_new_session("1a") is False
    assert not (tmp_path / "active_session.json").exists()


def test_profile_selection_persists_and_binds_paths(tmp_path):
    app = _make_app(tmp_path)
    first = app.create_profile("First")
    second = app.create_profile("Second")
    app.select_profile(first.id)

    restarted = _make_app(tmp_path)

    assert restarted.active_profile() == first
    assert restarted.checkpoint_store.path == (
        tmp_path / "profiles" / first.id / "active_session.json"
    )
    assert restarted.evaluation.log_path == (
        tmp_path / "profiles" / first.id / "sessions.jsonl"
    )
```

Use the existing public `SessionCheckpointStore.path` attribute in both the
test and implementation.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q tests/test_app_session_flow.py -k "requires_active_profile or persists_and_binds"`

Expected: FAIL because profile methods do not exist and the current app still
uses global paths.

- [ ] **Step 3: Initialize ProfileStore and add one binding method**

In `EllaGUIApp.__init__`, retain the requested `start_level` as
`self._default_start_level`, construct the registry at
`self.config.session_log_path.parent / "profiles.json"`, then call
`self._bind_profile(self.profile_store.active_profile())`.

```python
def _bind_profile(self, profile: Profile | None) -> None:
    self.session = SessionManager.from_config_file(
        start_level=self._default_start_level,
        hard_sentences=self._hard_sentences,
        seed_sentence=self._seed_sentence,
    )
    if profile is None:
        base = self.profile_store.profiles_root / "_unowned"
        history_path = base / "sessions.jsonl"
        checkpoint_path = base / "active_session.json"
    else:
        history_path = self.profile_store.history_path(profile.id)
        checkpoint_path = self.profile_store.checkpoint_path(profile.id)
    self.evaluation = EvaluationService(history_path, self.config.pass_bar)
    self.checkpoint_store = SessionCheckpointStore(checkpoint_path)
    self.selected_start_level = None
    self.checkpoint_phase = None
    self.checkpoint_latest_result = None
    self.latest_result = None
    self.latest_result_kind = None
```

The `_unowned` paths must never be created because all session entry points
are guarded. They avoid pointing any service at the legacy global files.

- [ ] **Step 4: Add profile orchestration methods**

```python
def profiles(self) -> tuple[Profile, ...]:
    return self.profile_store.list_profiles()

def active_profile(self) -> Profile | None:
    return self.profile_store.active_profile()

def create_profile(self, name: str) -> Profile:
    profile = self.profile_store.create(name)
    self._bind_profile(profile)
    return profile

def rename_profile(self, profile_id: str, name: str) -> Profile:
    return self.profile_store.rename(profile_id, name)

def select_profile(self, profile_id: str) -> Profile:
    profile = self.profile_store.select(profile_id)
    self._bind_profile(profile)
    return profile

def reset_profile_progress(self, profile_id: str) -> bool:
    cleaned = self.profile_store.reset_progress(profile_id)
    active = self.active_profile()
    if active is not None and active.id == profile_id:
        self._bind_profile(active)
    return cleaned

def delete_profile(self, profile_id: str) -> bool:
    was_active = self.active_profile()
    cleaned = self.profile_store.delete(profile_id)
    if was_active is not None and was_active.id == profile_id:
        self._bind_profile(None)
    return cleaned
```

`profile_session_summary(profile_id)` creates a temporary
`SessionCheckpointStore` for that profile and calls `summary()` using the
current curriculum pools, that profile's history path, and `config.pass_bar`.

- [ ] **Step 5: Guard all session operations**

At the top of `saved_session_summary`, `start_new_session`,
`save_active_session`, and `continue_saved_session`, return `None` or `False`
when `active_profile()` is `None`. `shutdown()` must save only when a profile
is active and a session has started. `clear_active_session()` continues to
clear the current checkpoint but never clears profile selection.

Update all existing tests that start sessions to call
`_make_app(tmp_path, create_profile=True)`. For restart tests, create the
profile only in the first app; the replacement must discover the persisted
active selection itself.

- [ ] **Step 6: Add exact cross-profile restore test**

```python
def test_profiles_restore_distinct_exact_sessions(tmp_path):
    app = _make_app(tmp_path)
    first = app.create_profile("First")
    assert app.start_new_session("1a")
    app.session.advance_to_next_sentence()
    app.save_active_session("reading")

    second = app.create_profile("Second")
    assert app.start_new_session("2c")
    app.save_active_session("reading")

    app.select_profile(first.id)
    assert app.continue_saved_session() == "reading"
    assert app.current_level == "1a"
    assert app.session.current_item_number() == 2

    app.select_profile(second.id)
    assert app.continue_saved_session() == "reading"
    assert app.current_level == "2c"
    assert app.session.current_item_number() == 1
```

- [ ] **Step 7: Run app and checkpoint tests, then commit**

Run: `pytest -q tests/test_app_session_flow.py tests/test_session_checkpoint.py`

Expected: all tests pass and no file appears at the legacy
`tmp_path / "active_session.json"` location.

```bash
git add src/ella_bot/ui/pygame_gui/app.py tests/test_app_session_flow.py
git commit -m "feat: bind sessions to active learner profiles"
```

---

### Task 4: Profiles page browsing, creation, and selection

**Files:**
- Create: `src/ella_bot/ui/pygame_gui/scenes/profiles.py`
- Create: `tests/test_profiles_scene.py`
- Modify: `src/ella_bot/ui/pygame_gui/app.py:334-342`

**Interfaces:**
- Consumes: Task 3 app profile methods and `SavedSessionSummary` fields `level`, `item_number`, and `phase`.
- Produces: `ProfilesScene`, registered under scene key `"profiles"`.

- [ ] **Step 1: Write failing scene behavior tests**

```python
# tests/test_profiles_scene.py
from unittest.mock import MagicMock

import pygame

from ella_bot.services.profile_store import Profile
from ella_bot.ui.pygame_gui.scenes.profiles import ProfilesScene


def _scene():
    pygame.font.init()
    app = MagicMock()
    app.screen = pygame.Surface((1280, 720))
    app.font_title = pygame.font.SysFont(None, 64)
    app.font_body = pygame.font.SysFont(None, 30)
    app.font_small = pygame.font.SysFont(None, 22)
    app.font_button = pygame.font.SysFont(None, 42)
    app.profiles.return_value = ()
    app.active_profile.return_value = None
    return ProfilesScene(app)


def test_empty_page_exposes_create_card():
    scene = _scene()
    scene.render()
    assert scene.create_button is not None


def test_clicking_profile_selects_and_returns_to_menu():
    scene = _scene()
    profile = Profile("a" * 32, "Maria", "2026-07-28T12:00:00+08:00")
    scene.app.profiles.return_value = (profile,)

    scene._select_profile(profile.id)

    scene.app.select_profile.assert_called_once_with(profile.id)
    scene.app.switch_scene.assert_called_once_with("main_menu")


def test_successful_creation_selects_and_opens_level_selection():
    scene = _scene()
    created = Profile("b" * 32, "Leo", "2026-07-28T12:00:00+08:00")
    scene.app.create_profile.return_value = created
    scene.name_input = " Leo "

    scene._save_name()

    scene.app.create_profile.assert_called_once_with(" Leo ")
    scene.app.switch_scene.assert_called_once_with("level_selection")
```

- [ ] **Step 2: Run the tests and verify the scene import fails**

Run: `pytest -q tests/test_profiles_scene.py`

Expected: collection fails because `ProfilesScene` does not exist.

- [ ] **Step 3: Implement scene state, navigation, and name input**

`ProfilesScene` must extend `BaseScene` and initialize:

```python
self.profile_cards: dict[str, pygame.Rect] = {}
self.manage_buttons: dict[tuple[str, str], pygame.Rect] = {}
self.create_button: pygame.Rect | None = None
self.back_button: pygame.Rect | None = None
self.modal: str | None = None
self.target_profile_id: str | None = None
self.name_input = ""
self.error_message = ""
self.pressed_button: str | None = None
```

Use `modal == "create"` for initial creation. `_open_create()` clears the
input/error, starts Pygame text input, and does nothing when five profiles
already exist. `handle_event()` processes `pygame.TEXTINPUT` only while a name
modal is open, appending text only while the candidate remains at most 20
characters. Handle Backspace, Enter/Keypad Enter, and Escape through
`pygame.KEYDOWN`. Always call `pygame.key.stop_text_input()` when closing the
modal or leaving the scene.

```python
def _save_name(self) -> None:
    try:
        self.app.create_profile(self.name_input)
    except (ProfileStoreError, OSError) as exc:
        self.error_message = str(exc) or "Profile could not be saved."
        return
    self._close_modal()
    self.app.switch_scene("level_selection")

def _select_profile(self, profile_id: str) -> None:
    try:
        self.app.select_profile(profile_id)
    except (ProfileStoreError, OSError) as exc:
        self.error_message = str(exc) or "Profile could not be selected."
        return
    self.app.switch_scene("main_menu")
```

- [ ] **Step 4: Implement the two-column layout and summaries**

Follow the existing white card, dark outer frame, pink inner border, button
shadow, and rounded-corner style from `LevelSelectionScene`. Draw at most five
cards in a two-column grid. Each card reserves its lower strip for management
buttons so the card selection hitbox does not overlap them.

For each profile, call `app.profile_session_summary(profile.id)` and render:

```python
def _summary_text(summary) -> str:
    if summary is None:
        return "Ready to begin"
    level = summary.level.upper()
    if summary.phase == "results":
        return f"Level {level} - Results"
    return f"Level {level} - Item {summary.item_number}"
```

Show `Selected` on the active profile. Show `+ Create Profile` while
`len(app.profiles()) < 5`; otherwise show `5 of 5 profiles` as noninteractive
text. Keep a Back button at the bottom-left.

- [ ] **Step 5: Register the scene**

Import `ProfilesScene` in `app.py` and add
`"profiles": ProfilesScene(self)` to the scene dictionary.

- [ ] **Step 6: Add rendering/input tests and run them**

Add tests that render five profiles and assert `create_button is None`, send
`TEXTINPUT` plus Backspace to a creation modal, verify a service validation
exception leaves the modal open with an error, and verify Back returns to
`main_menu` without calling `select_profile`.

Run: `pytest -q tests/test_profiles_scene.py tests/test_app_session_flow.py`

Expected: all tests pass.

- [ ] **Step 7: Commit the creation and selection UI**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py src/ella_bot/ui/pygame_gui/app.py tests/test_profiles_scene.py
git commit -m "feat: add learner profile selection page"
```

---

### Task 5: Rename, reset, and delete controls

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/profiles.py`
- Modify: `tests/test_profiles_scene.py`

**Interfaces:**
- Consumes: Task 3 `rename_profile`, `reset_profile_progress`, and `delete_profile` app methods.
- Produces modal states `"rename"`, `"reset"`, and `"delete"` with explicit target IDs.

- [ ] **Step 1: Write failing management tests**

```python
def test_rename_prefills_and_saves_without_selecting():
    scene = _scene()
    profile = Profile("a" * 32, "Old", "2026-07-28T12:00:00+08:00")
    scene._open_rename(profile)
    assert scene.name_input == "Old"
    scene.name_input = "New"

    scene._save_name()

    scene.app.rename_profile.assert_called_once_with(profile.id, "New")
    scene.app.select_profile.assert_not_called()
    scene.app.switch_scene.assert_not_called()


def test_reset_targets_only_named_profile():
    scene = _scene()
    profile = Profile("a" * 32, "Maria", "2026-07-28T12:00:00+08:00")
    scene._open_confirmation("reset", profile)
    scene._confirm_management()
    scene.app.reset_profile_progress.assert_called_once_with(profile.id)


def test_delete_active_profile_returns_to_generic_main_menu():
    scene = _scene()
    profile = Profile("a" * 32, "Maria", "2026-07-28T12:00:00+08:00")
    scene.app.active_profile.return_value = profile
    scene._open_confirmation("delete", profile)

    scene._confirm_management()

    scene.app.delete_profile.assert_called_once_with(profile.id)
    scene.app.switch_scene.assert_called_once_with("main_menu")
```

- [ ] **Step 2: Run focused tests and verify missing-state failures**

Run: `pytest -q tests/test_profiles_scene.py -k "rename or reset or delete"`

Expected: FAIL because management modal helpers are absent.

- [ ] **Step 3: Implement management actions and interception**

Add three small controls to every profile card and check them before the main
card hitbox in mouse-down handling. Encode keys as `rename:<id>`, `reset:<id>`,
and `delete:<id>`.

`_open_rename(profile)` sets `modal = "rename"`, stores the ID, prefills the
name, and starts text input. `_save_name()` branches by modal:

```python
if self.modal == "create":
    self.app.create_profile(self.name_input)
    destination = "level_selection"
else:
    self.app.rename_profile(self.target_profile_id, self.name_input)
    destination = None
```

After a successful rename, close the modal and remain on Profiles. This lets
the user immediately see the new name and avoids changing active selection.

`_open_confirmation(action, profile)` stores the exact action, target ID, and
target name. Render these exact meanings:

- Reset: `Erase all learning progress for Maria? The profile will remain.`
- Delete: `Delete Maria and all saved progress? This cannot be undone.`

`_confirm_management()` calls the matching app method. A reset remains on the
Profiles page and refreshes the card to `Ready to begin`. A delete remains on
Profiles when deleting an inactive profile; deleting the active profile
returns to Main Menu. A `False` cleanup return displays
`Some old profile files could not be removed.` while still reflecting the
successful logical reset/delete.

- [ ] **Step 4: Test hitbox precedence and failures**

Render a card, click its Rename rectangle, and assert
`app.select_profile` was not called. Add one test where `rename_profile`
raises `OSError("full")` and assert the rename modal remains open with an
error. Add one test where reset returns `False` and assert the cleanup warning
is rendered in `error_message`.

- [ ] **Step 5: Run and commit**

Run: `pytest -q tests/test_profiles_scene.py tests/test_profile_store.py`

Expected: all tests pass.

```bash
git add src/ella_bot/ui/pygame_gui/scenes/profiles.py tests/test_profiles_scene.py
git commit -m "feat: manage individual learner profiles"
```

---

### Task 6: Profile-aware Main Menu

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/main_menu.py:20-283`
- Modify: `tests/test_main_menu_scene.py`

**Interfaces:**
- Consumes: Task 3 `active_profile()` and `profiles()` and Task 4 scene key `"profiles"`.
- Produces: Profiles navigation, active greeting, and `show_profile_required_prompt` state.

- [ ] **Step 1: Write failing Start-guard and navigation tests**

```python
from ella_bot.services.profile_store import Profile


def test_start_without_profiles_opens_create_profile_prompt():
    scene = _scene()
    scene.app.active_profile.return_value = None
    scene.app.profiles.return_value = ()

    scene._do_start()

    assert scene.show_profile_required_prompt is True
    assert scene.profile_required_message == "Create a profile before starting."
    scene.app.saved_session_summary.assert_not_called()


def test_start_without_selection_opens_choose_profile_prompt():
    scene = _scene()
    scene.app.active_profile.return_value = None
    scene.app.profiles.return_value = (
        Profile("a" * 32, "Maria", "2026-07-28T12:00:00+08:00"),
    )
    scene._do_start()
    assert scene.profile_required_message == "Choose a profile before starting."


def test_profiles_action_opens_profiles_scene():
    scene = _scene()
    scene._do_profiles()
    scene.app.switch_scene.assert_called_once_with("profiles")
```

- [ ] **Step 2: Run focused tests and verify failures**

Run: `pytest -q tests/test_main_menu_scene.py -k "profile"`

Expected: FAIL because the profile guard and navigation do not exist.

- [ ] **Step 3: Add state and event routing**

Initialize and reset `show_profile_required_prompt`,
`profile_required_message`, `menu_profiles_button`,
`profile_required_open_button`, and `profile_required_cancel_button`.
Modal event routing takes precedence over resume and exit modals.

```python
def _do_profiles(self) -> None:
    self.app.switch_scene("profiles")

def _do_start(self) -> None:
    if self.app.active_profile() is None:
        self.profile_required_message = (
            "Create a profile before starting."
            if not self.app.profiles()
            else "Choose a profile before starting."
        )
        self.show_profile_required_prompt = True
        return
    summary = self.app.saved_session_summary()
    if summary is None:
        self.app.switch_scene("level_selection")
        return
    self.resume_summary = summary
    self.show_resume_prompt = True
```

The modal primary button closes the modal and opens `profiles`; Cancel only
closes the modal.

- [ ] **Step 4: Draw greeting and three actions**

Render beneath the title:

```python
profile = self.app.active_profile()
greeting = "Welcome!" if profile is None else f"Welcome, {profile.name}!"
```

Use `font_body` and `_TEXT`/dark text. Calculate the vertical button area from
the greeting bottom to `inner_rect.bottom - 36`. Fit Start, Profiles, and Exit
there with a shared height capped at 72 pixels and a gap capped at 16 pixels.
Keep the existing 300-pixel maximum width. Verify none overlaps the bot or
Settings gear at 1280x720.

- [ ] **Step 5: Add rendering and persisted-greeting tests**

Initialize Pygame fonts/surface in a rendering helper, render with and without
an active profile, and assert all three button rectangles are inside
`inner_rect` and non-overlapping. Test a real app restart in
`test_app_session_flow.py`: create/select Maria, construct a replacement app,
and assert `replacement.active_profile().name == "Maria"`.

- [ ] **Step 6: Run and commit**

Run: `pytest -q tests/test_main_menu_scene.py tests/test_app_session_flow.py`

Expected: all tests pass.

```bash
git add src/ella_bot/ui/pygame_gui/scenes/main_menu.py tests/test_main_menu_scene.py tests/test_app_session_flow.py
git commit -m "feat: make main menu profile aware"
```

---

### Task 7: Remove Settings reset and verify the complete feature

**Files:**
- Modify: `src/ella_bot/ui/pygame_gui/scenes/settings.py:20-285`
- Modify: `tests/test_settings_scene.py`
- Modify: `tests/test_gui_e2e.py`

**Interfaces:**
- Consumes: Profile-page Reset Progress from Task 5.
- Produces: Settings containing only application-wide controls.

- [ ] **Step 1: Replace the obsolete Settings reset test**

Delete `test_reset_progress_clears_checkpoint_before_returning_to_menu` and add:

```python
def test_settings_has_no_profile_reset_state():
    scene = _make_scene()
    assert not hasattr(scene, "show_reset_confirm")
    assert not hasattr(scene, "btn_reset")
    assert not hasattr(scene, "_reset_progress")
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `pytest -q tests/test_settings_scene.py::test_settings_has_no_profile_reset_state`

Expected: FAIL because reset state and behavior still exist.

- [ ] **Step 3: Remove Reset Progress from Settings**

Remove `_DANGER`, `_DANGER_PRESSED`, `_DANGER_BORDER`, reset fields,
reset-modal event precedence, the `"reset"` event route, `_reset_progress`,
the Reset Progress drawing block, and the confirmation overlay. Recenter the
remaining Volume and Listening Time sections vertically in the freed space.
Do not change `_tap_volume`, `_tap_listen`, or Back behavior.

- [ ] **Step 4: Run focused regression suites**

Run:

```bash
pytest -q tests/test_profile_store.py tests/test_profiles_scene.py tests/test_main_menu_scene.py tests/test_settings_scene.py tests/test_app_session_flow.py tests/test_session_checkpoint.py tests/test_level_selection_scene.py
```

Expected: all focused tests pass.

- [ ] **Step 5: Run the complete suite**

Run: `pytest -q`

Expected: all tests pass with zero failures.

- [ ] **Step 6: Make the interactive E2E harness profile-aware**

Import and register ProfilesScene in the custom E2E scene map. Immediately
after constructing app in main(), create a dedicated profile when no active
profile exists:

    if app.active_profile() is None:
        app.create_profile('E2E Reader')

This preserves the production Start guard while allowing AutoMainMenuScene to
call start_new_session('1a').

- [ ] **Step 7: Perform a manual GUI smoke test**

Run the existing GUI command documented in `README.md`, then verify in order:

1. No profile shows `Welcome!`.
2. Start opens the create-profile prompt.
3. Create Maria and choose Level 1A.
4. Complete one stable attempt and return to Main Menu.
5. Create Leo at Level 2C and return to Main Menu.
6. Switch to Maria and confirm the saved Level 1A item resumes.
7. Restart ELLA and confirm Maria remains selected and greeted.
8. Rename Maria, reset Leo, and delete an inactive profile.
9. Confirm Settings contains no Reset Progress action.

- [ ] **Step 8: Commit the Settings and E2E cleanup**

```bash
git add src/ella_bot/ui/pygame_gui/scenes/settings.py tests/test_settings_scene.py tests/test_gui_e2e.py
git commit -m "refactor: move progress reset to profiles"
```

- [ ] **Step 9: Review the final diff**

Run:

```bash
git status --short
git diff --check
git log --oneline -7
```

Expected: no whitespace errors; only planned feature files are changed by this
work; pre-existing unrelated changes remain identifiable and uncommitted or in
their original staged state.
