# Student Technical Handbook Design

Date: 2026-08-08

## Purpose

Create one self-contained technical handbook that helps high-school students
understand the entire ELLA codebase. The handbook must remain useful to readers
with coding experience while teaching unfamiliar terms and ideas to beginners
before relying on them.

The handbook will be added as `docs/STUDENT_TECHNICAL_HANDBOOK.md`. The existing
uncommitted `docs/TECHNICAL_DOCUMENTATION.md` draft will remain unchanged.

## Audience and Teaching Level

The audience is high-school students with mixed programming experience. The
writing will therefore use a layered teaching pattern:

1. Explain the idea in plain language.
2. Identify the relevant files.
3. Walk through what happens at runtime.
4. Show a short, verified code example when it adds understanding.
5. Point out common mistakes or misconceptions.
6. Place advanced implementation detail in an optional deeper section.

Technical terms such as ASR, TTS, event loop, thread, interface, factory, and
serialization will be defined when first introduced and collected in a
glossary. Analogies will support the explanation but will not replace accurate
technical descriptions.

## Documentation Approach

The handbook will use a layered learning journey rather than listing files in
alphabetical order. It will begin with what students see when they use ELLA,
trace one reading attempt through the application, and then examine each
subsystem. A module reference near the end will provide directory-level
completeness.

This approach was selected over two alternatives:

- A directory-first reference would be easy to look up but difficult for a
  beginner to understand as a connected system.
- A concept-first programming textbook would be approachable but too long and
  too far removed from the actual repository.

## Scope

### In-depth coverage

- Python application entry points and command-line interface
- Configuration loading and runtime dependency construction
- Core models, constants, events, and exceptions
- Reading-attempt orchestration and evaluation
- Automatic speech recognition, including simulated and Vosk engines
- Text-to-speech interfaces, engine selection, Piper, and fallback engines
- Pronunciation overrides and prerecorded prompt audio
- Profile, session, and checkpoint persistence
- Pygame application loop, scenes, components, animations, and media
- Validation, feedback, progression, and retry behavior
- Tests, fixtures, mocks, and safe extension practices
- Scripts used to run, test, or inspect the application

### High-level coverage

- The bundled `seeed-voicecard` Linux driver subtree, because its kernel-level
  C and hardware integration are substantially more advanced than ELLA's
  Python application
- Large binary, image, animation, font, video, and audio assets, catalogued by
  role rather than described file by file
- Historical migration and design documents, described by purpose and current
  relevance
- Scratch files and screenshots, clearly separated from production runtime
  code

Runtime profile and session data will be explained by schema and lifecycle.
The handbook will not reproduce personal student data from repository files.

## Handbook Structure

### Part I: Orientation

- Intended audience and ways to use the handbook
- What ELLA does and does not do
- Offline operation, speech recognition, and speech synthesis
- Technologies and external dependencies
- Repository map
- Five-minute system mental model
- Architecture diagram
- One complete reading-attempt walkthrough

### Part II: Application Internals

- Startup, entry points, CLI flags, and configuration precedence
- Core domain objects and event types
- Practice-level and session workflow
- ASR engines, captured audio, transcripts, and confidence
- TTS contract, factory, engines, overrides, and prerecorded playback
- Validation, scoring, feedback, and progression rules
- Services for attempts, profiles, sessions, checkpoints, and effects
- GUI event loop, scene lifecycle, transitions, components, animation, input,
  responsive layout, and media backgrounds
- INI and JSON data formats, generated files, and privacy considerations
- Concurrency, error handling, logging, fallbacks, and failure paths

### Part III: Working With the Project

- Installation and execution on Windows, Linux, and Raspberry Pi
- Required versus optional software and model files
- Running and understanding the pytest suite
- Adding or changing tests safely
- Troubleshooting audio, models, assets, configuration, and displays
- A guided first code-reading tour
- Small, safe student exercises

### Part IV: Reference

- Module-by-module Python source reference
- Configuration and data-file reference
- Assets, scripts, screenshots, scratch files, and historical documents
- High-level Raspberry Pi and Seeed voice-card explanation
- Security, privacy, accessibility, and offline-operation notes
- Glossary and further-learning directions
- Final architecture recap and change-impact guide

## Diagrams and Examples

Mermaid diagrams will be used only where relationships are clearer visually:

- Major subsystem architecture
- Startup and dependency construction
- Scene transitions
- Reading-attempt sequence
- Data persistence flow
- TTS and ASR selection/fallback flow

Examples will be short excerpts or simplified pseudocode tied to the current
source. Any simplified example will be labelled as such. File paths and symbol
names will be checked against the live repository.

## Accuracy and Source of Truth

The live Python source, configuration files, package metadata, and tests are
the source of truth. Existing documentation may provide context but will not be
copied without verification. This is important because the preserved
`docs/TECHNICAL_DOCUMENTATION.md` draft currently mentions components that do
not exist in the live tree and describes some behavior differently from the
implementation.

The documentation pass will inspect every meaningful Python module and test
module. It will distinguish:

- Current runtime behavior
- Optional or fallback behavior
- Development-only utilities
- Generated data
- Historical plans
- Third-party or externally maintained code

Unknown or environment-dependent behavior will be labelled explicitly instead
of presented as a guaranteed fact.

## Error Handling and Troubleshooting Coverage

The handbook will explain how errors move through command startup, audio
engines, worker threads, application events, scene state, and persistence. It
will document existing fallbacks and note where the application logs, surfaces,
or suppresses failures. Troubleshooting advice will map observable symptoms to
likely causes and safe diagnostic commands.

## Verification

Before completion:

- Check all documented paths and Python symbols against the repository.
- Compare configuration examples with `AppConfig`, the CLI parser, and
  `config/settings.ini`.
- Compare architecture and workflows with the implementation and tests.
- Run the relevant automated test suite when the environment permits.
- Scan the handbook for placeholder text, broken local links, contradictions,
  unexplained jargon, and claims inherited from obsolete documents.
- Confirm that `docs/TECHNICAL_DOCUMENTATION.md` was not modified.

## Deliverable

The final deliverable is one new Markdown file:

`docs/STUDENT_TECHNICAL_HANDBOOK.md`

It will be self-contained, navigable through a table of contents, readable in a
standard Git hosting interface, and detailed enough to serve both as a guided
lesson and as a practical codebase reference.
