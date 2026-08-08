import time
from pathlib import Path
from typing import Callable, Optional

from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


_SOUND_CACHE: dict[tuple, object] = {}
DEFAULT_GAIN_FACTOR: float = 1.8
DEFAULT_TARGET_PEAK_FRACTION: float = 0.95


def boost_sound_volume(
    sound: "pygame.mixer.Sound",
    gain_factor: Optional[float] = None,
    target_peak_fraction: Optional[float] = None,
    volume_scale: float = 1.0,
) -> "pygame.mixer.Sound":
    """Boost PCM volume of a Pygame Sound by normalizing its peak amplitude and applying gain_factor.

    Applies RMS gain expansion and a tanh soft-limiter to prevent clipping while maximizing output volume.
    """
    gf = gain_factor if gain_factor is not None else DEFAULT_GAIN_FACTOR
    tpf = target_peak_fraction if target_peak_fraction is not None else DEFAULT_TARGET_PEAK_FRACTION

    try:
        import numpy as np
        import pygame

        arr = pygame.sndarray.array(sound)
        if arr.size == 0:
            return sound
        dtype = arr.dtype
        arr_float = arr.astype(np.float32)
        peak = np.max(np.abs(arr_float))
        if peak < 1e-5:
            return sound

        max_int = 32767.0 if dtype == np.int16 else (127.0 if dtype == np.int8 else 32767.0)
        vol = max(0.1, min(1.0, volume_scale))

        target_peak = max_int * tpf * vol
        norm_gain = target_peak / peak
        total_gain = norm_gain * max(0.1, gf)
        boosted = arr_float * total_gain

        # Soft limiter (tanh compression) to boost RMS loudness without hard digital clipping
        threshold = max_int * 0.85
        over = np.abs(boosted) > threshold
        if np.any(over):
            sign = np.sign(boosted)
            abs_val = np.abs(boosted)
            compressed = threshold + (max_int - threshold) * np.tanh((abs_val - threshold) / (max_int - threshold))
            boosted = np.where(over, sign * compressed, boosted)

        boosted_arr = np.clip(boosted, -max_int, max_int).astype(dtype)
        return pygame.sndarray.make_sound(boosted_arr)
    except Exception as exc:
        logger.debug("Sound volume boost fallback: %s", exc)
        return sound


def load_audio_sound(
    wav_path: Path | str,
    gain_factor: Optional[float] = None,
    target_peak_fraction: Optional[float] = None,
    volume_scale: float = 1.0,
) -> "pygame.mixer.Sound":
    """Load a WAV audio file and return a volume-boosted Pygame Sound object."""
    gf = gain_factor if gain_factor is not None else DEFAULT_GAIN_FACTOR
    tpf = target_peak_fraction if target_peak_fraction is not None else DEFAULT_TARGET_PEAK_FRACTION

    path_str = str(wav_path)
    cache_key = (path_str, round(volume_scale, 2), round(gf, 2), round(tpf, 2))
    if cache_key in _SOUND_CACHE:
        return _SOUND_CACHE[cache_key]

    import pygame

    sound = pygame.mixer.Sound(path_str)
    boosted = boost_sound_volume(
        sound,
        gain_factor=gf,
        target_peak_fraction=tpf,
        volume_scale=volume_scale,
    )
    if len(_SOUND_CACHE) > 200:
        _SOUND_CACHE.clear()
    _SOUND_CACHE[cache_key] = boosted
    return boosted


def play_sound_effect(filename: str, app: Optional[object] = None, gain_factor: Optional[float] = None) -> None:
    """Play a sound effect file from assets/audio/sfx/ asynchronously via Pygame mixer with volume boost."""
    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                return
        sfx_path = resolve_asset_path(f"assets/audio/sfx/{filename}")
        if not sfx_path.exists():
            logger.warning("Sound effect file not found: %s", sfx_path)
            return

        vol_scale = 1.0
        if app and getattr(app, "tts", None) and hasattr(app.tts, "config"):
            vol_scale = getattr(app.tts.config, "volume", 1.0)

        kwargs = {"volume_scale": vol_scale}
        if gain_factor is not None:
            kwargs["gain_factor"] = gain_factor

        sound = load_audio_sound(sfx_path, **kwargs)
        sound.play()
    except Exception as exc:
        logger.warning("Could not play sound effect %s: %s", filename, exc)


