# Piper Consonant Audition Comparison

**Date:** 2026-07-23

## Goal

Create a safe audition comparison for the level 1B consonants using ELLA's existing Piper model. The comparison will help select clearer synthesis settings without changing normal application playback, using another voice, adding carrier words, restoring a schwa, or introducing recorded clips.

## Problem

Piper synthesizes several bare consonant phoneme sequences as very short, muffled, or speech-like artifacts. Reducing the global rate from 190 to 130 lengthens some generated audio but does not consistently improve clarity. Stop consonants cannot be made natural merely by stretching them, and aggressive stretching can introduce distortion.

The current Piper path also applies the same warmth filter and synthesis variability settings to isolated phonemes that it applies to longer speech. Those choices may obscure consonant cues or make isolated output less stable.

## Scope

Extend `scripts/audition_level.py` with an explicit Piper comparison mode. It will use only the configured `en_US-hfc_female-medium.onnx` model and will not alter ELLA's runtime TTS path.

The comparison will support one target at a time with `--only`, as well as all level 1B targets. For each target it will print the active variant before playing it and leave a clear pause between variants.

## Variants

The comparison will render these four variants from the same Piper voice. Rates use the existing Piper conversion of `length_scale = 200 / rate`:

1. **Current:** Rate 190, `noise_scale=0.667`, `noise_w_scale=0.8`, the warmth filter enabled, and no added silence. This is the control.
2. **Clean:** Rate 190, `noise_scale=0.3`, `noise_w_scale=0.3`, the warmth filter disabled, and no added silence.
3. **Relaxed:** Rate 145, `noise_scale=0.3`, `noise_w_scale=0.3`, the warmth filter disabled, and 200 ms of leading and trailing silence.
4. **Class-tuned:** `noise_scale=0.2`, `noise_w_scale=0.2`, the warmth filter disabled, and 250 ms of leading and trailing silence. Stop or affricate sounds use rate 170, continuous sounds use rate 125, and consonant sequences use rate 145. This avoids aggressive stretching of stop sounds while allowing continuous sounds more time.

The comparison will not repeat consonants, append vowels, or synthesize explanatory words.

## Consonant Classes

The class-tuned variant will distinguish:

- Stop or affricate sounds: B, C, D, G, J, K, P, T
- Continuous or continuable sounds: F, H, L, M, N, R, S, V, W, Y, Z
- Consonant sequences: Q and X

This classification controls duration only. The phoneme mappings in `config/pronunciation_overrides.json` remain unchanged during the comparison.

## Command-Line Interface

The existing audition behavior remains the default. Comparison mode will be opt-in:

```bash
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only b
./.venv/bin/python scripts/audition_level.py 1b --compare-piper
```

`--compare-piper` will require the Piper engine and model. It will reject incompatible options with a clear message rather than silently falling back to another engine.

## Data Flow

1. Load the level pool and level-scoped pronunciation overrides through the existing audition path.
2. Validate that comparison mode is running against level 1B phoneme entries and an available Piper model.
3. Convert each configured phoneme string to IDs once per variant using the existing Piper model API.
4. Apply only the variant's synthesis configuration and optional filter.
5. Add silence for listening separation where specified, then play the result through the existing audio device.
6. Print enough information to identify the target and variant being heard.

No generated audio files will be stored.

## Error Handling

- Report a missing or invalid Piper model before starting playback.
- Report an unavailable output device with the target and variant that failed.
- Reject comparison mode for levels other than 1B.
- Preserve the existing `--dry-run` behavior and avoid initializing audio during dry runs.
- Exit nonzero for invalid combinations rather than changing engines automatically.

## Testing

Add focused tests for argument validation, variant selection, consonant classification, and synthesis configuration. Audio-quality judgment remains a manual audition because automated tests cannot determine whether a consonant sounds natural.

Run the script tests and the existing Piper/pronunciation tests. Then audition representative stop, continuous, affricate, and sequence sounds before running all 21 consonants:

```bash
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only b
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only f
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only j
./.venv/bin/python scripts/audition_level.py 1b --compare-piper --only x
```

The user will choose a preferred variant or report that none is acceptable. Production playback will not be changed until that audible review is complete.

## Out of Scope

- Changing ELLA's runtime Piper behavior
- Changing the pronunciation override mappings
- Using eSpeak, another Piper voice, carrier words, or recorded audio
- Changing ASR, validation, accepted answers, scoring, or progression
- Claiming that tuning can overcome every limitation of the voice model
