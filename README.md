# E.L.L.A. (Offline Reading Assistant)

This project runs an offline reading assistant GUI with:
- speech recognition (Vosk)
- reading accuracy feedback
- pronunciation coaching
- level progression (Easy -> Medium A/B/C -> Hard)

## Run Command

From this folder:

```bash
cd /Users/juliusjervinbundalian/Documents/ella-bot/ella-bot
/Users/juliusjervinbundalian/Documents/ella-bot/.venv/bin/python main.py \
	--gui \
	--use-mic \
	--vosk-model ./models/vosk-model-small-en-us-0.15 \
	--listen-seconds 5 \
	--input-device 0 \
	--audio-feedback \
	--tts-engine say \
	--tts-voice Samantha \
	--tts-rate 125 \
	--pronunciation-overrides ./config/empty_overrides.json
```

## Optional Start Level

You can start at a specific level:

```bash
--start-level easy
--start-level medium-a
--start-level medium-b
--start-level medium-c
--start-level hard
```

Example:

```bash
cd /Users/juliusjervinbundalian/Documents/ella-bot/ella-bot
/Users/juliusjervinbundalian/Documents/ella-bot/.venv/bin/python main.py \
	--gui \
	--start-level medium-b \
	--use-mic \
	--vosk-model ./models/vosk-model-small-en-us-0.15 \
	--listen-seconds 5 \
	--input-device 0 \
	--audio-feedback \
	--tts-engine say \
	--tts-voice Samantha \
	--tts-rate 125 \
	--pronunciation-overrides ./config/empty_overrides.json
```
