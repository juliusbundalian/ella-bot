from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WordScore:
    word: str
    confidence: float


@dataclass
class ASRResult:
    transcript: str
    words: List[WordScore]


class BaseASR:
    """Abstract ASR adapter."""

    def transcribe(self, expected_sentence: Optional[str] = None) -> ASRResult:
        raise NotImplementedError


class SimulatedASR(BaseASR):
    """Development ASR adapter for keyboard input."""

    def __init__(self, simulated_text: str):
        self.simulated_text = simulated_text

    def transcribe(self, expected_sentence: Optional[str] = None) -> ASRResult:
        words = [WordScore(word=w, confidence=0.9) for w in self.simulated_text.split()]
        return ASRResult(transcript=self.simulated_text, words=words)


class VoskASR(BaseASR):
    """
    Offline microphone ASR using Vosk.

    Requires optional dependencies:
    - vosk
    - sounddevice

    Install on Raspberry Pi:
        pip install vosk sounddevice
    """

    def __init__(
        self,
        model_path: str,
        sample_rate: int = 16000,
        listen_seconds: int = 4,
        input_device: int | None = None,
    ):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.listen_seconds = listen_seconds
        self.input_device = input_device

    def transcribe(self, expected_sentence: Optional[str] = None) -> ASRResult:
        try:
            import queue
            sd = importlib.import_module("sounddevice")
            vosk = importlib.import_module("vosk")
        except Exception as exc:
            raise RuntimeError(
                "VoskASR dependencies missing. Install with: pip install vosk sounddevice"
            ) from exc

        model = vosk.Model(self.model_path)
        recognizer = vosk.KaldiRecognizer(model, self.sample_rate)
        recognizer.SetWords(True)

        audio_queue: queue.Queue[bytes] = queue.Queue()

        def callback(indata, frames, time, status):
            if status:
                pass
            audio_queue.put(bytes(indata))

        print("Speak now...")

        with sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=8000,
            dtype="int16",
            channels=1,
            device=self.input_device,
            callback=callback,
        ):
            total_blocks = max(1, int((self.listen_seconds * self.sample_rate) / 8000))
            for _ in range(total_blocks):
                data = audio_queue.get()
                recognizer.AcceptWaveform(data)

        final_json = json.loads(recognizer.FinalResult())
        transcript = final_json.get("text", "").strip()

        words: List[WordScore] = []
        for item in final_json.get("result", []):
            w = item.get("word", "")
            conf = float(item.get("conf", 0.0))
            if w:
                words.append(WordScore(word=w, confidence=conf))

        return ASRResult(transcript=transcript, words=words)
