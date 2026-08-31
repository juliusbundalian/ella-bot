from __future__ import annotations

import importlib
import json
import queue
from dataclasses import dataclass
from typing import List, Optional, Callable

from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WordScore:
	word: str
	confidence: float


@dataclass
class ASRResult:
	transcript: str
	words: List[WordScore]


def format_attempt_diagnostics(
	capture_seconds: float,
	processed_bytes: int,
	processed_blocks: int,
	queued_bytes: int,
	queued_blocks: int,
	sample_rate: int,
	decoder_seconds: float,
	transcript: str,
	words: List[WordScore],
) -> str:
	"""Format one debug summary for a microphone transcription attempt."""
	bytes_per_second = sample_rate * 2  # 16-bit mono PCM
	processed_seconds = processed_bytes / bytes_per_second
	queued_seconds = queued_bytes / bytes_per_second
	word_confidences = ", ".join(
		f"{word.word}:{word.confidence:.2f}" for word in words
	)
	return (
		f"capture={capture_seconds:.2f}s "
		f"processed={processed_seconds:.2f}s/{processed_blocks} blocks "
		f"backlog={queued_seconds:.2f}s/{queued_blocks} blocks "
		f"decode={decoder_seconds:.2f}s "
		f"transcript={transcript!r} words=[{word_confidences}]"
	)


class BaseASR:
	"""Abstract ASR adapter."""

	def transcribe(self, expected_sentence: Optional[str] = None, is_paused: Optional[Callable[[], bool]] = None) -> ASRResult:
		bypass = getattr(self, "bypass_transcription", None)
		if bypass is not None:
			self.bypass_transcription = None  # Clear the bypass flag
			words = [WordScore(word=w, confidence=0.99) for w in bypass.split()]
			return ASRResult(transcript=bypass, words=words)
		raise NotImplementedError


class SimulatedASR(BaseASR):
	"""Development ASR adapter for keyboard input."""

	def __init__(self, simulated_text: str):
		self.simulated_text = simulated_text

	def transcribe(self, expected_sentence: Optional[str] = None, is_paused: Optional[Callable[[], bool]] = None) -> ASRResult:
		words = [WordScore(word=w, confidence=0.9) for w in self.simulated_text.split()]
		return ASRResult(transcript=self.simulated_text, words=words)


