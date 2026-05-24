# E.L.L.A. – Project Analysis

Date: 2026-05-19
Branch: `enh/ui-and-flow-enhancements`

E.L.L.A. is an offline reading assistant: it shows a target phrase, records
the child reading it via Vosk, scores accuracy with a Levenshtein-style word
alignment, then speaks coaching feedback through a configurable TTS backend.
The UI is a Pygame scene manager intended for a touchscreen kiosk (Raspberry
Pi 5 + ReSpeaker is the target hardware).

---

## 1. App Architecture

```
ella-bot (console script)
        │
        ▼
src/ella_bot/cli/main.py
   • argparse + settings.ini merge (config/app_config.py)
   • build_asr(args)   → SimulatedASR | VoskASR
   • build_tts(args)   → factory in speech/tts/factory.py
   • load_pronunciation_overrides()
   • run_gui(args)     → EllaGUIApp(...)
        │
        ▼
ui/pygame_gui/app.py    EllaGUIApp  (SceneManager)
   • owns: asr, tts, animator, screen, level state, event_queue
   • scenes: IntroScene → MainMenuScene → ReadingPromptScene
        │
        ▼
ReadingPromptScene  (single class, 633 lines)
   ├─ worker thread per attempt
   │     ├─ tts.speak(announcement)
   │     ├─ asr.transcribe(target)
   │     ├─ validate_spoken_text() → WER, alignment, missing/incorrect
   │     ├─ build_feedback() + build_spoken_feedback_with_coaching()
   │     ├─ tts.speak(line) per feedback line
   │     └─ try_level_up() / advance_to_next_sentence()
   ├─ main thread: drain event_queue, render scene, drive Pygame
   └─ bot/* sprite frame state machine (separate from AvatarAnimator)
```

**Domain layers actually used today**

| Layer | What lives there | State |
|---|---|---|
| `cli/` | argparse, factory wiring, run_gui | live |
| `config/app_config.py` | `settings.ini` → dict | live |
| `speech/asr/` | `SimulatedASR`, `VoskASR` (defined in `base.py`) | live |
| `speech/tts/` | base + 4 engines (espeak, pyttsx3, mac say, respeaker) | live |
| `speech/tts/engines/` | piper, kokoro | live |
| `validation/validators.py` | normalize, align_words, WER, highlight | live |
| `validation/feedback.py` | child-tone messages, ARPAbet coaching | live |
| `ui/pygame_gui/` | scenes, animator, helpers, GUIConfig | live |
| `ui/console/console_ui.py` | text renderer | defined, never called |
| `core/`, `services/`, `validation/alignment.py`, `validation/confidence.py`, `utils/audio.py`, `utils/logging.py`, `config/base.py`, `config/defaults.py`, `speech/interfaces.py`, `ui/interfaces.py`, `ui/pygame_gui/components/*` | placeholders (`pass`) | scaffolded by `MIGRATION_PLAN.md`, never filled |

The codebase is a partially-executed version of `MIGRATION_PLAN.md`: the
src-layout move and TTS/Vosk extraction happened, but the deeper layering
(services, interfaces, components) is still empty `pass` stubs.

---

## 2. Current Technologies

| Concern | Stack |
|---|---|
| Language | Python (`requires-python = ">=3.9"` in pyproject, README says 3.10+, current venv runs 3.14) |
| ASR | Vosk (`vosk-model-small-en-us-0.15`, ~68 MB) via `sounddevice` raw input stream |
| TTS engines | Kokoro-ONNX (310 MB), Piper (subprocess + custom warmth filter), pyttsx3, macOS `say`, espeak-ng, ReSpeaker (espeak through ALSA) |
| Audio I/O | `sounddevice`, `numpy` (Piper warmth FIR, Kokoro playback) |
| GUI | `pygame-ce` (scene manager + manual rect/render code) |
| Phonetics | `pronouncing` (CMU dict → custom ARPAbet→"kid-friendly sound" mapper) |
| Packaging | `setuptools` + `pyproject.toml`, console script `ella-bot` |
| Persistence | None (level/progress lives in memory only) |
| Tests | None (`scripts/smoke_test.bat` is empty in tree) |
| Logging | `print()` everywhere |

