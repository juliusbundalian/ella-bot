from __future__ import annotations

from typing import Optional

from ella_bot.speech.asr.simulated import SimulatedASR
from ella_bot.speech.asr.vosk_engine import VoskASR


def build_asr(
    *,
    use_mic: bool,
    spoken: str = "",
    vosk_model_path: str = "",
    sample_rate: Optional[int] = None,
    listen_seconds: int = 4,
    input_device: Optional[int] = None,
):
    """Construct the ASR engine. Mirrors speech/tts/factory.build_tts.

    Model-path resolution stays with the caller (the CLI), so this factory
    receives an already-resolved vosk_model_path.
    """
    if use_mic:
        return VoskASR(
            model_path=str(vosk_model_path),
            sample_rate=sample_rate,
            listen_seconds=listen_seconds,
            input_device=input_device,
        )
    return SimulatedASR(simulated_text=spoken)
