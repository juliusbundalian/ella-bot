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

Ensure you have created a virtual environment and installed the package:

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Windows:**
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

## Running the Assistant

From your terminal (with your virtual environment activated), simply run:
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
tts_rate = 150
pronunciation_overrides = ./config/pronunciation_overrides.json

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

### Platform-Specific TTS Notes
- **Windows**: Uses `pyttsx3` (default via `auto`)
- **macOS**: Uses built-in `say` command (default via `auto`)
- **Linux**: Uses `espeak-ng` (default via `auto`). Install: `sudo apt install espeak-ng`

## Content Storage

All reading items for each level are stored in `config/level_pools.json`:
- Phonics patterns use display/speech separation for TTS pronunciation
- Single letters display as letters but speak as sounds (e.g., "a" speaks as "ah")
- Validation uses the display form for better ASR accuracy
- Pronunciation overrides in `config/pronunciation_overrides.json` ensure accurate TTS output

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