---

## 3. Speech Pipeline – End to End

```
1. Scene starts attempt           (ReadingPromptScene._start_attempt)
       │ spawns daemon Thread → _attempt_worker
       ▼
2. Announcement TTS               (tts.speak("Alright! You're on the 1A level…"))
       │ target word substituted via pronunciation_overrides regex
       ▼
3. Vosk listening                 (VoskASR.transcribe)
       │ RawInputStream blocksize 4000 frames @ device default SR (typically 48 kHz)
       │ KaldiRecognizer + SetWords(True)
       │ runs for `listen_seconds` (default 5)
       ▼
4. Final result parsed            → ASRResult(transcript, [WordScore(word, conf)])
       ▼
5. Validation                     (validators.validate_spoken_text)
       │ tokenize → align_words (DP edit-distance, with ASR_HOMOPHONES for single letters)
       │ → WER, accuracy, missing/incorrect/extra, AlignmentToken list
       ▼
6. Feedback synthesis             (feedback.build_feedback)
       │ score_to_level → random "Excellent!/Almost!/Try again!" line
       │ pronunciation_hints filtered by ASR confidence (<0.65) or string similarity (<0.7)
       ▼
7. Coaching expansion             (build_spoken_feedback_with_coaching)
       │ apply_pronunciation_overrides + auto_pronunciation_coaching (pronouncing → ARPAbet → "kuh ah t")
       │ append "let me read it for you: <sentence>"
       ▼
8. TTS reads each line            (tts.speak per line; blocking unless engine is non_blocking)
       ▼
9. Level book-keeping             (try_level_up / advance_to_next_sentence)
       │ thresholds in app.py: 0.85 phonics, 0.88 2A, 0.90 2B … 1.01 (never) for 3/4
       ▼
10. State pushed via event_queue  ("state", "listening") → main thread renders next frame
```

Worker–main thread coupling is via `queue.Queue` of `(event, payload)` tuples
plus direct writes to `app.state`, `app.prompt_active`, `app.expected_sentence`,
etc. The worker mutates app state without locking.

---

## 4. Performance Issues on Raspberry Pi 5

These are the things most likely to hurt on Pi 5 (vs. dev macOS):

1. **Kokoro-ONNX is too heavy for Pi 5.** The bundled model is 310 MB FP32
   (`kokoro-v1.0.onnx`). README points to the int8 variant but the default
   filename in `settings.ini`/CLI is the FP32 file. On a Pi 5 the first
   synthesis can take 10–30 s and each subsequent one ~real-time at best.
   Force int8 (`kokoro-v1.0.int8.onnx`) or default Pi to Piper.
2. **`draw_gradient` runs every frame at 60 FPS.** `ui_helpers.draw_gradient`
   draws one `pygame.draw.line` per vertical pixel of the screen (~720 lines)
   each frame – pure Python, no caching. Cache to a `Surface` once.
3. **Avatar/bot frames rescaled every frame.** `_draw_bot` calls
   `pygame.transform.smoothscale` per render; `IntroScene` does the same.
   Pre-scale on state change.
4. **Two animation systems running in parallel.** `AvatarAnimator` (faces/)
   *and* the per-scene `bot_frames` loader (bot/) both load PNGs and tick
   independently. Reading prompt drives bot/, intro drives faces/. Pick one.
5. **Per-attempt `pyttsx3.init()`** (engines/base.py `Pyttsx3TTS.speak`) is
   slow; on Linux/eSpeak it spins up a fresh engine every call. Reuse it.
6. **Vosk model loaded twice in `vosk_engine.py`.** The version in `base.py`
   pre-loads in `__init__` *and* in `transcribe`; the version in
   `asr/vosk_engine.py` and `asr/simulated.py` calls `vosk.Model()` again
   inside `transcribe()`. On Pi the second load = several seconds.
