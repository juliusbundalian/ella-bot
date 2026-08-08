# Strict Fluency Confidence Threshold

## Goal

Reduce false reading failures in Levels 3 and 4 when Vosk recognizes a word correctly but assigns it modest confidence.

## Design

Define a named validation-module constant, `STRICT_FLUENCY_CONFIDENCE`, with a value of `0.35`. During strict-fluency validation, an otherwise matching word remains correct when its confidence is at least this value; a lower-confidence match remains an error.

Levels 1 and 2 remain unchanged because they do not enable strict fluency validation.

## Testing

Add validator tests that verify a matching strict-fluency word at `0.35` is accepted and one below `0.35` is rejected. Existing punctuation normalization and word-substitution behavior remain unchanged.
