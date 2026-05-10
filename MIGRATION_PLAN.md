# E.L.L.A. Src Migration & Architecture Refactor Plan

## Overview

This plan describes a phased migration from a flat project layout to a modern `src/` package structure combined with a full architectural redesign. The strategy emphasizes **slow, careful progress** with explicit rollback checkpoints at each phase.

## Core Strategy

1. Establish a safety baseline
2. Add packaging infrastructure
3. Build the target architecture in parallel with the existing code
4. Move logic gradually behind temporary adapters
5. Normalize path/resource handling
6. Switch runtime entrypoints
7. Remove legacy code and migration hacks
8. Harden with smoke tests and documentation updates

Each phase is independently reversible and verifiable before proceeding to the next.

---

## Phases

### Phase 0: Baseline and Safety Net

**Goal:** Capture current runtime behavior as a known-good reference.

**Actions:**
1. Run `python main.py --help` and record output
2. Run existing GUI command with mic/TTS enabled and record success/output
3. Create a migration branch as rollback checkpoint A

**Verification:**
- Both commands execute without errors
- Output matches expectations

**Commit Message:** `chore(baseline): capture pre-migration runtime behavior`

---

### Phase 1: Packaging Foundation

**Goal:** Add `pyproject.toml` with src discovery and console script without moving code.

**Dependencies:** None (Phase 0 complete)

**Actions:**
1. Create `pyproject.toml` with:
   - `src/` layout discovery (setuptools)
   - `ella-bot` console script entry point → `src.ella_bot.cli.main:main`
   - Optional dependency groups (vosk, sounddevice, pygame-ce, pronouncing)
   - Python version constraints (≥3.9)
2. Keep existing flat `ella_bot/` and `main.py` untouched
3. Run `pip install -e .` from repo root
4. Verify import still works: `from ella_bot.speech import offline_asr`

**Verification:**
- `pip install -e .` succeeds
- `python -c "from ella_bot.speech import offline_asr; print('OK')"` works
- Rollback checkpoint B

**Commit Message:** `feat(packaging): add pyproject.toml with src layout configuration`

---

### Phase 2: Build Target Structure Under src

**Goal:** Create redesigned module hierarchy under `src/ella_bot` without changing behavior.

**Dependencies:** Phase 1 complete

**Actions:**
1. Create directory tree under `src/ella_bot/`:
   ```
   src/ella_bot/
   ├── __init__.py
   ├── core/
   │   ├── __init__.py
   │   ├── models.py              # (placeholder)
   │   ├── exceptions.py          # (placeholder)
   │   └── constants.py           # (placeholder)
   ├── speech/
   │   ├── __init__.py
   │   ├── interfaces.py          # (placeholder)
   │   ├── asr/
   │   │   ├── __init__.py
   │   │   ├── base.py            # (placeholder)
   │   │   ├── vosk_engine.py     # (placeholder)
   │   │   ├── simulated.py       # (placeholder)
   │   │   └── factory.py         # (placeholder)
   │   └── tts/
   │       ├── __init__.py
   │       ├── base.py            # (placeholder)
   │       ├── engines/
   │       │   ├── __init__.py
   │       │   ├── espeak.py      # (placeholder)
   │       │   ├── pyttsx3.py     # (placeholder)
   │       │   ├── mac_say.py     # (placeholder)
   │       │   └── respeaker.py   # (placeholder)
   │       └── factory.py         # (placeholder)
   ├── validation/
   │   ├── __init__.py
   │   ├── validators.py          # (placeholder)
   │   ├── alignment.py           # (placeholder)
   │   ├── feedback.py            # (placeholder)
   │   └── confidence.py          # (placeholder)
   ├── ui/
   │   ├── __init__.py
   │   ├── interfaces.py          # (placeholder)
   │   ├── console/
   │   │   ├── __init__.py
   │   │   └── console_ui.py      # (placeholder)
   │   └── pygame_gui/
   │       ├── __init__.py
   │       ├── app.py             # (placeholder)
   │       ├── animator.py        # (placeholder)
   │       ├── config.py          # (placeholder)
   │       └── components/
   │           ├── __init__.py
   │           ├── menu.py        # (placeholder)
   │           ├── button.py      # (placeholder)
   │           └── dialog.py      # (placeholder)
   ├── services/
   │   ├── __init__.py
   │   ├── app_service.py         # (placeholder)
   │   └── session_manager.py     # (placeholder)
   ├── config/
   │   ├── __init__.py
   │   ├── base.py                # (placeholder)
   │   ├── defaults.py            # (placeholder)
   │   └── loader.py              # (placeholder)
   ├── utils/
   │   ├── __init__.py
   │   ├── file_utils.py          # (placeholder)
   │   ├── audio.py               # (placeholder)
   │   └── logging.py             # (placeholder)
   └── cli/
       ├── __init__.py
       └── main.py                # (placeholder, to be filled in Phase 5)
   ```

