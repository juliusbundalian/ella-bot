# E.L.L.A. (Offline Reading Assistant)

This project runs an offline reading assistant GUI with:
- speech recognition (Vosk)
- reading accuracy feedback
- pronunciation coaching
- structured level progression with phonics, sight words, vocabulary, phrases, and full sentences

## Level Progression

The app uses a carefully structured progression through 11 levels:

**Phase 1: Phonics Foundation (1A-1G)**
- **1A**: Single vowels (a, e, i, o, u)
- **1B**: Consonants (b-z)
- **1C**: Consonant-Vowel patterns (ba, be, bi, bo, bu, etc.)
- **1D**: Vowel digraphs (ea, ai, oo, etc.)
- **1E**: Consonant digraphs (ch, sh, th, etc.)
- **1F**: Trigraphs and quadgraphs (tch, ough, etc.)
- **1G**: Consonant blends (bl, st, tr, etc.)

**Phase 2: Vocabulary & Sight Words (2A-2D)**
- **2A**: Basic sight words (on, with, can, not, for, etc.) - 39 words
- **2B**: High frequency words (Easy) - 101 words
- **2C**: High frequency words (Average) - 100 words
- **2D**: High frequency words (Difficult) - 63 words

**Phase 3: Connected Text (3-4)**
- **3**: Phrases (175 multi-word phrases)
- **4**: Full sentences (84 complete sentences)

## Installation

**Requirements**: Python 3.10 or higher (Required for Kokoro TTS).

Ensure you have created a virtual environment and installed the package:

**macOS/Linux:**
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
ella-bot
```

## Running the Assistant

Ensure your virtual environment is activated before running the app. If you haven't installed the package yet, see the [Installation](#installation) section.

From your terminal, simply run:
```bash
ella-bot
```

Or specify a starting level:
```bash
ella-bot --start-level 2a
ella-bot --start-level 3
ella-bot --start-level 4
```

## Configuration (`config/settings.ini`)

All default preferences are stored in `config/settings.ini`. You can edit this file to customize your experience:

```ini
[System]
# Starting level: 1a, 1b, 1c, 1d, 1e, 1f, 1g, 2a, 2b, 2c, 2d, 3, 4
start_level = 1a

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

Pass command-line flags to temporarily override settings:
```bash
ella-bot --start-level 2b --tts-rate 200 --fullscreen
```

### Voice Quality (Kokoro TTS) ✅
For the most natural, human-like voice, we recommend using **Kokoro TTS**. 

1. **Install Dependencies**:

**Windows / Linux:**
```bash
pip install kokoro-onnx sounddevice
```

**macOS:**
macOS requires some system libraries for audio playback and phonemization. Use Homebrew to install them before installing the Python packages:
```bash
brew install portaudio espeak-ng
pip install kokoro-onnx sounddevice
```

2. **Download Model Files**:
Place the following files in your `models/` directory:
- [`kokoro-v1.0.int8.onnx`](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx) (Recommended for speed)
- [`voices-v1.0.bin`](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin)

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
