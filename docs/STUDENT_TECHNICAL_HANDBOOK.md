# ELLA Student Technical Handbook

This handbook explains how the ELLA offline reading assistant works. It is
written for high-school students: you do not need to be an experienced
programmer, but readers who already know Python will still find implementation
details and file references.

The descriptions in this handbook were checked against the source code and
tests present on 8 August 2026. ELLA is still being developed, so future code
may behave differently.

## Table of Contents

- [Part I — Meet ELLA](#part-i--meet-ella)
  - [Choose a reading path](#choose-a-reading-path)
  - [What ELLA does](#what-ella-does)
  - [The important vocabulary](#the-important-vocabulary)
  - [Technologies used](#technologies-used)
  - [Repository map](#repository-map)
  - [A five-minute mental model](#a-five-minute-mental-model)
  - [System architecture](#system-architecture)
  - [First walkthrough](#first-walkthrough)
- [Part II — Follow the Program](#part-ii--follow-the-program)
- [Part III — Understand the Subsystems](#part-iii--understand-the-subsystems)
- [Part IV — Work With the Project](#part-iv--work-with-the-project)
- [Part V — Repository Reference](#part-v--repository-reference)
- [Glossary](#glossary)
- [Final Architecture Recap](#final-architecture-recap)

## Part I — Meet ELLA

### Choose a reading path

You can use this handbook in different ways:

- **New coder:** Read Part I in order, follow one practice attempt in Part II,
  and use the glossary whenever a new term appears. Then try the guided tour
  and exercises in Part IV.
- **Student who knows Python:** Skim Part I, study Parts II and III, and use the
  module tables in Part V while reading the source beside this handbook.
- **Teacher or mentor:** Begin with the architecture and privacy sections, then
  choose individual subsystem chapters for lessons.

> **Reading tip:** A file path such as `src/ella_bot/services/evaluation.py`
> tells you where to look. A name such as `EvaluationService` identifies a
> class inside that file. You do not need to understand every line on your
> first reading.

### What ELLA does

ELLA is an interactive reading-practice application. A learner chooses a local
profile and a reading level. ELLA shows or plays a sound, word, phrase, or
sentence; may listen through a microphone; evaluates the response; provides
encouraging feedback; and saves progress for later.

Its curriculum moves through four broad tiers:

1. **Tier 1, levels 1A–1G:** vowels, consonants, letter combinations, and
   blends. These levels mainly use prerecorded demonstrations and practice.
2. **Tier 2, levels 2A–2D:** sight words and increasingly difficult words.
3. **Tier 3:** phrases.
4. **Tier 4:** complete sentences.

The canonical level order, thresholds, and attempt limits live in
`src/ella_bot/core/constants.py`; the actual practice pools live in
`config/level_pools.json`.

ELLA is designed to run without sending a learner's voice or progress to a
cloud service. Vosk speech recognition, Piper speech synthesis, the GUI, and
saved profiles all run locally. “Offline” describes normal operation after the
software, speech models, and dependencies have been installed. Downloading
those items initially may require internet access.

ELLA is not a general conversational artificial intelligence system. It does
not invent lessons from an online language model, diagnose speech or learning
conditions, or replace a teacher. Its decisions come from configured lesson
items and explicit Python rules.

### The important vocabulary

| Term | Beginner-friendly meaning | ELLA example |
|---|---|---|
| **Application** | A complete program a person uses. | The ELLA reading assistant. |
| **Module** | Usually one Python `.py` file containing related code. | `evaluation.py` contains evaluation data types and logic. |
| **Class** | A reusable blueprint combining data and behavior. | `ProfileStore` manages learner profiles. |
| **Service** | Code focused on one application job rather than drawing a screen. | `SessionManager` controls lesson position and progression. |
| **GUI** | Graphical user interface: screens, pictures, text, and buttons. | ELLA's Pygame interface. |
| **CLI** | Command-line interface: options typed in a terminal. | `ella-bot --start-level 2a`. |
| **ASR** | Automatic speech recognition: sound becomes text. | Vosk transcribes microphone audio. |
| **TTS** | Text-to-speech: text becomes spoken audio. | Piper reads a prompt aloud. |
| **Configuration** | Settings that change behavior without changing source code. | `listen_seconds = 8` in `settings.ini`. |
| **Persistence** | Saving data so it survives after the program closes. | Profiles, checkpoints, and history files. |
| **Event** | A small message saying that something happened. | `AttemptReady` tells the app an attempt finished. |
| **Test** | Code that checks whether other code behaves as expected. | A test verifies that a corrupt checkpoint is archived. |

### Technologies used

The package declaration in `pyproject.toml` requires Python 3.9 or newer. The
README recommends Python 3.10 or newer. Using 3.10+ is the safer student setup
because some optional speech tools may have narrower support than ELLA's own
Python code.

| Technology | Role in ELLA | Required or conditional |
|---|---|---|
| Python | Main programming language. | Required. |
| Pygame CE | Window, drawing, pointer/keyboard events, audio mixer. | Required by package metadata. |
| Vosk | Local speech-to-text model and recognizer. | Used when microphone mode is enabled. |
| `sounddevice` | Captures microphone samples for Vosk. | Used with microphone ASR. |
| Piper | Main configured local TTS engine. | Used when audio feedback selects Piper. |
| `pyttsx3`, eSpeak, macOS `say` | Alternative local TTS paths. | Platform- or configuration-dependent. |
| NumPy | Numeric audio arrays and sound processing. | Required by package metadata. |
| `pronouncing` | CMU pronunciation dictionary used for coaching hints. | Required by package metadata. |
| `rlottie-python` | Renders Lottie vector animations. | Used when compatible animation data loads. |
| OpenCV headless | Decodes video backgrounds without opening its own window. | Used for video backgrounds. |
| JSON, JSONL, INI | Text formats for lessons, progress, history, and settings. | Python's standard library reads/writes them. |
| pytest | Automated test runner. | Development dependency. |

Kokoro appears as a supported TTS choice in the code, but its package is not
declared in `pyproject.toml`. It is therefore an optional, manually installed
backend. Model files under `models/` and the Windows Piper executable under
`piper/` are runtime resources rather than ordinary Python packages.

### Repository map

This is a purpose-based map, not a list of every media file:

```text
ella-bot/
├── src/ella_bot/          Main Python package
│   ├── cli/               Startup and command-line wiring
│   ├── config/            Load and save application settings
│   ├── core/              Shared level constants and event messages
│   ├── services/          Attempts, progress, profiles, sessions, audio
│   ├── speech/            ASR/TTS interfaces, factories, and engines
│   ├── ui/                Console helper and Pygame GUI
│   ├── utils/             Path and logging helpers
│   └── validation/        Text comparison and learner feedback
├── tests/                 Automated application tests
├── config/                INI and JSON configuration/lesson data
├── assets/                Images, fonts, videos, animations, and lesson audio
├── bot/ and faces/        Robot animation frame collections
├── models/                Local speech model files (environment resources)
├── piper/                 Local Piper executable/resources
├── data/                  Generated profile registry, checkpoints, and history
├── scripts/               Audition, desktop-launch, sound, and smoke utilities
├── scratch/               Experiments and generated development previews
├── docs/                  Guides, reports, designs, and implementation plans
├── seeed-voicecard/       External Linux/ReSpeaker driver source
├── pyproject.toml         Python packaging and dependency declaration
├── README.md              Short setup and project overview
└── main.py                Deprecated compatibility launcher
```

Important boundaries:

- `src/ella_bot/` is the production application code.
- `tests/` is verification code; it is not imported during a normal lesson.
- `data/` changes while people use ELLA. Treat it as private runtime data, not
  as curriculum source.
- `scratch/` contains experiments, not supported application features.
- `docs/superpowers/` records historical designs and plans. These explain why
  changes were considered but do not override the current source.
- `seeed-voicecard` is recorded by Git as a submodule-style entry, but this
  checkout has no matching `.gitmodules` mapping. Its files are present, yet
  Git's usual `submodule` command cannot fully manage that relationship here.

The media is much larger than the Python source: `assets/` alone is about
90 MB in this checkout. Large size does not mean architectural importance;
videos and audio contain data, while Python modules contain decisions.

### A five-minute mental model

Think of ELLA as a small school team:

- The **CLI and configuration loader** prepare the classroom.
- The **Pygame app** coordinates the lesson and changes screens.
- A **scene** draws one screen and reacts to input.
- The **session manager** knows which item and level come next.
- The **attempt runner** coordinates speaking, listening, checking, and
  posting a result.
- The **ASR engine** turns microphone audio into words.
- The **validator** aligns expected and recognized words.
- The **feedback code** turns comparison details into learner-friendly text.
- The **evaluation service** summarizes attempts and ratings.
- The **profile/checkpoint stores** preserve progress safely.
- The **TTS engine and sound-effects service** produce spoken and prerecorded
  audio.

The analogy is helpful, but ownership matters technically: `EllaGUIApp` owns
the major services and current UI state; scenes receive the app and call those
services rather than constructing independent copies.

### System architecture

```mermaid
flowchart LR
    Learner[Student] --> UI[Pygame scenes]
    CLI[CLI + settings.ini] --> App[EllaGUIApp]
    App --> UI
    App --> Session[SessionManager]
    App --> Runner[AttemptRunner]
    App --> Eval[EvaluationService]
    App --> Profiles[ProfileStore]
    App --> Checkpoint[SessionCheckpointStore]
    Runner --> ASR[ASR engine]
    Runner --> TTS[TTS engine]
    Runner --> Validate[Validation + feedback]
    Runner --> Session
    Runner --> Eval
    UI --> SFX[Sound effects + prerecorded prompts]
    Profiles --> Disk[(Local JSON files)]
    Checkpoint --> Disk
    Eval --> History[(Local JSONL history)]
    ASR --> Mic[Microphone]
    TTS --> Speaker[Speaker]
    SFX --> Speaker
```

Arrows mean “uses” or “sends data to.” For example, the attempt runner uses an
ASR engine; the ASR engine does not control the attempt runner.

### First walkthrough

The preferred installed command is:

```bash
ella-bot
```

`pyproject.toml` maps that command to `ella_bot.cli.main:main`. The call path is:

```text
main()
  → parse_args()                         CLI values + settings.ini defaults
  → run_gui(args)
      → build_asr(args)                  simulated or Vosk
      → build_tts_if_enabled(args)       none or selected speech engine
      → load_pronunciation_overrides()
      → EllaGUIApp(...)
      → EllaGUIApp.run()                 Pygame event loop
```

The root `main.py` reaches the same function but prints a deprecation warning.
The `--gui` setting is currently parsed and loaded, yet `main()` always calls
`run_gui`; there is no active CLI branch to a console-only lesson.

Command-line values normally override defaults loaded from
`config/settings.ini` because `argparse` reads the INI values with
`set_defaults()` before parsing the command line. Not every possible
configuration value is a CLI option, and unknown keys are ignored by
`load_settings()`.

## Part II — Follow the Program

### From a terminal command to a running app

`main()` in `src/ella_bot/cli/main.py` has a deliberately small job: parse
settings and start the GUI. The work is separated so tests can check argument
parsing and engine construction without opening a real window.

The startup stages are:

1. `load_settings()` reads recognized keys from `config/settings.ini` into a
   Python dictionary.
2. `ArgumentParser.set_defaults()` uses that dictionary as the CLI defaults.
3. `parse_args()` replaces a default when the user supplies a command-line
   option.
4. `run_gui()` resolves paths and maps numeric shortcuts `1` and `2` to `1a`
   and `2a`.
5. The ASR factory constructs `SimulatedASR` or `VoskASR`.
6. If audio feedback is enabled, the TTS factory constructs a speech engine;
   otherwise the app receives `None`.
7. `EllaGUIApp` constructs the shared services, scenes, profile store, and
   runtime state, then `run()` starts Pygame.

```mermaid
flowchart TD
    INI[config/settings.ini] --> Parse[parse_args]
    Terminal[Command-line options] --> Parse
    Parse --> Paths[Resolve project-relative paths]
    Paths --> ASRFactory[ASR factory]
    Paths --> TTSFactory[TTS factory, if enabled]
    ASRFactory --> App[EllaGUIApp]
    TTSFactory --> App
    Overrides[pronunciation_overrides.json] --> App
    App --> Loop[Pygame run loop]
```

`main()` catches any exception that escapes startup or the GUI and prints a
`[Runtime error]` message. This keeps a traceback from being the only message a
learner sees, but it also means the process does not currently return a
purpose-specific error code.

### Configuration precedence and dependency construction

**Precedence** means which setting wins when the same option appears in more
than one place:

```text
CLI option supplied by the user
        wins over
recognized value in config/settings.ini
        wins over
default written in parse_args()
```

For example, `settings.ini` currently sets an eight-second listening window.
Running `ella-bot --listen-seconds 5` changes it to five seconds for that run.
The Settings scene can persist selected values back to the INI file through
`save_setting()`.

Important current settings include:

| Section | Keys read by the application |
|---|---|
| `[System]` | `start_level`, `sentence_file`, `session_log` |
| `[Speech]` | `use_mic`, `vosk_model`, `listen_seconds`, `sample_rate`, `input_device` |
| `[TTS]` | `audio_feedback`, `tts_engine`, `tts_rate`, models, Piper synthesis values, `volume`, pronunciation overrides |
| `[GUI]` | `gui`, `fullscreen`, width, height, and left padding |

`sentence_file` is read into the defaults dictionary even though the present
CLI parser has no argument with that name. Conversely, not every internal
value is meant to be configured. This is a reminder that “present in a config
file” and “actively used by the runtime” are different claims.

Paths are resolved in three places:

- `resolve_existing_path()` tries the literal path and then the project root.
- `resolve_model_path()` in `utils/file_utils.py` puts bare model filenames
  under `models/`.
- `GUIConfig` receives an absolute or project-root-relative session log path.

A **factory** is a function that chooses and constructs an object. Factories
keep the CLI from knowing all constructor details. The ASR factory's decision
is simple: microphone mode means `VoskASR`; otherwise it creates
`SimulatedASR`. The TTS factory has more choices and fallbacks, described in
Part III.

### Core constants and immutable events

`src/ella_bot/core/constants.py` is the single Python source for:

- the ordered list of 13 levels;
- each level's pass threshold;
- the mapping from sublevel to tier;
- a maximum of one attempt per Tier 1 item and three attempts per later item;
- a ten-item session cap for Tier 2 and above.

Levels 3 and 4 have thresholds of `1.01`, which is above the maximum possible
accuracy of `1.0`. Tests explicitly call these “unreachable by threshold.”
Their completion is therefore handled through session/final-evaluation flow,
not ordinary automatic level-up based on a score above 101%.

`src/ella_bot/core/events.py` defines six frozen dataclasses:

| Event | Payload and purpose |
|---|---|
| `StateChanged` | A new robot/application state such as listening. |
| `MessageChanged` | New text for the scene to display. |
| `ErrorOccurred` | An error string that crossed a worker boundary. |
| `AttemptReady` | A completed attempt view model. |
| `SubLevelCompleted` | A result plus whether the result represents a sublevel or tier. |
| `SessionCompleted` | The final cumulative result. |

“Frozen” means code cannot replace a dataclass field after construction. That
makes an event safer to pass between threads: the sender and receiver cannot
quietly rewrite the same message. Some payloads are annotated as `Any`, so the
type checker cannot verify their exact shape; runtime tests provide part of the
contract.

`core/models.py` and `core/exceptions.py` currently contain only placeholder
statements. They are architectural space for future shared types, not active
model or error systems. This handbook does not assign them behavior they do
not have.

## Part III — Understand the Subsystems

### How ELLA listens: ASR

An ASR engine implements one main operation:

```python
transcribe(expected_sentence=None, is_paused=None) -> ASRResult
```

`ASRResult` contains the complete `transcript` and a list of `WordScore`
objects. Each word score contains a recognized word and Vosk's confidence from
`0.0` to `1.0`. Confidence is evidence from the recognizer, not a probability
that the learner understands the word.

#### Simulated recognition

`SimulatedASR` returns the text supplied with `--spoken`. Every simulated word
gets confidence `0.9`. This path is valuable for development because it tests
the lesson flow without requiring a microphone or model.

There are similarly named ASR classes in both `asr/simulated.py` and
`asr/vosk_engine.py`. The active factory imports `SimulatedASR` from the first
file and `VoskASR` from the second. The other duplicated definitions are not
selected by `build_asr()`.

#### Vosk microphone recognition

The active `VoskASR` performs these steps:

1. Load the local Vosk model during construction.
2. Open a persistent `sounddevice.RawInputStream` for mono, signed 16-bit audio.
3. Let the audio callback place byte chunks into a thread-safe queue.
4. At the start of an attempt, discard old queued audio and create a fresh
   `KaldiRecognizer`.
5. For `listen_seconds`, take chunks from the queue and feed them to Vosk.
6. Stop early with an empty result if the pause/cancel callback becomes true.
7. Parse Vosk's final JSON into the transcript and per-word scores.
8. Log capture time, decoded audio, remaining queue backlog, decoder time, and
   word confidences.

The default stream block size is 4,000 frames. The configured sample rate is
currently 16,000 samples per second. Because each mono sample is a signed
16-bit value (two bytes), one second contains about 32,000 audio bytes.

The stream starts early to reduce delay, but that creates a possible backlog;
the diagnostics make that visible. If opening the stream fails, construction
logs an error and continues with `_stream` unset. A later transcription tries
to start it again. Missing or invalid Vosk model files instead cause a detailed
`RuntimeError` during model loading.

The ASR does not use Whisper, a cloud API, or a file named
`post_processor.py`. Correction rules that compensate for known Vosk
misrecognitions are part of `validation/validators.py`.

### How ELLA speaks: TTS and prerecorded audio

The `TTSEngine` protocol says a compatible object must have `speak(text)` and
`stop()`. The richer `BaseTTS` also supplies optional `pause()`, `resume()`,
`set_volume()`, and `current_amplitude`. The amplitude value lets robot
animation react while speech is playing.

`TTSConfig` carries voice, rate, nonblocking mode, volume, Piper model and
synthesis values, and Kokoro model paths. A TTS call is **blocking** when it
does not return until speech playback finishes. Some engines support a
nonblocking mode that uses a subprocess or background thread.

#### Engine selection

An explicit engine name constructs that backend. For `auto`, the current order
is:

```mermaid
flowchart TD
    Start[auto] --> PiperModel{Piper model exists?}
    PiperModel -- yes --> Piper[Try Piper]
    PiperModel -- no or load fails --> KokoroFiles{Kokoro model + voices exist?}
    KokoroFiles -- yes --> Kokoro[Try Kokoro]
    KokoroFiles -- no or load fails --> OS{Platform}
    OS -- macOS --> Say[macOS say]
    Say --> Pyttsx3[pyttsx3 fallback]
    Pyttsx3 --> EspeakMac[eSpeak fallback]
    OS -- Linux/other --> Driver{Seeed/ac108 module loaded?}
    Driver -- yes --> ReSpeaker[ReSpeaker/eSpeak]
    Driver -- no or failure --> Espeak[eSpeak]
    Espeak --> Pyttsx3Linux[pyttsx3 fallback]
```

Explicit Piper or Kokoro selection also falls back to `auto` when required
model files do not exist. An unsupported name raises `ValueError`.

The classic backends—eSpeak, `pyttsx3`, macOS `say`, and ReSpeaker/eSpeak—are
implemented in `speech/tts/base.py`. Several same-named files under
`speech/tts/engines/` are placeholders; Piper and Kokoro are the implemented
neural engines in that folder.

#### Piper

`PiperTTS` loads one `PiperVoice` and reuses it. It synthesizes chunks, applies
a gentle three-point finite impulse response (FIR) smoothing filter, mixes 30%
of the smoothed signal with 70% of the original, peak-normalizes the result,
and sends signed 16-bit chunks to a `sounddevice.RawOutputStream`.

The filter operation is:

```python
smoothed = np.convolve(audio, [0.25, 0.50, 0.25], mode="same")
output = 0.70 * audio + 0.30 * smoothed
```

That is a short real excerpt from `_apply_warmth()`. It softens rapid sample
changes while retaining most of the original signal. Piper also:

- maps the configured words-per-minute rate to Piper's `length_scale`;
- clamps volume during normalization;
- serializes speech with `_speak_lock`, avoiding two voices writing together;
- streams roughly 50 ms playback pieces;
- reports each piece's peak amplitude for animation;
- checks stop and pause events between pieces;
- has a special `phonemes:` path for configured IPA-like phoneme strings.

The program catches and logs errors inside Piper playback rather than letting
them escape to the whole application. This keeps the UI alive, but a failed
utterance can be silent.

#### Kokoro and system voices

`KokoroTTS` warms its ONNX model on a daemon thread, uses voice `af_heart` when
none is selected, maps 150 words per minute to speed `1.0`, and plays generated
samples through `sounddevice`. Its dependency, `kokoro-onnx`, is optional and
must be installed separately.

eSpeak, macOS `say`, and ReSpeaker launch operating-system commands.
`pyttsx3` initializes an engine for each utterance; on Windows it also attempts
to initialize COM in the calling thread. These differences explain why one
backend may work on a laptop while another is better suited to the Pi.

Prerecorded Tier 1 lesson prompts are a separate path managed by
`services/sound_effects.py`. They do not pass through neural TTS at all. That
path is explained with the attempt runner later in this part.

### How ELLA compares spoken and expected text

Validation starts by extracting sequences matching letters and apostrophes and
lowercasing them. Punctuation and digits do not become comparison tokens.

For a phrase or sentence, `align_words()` uses dynamic programming: it builds a
table of the cheapest edits needed to transform recognized words into expected
words. Each operation is recorded as:

| Operation | Meaning | Cost |
|---|---|---:|
| `equal` | Words match or an allowed equivalent matches. | 0 |
| `sub` | A recognized word replaces an expected word. | 1 |
| `del` | An expected word is missing. | 1 |
| `ins` | An extra recognized word appears. | 1 |

Word error rate (WER) and accuracy are then calculated as:

```text
edits = missing + substitutions + extra
WER = edits / number of expected words
accuracy = max(0, 1 - WER)
```

Example: expected `we read books`, recognized `we red`. The alignment can count
`red` as an allowed homophone of `read`, then mark `books` as missing. That is
one edit across three expected words: WER is about `0.333`, and accuracy is
about `0.667`.

The implementation adds curriculum-specific fairness rules:

- common strict homophones such as `to`/`two` may match;
- dropped `-ed` and possessive endings can match in selected forms;
- known Vosk phrase substitutions are reversed only when the target word
  appears in the expected text;
- a single-item lesson succeeds if the target or one of its broad configured
  ASR equivalents appears anywhere in the transcript, ignoring extra noise;
- strict fluency mode turns an otherwise matching word into an error below
  `0.35` Vosk confidence.

The single-item equivalence tables are intentionally generous for early
phonics. They should not be interpreted as a general English homophone
dictionary.

`ValidationResult` keeps WER, accuracy, missing words, incorrect pairs, extra
words, and the complete alignment. `build_highlighted_expected()` places
brackets around nonmatching expected words for simple display.

### How feedback and pronunciation coaching are built

`build_feedback()` converts validation details into a `FeedbackResult`:

- accuracy at least `0.95` receives a randomly selected success phrase;
- accuracy from `0.75` to below `0.95` receives an “almost” phrase;
- lower accuracy receives a retry phrase;
- missing, substituted, and extra words become detail strings;
- up to four hint candidates are collected, while normal spoken feedback uses
  at most two.

The phrase selection is random, so tests check categories and contents instead
of relying on one permanent sentence.

Feedback distinguishes a sound, word, phrase, or sentence. On an unsuccessful
attempt it may identify the first difficult word, speak it slowly, demonstrate
the complete target, and invite another try. Manual pronunciation overrides
come from `config/pronunciation_overrides.json`.

Overrides need careful scoping. Entries such as `go` can represent a phonics
sound in Tier 1 but an ordinary word later. `overrides_for_level()` therefore
returns the table only for Tier 1. In multiword targets, common short words and
single letters are also excluded from targeted replacement so a normal
sentence is not mangled.

If no manual form is available, `auto_pronunciation_coaching()` can query the
CMU pronunciation dictionary through `pronouncing`, translate ARPAbet symbols
to child-friendly sound chunks, or fall back to a basic vowel-based syllable
split. ARPAbet is a set of text symbols for English speech sounds; for example,
`CH` maps to “ch.” This coaching is a practical heuristic, not a complete
phonetics engine.

## Part IV — Work With the Project

## Part V — Repository Reference

## Glossary

## Final Architecture Recap