def play_level_sound(passed: bool) -> None:
    """Play pass or fail sound effect when finishing a level.

    Pass: Confetti popping and kids cheering (FNAF level success cheer).
    Fail: Encouraging gentle chime so the user is not discouraged.
    """
    sfx_file = "level_pass.wav" if passed else "level_fail.wav"
    play_sound_effect(sfx_file)


def play_button_click() -> None:
    """Play crisp button click sound effect."""
    play_button_click_path = resolve_asset_path("assets/audio/sfx/button_click.wav")
    if play_button_click_path.exists():
        play_sound_effect("button_click.wav")


def resolve_level1_playback(level: str, item: str) -> Optional[Path]:
    """Resolve pre-recorded playback audio for a Level 1 item.

    Checks assets/Level 1 playbacks/playbacks/{LEVEL}/ for matching .wav files.
    """
    folder = str(level).strip().upper()
    base_dir = resolve_asset_path("assets/Level 1 playbacks/playbacks")
    sub_dir = base_dir / folder
    if not sub_dir.exists():
        return None

    item_clean = item.lower().strip()
    # 1. Direct match (e.g. b.wav for item 'b')
    exact_wav = sub_dir / f"{item_clean}.wav"
    if exact_wav.exists():
        return exact_wav

    # 2. Sound prefix match for "sound (word)" format (e.g. "ch (chip)" -> "ch.wav")
    sound_prefix = item_clean.split("(")[0].strip() if "(" in item_clean else item_clean
    prefix_wav = sub_dir / f"{sound_prefix}.wav"
    if prefix_wav.exists():
        return prefix_wav

    # 3. Match sound substring in item (e.g. ch.wav for 'chip', dge.wav for 'bridge', bl.wav for 'blue')
    if sub_dir.exists():
        wav_files = sorted(sub_dir.glob("*.wav"), key=lambda p: len(p.stem), reverse=True)
        for wav_file in wav_files:
            sound_name = wav_file.stem.lower()
            if sound_name in item_clean:
                return wav_file
    return None


LEVEL1_START_PROMPTS = [
    "lets_start_our_reading_practice",
    "lets_learn_some_sounds",
    "lets_have_fun_practicing_sounds",
    "lets_begin",
    "welcome",
    "hello",
]

LEVEL1_TRANSITION_PROMPTS = [
    "here_comes_the_next_one",
    "lets_continue",
    "lets_keep_going",
    "lets_move_on",
    "lets_practice_another_sound",
    "lets_try_another_one",
]

LEVEL1_ATTENTION_PROMPTS = [
    "listen_to_the_sound",
    "listen_carefully",
    "here_is_the_sound",
    "lets_hear_it_first",
    "lets_hear_the_sound_together",
    "pay_close_attention",
    "use_your_listening_ears",
    "lets_practice_together",
]

LEVEL1_ACTION_PROMPTS = [
    "now_its_your_turn",
    "can_you_say",
    "try_saying_it",
    "repeat_after_me",
    "your_turn",
    "you_try",
]

LEVEL1_PRAISE_PROMPTS = [
    "nice_job",
    "well_done",
    "wonderful",
    "fantastic",
    "great_effort",
    "excellent_effort",
    "great_practice",
    "keep_it_up",
    "youre_doing_great",
]


def resolve_level1_prompt(prompt_name: str) -> Optional[Path]:
    """Resolve pre-recorded prompt audio from assets/Level 1 playbacks/prompts/."""
    base_dir = resolve_asset_path("assets/Level 1 playbacks/prompts")
    clean_name = prompt_name.strip()
    if not clean_name.startswith("prompt_"):
        clean_name = f"prompt_{clean_name}"
    if not clean_name.endswith(".wav"):
        clean_name = f"{clean_name}.wav"
    wav_path = base_dir / clean_name
    if wav_path.exists():
        return wav_path
    return None


