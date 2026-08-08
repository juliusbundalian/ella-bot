# Student Technical Handbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create one accurate, self-contained handbook that teaches high-school students with mixed coding experience how the complete ELLA repository works.

**Architecture:** Build a single Markdown document in layers: orient the reader, trace runtime behavior, explain each subsystem, teach safe project work, and finish with a complete module/repository reference. Treat the live Python source, configuration, package metadata, and tests as authoritative; use existing documents only as historical context.

**Tech Stack:** Markdown, Mermaid, Python 3.9+, pytest, Pygame CE, Vosk, Piper and other TTS backends, INI configuration, JSON/JSONL persistence, Raspberry Pi and Seeed voice-card integration.

## Global Constraints

- Create only `docs/STUDENT_TECHNICAL_HANDBOOK.md` as the handbook deliverable.
- Preserve `docs/TECHNICAL_DOCUMENTATION.md` byte-for-byte.
- Write for high-school students with mixed programming experience.
- Define a technical term before relying on it and collect important terms in a glossary.
- Cover ELLA's Python application in depth.
- Cover `seeed-voicecard` and binary/media assets at a high level.
- Explain profile/session files structurally without reproducing personal student data.
- Clearly label current behavior, fallback behavior, development utilities, generated data, historical material, and third-party code.
- Verify every file path, symbol, configuration name, and runtime claim against the live repository.
- Do not copy unverified claims from `docs/TECHNICAL_DOCUMENTATION.md` or `PROJECT_ANALYSIS.md`.
- Use Mermaid only when it makes a relationship or sequence materially clearer.
- Keep code excerpts short; label simplified pseudocode explicitly.

---

### Task 1: Build the Verified Orientation and Repository Map

**Files:**
- Create: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Read: `README.md`
- Read: `pyproject.toml`
- Read: `requirements.txt`
- Read: `main.py`
- Read: `src/ella_bot/cli/main.py`
- Read: `src/ella_bot/config/app_config.py`
- Read: `config/settings.ini`
- Read: `config/level_pools.json`
- Read: `.gitmodules` if present
- Read: `seeed-voicecard/README.md`

**Interfaces:**
- Consumes: Approved design in `docs/superpowers/specs/2026-08-08-student-technical-handbook-design.md`.
- Produces: The handbook title, navigation, reader contract, repository map, architecture overview, and terminology conventions used by every later task.

- [ ] **Step 1: Capture the current source inventory before drafting**

Run:

```bash
rg --files src/ella_bot -g '*.py' | sort
rg --files tests -g '*.py' | sort
find config assets bot faces scripts scratch docs -maxdepth 2 -type f | sort
git submodule status
```

Expected: the output identifies all production Python modules, all test modules,
the major resource categories, and whether `seeed-voicecard` is a submodule.
Do not include individual runtime profile contents in notes.

- [ ] **Step 2: Verify startup and dependency facts**

Run:

```bash
sed -n '1,260p' pyproject.toml
sed -n '1,280p' src/ella_bot/cli/main.py
sed -n '1,220p' src/ella_bot/config/app_config.py
sed -n '1,260p' config/settings.ini
sed -n '1,180p' main.py
```

Expected: package metadata, console entry point, supported CLI options,
configuration keys, and the root compatibility entry point are visible. Record
disagreements between prose documentation and executable configuration as
limitations rather than silently choosing the older claim.

- [ ] **Step 3: Create the document framework and Part I**

Create `docs/STUDENT_TECHNICAL_HANDBOOK.md` with these exact top-level sections:

```markdown
# ELLA Student Technical Handbook

## Table of Contents
## Part I — Meet ELLA
## Part II — Follow the Program
## Part III — Understand the Subsystems
## Part IV — Work With the Project
## Part V — Repository Reference
## Glossary
## Final Architecture Recap
```

Under Part I, write:

- who the handbook is for and three suggested reading paths (new coder,
  experienced student, teacher/mentor);
