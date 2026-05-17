# E.L.L.A. (Offline Reading Assistant)

This project runs an offline reading assistant GUI with:
- speech recognition (Vosk)
- reading accuracy feedback
- pronunciation coaching
- level progression (Easy -> Medium A/B/C -> Hard)

## Installation

**Requirements**: Python 3.10 or higher (Required for Kokoro TTS).

Ensure you have created a virtual environment and installed the package:
```bash
# Create environment (ensure you are using Python 3.10+)
# TIP: On Windows, use 'py -3.14 -m venv .venv_314' to pick a specific version
python -m venv .venv_314
# On Windows use: .\.venv_314\Scripts\activate
source .venv_314/bin/activate

# Upgrade pip and install
python -m pip install --upgrade pip
pip install -e .
```

## Quick Start (Windows)

To quickly activate the virtual environment and start the assistant, run:
```powershell
.\.venv_314\Scripts\activate
python src/ella_bot/cli/main.py --tts-engine kokoro --audio-feedback --random-sentence
```

## Running the Assistant

Ensure your virtual environment is activated before running the app. If you haven't installed the package yet, see the [Installation](#installation) section.

From your terminal, simply run:
```bash
python src/ella_bot/cli/main.py
```
*(If you installed the package with `pip install -e .`, you can also just type `ella-bot`)*

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
tts_rate = 160
pronunciation_overrides = ./config/pronunciation_overrides.json
# Kokoro Settings
kokoro_model = kokoro-v1.0.int8.onnx
kokoro_voices = voices-v1.0.bin

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

### Voice Quality (Kokoro TTS) ✅
For the most natural, human-like voice, we recommend using **Kokoro TTS**. 

1. **Install Dependencies**:
```bash
pip install kokoro-onnx sounddevice
```

2. **Download Model Files**:
Place the following files in your `models/` directory:
- `kokoro-v1.0.int8.onnx` (Recommended for speed)
- `voices-v1.0.bin`

3. **Enable in Settings**:
Set `tts_engine = kokoro` in `config/settings.ini` or run with `--tts-engine kokoro`.

### Platform-Specific TTS Notes
- **Windows/Linux/macOS**: Setting `tts_engine = auto` will automatically prioritize **Kokoro** (if models are found), then **Piper**, and finally system voices (`pyttsx3`, `say`, or `espeak`).

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