2. All `__init__.py` files can be empty for now
3. All module files are placeholders with `pass` or stub docstrings
4. Old flat `ella_bot/` remains unchanged

**Verification:**
- All files exist
- `python -c "import src.ella_bot; print('OK')"` works
- Rollback checkpoint C

**Commit Message:** `feat(architecture): scaffold src/ package structure with domain layers`

---

### Phase 3: Migrate Logic With Temporary Adapters

**Goal:** Move actual code into new module locations behind backward-compatible re-export adapters.

**Dependencies:** Phase 2 complete

**Subphases:** 3a (validation), 3b (speech), 3c (ui)

#### Phase 3a: Migrate Validation & Feedback

**Actions:**
1. Copy content from `ella_bot/validation/text_validation.py` → `src/ella_bot/validation/validators.py`
2. Copy content from `ella_bot/feedback/feedback_engine.py` → `src/ella_bot/validation/feedback.py`
3. Create temporary adapter in `ella_bot/validation/text_validation.py`:
   ```python
   """Backward-compatible re-export adapter."""
   from src.ella_bot.validation.validators import *
   from src.ella_bot.validation.feedback import *
   ```
4. Update `ella_bot/feedback/feedback_engine.py` to re-export from `src.ella_bot.validation.feedback`
5. Test: `python main.py --help` still works
6. Rollback checkpoint D-1

#### Phase 3b: Migrate Speech

**Actions:**
1. Copy content from `ella_bot/speech/offline_asr.py` → `src/ella_bot/speech/asr/simulated.py` and `vosk_engine.py`
2. Copy content from `ella_bot/speech/tts_offline.py` → `src/ella_bot/speech/tts/engines/`
3. Create factory stubs in `src/ella_bot/speech/asr/factory.py` and `tts/factory.py`
4. Create temporary adapters in old locations re-exporting from src
5. Test: `python main.py --help` works
6. Rollback checkpoint D-2

#### Phase 3c: Migrate UI

**Actions:**
1. Copy `ella_bot/ui/console_ui.py` → `src/ella_bot/ui/console/console_ui.py`
2. Copy `ella_bot/ui/gui_pygame.py` → `src/ella_bot/ui/pygame_gui/app.py`
3. Copy `ella_bot/ui/avatar_animator.py` → `src/ella_bot/ui/pygame_gui/animator.py`
4. Copy `ella_bot/ui/gui_config.py` → `src/ella_bot/ui/pygame_gui/config.py`
5. Create temporary adapters in old locations
6. Test: both console and GUI still work
7. Rollback checkpoint D-3

**Verification for entire Phase 3:**
- `python main.py --help` succeeds
- `python main.py --expected "hello world" --spoken "hello world"` (console) succeeds
- `PYTHONPATH=src python -m ella_bot.cli.main --help` works (preparation for cutover)
- No import errors in old or new locations

**Commit Message:** (one per subphase)
- `feat(validation): move validation and feedback to src/`
- `feat(speech): move speech ASR/TTS to src/`
- `feat(ui): move UI console and pygame to src/`

---

### Phase 4: Normalize Path Resolution

**Goal:** Make config, model, and asset paths deterministic and cwd-independent.

**Dependencies:** Phase 3 complete

**Actions:**
1. Create `src/ella_bot/utils/file_utils.py` with:
   - `get_project_root()` → resolves to repo root from package location
   - `resolve_asset_path(relative_path)` → project_root / relative_path
   - `resolve_config_path(relative_path)` → project_root / "config" / relative_path
   - `resolve_model_path(relative_path)` → project_root / "models" / relative_path

2. Update `src/ella_bot/ui/pygame_gui/config.py`:
   - Change `assets_dir: Path = Path("./assets")` → use `resolve_asset_path("assets")`

3. Update `src/ella_bot/cli/main.py` (when filled in Phase 5):
   - Use `resolve_config_path()` and `resolve_model_path()` for defaults

**Verification:**
- From a different working directory (e.g., `/tmp`), run:
  ```bash
  cd /tmp
  python -m ella_bot.cli.main --help
  ```
  Succeeds without path errors.
