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
		sample_rate: int | None = None,
		listen_seconds: int = 4,
		input_device: int | None = None,
	):
		self.model_path = model_path
		self.sample_rate = sample_rate
		self.listen_seconds = listen_seconds
		self.input_device = input_device
		self._model = None
		self._recognizer = None
		
		# Force load model during initialization to avoid runtime lag
		print(f"Loading ASR Model from {self.model_path}...")
		self._ensure_model_loaded()
		print("ASR Model Loaded Successfully.")

	def _ensure_model_loaded(self):
		if self._model is not None:
			return
		
		try:
			import sys
			vosk = importlib.import_module("vosk")
			# Redirect stderr during model load to avoid messy console output
			self._model = vosk.Model(str(self.model_path))
		except Exception as exc:
			error_msg = (
				f"\n\n[!!!] CRITICAL ERROR: Could not load speech recognition model.\n"
				f"Path checked: {self.model_path}\n\n"
				f"TO FIX THIS:\n"
				f"1. Download the model: https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip\n"
				f"2. Extract it into your 'models' folder.\n"
				f"3. Ensure the folder name is 'vosk-model-small-en-us-0.15'\n\n"
				f"Original Error: {exc}\n"
			)
			raise RuntimeError(error_msg) from exc

	def transcribe(self, expected_sentence: Optional[str] = None) -> ASRResult:
		try:
			import queue
			sd = importlib.import_module("sounddevice")
			vosk = importlib.import_module("vosk")
		except Exception as exc:
			raise RuntimeError(
				"VoskASR dependencies missing. Install with: pip install vosk sounddevice"
			) from exc

		self._ensure_model_loaded()

		if self.sample_rate is None:
			try:
				device_info = sd.query_devices(self.input_device, "input")
				self.sample_rate = int(device_info.get("default_samplerate", 16000))
				print(f"[ASR] Detected default sample rate: {self.sample_rate}Hz")
			except Exception:
				self.sample_rate = 16000

		recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
		recognizer.SetWords(True)

		audio_queue: queue.Queue[bytes] = queue.Queue()

		def callback(indata, frames, time, status):
			if status:
				print(f"[Audio Status] {status}")
			audio_queue.put(bytes(indata))

		try:
			device_info = sd.query_devices(self.input_device, "input")
			print(f"[ASR] Initializing microphone: {device_info.get('name', 'Unknown')} at {self.sample_rate}Hz")
		except Exception as e:
			print(f"[ASR] Warning: Could not query device info: {e}")

		try:
			import time
			with sd.RawInputStream(
				samplerate=self.sample_rate,
				blocksize=4000,
				dtype="int16",
				channels=1,
				device=self.input_device,
				callback=callback,
			):
				print(f"[ASR] Recording started. Will listen for {self.listen_seconds} seconds...")
				start_time = time.time()
				last_log_time = start_time
				
				while True:
					elapsed = time.time() - start_time
					if elapsed >= self.listen_seconds:
						break
						
					# Log every second
					if time.time() - last_log_time >= 1.0:
						print(f"[ASR] ... recording ({int(elapsed)}s / {self.listen_seconds}s)")
						last_log_time = time.time()

					try:
						# Short timeout to keep the loop responsive
						data = audio_queue.get(timeout=0.1)
						recognizer.AcceptWaveform(data)
					except queue.Empty:
						continue
				
				print("[ASR] Recording loop finished.")
		except Exception as exc:
			print(f"[ASR Error] Could not open microphone: {exc}")
			raise RuntimeError(f"Microphone error: {exc}")

		print("[ASR] Finalizing recognition result...")
		final_result_str = recognizer.FinalResult()
		print(f"[ASR] FinalResult() called. Raw length: {len(final_result_str)}")
		final_json = json.loads(final_result_str)
		transcript = final_json.get("text", "").strip()

		words: List[WordScore] = []
		for item in final_json.get("result", []):
			w = item.get("word", "")
			conf = float(item.get("conf", 0.0))
			if w:
				words.append(WordScore(word=w, confidence=conf))

		return ASRResult(transcript=transcript, words=words)