7. **`KaldiRecognizer` created per attempt at the device default sample rate**
   (typically 48 kHz on ReSpeaker), but the Vosk small model is trained at
   16 kHz – this both wastes CPU and degrades accuracy. Force 16 kHz and
   downsample on the input stream.
8. **`_apply_warmth` for Piper buffers the entire utterance** before playback
   – first audible byte is delayed. Stream it.
9. **Three placeholder files are listed as duplicate ASR sources** (`base.py`,
   `vosk_engine.py`, `simulated.py` all contain near-identical Vosk code) –
   on import this isn't a perf issue but it confuses dependency analysis
   (see §7).
10. **`bool` fullscreen logic is inverted.** In `app.py` line 178:
    `fullscreen = True if not self.config.fullscreen else self.config.fullscreen`
    always evaluates `True`, forcing fullscreen on every launch. This makes
    benchmarking windowed mode misleading.
11. **`time.sleep(0.6)` in the worker** between attempts plus blocking
    `tts.speak` per line means an attempt cycle is dominated by serial TTS
    waits, not compute. Pipeline the next listen behind the last feedback line.

---

## 5. Missing Components

**Architectural placeholders that the migration plan says should exist:**

- `core/models.py`, `core/exceptions.py`, `core/constants.py` — typed domain
  objects (`AttemptResult`, `LevelProgress`) and a custom exception hierarchy
- `speech/interfaces.py` and `ui/interfaces.py` — protocol/ABC contracts so
  the GUI can be swapped or unit-tested
- `speech/asr/factory.py` — counterpart to `tts/factory.py`; today
  `cli/main.py` constructs ASR by hand
- `services/app_service.py`, `services/session_manager.py` — the layer that
  owns level progression (currently mixed into `EllaGUIApp` and
  `ReadingPromptScene`)
- `validation/alignment.py`, `validation/confidence.py` — split out of
  `validators.py` per plan
- `config/base.py`, `config/defaults.py` — typed config schema; today
  `loader.py` is a long `if parser.has_option…` ladder
- `utils/logging.py`, `utils/audio.py` — central logging (replace `print`)
  and audio resampling / device probing
- `ui/pygame_gui/components/{button,menu,dialog}.py` — pause modal and menu
  buttons are still inlined in scenes
- `ui/console/console_ui.py` exists but `cli/main.py` only calls `run_gui` —
  no `--no-gui` path
- `tests/` — zero tests; `scripts/smoke_test.bat` is essentially empty
- Settings scene / Tutorial scene — wired in main menu as "coming soon"
- Progress persistence — `level_indices` reset on restart
- Microphone calibration / VAD — fixed `listen_seconds` window; no
  silence-based endpointing

**Documentation/distribution gaps:**