- Rollback checkpoint E

**Commit Message:** `feat(config): centralize path resolution for config/models/assets`

---

### Phase 5: Entrypoint Cutover

**Goal:** Switch runtime to package entrypoint; stop relying on root `main.py`.

**Dependencies:** Phases 3-4 complete

**Actions:**
1. Copy content from `main.py` → `src/ella_bot/cli/main.py`
   - Update all imports to use `src.ella_bot.*` (no adapters)
   - Use path-resolution functions from `utils/file_utils.py`

2. Update `src/ella_bot/cli/__init__.py` to expose `main` function

3. Verify both run mechanisms:
   ```bash
   python -m ella_bot.cli.main --help
   ella-bot --help
   ```

4. Deprecate root `main.py` — do NOT run it as primary entrypoint anymore

5. Rollback checkpoint F

**Verification:**
- `python -m ella_bot.cli.main --help` succeeds
- `ella-bot --help` succeeds
- Both show identical help output
- Console and GUI flows work with new entrypoint
- README examples updated to use new entrypoints

**Commit Message:** `feat(cli): introduce package entrypoint and deprecate root main.py`

---

### Phase 6: Remove Legacy Code and Migration Hacks

**Goal:** Delete old flat-layout modules and temporary adapters.

**Dependencies:** Phase 5 complete (all imports have switched)

**Actions:**
1. Delete old adapter files:
   - Remove adapter re-exports from `ella_bot/validation/`
   - Remove adapter re-exports from `ella_bot/feedback/`
   - Remove adapter re-exports from `ella_bot/speech/`
   - Remove adapter re-exports from `ella_bot/ui/`

2. Delete legacy modules:
   - `ella_bot/validation/text_validation.py` (now in src)
   - `ella_bot/feedback/feedback_engine.py` (now in src)
   - `ella_bot/speech/offline_asr.py` (now in src)
   - `ella_bot/speech/tts_offline.py` (now in src)
   - `ella_bot/ui/console_ui.py` (now in src)
   - `ella_bot/ui/gui_pygame.py` (now in src)
   - `ella_bot/ui/avatar_animator.py` (now in src)
   - `ella_bot/ui/gui_config.py` (now in src)

3. Clean up `ella_bot/__init__.py`:
   - Remove `__path__.append(...)` hack for src
   - Keep only: `"""E.L.L.A. package."""`

4. Clean up `ella_bot/speech/__init__.py`:
   - Remove `__path__.append(...)` hack
   - Keep only: `"""Speech module for E.L.L.A."""`

5. Root `main.py` is deprecated but can stay as fallback for now (decide later)

**Verification:**
- `python -m ella_bot.cli.main --help` still works
- `ella-bot --help` still works
- No imports from old flat locations remain in source
- Search for `from ella_bot.speech.offline_asr` → no results
- Search for `__path__.append` → no results
- Rollback checkpoint G

**Commit Message:** `refactor(cleanup): remove legacy flat-layout modules and migration adapters`

---

### Phase 7: Hardening & Documentation

**Goal:** Update documentation, add smoke tests, and verify real-world usage.

**Dependencies:** Phase 6 complete

**Actions:**

#### 7a: Update Documentation
1. Update `README.md`:
   - Change "Run Command" section from:
     ```bash
     python main.py --gui ...
     ```
     to:
     ```bash
     ella-bot --gui ...
     # or
     python -m ella_bot.cli.main --gui ...
     ```
   - Keep working directory context (still run from repo root for relative paths to config/models/assets)

2. Add `MIGRATION_NOTES.md` documenting:
   - What changed (src layout, architecture redesign)
   - How to install from source (`pip install -e .`)
   - Console script availability (`ella-bot`)
   - Module changes for downstream users

#### 7b: Smoke Tests
Create simple verification checks in `src/ella_bot/cli/main.py` or a new `scripts/smoke_test.sh`:
1. Help command: `ella-bot --help` → exit 0
2. Console run: `ella-bot --expected "test" --spoken "test"` → no error, output contains "test"
3. GUI boot: `ella-bot --gui --expected "test" --spoken "test" --start-level easy` (headless or with timeout)
4. From different cwd: `cd /tmp && ella-bot --help` → works

#### 7c: Final Cleanup Scan
1. Search for forbidden patterns:
   - `__path__.append` → should be 0 results
   - `from ella_bot.speech.offline_asr` → should be 0 results
   - `from ella_bot.feedback.feedback_engine` → should be 0 results
   - `from ella_bot.validation.text_validation` → should be 0 results
