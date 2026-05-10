# E.L.L.A. (Offline Reading Assistant)

This project runs an offline reading assistant GUI with:
- speech recognition (Vosk)
- reading accuracy feedback
- pronunciation coaching
- level progression (Easy -> Medium A/B/C -> Hard)

## Installation

Ensure you have created a virtual environment and installed the package:
```bash
python -m venv .venv
# On Windows use: .\.venv\Scripts\activate
source .venv/bin/activate
pip install -e .
```

## Running the Assistant

Because the project uses a centralized configuration file, running the app is extremely simple!

From your terminal (with your virtual environment activated), simply run:
```bash
ella-bot
```

## Configuration (`config/settings.ini`)

All default preferences (such as TTS engine, starting level, and model paths) are now permanently stored in `config/settings.ini`. You can open and edit this file to customize your experience without typing long commands:

```ini
[System]
start_level = easy
sentence_file = ./config/sample_sentences.txt

[Speech]
use_mic = True
vosk_model = ./models/vosk-model-small-en-us-0.15
listen_seconds = 5

[TTS]
audio_feedback = True
tts_engine = auto
tts_rate = 150
pronunciation_overrides = ./config/pronunciation_overrides.json

[GUI]
gui = True
fullscreen = False
gui_width = 1280
gui_height = 720
```

### Overriding Settings on the Fly

If you want to temporarily override a setting without modifying your `settings.ini` file, you can still pass standard command-line flags:
```bash
ella-bot --start-level hard --tts-rate 200 --fullscreen
```

### Platform-Specific TTS Notes
- **Windows**: The config defaults to `auto` which uses `pyttsx3`.
- **macOS**: The config defaults to `auto` which uses the built-in `say` command.
- **Linux**: The config defaults to `auto` which uses `espeak`. Ensure it is installed (`sudo apt install espeak-ng`).

## ReSpeaker Setup (Raspberry Pi)

For the ReSpeaker audio HAT on Raspberry Pi:

1. Install ReSpeaker drivers and dependencies:
```bash
sudo apt install -y alsa-utils pulseaudio espeak-ng
sudo pip install vosk sounddevice
```

2. Install ReSpeaker kernel driver (2-mic or 4-mic):
```bash
git clone https://github.com/respeaker/seeed-voicecard.git
cd seeed-voicecard
sudo ./install.sh
sudo reboot
```

3. Update your `config/settings.ini` or run with CLI overrides:
```bash
ella-bot --tts-engine respeaker --input-device 1 --sample-rate 48000
```