class VoskASR(BaseASR):
	"""
	Offline microphone ASR using Vosk with a persistent background recording stream.
	"""

	def __init__(
		self,
		model_path: str,
		sample_rate: int | None = None,
		listen_seconds: int = 4,
		input_device: int | None = None,
		mic_gain: float = 1.0,
	):
		self.model_path = model_path
		self.sample_rate = sample_rate
		self.listen_seconds = listen_seconds
		self.input_device = input_device
		self.mic_gain = max(0.1, float(mic_gain))
		self._model = None
		self._recognizer = None
		self._audio_queue = queue.Queue()
		self._stream = None

		# Force load model during initialization to avoid runtime lag
		logger.info("Loading ASR Model from %s (mic_gain=%.1f)", self.model_path, self.mic_gain)
		self._ensure_model_loaded()
		logger.info("ASR Model Loaded Successfully")

		# Start the persistent background stream immediately
		self._start_background_stream()

	def _ensure_model_loaded(self):
		if self._model is not None:
			return

		try:
			vosk = importlib.import_module("vosk")
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

	def _start_background_stream(self):
		try:
			sd = importlib.import_module("sounddevice")
			np = importlib.import_module("numpy")
			if self.sample_rate is None:
				try:
					device_info = sd.query_devices(self.input_device, "input")
					self.sample_rate = int(device_info.get("default_samplerate", 16000))
				except Exception:
					self.sample_rate = 16000

			self._skip_pop_frames = int(self.sample_rate * 0.08)
			self._frames_processed = 0
			self._prev_x = 0.0
			self._prev_y = 0.0

			def callback(indata, frames, time, status):
				if status:
					logger.warning("[ASR Audio Status] %s", status)
				pcm = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
				if self._frames_processed < self._skip_pop_frames:
					pcm[:] = 0.0
					self._frames_processed += frames

				# 1st-order IIR DC-Blocker High-Pass Filter (strips DC offset & low frequency hum)
				filtered = np.zeros_like(pcm)
				prev_x = self._prev_x
				prev_y = self._prev_y
				for i in range(len(pcm)):
					curr_x = pcm[i]
					curr_y = curr_x - prev_x + 0.995 * prev_y
					filtered[i] = curr_y
					prev_x = curr_x
					prev_y = curr_y
				self._prev_x = prev_x
				self._prev_y = prev_y

				gain = max(1.0, self.mic_gain)
				boosted = np.clip(filtered * gain, -32768, 32767).astype(np.int16)
				self._audio_queue.put(boosted.tobytes())

			self._stream = sd.RawInputStream(
				samplerate=self.sample_rate,
				blocksize=4000,
				dtype="int16",
				channels=1,
				device=self.input_device,
				callback=callback,
			)
			self._stream.start()
			logger.info("[ASR] Persistent background microphone stream started successfully.")
		except Exception as exc:
			logger.error("[ASR] Could not start persistent background microphone stream: %s", exc)

	def transcribe(self, expected_sentence: Optional[str] = None, is_paused: Optional[Callable[[], bool]] = None) -> ASRResult:
		bypass = getattr(self, "bypass_transcription", None)
		if bypass is not None:
			self.bypass_transcription = None  # Clear the bypass flag
			words = [WordScore(word=w, confidence=0.99) for w in bypass.split()]
			return ASRResult(transcript=bypass, words=words)

		try:
			vosk = importlib.import_module("vosk")
		except Exception as exc:
			raise RuntimeError(
				"VoskASR dependencies missing. Install with: pip install vosk sounddevice"
			) from exc

		self._ensure_model_loaded()

		# Ensure background stream is active (auto-recovery)
		if self._stream is None or not getattr(self._stream, "active", False):
			self._start_background_stream()

		# 1. Instantly clear any accumulated background audio from the queue
		while not self._audio_queue.empty():
			try:
				self._audio_queue.get_nowait()
			except queue.Empty:
				break

		# 2. Recreate KaldiRecognizer for a clean slate
		recognizer = vosk.KaldiRecognizer(self._model, self.sample_rate)
		recognizer.SetWords(True)

		logger.info("[ASR] Recording started instantly. Will listen for %d seconds", self.listen_seconds)

		import time
		start_time = time.monotonic()
		last_log_time = start_time
		processed_bytes = 0
		processed_blocks = 0
		decoder_seconds = 0.0

		while True:
			if is_paused is not None and is_paused():
				logger.info("[ASR] Transcription aborted due to pause/quit.")
				return ASRResult(transcript="", words=[])

			elapsed = time.monotonic() - start_time
			if elapsed >= self.listen_seconds:
				break

			# Log every second
			if time.monotonic() - last_log_time >= 1.0:
				logger.debug("[ASR] Recording: %ds / %ds", int(elapsed), self.listen_seconds)
				last_log_time = time.monotonic()

			try:
				# 3. Read incoming bytes instantly from the queue (zero start lag!)
				data = self._audio_queue.get(timeout=0.1)
				decode_start = time.monotonic()
				recognizer.AcceptWaveform(data)
				decoder_seconds += time.monotonic() - decode_start
				processed_bytes += len(data)
				processed_blocks += 1
			except queue.Empty:
				continue

		logger.debug("[ASR] Recording loop finished")

		logger.debug("[ASR] Finalizing recognition result")
		decode_start = time.monotonic()
		final_result_str = recognizer.FinalResult()
		decoder_seconds += time.monotonic() - decode_start
		final_json = json.loads(final_result_str)
		transcript = final_json.get("text", "").strip()

		words: List[WordScore] = []
		for item in final_json.get("result", []):
			w = item.get("word", "")
			conf = float(item.get("conf", 0.0))
			if w:
				words.append(WordScore(word=w, confidence=conf))

		with self._audio_queue.mutex:
			queued_chunks = tuple(self._audio_queue.queue)
		queued_bytes = sum(len(chunk) for chunk in queued_chunks)
		queued_blocks = len(queued_chunks)
		logger.info(
			"[ASR] %s",
			format_attempt_diagnostics(
				capture_seconds=time.monotonic() - start_time,
				processed_bytes=processed_bytes,
				processed_blocks=processed_blocks,
				queued_bytes=queued_bytes,
				queued_blocks=queued_blocks,
				sample_rate=self.sample_rate,
				decoder_seconds=decoder_seconds,
				transcript=transcript,
				words=words,
			),
		)

		return ASRResult(transcript=transcript, words=words)