- `requirements.txt` is a comment-only file; pyproject's `dependencies` omits
  `numpy`, `kokoro-onnx`, `pronouncing` (it's listed) — installing fresh on
  Pi will fail until extras are added
- No `[project.optional-dependencies]` groups (e.g. `pi`, `kokoro`, `piper`)
- No systemd unit / kiosk autostart guidance
- No license file

---

## 6. Suggested Modularization

1. **Break up `ReadingPromptScene` (633 lines).** Extract:
   - `services/attempt_runner.py` – the worker thread (TTS → ASR → validate
     → feedback → TTS), returning an `AttemptResult`
   - `ui/pygame_gui/components/pause_modal.py` and `confirm_modal.py`
   - `ui/pygame_gui/bot_sprite.py` – the second animation system
   The scene then only orchestrates input events, modal state, and rendering.
2. **Promote `EllaGUIApp` level state into `services/session_manager.py`** so
   the same progression logic could drive a console UI or a test.
3. **Type the config.** Replace `config/loader.py`'s ladder with
   `pydantic` (or `dataclasses` + `from_ini`) producing an `AppConfig`
   passed everywhere instead of an `argparse.Namespace`.
4. **Use the existing interfaces stubs.** Define `ASREngine`, `TTSEngine`,
   `UIShell`, `ProgressionPolicy` Protocols in `speech/interfaces.py` /
   `ui/interfaces.py`. Then write an `ASRFactory` mirroring `build_tts`.
5. **Move sprite/asset loading out of render paths** into a one-time
   `AssetCache` (pre-scaled per state).
6. **Add a `core/events.py`** with concrete event dataclasses instead of
   `("state", "listening")` tuples — eliminates the per-event `isinstance`
   ladder in `_drain_event_queue`.
7. **Single source of truth for the level list.** `level_order`,
   `level_thresholds`, and `level_pools.json` are scattered between
   `app.py`, `cli/main.py` choices, and the README. Centralize in
   `services/level_catalog.py`.
8. **Replace `print()` with `logging`** (level filtering, ring-buffer of
   recent errors already conceptually exists as `self.error_log`).

---

## 7. Files That Appear Unused (or Effectively Dead)

| File | Status |
|---|---|
| `main.py` (root) | Self-marked "deprecated"; only a shim into `cli/main.py` |
| `test.wav`, `test5.wav`, `test7.wav` | ~1.2 MB total at repo root, no code references |
| `faces/*.png` (whole tree) | Loaded by `AvatarAnimator`, but the live `ReadingPromptScene` only renders `bot/` frames. `IntroScene` uses the animator. Either the bot/ or faces/ tree is redundant for most runtime. |
| `config/empty_overrides.json` | Not referenced from code |
| `scripts/smoke_test.bat` | Windows-only batch placeholder; never invoked in CI |
| `src/ella_bot/ui/console/console_ui.py` | Functional, but `cli/main.py` always calls `run_gui` |
| `src/ella_bot/speech/asr/base.py`, `simulated.py`, `vosk_engine.py` | All three contain near-duplicate copies of `BaseASR`, `SimulatedASR`, `VoskASR`. `cli/main.py` imports only `SimulatedASR` from `simulated.py` and `VoskASR` from `vosk_engine.py`; `base.py` is dead. |
| `src/ella_bot/utils/{logging,audio}.py` | Placeholder `pass` |
| `src/ella_bot/core/{models,exceptions,constants}.py` | Placeholder `pass` |
| `src/ella_bot/services/*.py` | Placeholder `pass` |
| `src/ella_bot/validation/{alignment,confidence}.py` | Placeholder `pass` (logic actually lives in `validators.py`) |
| `src/ella_bot/config/{base,defaults}.py` | Placeholder `pass` |
| `src/ella_bot/speech/interfaces.py`, `ui/interfaces.py` | Placeholder `pass` |
| `src/ella_bot/ui/pygame_gui/components/{button,dialog,menu}.py` | Placeholder `pass` (live buttons are inlined in scenes) |
| `src/ella_bot.egg-info/` | Build artifact – should be `.gitignore`d |
| `MIGRATION_PLAN.md`, `MIGRATION_NOTES.md` | Migration is partly done; keep or archive |

`loader.py` also reads `start_level`, `sentence_file`, `use_mic`,
`vosk_model`, etc., but `sentence_file` and `use_mic` aren't matched in
`parse_args` so they're silently dropped — half-dead config keys.

---

## 8. Security & Stability Concerns

**Stability**

1. **Hard-coded relative path in `app.py`:** `open("config/level_pools.json")`
   breaks if the app is launched from any directory other than the project
   root. Should use `get_project_root() / "config" / "level_pools.json"`.
2. **Fullscreen toggle is inverted** (see §4 #10) – `--fullscreen False` has
   no effect.
3. **Thread safety:** `_attempt_worker` mutates `app.prompt_active`,
   `app.state`, `app.expected_sentence`, `app.completed_in_level`,
   `app.latest_attempt` directly from the worker thread. The main thread
   reads them every frame. Race-prone (especially `expected_sentence`
   changing mid-render).
4. **`tts.stop()` is not consistent.** Pausing during Kokoro calls
   `sd.stop()` but the worker may already be inside a blocking
   `kokoro.create()` (ONNX session) which cannot be interrupted – the
   "paused" state lies until the synthesis completes.
5. **Bare `except Exception:` swallowing** is used in 20+ places (asset
   loading, TTS warmups, COM init, override parsing). Failures look like
   silent no-ops; only `print` to stderr in some paths.
6. **Vosk model load happens lazily inside `transcribe()`** in `vosk_engine.py`
   – first attempt blocks the worker for seconds while the UI sits in
   "listening" state. The `base.py` copy fixes this but isn't the one
   imported.
7. **Pre-warm in `KokoroTTS.__init__`** is a daemon thread that does
   `self._kokoro.create(" ", …)` — if the user clicks Start before warmup
   finishes, the lock serializes and the first attempt blocks indefinitely.
   No timeout, no UI affordance.
8. **No persistence:** crash or reboot → child is back to 1A.
9. **No backpressure on `event_queue`** – an error storm in the worker
   could fill it and starve the renderer.
10. **`level_thresholds["3"] = 1.01`** means level 3 and 4 are unreachable
    via `_try_level_up`; advancement only happens via `advance_to_next_sentence`
    when feedback starts with "Excellent/Great/...". That coupling to TTS
    string content is fragile.

**Security**

1. **`pronunciation_overrides.json` loaded with `json.loads`** then strings
   are fed into `tts.speak()` (subprocess args for espeak/say/Piper). All
   engines use `subprocess.Popen` with an argv list (no `shell=True`), so
   command-injection risk is low — but Piper writes user text to stdin,
   espeak/say put it on argv. Worth sanitizing length / control chars to
   avoid weird ALSA crashes.
2. **`load_pronunciation_overrides` silently returns `{}` on any parse
   error** – a malformed override file gives no diagnostic to the operator
   (a kiosk owner won't know overrides are off).
3. **No model integrity check.** Vosk and Kokoro models are loaded from
   disk paths supplied via CLI/`settings.ini`; a tampered model directory
   could load arbitrary native code through ONNX runtime or Kaldi. For a
   kiosk shipped to families this matters – ship a manifest with SHA-256s.
4. **`build_tts` calls `subprocess.run(["lsmod"], …)`** with `check=False`
   to detect ReSpeaker. Fine on Pi, fails gracefully elsewhere, but should
   be skipped on non-Linux to avoid the spawn cost.
5. **`.claude/settings.local.json`** is tracked – review it doesn't contain
   anything machine-specific you didn't mean to publish.
6. **Egg-info checked in** (`src/ella_bot.egg-info/`) leaks dev paths;
   should be in `.gitignore`.
7. **Microphone always-on for `listen_seconds`** is acceptable for the
   product, but there's no on-screen recording indicator beyond the bot
   sprite – worth making explicit for parental trust.

---

## Quick-win Punch List (highest leverage first)

1. Fix `get_project_root()` for `level_pools.json` in `app.py`.
2. Fix inverted fullscreen logic (`app.py` ~line 178).
3. Cache the gradient background to a `Surface`.
4. Force Vosk to 16 kHz; downsample mic input.
5. Default Kokoro path to the `int8` model; gate Kokoro by platform on Pi.
6. Delete the dead duplicate of `BaseASR/VoskASR` in `speech/asr/base.py`.
7. Pre-scale bot/face sprites on state change instead of per frame.
8. Replace `print` with a `logging` config and persist last N errors.
9. Add `[project.optional-dependencies]` (`kokoro`, `piper`, `pi`) and
   declare `numpy`, `kokoro-onnx` explicitly.
10. Extract `_attempt_worker` into `services/attempt_runner.py` and put the
    worker's writes to `app` behind a single `update_state(...)` method
    that takes the GUI lock — eliminates the thread races.
