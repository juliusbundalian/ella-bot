import math
import struct
import wave
from pathlib import Path


def generate_click_sound(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 44100
    duration = 0.05  # 50 ms
    num_samples = int(sample_rate * duration)

    frames = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        # Fast attack (2ms), exponential decay
        attack = min(1.0, i / (sample_rate * 0.002))
        decay = math.exp(-i / (num_samples * 0.25))
        env = attack * decay
        # Frequency pitch drop from 950Hz to 450Hz for a crisp pop/click feel
        freq = 950.0 - 500.0 * (i / num_samples)
        sample_val = math.sin(2.0 * math.pi * freq * t)
        # Add subtle second harmonic for warmth
        sample_val += 0.3 * math.sin(4.0 * math.pi * freq * t)
        val = int(32767.0 * 0.5 * env * sample_val)
        val = max(-32768, min(32767, val))
        frames.extend(struct.pack('<h', val))

    with wave.open(str(output_path), 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)


if __name__ == '__main__':
    target = Path(__file__).resolve().parent.parent / 'assets' / 'audio' / 'sfx' / 'button_click.wav'
    generate_click_sound(target)
    print(f'Generated {target} ({target.stat().st_size} bytes)')