def resolve_random_level1_intro_prompt(
    is_first_item: bool = False, last_prompt: str = ""
) -> tuple[Optional[Path], str]:
    """Return a random pre-recorded Level 1 intro prompt path and prompt key, avoiding repeating last_prompt."""
    import random
    pool = LEVEL1_START_PROMPTS if is_first_item else LEVEL1_ATTENTION_PROMPTS
    candidates = [p for p in pool if p != last_prompt]
    if not candidates:
        candidates = pool
    chosen = random.choice(candidates)
    path = resolve_level1_prompt(chosen)
    return path, chosen


def build_level1_audio_sequence(
    level: str,
    item: str,
    item_number: int = 1,
    recent_keys: Optional[set[str]] = None,
) -> tuple[list[Path], list[Path], list[str]]:
    """Build natural pre-sound and post-sound prompt sequences for Level 1 practice.

    Returns (pre_paths, post_paths, keys_used).
    """
    import random
    recent_keys = recent_keys or set()
    pre_paths: list[Path] = []
    post_paths: list[Path] = []
    keys_used: list[str] = []

    def pick_prompt(pool: list[str], target_list: list[Path]) -> Optional[str]:
        candidates = [p for p in pool if p not in recent_keys and p not in keys_used]
        if not candidates:
            candidates = [p for p in pool if p not in keys_used]
        if not candidates:
            candidates = pool
        chosen = random.choice(candidates)
        path = resolve_level1_prompt(chosen)
        if path and path.exists():
            target_list.append(path)
            keys_used.append(chosen)
            return chosen
        return None

    # 1. Pre-sound intro prompts
    if item_number == 1:
        pick_prompt(LEVEL1_START_PROMPTS, pre_paths)
        pick_prompt(LEVEL1_ATTENTION_PROMPTS, pre_paths)
    else:
        if random.random() < 0.5:
            pick_prompt(LEVEL1_TRANSITION_PROMPTS, pre_paths)
            pick_prompt(LEVEL1_ATTENTION_PROMPTS, pre_paths)
        else:
            pick_prompt(LEVEL1_ATTENTION_PROMPTS, pre_paths)

    # 2. Post-sound action prompt (e.g. "Now it's your turn!", "Try saying it!", "Your turn!")
    pick_prompt(LEVEL1_ACTION_PROMPTS, post_paths)

    return pre_paths, post_paths, keys_used


def play_audio_sequence(
    wav_paths: list[Path],
    is_paused: Optional[Callable[[], bool]] = None,
    app: Optional[object] = None,
) -> bool:
    """Play a sequence of WAV audio files back-to-back with brief natural pauses between them.

    Returns True if aborted during playback, False otherwise.
    """
    for idx, path in enumerate(wav_paths):
        if not path or not path.exists():
            continue
        aborted = play_audio_file(path, is_paused=is_paused, app=app)
        if aborted:
            return True
        if idx < len(wav_paths) - 1:
            time.sleep(0.10)
            if is_paused and is_paused():
                return True
    return False


def play_audio_file(
    wav_path: Path,
    is_paused: Optional[Callable[[], bool]] = None,
    app: Optional[object] = None,
    gain_factor: Optional[float] = None,
) -> bool:
    """Play a WAV audio file using Pygame mixer with peak-normalized volume boost.

    Returns True if aborted during playback, False otherwise.
    """
    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                return False

        vol_scale = 1.0
        if app and getattr(app, "tts", None) and hasattr(app.tts, "config"):
            vol_scale = getattr(app.tts.config, "volume", 1.0)

        kwargs = {"volume_scale": vol_scale}
        if gain_factor is not None:
            kwargs["gain_factor"] = gain_factor

        sound = load_audio_sound(wav_path, **kwargs)
        channel = sound.play()
        while channel and channel.get_busy():
            if is_paused and is_paused():
                sound.stop()
                if app and getattr(app, "tts", None) is not None:
                    app.tts.current_amplitude = 0.0
                return True
            time.sleep(0.02)

        if app and getattr(app, "tts", None) is not None:
            app.tts.current_amplitude = 0.0

        return False
    except Exception as exc:
        if app and getattr(app, "tts", None) is not None:
            app.tts.current_amplitude = 0.0
        logger.warning("Error playing audio file %s: %s", wav_path, exc)
        return False