2. Verify `src/ella_bot/` is the only package source
3. Verify `pip list | grep ella` shows package correctly

**Verification:**
- README examples run without modification
- All smoke tests pass
- Cleanup scan finds no legacy imports
- Rollback checkpoint H (final)

**Commit Messages:**
- `docs(readme): update run commands to package entrypoint`
- `docs: add migration notes and installation guide`
- `test(smoke): add basic CLI/GUI smoke test script`

---

## File Inventory

### Files to Create
- `pyproject.toml` (Phase 1)
- `src/ella_bot/` entire hierarchy (Phase 2)
- `src/ella_bot/cli/main.py` (Phase 5, moved from root)
- `src/ella_bot/utils/file_utils.py` (Phase 4)
- `MIGRATION_NOTES.md` (Phase 7)
- `scripts/smoke_test.sh` (Phase 7)

### Files to Modify
- `README.md` (Phase 7)
- `ella_bot/__init__.py` (Phase 6)
- `ella_bot/speech/__init__.py` (Phase 6)
- Individual module files (Phases 3-4)

### Files to Delete
- Old flat modules in `ella_bot/` (Phase 6)
- Temporary adapters (Phase 6)
- Possibly `main.py` (Phase 6, optional)

### Files to Keep Unchanged
- `config/`, `models/`, `assets/`, `faces/` directories and content
- `requirements.txt` (or migrate to pyproject.toml extras)
- `.gitignore` (may add `src/` build artifacts)

---

## Rollback Checkpoints Summary

| Phase | Checkpoint | Condition | Rollback Via |
|-------|-----------|-----------|--------------|
| 0 | A | Baseline captured | `git checkout baseline-commit` |
| 1 | B | Packaging config added | `git revert packaging-commit` |
| 2 | C | Src skeleton created | `git revert scaffold-commit` |
| 3a | D-1 | Validation moved | `git revert validation-commit` |
| 3b | D-2 | Speech moved | `git revert speech-commit` |
| 3c | D-3 | UI moved | `git revert ui-commit` |
| 4 | E | Path resolution added | `git revert path-commit` |
| 5 | F | Entrypoint switched | `git revert entrypoint-commit` |
| 6 | G | Legacy code removed | `git revert cleanup-commit` |
| 7 | H | Docs and tests added | `git revert docs-and-tests-commit` |

---

## Commit Strategy

- **One phase = One or more focused commits** (atomic changes, clear intent)
- **Avoid mixing code moves with behavior changes** (makes blame and bisect harder)
- **Commit messages follow convention:**
  - `feat(scope):` for new functionality
  - `refactor(scope):` for code reorganization
  - `chore(scope):` for infrastructure/config
  - `docs(scope):` for documentation
  - `test(scope):` for testing

---

## Testing & Validation

### Before Starting
```bash
python main.py --help
python main.py --expected "hello world" --spoken "hello world"
# (record success)
```

### After Each Phase
- Run `pip install -e .` to ensure packaging is valid
- Run both console and GUI flows if applicable
- Check for import errors and runtime failures

### Before Final Cleanup
- From non-repo directory, run `ella-bot --help`
- Verify all path resolution works
- Run smoke test script

---

## Notes & Considerations

1. **No behavior changes** in this migration beyond code organization.
2. **Backward compatibility** is maintained during Phases 3-5 via adapters, then removed in Phase 6.
3. **Test gap:** Currently no test suite. Phase 7 adds minimal smoke tests as a foundation for future expansion.
4. **Dependency changes:** `pyproject.toml` introduces optional groups; no core runtime dependencies are added.
5. **Installation:** Post-migration, users can `pip install -e .` from repo root to get `ella-bot` command.

---

## Questions & Decisions

**Q: What if a phase fails?**  
A: Roll back to the previous checkpoint and diagnose. Each phase is isolated, so failure in Phase 4 does not affect Phase 3.

**Q: Do I have to migrate all modules at once?**  
A: No. Phase 3 is broken into subphases so you can migrate validation, then speech, then UI in separate commits.

**Q: Can I keep using root `main.py` after migration?**  
A: It is deprecated in Phase 5 but can remain in the repo. The canonical entrypoint is `ella-bot` or `python -m ella_bot.cli.main`.

**Q: Do I need to update all external documentation?**  
A: Yes, any README files or installation guides should be updated in Phase 7 to reflect new entrypoints.

