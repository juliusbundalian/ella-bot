# ELLA Scripts & Auto-Pull Service

This directory contains utility scripts for ELLA Bot operation and service management.

## Key Scripts

* `auto_pull_on_connect.sh` - Automated Git pull script triggered upon internet connection.
* `install_auto_pull_service.sh` - Installs `ella-auto-pull.service` into `~/.config/systemd/user/`.
* `check_recorded_audio.py` - Checks every configured Level 1 and 2 item for a matching playback WAV.

## Recorded Voice Check

Before deploying, run from the repository root:

```bash
python scripts/check_recorded_audio.py
```

The check uses the same recording lookup as the app and exits with status 1 if
any item is missing. Levels 3 and 4 are excluded because they use TTS.

The word **speaking** was removed from Level 2B because no matching human
recording is available. Before adding curriculum items, add their corresponding
recordings and rerun this check.

On the Raspberry Pi, verify these words through their first announcement, retry,
and replay: Level 2B **people**, Level 2C **pilgrimage**, and Level 2D **placid**.
Also finish a Level 1 sublevel to confirm the human completion announcement
(recording 463 or 464), and exhaust an item's attempts to verify recording 457.
Confirm that a correct answer still uses a recorded praise prompt.

## Reading Status Verification

Levels 2–4 show a persistent status panel: **Listen to ELLA**, **Getting ready**,
**Listening — Speak now**, **Processing**, and the response outcome. The listening
cue follows the recognizer's accepted response window. Learners should say the
item once, then wait; the configured recording duration is unchanged.

The outcome is **Correct**, **Try again**, **I didn't hear you**, or
**Attempts completed**, with the current attempt number. The answered item stays
on screen during feedback and for at least 1.5 seconds of unpaused time. The
scored result and next position are saved before that display hold.

Level 1 shows **Your turn to practise** with Replay/Next instructions. It does
not display a microphone or claim to score a spoken response.

Before using the new instructions for data gathering, verify on the Pi:

1. Speak only after **Speak now**; check that **Processing** appears when the
   response window closes, including after silence.
2. Test correct, incorrect, silent, and third unsuccessful attempts. Confirm the
   counter, outcome, recording 457, and next item agree.
3. Pause and resume during recording, slow recognition, spoken feedback, and the
   outcome display. An interrupted capture restarts without consuming an attempt.
4. Return to the menu during feedback and continue. A completed result must not
   be repeated or replaced with an unfinished reading checkpoint.
5. Pause during Level 1 completion audio; verify the next practice sublevel is
   available after resuming.
6. Check readability at the device's screen resolution, including long Level 4
   text and audio feedback disabled. Observe whether learners still repeat words
   before considering separate end-of-speech detection or extra sound cues.

## Documentation & Troubleshooting

For detailed documentation, root cause analysis of git stash errors, and troubleshooting steps for auto-pull issues, see:
* [`docs/AUTO_PULL_README.md`](../docs/AUTO_PULL_README.md)
