"""Generate a short ELLA greeting as a WAV file using Piper TTS."""
import sys
import wave
import numpy as np

sys.path.insert(0, r"d:\Project ELLA\ella-bot\src")
from piper import PiperVoice, SynthesisConfig

MODEL_PATH = r"d:\Project ELLA\ella-bot\models\en_US-hfc_female-medium.onnx"
OUTPUT_WAV = r"d:\Project ELLA\ella-bot\ella_hi_im_ella.wav"
TEXT = "Hi, I'm ELLA!"

print(f"Loading Piper model: {MODEL_PATH}")
voice = PiperVoice.load(MODEL_PATH)

# Excited tone but calm delivery pace
syn_config = SynthesisConfig(
    length_scale=1.3,       # calm, unhurried pace
    noise_scale=0.75,       # moderate expressiveness
    noise_w_scale=0.7,      # steady rhythm, not rushed
)

print(f"Synthesizing: {TEXT}")
all_audio = []
sample_rate = 22050

for chunk in voice.synthesize(TEXT, syn_config=syn_config):
    pcm = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).copy()
    all_audio.append(pcm)
    sample_rate = chunk.sample_rate

audio_data = np.concatenate(all_audio).astype(np.float32)

# Pitch shift up ~5% to sound brighter/more excited
from scipy.signal import resample
original_len = len(audio_data)
pitch_factor = 1.05  # higher = brighter
stretched = resample(audio_data, int(original_len / pitch_factor))
audio_data = stretched.astype(np.float32)

# Normalize
peak = np.max(np.abs(audio_data))
if peak > 0:
    audio_data = (audio_data / peak) * 32767 * 0.95
audio_data = audio_data.astype(np.int16)

print(f"Writing WAV to: {OUTPUT_WAV}")
with wave.open(OUTPUT_WAV, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    wf.writeframes(audio_data.tobytes())

duration = len(audio_data) / sample_rate
print(f"Done! WAV file saved: {OUTPUT_WAV}")
print(f"Duration: {duration:.2f}s, Sample rate: {sample_rate}Hz")
