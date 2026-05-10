# E.L.L.A. (Offline Reading Assistant)

This project runs an offline reading assistant GUI with:
- speech recognition (Vosk)
- reading accuracy feedback
- pronunciation coaching
- level progression (Easy -> Medium A/B/C -> Hard)

## Run Command

From this folder:

```bash
source .venv/bin/activate && python main.py \
	--gui \
	--use-mic \
	--vosk-model ./models/vosk-model-small-en-us-0.15 \
	--listen-seconds 5 \
	--audio-feedback \
	--tts-engine auto \
	--tts-rate 150 \
	--pronunciation-overrides ./config/pronunciation_overrides.json
```

### TTS Engine Options

- `--tts-engine auto` (default) - Auto-selects espeak on Linux, say on macOS, or respeaker on RPi with ReSpeaker
- `--tts-engine espeak` - Linux native; install with: `sudo apt install espeak-ng`
- `--tts-engine pyttsx3` - Cross-platform; install with: `pip install pyttsx3`
- `--tts-engine respeaker` - Raspberry Pi with ReSpeaker hardware; install with: `sudo apt install espeak-ng alsa-utils`

## ReSpeaker Setup (Raspberry Pi)

For ReSpeaker audio hat on Raspberry Pi:

1. Install ReSpeaker drivers and dependencies:
```bash
sudo apt install -y alsa-utils pulseaudio
sudo pip install vosk sounddevice
```

2. Install ReSpeaker kernel driver (2-mic or 4-mic):
```bash
git clone https://github.com/respeaker/seeed-voicecard.git
cd seeed-voicecard
sudo ./install.sh
sudo reboot
```

3. Verify ReSpeaker is detected:
```bash
arecord -l  # Check microphone device
aplay -l    # Check speaker device
```

4. Run with ReSpeaker (auto-detection) using the detected device index and optional sample rate:
```bash
source .venv/bin/activate && python main.py \
	--gui \
	--use-mic \
	--vosk-model ./models/vosk-model-small-en-us-0.15 \
	--listen-seconds 5 \
	--audio-feedback \
	--tts-engine auto \
	--input-device 1 \
	--sample-rate 48000 \
	--pronunciation-overrides ./config/pronunciation_overrides.json
```

## Windows

You can run this on Windows using either Command Prompt (cmd) or PowerShell. Ensure you are in the `ella-bot` directory first.

### Using Command Prompt (cmd)
```cmd
cd ella-bot
.venv\Scripts\activate
python main.py --gui --use-mic --vosk-model .\models\vosk-model-small-en-us-0.15 --listen-seconds 5 --audio-feedback --tts-engine pyttsx3 --tts-rate 150 --pronunciation-overrides .\config\pronunciation_overrides.json
```

### Using PowerShell
```powershell
cd ella-bot
.\.venv\Scripts\activate
python main.py --gui --use-mic --vosk-model .\models\vosk-model-small-en-us-0.15 --listen-seconds 5 --audio-feedback --tts-engine pyttsx3 --tts-rate 150 --pronunciation-overrides .\config\pronunciation_overrides.json
```

Note: `pyttsx3` is recommended for TTS on Windows.

## MacOS

You can run and test this on Mac using the following command:

```bash
cd /Users/juliusjervinbundalian/Documents/ella-bot/ella-bot
source ../.venv/bin/activate && python main.py \
  --gui \
  --use-mic \
  --vosk-model ./models/vosk-model-small-en-us-0.15 \
  --listen-seconds 5 \
  --audio-feedback \
  --tts-engine say \
  --tts-voice Samantha \
  --tts-rate 125 \
  --pronunciation-overrides ./config/pronunciation_overrides.json
```

Note: Adjust `--input-device` based on your `sounddevice.query_devices()` output. For ReSpeaker 2-mic HAT, the device index may be `1`.

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
source .venv/bin/activate && python main.py \
	--gui \
	--start-level medium-b \
	--vosk-model ./models/vosk-model-small-en-us-0.15 \
	--listen-seconds 5 \
	--audio-feedback \
	--tts-engine auto \
	--tts-rate 150 \
	--pronunciation-overrides ./config/pronunciation_overrides.json
```
