# ASR Attempt Diagnostics

## Goal

Expose enough debug information to determine whether Vosk decoding is falling behind live microphone capture on the Raspberry Pi.

## Design

At the end of each microphone transcription attempt, `VoskASR` will emit one debug log summary containing capture duration, processed audio duration, processed block count, queued block count, queued audio duration, decoder elapsed time, transcript, and per-word confidence scores.

The diagnostics are debug logs only. They do not alter recognition, audio capture, scoring, persistence, or user-facing output, and they do not save audio.

## Testing

Extract the summary formatting into a small helper and test that it reports the supplied counters, durations, transcript, and word-confidence pairs.