- what ELLA does and does not do;
- offline-operation boundaries;
- ASR, TTS, GUI, service, configuration, persistence, and test definitions;
- a technology table based on `pyproject.toml` and the actual imports;
- a repository tree grouped by runtime source, tests, config, assets, data,
  scripts, historical documents, scratch material, and external driver code;
- a five-minute mental model;
- a Mermaid component diagram whose arrows match imports and runtime ownership;
- a short first walkthrough from `ella-bot` to `EllaGUIApp`.

- [ ] **Step 4: Check Part I for navigability and unsupported claims**

Run:

```bash
rg -n '^#|^##|^###' docs/STUDENT_TECHNICAL_HANDBOOK.md
rg -n 'Whisper|faster-whisper|post_processor|cloud API|100% offline' docs/STUDENT_TECHNICAL_HANDBOOK.md
git diff --check -- docs/STUDENT_TECHNICAL_HANDBOOK.md
```

Expected: the complete framework and Part I headings appear; obsolete speech
components do not appear as current implementation; whitespace validation is
clean. If “100% offline” appears, its paragraph must state the installation and
model-download qualification.

- [ ] **Step 5: Commit the orientation**

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: introduce ELLA student handbook"
```

### Task 2: Document Startup, Domain Types, Speech, and Validation

**Files:**
- Modify: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Read: `src/ella_bot/core/constants.py`
- Read: `src/ella_bot/core/events.py`
- Read: `src/ella_bot/core/models.py`
- Read: `src/ella_bot/core/exceptions.py`
- Read: `src/ella_bot/speech/interfaces.py`
- Read: `src/ella_bot/speech/asr/factory.py`
- Read: `src/ella_bot/speech/asr/simulated.py`
- Read: `src/ella_bot/speech/asr/vosk_engine.py`
- Read: `src/ella_bot/speech/tts/base.py`
- Read: `src/ella_bot/speech/tts/factory.py`
- Read: `src/ella_bot/speech/tts/engines/*.py`
- Read: `src/ella_bot/validation/validators.py`
- Read: `src/ella_bot/validation/feedback.py`
- Read: `config/pronunciation_overrides.json`
- Test reference: `tests/test_cli.py`
- Test reference: `tests/test_asr_factory.py`
- Test reference: `tests/test_tts_piper.py`
- Test reference: `tests/test_pronunciation_overrides.py`
- Test reference: `tests/test_validators.py`
- Test reference: `tests/test_feedback.py`

**Interfaces:**
- Consumes: Part I vocabulary and architecture map.
- Produces: Part II startup/data-flow explanation and the speech/validation chapters of Part III.

- [ ] **Step 1: Trace construction and protocol boundaries**

Run:

```bash
rg -n '^(class|def) |build_asr|build_tts|EllaGUIApp|ASREngine|TTSEngine' src/ella_bot/cli src/ella_bot/core src/ella_bot/speech
sed -n '1,280p' src/ella_bot/speech/asr/factory.py
sed -n '1,320p' src/ella_bot/speech/tts/factory.py
```

Expected: the handbook author can distinguish the CLI wrapper functions from
the ASR factory module, the protocol interfaces from base classes, and the
factory's real engine-selection/fallback order.

- [ ] **Step 2: Trace one recognition and validation operation**

Run:

```bash
sed -n '1,340p' src/ella_bot/speech/asr/vosk_engine.py
sed -n '1,470p' src/ella_bot/validation/validators.py
sed -n '1,560p' src/ella_bot/validation/feedback.py
```

Expected: microphone capture, Vosk result parsing, diagnostic formatting,
normalization, word alignment, confidence handling, score calculation,
feedback construction, and pronunciation coaching can be described using the
actual thresholds and data shapes.

- [ ] **Step 3: Write Part II startup flow and Part III speech chapters**

Add these subsections:

```markdown
### From a Terminal Command to a Running App
### Configuration Precedence and Dependency Construction
### Core Constants and Immutable Events
### How ELLA Listens: ASR
### How ELLA Speaks: TTS and Prerecorded Audio
### How ELLA Compares Spoken and Expected Text
### How Feedback and Pronunciation Coaching Are Built
```

Include a Mermaid dependency-construction diagram and an attempt sequence
segment. Explain that empty or minimal scaffold modules are present without
inventing responsibilities for them. Explain duplicated ASR class names only
after verifying which imports the running CLI uses.

- [ ] **Step 4: Cross-check speech claims against focused tests**

Run:

```bash
.venv/bin/pytest tests/test_cli.py tests/test_asr_factory.py tests/test_tts_piper.py tests/test_pronunciation_overrides.py tests/test_validators.py tests/test_feedback.py -q
```

Expected: all selected tests pass. If hardware/model-dependent behavior is not
exercised by these tests, label it as environment-dependent in the handbook.

- [ ] **Step 5: Commit the runtime and speech chapters**

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: explain ELLA startup and speech pipeline"
```

### Task 3: Document Services, Progression, Persistence, and Concurrency

**Files:**
- Modify: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Read: `src/ella_bot/services/attempt_runner.py`
- Read: `src/ella_bot/services/evaluation.py`
- Read: `src/ella_bot/services/profile_store.py`
- Read: `src/ella_bot/services/session_checkpoint.py`
- Read: `src/ella_bot/services/session_manager.py`
- Read: `src/ella_bot/services/sound_effects.py`
- Read: `src/ella_bot/utils/file_utils.py`
- Read: `src/ella_bot/utils/logging.py`
- Test reference: `tests/test_attempt_runner.py`
- Test reference: `tests/test_evaluation.py`
- Test reference: `tests/test_profile_store.py`
- Test reference: `tests/test_session_checkpoint.py`
- Test reference: `tests/test_session_manager.py`
- Test reference: `tests/test_sound_effects.py`
- Test reference: `tests/test_app_session_flow.py`

**Interfaces:**
- Consumes: Startup, event, ASR, TTS, validation, and feedback concepts from Task 2.
- Produces: The authoritative reading-attempt flow, level progression rules, persistence schemas, threading model, and failure behavior used by GUI chapters.

- [ ] **Step 1: Trace ownership and service calls**

Run:

```bash
rg -n '^(class|def) |Thread|Queue|post_event|checkpoint|profile|session|finish_|save|restore|replace' src/ella_bot/services src/ella_bot/ui/pygame_gui/app.py
```

Expected: ownership between `EllaGUIApp`, `AttemptRunner`, `SessionManager`,
`EvaluationService`, `ProfileStore`, and `SessionCheckpointStore` is clear,
including worker-thread boundaries and event delivery.

- [ ] **Step 2: Verify data shapes and transaction safety**

Run:

```bash
sed -n '1,360p' src/ella_bot/services/profile_store.py
sed -n '1,340p' src/ella_bot/services/session_checkpoint.py
sed -n '1,380p' src/ella_bot/services/evaluation.py
sed -n '1,360p' src/ella_bot/services/session_manager.py
```

Expected: document profile limits/validation, per-profile paths, JSON registry,
JSONL history, checkpoint versions, atomic replacement/archive behavior,
session pools, tier boundaries, attempt limits, thresholds, and reset/retry
semantics without quoting real profile records.

- [ ] **Step 3: Write the service and persistence chapters**

Add these subsections:

```markdown
### The Complete Practice Attempt
### Levels, Tiers, Attempts, Passing, and Progression
### Evaluation Results and Ratings
### Profiles and Per-Student Storage
### Saving, Restoring, and Recovering Sessions
### Threads, Events, Cancellation, and Safe Shutdown
### Sound Effects and Prerecorded Level 1 Practice
### Error Paths and Existing Safeguards
```

Include a reading-attempt sequence diagram and a data-persistence flow diagram.
Show fabricated JSON/JSONL examples that match the actual schemas and label them
as examples. Explain why atomic writes and worker shutdown matter using
student-accessible language.

- [ ] **Step 4: Cross-check service claims against focused tests**

Run:

```bash
.venv/bin/pytest tests/test_attempt_runner.py tests/test_evaluation.py tests/test_profile_store.py tests/test_session_checkpoint.py tests/test_session_manager.py tests/test_sound_effects.py tests/test_app_session_flow.py -q
```

Expected: all selected tests pass, including corruption recovery, transactional
session changes, profile isolation, progression, and worker-shutdown cases.

- [ ] **Step 5: Commit the services and data chapters**

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: explain ELLA services and saved progress"
```

### Task 4: Document the GUI, Scenes, Components, and Media

**Files:**
- Modify: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Read: `src/ella_bot/ui/interfaces.py`
- Read: `src/ella_bot/ui/console/console_ui.py`
- Read: `src/ella_bot/ui/pygame_gui/app.py`
- Read: `src/ella_bot/ui/pygame_gui/scene.py`
- Read: `src/ella_bot/ui/pygame_gui/config.py`
- Read: `src/ella_bot/ui/pygame_gui/animator.py`
- Read: `src/ella_bot/ui/pygame_gui/bot_sprite.py`
- Read: `src/ella_bot/ui/pygame_gui/lottie_bg.py`
- Read: `src/ella_bot/ui/pygame_gui/video_bg.py`
- Read: `src/ella_bot/ui/pygame_gui/ui_helpers.py`
- Read: `src/ella_bot/ui/pygame_gui/components/*.py`
- Read: `src/ella_bot/ui/pygame_gui/scenes/*.py`
- Test reference: all `tests/test_*scene.py`, `tests/test_bot_sprite.py`, `tests/test_confetti.py`, `tests/test_lottie_bg.py`, `tests/test_on_screen_keyboard.py`, `tests/test_reading_prompt_auto_continue.py`, and `tests/test_gui_e2e.py`

**Interfaces:**
- Consumes: Application ownership, service APIs, typed events, worker lifecycle, and persistence flow from Tasks 2–3.
- Produces: The scene map, event-loop explanation, render/input lifecycle, reusable component reference, and asset-loading/fallback behavior.

- [ ] **Step 1: Map the scene lifecycle and transitions**

Run:

```bash
rg -n 'class .*Scene|switch_scene|on_enter|on_exit|handle_event|update|render|prepare_shutdown' src/ella_bot/ui/pygame_gui
```

Expected: every live scene and transition is accounted for, including intro,
main menu, profiles, level selection, reading prompt, results, final evaluation,
and settings. The console renderer is identified as a separate capability, not
mistaken for the default execution path.

- [ ] **Step 2: Trace drawing, input, animation, and fallbacks**

Run:

```bash
rg -n 'pygame\.|VIDEO|Lottie|fallback|Button|PauseModal|OnScreenKeyboard|Confetti|BotSprite|Animator' src/ella_bot/ui/pygame_gui
```

Expected: distinguish Pygame's event loop, logical and physical coordinates,
buttons, keyboard input, pause/cancel behavior, robot animation systems,
Lottie/video/static fallbacks, responsive text, and asset resolution.

- [ ] **Step 3: Write the GUI chapters**

Add these subsections:

```markdown
### Pygame's Event–Update–Render Loop
### Scene Lifecycle and Screen Transitions
### The Application's Scenes
### Buttons, the On-Screen Keyboard, Modals, and Confetti
### Robot Animation and Application State
### Lottie, Video, Images, Fonts, and Fallbacks
### Responsive Layout and Touch Input
### GUI Failure Handling and Shutdown
```

Include a Mermaid scene-transition diagram based on verified calls. Add a small
pseudocode event-loop example labelled “simplified”. Note where tests use fake
surfaces, monkeypatching, headless video, or stub services.

- [ ] **Step 4: Cross-check GUI claims against focused tests**

Run:

```bash
.venv/bin/pytest tests/test_app_session_flow.py tests/test_bot_sprite.py tests/test_confetti.py tests/test_final_eval_scene.py tests/test_gui_e2e.py tests/test_level_selection_scene.py tests/test_lottie_bg.py tests/test_main_menu_scene.py tests/test_on_screen_keyboard.py tests/test_profiles_scene.py tests/test_reading_prompt_auto_continue.py tests/test_results_scene.py tests/test_settings_scene.py -q
```

Expected: all selected GUI, transition, input, layout, animation, and shutdown
tests pass in the configured test environment.

- [ ] **Step 5: Commit the GUI chapters**

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: explain ELLA interface and scenes"
```

### Task 5: Add Setup, Testing, Exercises, Troubleshooting, and Complete Reference

**Files:**
- Modify: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Read: `tests/conftest.py`
- Read: all `tests/test_*.py`
- Read: `scripts/audition_level.py`
- Read: `scripts/smoke_test.bat`
- Read: `scripts/ella-bot.desktop`
- Read: `install.cmd`
- Read: `MIGRATION_PLAN.md`
- Read: `MIGRATION_NOTES.md`
- Read: `docs/PEDAGOGY_UPDATES_JULY.md`
- Read: `seeed-voicecard/README.md`
- Read: `seeed-voicecard/Makefile`
- Read: `seeed-voicecard/dkms.conf`

**Interfaces:**
- Consumes: All architecture, runtime, service, data, and GUI chapters.
- Produces: Parts IV–V, student exercises, troubleshooting, source/test module inventory, privacy/accessibility notes, glossary, and architecture recap.

- [ ] **Step 1: Verify installation and execution paths**

Run:

```bash
sed -n '1,260p' README.md
sed -n '1,260p' pyproject.toml
sed -n '1,260p' install.cmd
sed -n '1,220p' scripts/ella-bot.desktop
sed -n '1,260p' seeed-voicecard/README.md
```

Expected: separate package installation from optional model/hardware setup;
separate Windows, Linux, and Raspberry Pi instructions; do not claim a platform
was tested merely because an installer exists.

- [ ] **Step 2: Build the module and test reference from the live tree**

Run:

```bash
rg --files src/ella_bot -g '*.py' | sort
rg --files tests -g '*.py' | sort
rg -n '^(class|def) ' src/ella_bot tests scripts/audition_level.py
```

Expected: Part V contains an entry for every meaningful production Python
module and groups test modules by behavior. Empty `__init__.py` files may be
grouped, while minimal scaffold modules must be identified honestly.

- [ ] **Step 3: Write practical student material**

Add:

- setup and run instructions with prerequisites and environment qualifications;
- an explanation of fixtures, fakes, mocks, monkeypatching, temporary paths,
  and headless GUI testing;
- exact commands for a small focused test and the full suite;
- a guided code-reading route;
- safe exercises: change feedback wording, add a configured practice item,
  adjust a GUI setting, and add a validation test;
- troubleshooting tables mapping symptoms to likely causes and safe checks;
- privacy, security, accessibility, and offline-operation considerations.

Each exercise must state the files involved, what students should observe, and
how to verify the change. Do not instruct students to edit real profile data or
run destructive system commands.

- [ ] **Step 4: Write the repository reference and closing material**

Add:

- source-module tables grouped by package;
- test-suite tables grouped by subsystem;
- configuration and data-format tables;
- purpose-level inventories for asset categories, scripts, screenshots,
  scratch files, migration/design documents, and root audio files;
- a high-level explanation of ALSA, kernel modules, device-tree overlays, DKMS,
  and the `seeed-voicecard` boundary;
- a glossary defining every recurring acronym and programming pattern;
- learning-next suggestions by topic;
- a final architecture recap and change-impact table.

- [ ] **Step 5: Verify reference completeness**

Run:

```bash
for path in $(rg --files src/ella_bot -g '*.py'); do base=$(basename "$path"); rg -q "$base" docs/STUDENT_TECHNICAL_HANDBOOK.md || echo "Missing: $path"; done
for term in ASR TTS GUI JSON JSONL INI API PCM FPS CLI; do rg -q "${term}" docs/STUDENT_TECHNICAL_HANDBOOK.md || echo "Undefined candidate: ${term}"; done
git diff --check -- docs/STUDENT_TECHNICAL_HANDBOOK.md
```

Expected: no meaningful source module is missing, each recurring acronym has a
definition or glossary entry, and Markdown whitespace validation is clean.

- [ ] **Step 6: Commit the practical and reference sections**

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: complete ELLA student handbook reference"
```

### Task 6: Perform Final Accuracy, Readability, and Preservation Verification

**Files:**
- Modify if corrections are needed: `docs/STUDENT_TECHNICAL_HANDBOOK.md`
- Verify unchanged: `docs/TECHNICAL_DOCUMENTATION.md`
- Verify against: `docs/superpowers/specs/2026-08-08-student-technical-handbook-design.md`

**Interfaces:**
- Consumes: The complete handbook from Tasks 1–5.
- Produces: A verified final handbook with test evidence and no changes to the preserved draft.

- [ ] **Step 1: Scan for placeholders, obsolete claims, and accidental private-data examples**

Run:

```bash
rg -n 'TBD|FIXME|implement later|fill in|Whisper|faster-whisper|post_processor' docs/STUDENT_TECHNICAL_HANDBOOK.md
rg -n '3a530a291f7e4037ae1bfb93d53050fa|c7b3af52c3984c24b28562548ade3716' docs/STUDENT_TECHNICAL_HANDBOOK.md
```

Expected: no placeholders, obsolete live-architecture claims, or real profile
identifiers appear. Historical mentions are acceptable only when explicitly
labelled historical.

- [ ] **Step 2: Validate local Markdown links and referenced paths**

Run a short read-only Python check that extracts non-web Markdown link targets,
strips anchors and line suffixes, and reports targets that do not exist relative
to the handbook or repository root.

```bash
.venv/bin/python -c 'import pathlib,re; p=pathlib.Path("docs/STUDENT_TECHNICAL_HANDBOOK.md"); t=p.read_text(); links=re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]*)?\)",t); missing=[x for x in links if "://" not in x and not (p.parent/x).exists() and not pathlib.Path(x).exists()]; print("\n".join(missing))'
```

Expected: no output.

- [ ] **Step 3: Run the full automated test suite**

Run:

```bash
.venv/bin/pytest -q
```

Expected: the suite passes. If an environment-dependent test cannot run,
record the exact failing command and reason in the final handoff; do not turn
the limitation into a success claim.

- [ ] **Step 4: Verify preservation and review the final diff**

Run:

```bash
git status --short
git diff -- docs/TECHNICAL_DOCUMENTATION.md
git diff --check
git log --oneline -6
```

Expected: no new diff was introduced for `docs/TECHNICAL_DOCUMENTATION.md` by
this work; the new handbook is the only implementation deliverable; whitespace
checks pass; handbook commits are visible. Pre-existing unrelated worktree
changes remain untouched.

- [ ] **Step 5: Read the handbook once as a beginner and once as a maintainer**

Beginner pass criteria:

- unfamiliar terms are defined before use;
- each major section starts with purpose before implementation;
- diagrams have prose explanations;
- exercises include safe verification and expected observations.

Maintainer pass criteria:

- paths, symbols, settings, data shapes, and thresholds match source;
- ownership and thread boundaries are explicit;
- fallback and historical paths are not presented as primary runtime behavior;
- every meaningful module is represented in the reference.

Correct every issue found in the same handbook file.

- [ ] **Step 6: Commit final corrections**

If the review changed the handbook:

```bash
git add docs/STUDENT_TECHNICAL_HANDBOOK.md
git commit -m "docs: verify ELLA student handbook"
```

If no correction was required, do not create an empty commit.
