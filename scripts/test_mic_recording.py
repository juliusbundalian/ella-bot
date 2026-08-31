#!/usr/bin/env python3
"""
Interactive Microphone Recording Test Script for ELLA Bot
Records audio using ELLA's exact microphone settings (mic_gain & soft-knee tanh compression),
saves raw and boosted WAV files to data/, and outputs ASR transcription test results.
"""

from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

# Add src to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

try:
    import numpy as np
    import sounddevice as sd
except ImportError as exc:
    print(f"Missing required audio dependencies: {exc}")
    print("Please run inside the virtual environment: ./.venv/bin/python scripts/test_mic_recording.py")
    sys.exit(1)

from ella_bot.config.app_config import load_settings
from ella_bot.speech.asr.factory import build_asr


def record_test_audio(duration: int = 5) -> None:
    settings = load_settings()
    mic_gain = float(settings.get("mic_gain", 8.0))
    sample_rate = int(settings.get("sample_rate", 16000))
    input_device = settings.get("input_device", None)
    vosk_model = settings.get("vosk_model", "./models/vosk-model-small-en-us-0.15")

    output_dir = ROOT_DIR / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_wav_path = output_dir / "test_mic_raw.wav"
    boosted_wav_path = output_dir / "test_mic_boosted.wav"

    print("=" * 60)
    print("  E.L.L.A. Microphone Sensitivity Recording Test")
    print("=" * 60)
    print(f"Sample Rate : {sample_rate} Hz")
    print(f"Mic Gain    : {mic_gain}x (Soft-knee tanh dynamic compression)")
    print(f"Duration    : {duration} seconds")
    print(f"Input Device: {input_device if input_device is not None else 'Default system input'}")
    print("-" * 60)

    print("\nPreparing to record...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1.0)

    print("\n>>> RECORDING STARTED! Speak or whisper now... <<<")
    
    # Record raw 16-bit mono PCM
    raw_frames = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        device=input_device,
    )
    sd.wait()  # Wait until recording is finished
    print(">>> RECORDING COMPLETE! Processing audio... <<<\n")

    raw_audio = raw_frames.flatten()
    
    # Strip initial 80ms hardware pop
    pop_samples = int(sample_rate * 0.08)
    clean_audio = raw_audio.astype(np.float32)
    if len(clean_audio) > pop_samples:
        clean_audio[:pop_samples] = 0.0

    # 1st-order IIR DC-Blocker High-Pass Filter
    filtered = np.zeros_like(clean_audio)
    prev_x, prev_y = 0.0, 0.0
    for i in range(len(clean_audio)):
        curr_x = clean_audio[i]
        curr_y = curr_x - prev_x + 0.995 * prev_y
        filtered[i] = curr_y
        prev_x, prev_y = curr_x, curr_y

    gain = max(1.0, mic_gain)
    boosted_audio = np.clip(filtered * gain, -32768, 32767).astype(np.int16)

    # Save raw WAV
    with wave.open(str(raw_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_audio.tobytes())

    # Save boosted WAV
    with wave.open(str(boosted_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(boosted_audio.tobytes())

    # Audio Statistics
    raw_peak = np.max(np.abs(raw_audio))
    boosted_peak = np.max(np.abs(boosted_audio))
    raw_rms = np.sqrt(np.mean(raw_audio.astype(np.float32) ** 2))
    boosted_rms = np.sqrt(np.mean(boosted_audio.astype(np.float32) ** 2))

    print("-" * 60)
    print("AUDIO RECORDING ANALYSIS:")
    print("-" * 60)
    print(f"Raw Audio Peak Amplitude     : {raw_peak} / 32767 ({raw_peak / 32767 * 100:.1f}%)")
    print(f"Boosted Audio Peak Amplitude : {boosted_peak} / 32767 ({boosted_peak / 32767 * 100:.1f}%)")
    print(f"Raw Audio RMS Loudness       : {raw_rms:.1f}")
    print(f"Boosted Audio RMS Loudness   : {boosted_rms:.1f}")
    print(f"RMS Gain Increase            : {boosted_rms / max(1.0, raw_rms):.2f}x")
    print("-" * 60)
    print(f"Saved Raw WAV     : {raw_wav_path}")
    print(f"Saved Boosted WAV : {boosted_wav_path}")
    print("-" * 60)

    # Attempt Vosk ASR test if model exists
    model_path = ROOT_DIR / vosk_model
    if model_path.exists():
        print("\nTesting Vosk ASR Recognition on recorded audio...")
        try:
            import json
            import vosk
            model = vosk.Model(str(model_path))
            rec = vosk.KaldiRecognizer(model, sample_rate)
            rec.SetWords(True)
            rec.AcceptWaveform(boosted_audio.tobytes())
            result = json.loads(rec.FinalResult())
            transcript = result.get("text", "").strip()
            print(f"-> Vosk Recognized Transcript: '{transcript}'")
        except Exception as exc:
            print(f"Vosk recognition test error: {exc}")
    else:
        print(f"\nVosk model path not found at {model_path}, skipping ASR transcript test.")

    print("\nRecording test complete!")


if __name__ == "__main__":
    duration_arg = 5
    if len(sys.argv) > 1:
        try:
            duration_arg = int(sys.argv[1])
        except ValueError:
            pass
    record_test_audio(duration=duration_arg)
