# English Phonics for Levels 1A and 1B

**Date:** 2026-07-23

## Goal

Make ELLA demonstrate standard beginner English phonics sounds for the single-letter targets in levels 1A and 1B. Keep student recognition, scoring, accepted answers, and level progression unchanged.

## Current Behavior

`config/pronunciation_overrides.json` supplies the spoken form used when `AttemptRunner` announces a target and when corrective coaching models it. The level 1A entries currently use Filipino-style vowel sounds, while level 1B adds a spoken schwa to most consonants, such as `buh` and `kuh`.

The validation path is separate. `src/ella_bot/validation/validators.py` uses `ASR_HOMOPHONES` to interpret Vosk transcripts for single-item lessons. It does not consume the pronunciation override file.

## Design

Update only the single-letter entries at the beginning of `config/pronunciation_overrides.json`.

Level 1A will use the common short English vowel phonemes:

- `a` → /æ/ as in *apple*
- `e` → /ɛ/ as in *egg*
- `i` → /ɪ/ as in *igloo*
- `o` → /ɑ/ as in *octopus* in American English
- `u` → /ʌ/ as in *up*

Level 1B will use the standard beginner consonant phonemes without an added schwa:

- `b` /b/, `c` /k/, `d` /d/, `f` /f/, `g` /ɡ/, `h` /h/
- `j` /dʒ/, `k` /k/, `l` /l/, `m` /m/, `n` /n/, `p` /p/
- `q` /kw/, `r` /ɹ/, `s` /s/, `t` /t/, `v` /v/, `w` /w/
- `x` /ks/, `y` /j/, `z` /z/

The mappings will use the existing `phonemes:` form supported by the configured Piper engine. The consonant choices follow the usual beginner convention: hard C as in *cat*, hard G as in *go*, and X as /ks/.

All consonant-vowel blend entries used by levels 1C–1G remain unchanged.

## Data Flow

1. `AttemptRunner` gets the current single-letter target from `SessionManager`.
2. `overrides_for_level()` exposes the pronunciation overrides for Tier 1.
3. The runner substitutes the revised direct phoneme value into the initial announcement or corrective model.
4. Piper synthesizes the English phoneme sequence.
5. Vosk transcription and `validate_spoken_text()` continue through the existing, unchanged grading path.

## Error Handling

No new runtime branch or fallback is required. The existing attempt runner catches TTS errors and posts an `ErrorOccurred` event. This change uses the same override format already supported by Piper.

## Testing

Add focused tests that load the real override file and assert the exact English phoneme mappings for every level 1A and 1B target. Retain existing tests that prove Tier 1 overrides are used and Tier 2 words do not receive phonics overrides.

Run the pronunciation/attempt test subset and the complete automated suite. An audible smoke test with representative vowel and consonant targets is recommended because text assertions cannot evaluate synthesized sound quality.

## Out of Scope

- No changes to `ASR_HOMOPHONES` or any validator logic
- No removal of currently accepted student pronunciations
- No scoring, threshold, curriculum-pool, or progression changes
- No changes to level 1C–1G blend pronunciations
- No new recorded audio assets or TTS engine abstraction
