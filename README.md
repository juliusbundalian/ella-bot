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

Ella requires Python 3.10 or higher. The initial installation also requires an
internet connection to download the project dependencies and offline speech
models. After setup, Ella can run without an internet connection.

### Windows

#### 1. Install the required software

Install the following before downloading Ella:

- **Python 3.10 or higher (64-bit):** Download it from
  [python.org](https://www.python.org/downloads/windows/). If the installer
  shows an **Add Python to PATH** option, enable it.
- **Git for Windows:** Download it from
  [git-scm.com](https://git-scm.com/install/windows/) and keep the default
  installation options. Git is optional if the trainer provides the project
  as a ZIP file.
- A working microphone and speakers or headphones.

Open a new PowerShell window and verify the installations:

```powershell
py --version
git --version
```

The Python command must report version 3.10 or higher. If a command is not
recognized, close and reopen PowerShell after installing the software.

#### 2. Download the project

Clone the repository, then enter the project directory:

```powershell
git clone https://github.com/juliusbundalian/ella-bot.git
cd ella-bot
```

If the project was provided as a ZIP file, extract it, open the extracted
`ella-bot` folder in File Explorer, type `powershell` in the address bar, and
press Enter. Run all remaining commands from that project folder.

#### 3. Create and activate a virtual environment

Create a virtual environment named `.venv`:

```powershell
py -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell reports that script execution is disabled, allow scripts only
for the current PowerShell window and activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

For Command Prompt instead of PowerShell, use:

```bat
.venv\Scripts\activate.bat
```

The terminal prompt should now begin with `(.venv)`.

#### 4. Install the project requirements

With the virtual environment active, upgrade pip and install Ella:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

The second command reads `pyproject.toml` and installs Ella together with its
required packages, including Vosk, SoundDevice, Pygame, Piper TTS, and the
other runtime dependencies. Do not install each package manually.

Verify that the dependencies and Ella command were installed:

```powershell
python -m pip check
ella-bot --help
```

#### 5. Install the offline speech models

The large model files are intentionally not stored in Git. A fresh clone must
have the following files added to its `models` folder. The trainer may provide
a prepared `models` folder so everyone does not need to download the files
individually.

1. Download
   [`vosk-model-small-en-us-0.15.zip`](https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip),
   extract it, and place the extracted `vosk-model-small-en-us-0.15` folder
   inside `models`.
2. Download the Piper
   [`en_US-hfc_female-medium.onnx`](https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx?download=true)
   model and its
   [`en_US-hfc_female-medium.onnx.json`](https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/hfc_female/medium/en_US-hfc_female-medium.onnx.json?download=true)
   configuration file. Place both files directly inside `models`.

The completed structure should look like this:

```text
ella-bot/
|-- models/
|   |-- vosk-model-small-en-us-0.15/
|   |   |-- am/
|   |   |-- conf/
|   |   |-- graph/
|   |   `-- ivector/
|   |-- en_US-hfc_female-medium.onnx
|   `-- en_US-hfc_female-medium.onnx.json
|-- config/
|-- src/
`-- pyproject.toml
```

#### 6. Allow microphone access

In Windows, open **Settings > Privacy & security > Microphone**. Turn on
**Microphone access** and **Let desktop apps access your microphone**.

#### 7. Run Ella

From the project directory, with `(.venv)` visible in the terminal prompt:

```powershell
ella-bot
```

If the `ella-bot` command is not recognized, use this equivalent command:

```powershell
python -m ella_bot.cli.main
```

To exit the virtual environment after closing Ella, run `deactivate`.

### macOS/Linux

Install Python 3.10 or higher and Git, then run:

```bash
git clone https://github.com/juliusbundalian/ella-bot.git
cd ella-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Add the Vosk and Piper files described in
[Install the offline speech models](#5-install-the-offline-speech-models), then
start Ella:

```bash
ella-bot
```

## Quick Start

After the initial installation, open a terminal in the project folder and run:

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
ella-bot
```

**macOS/Linux:**

```bash
source .venv/bin/activate
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
session_log = ./data/sessions.jsonl

[Speech]
use_mic = True
vosk_model = ./models/vosk-model-small-en-us-0.15
listen_seconds = 8
sample_rate = 16000

[TTS]
audio_feedback = True
tts_engine = piper
tts_rate = 170
piper_binary = ./piper/piper.exe
piper_model = ./models/en_US-hfc_female-medium.onnx
noise_scale = 0.667
noise_w = 0.8
length_scale = 1
volume = 4
pronunciation_overrides = ./config/pronunciation_overrides.json
# Kokoro Settings
kokoro_model = kokoro-v1.0.onnx
kokoro_voices = voices-v1.0.bin

[GUI]
gui = True
fullscreen = False
gui_width = 1000
gui_height = 600
gui_left_padding = 18
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
- [`kokoro-v1.0.onnx`](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx) (Full Precision)
- [`voices-v1.0.bin`](https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin)

3. **Enable in Settings**:
Set `tts_engine = kokoro` in `config/settings.ini` or run with `--tts-engine kokoro`.

### Platform-Specific TTS Notes
- **Windows/Linux/macOS**: Setting `tts_engine = auto` will automatically prioritize **Piper** (if its model is found), then **Kokoro**, and finally a supported system voice.

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
