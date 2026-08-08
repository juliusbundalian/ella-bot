import time
from pathlib import Path
from typing import Callable, Optional

from ella_bot.utils.file_utils import resolve_asset_path
from ella_bot.utils.logging import get_logger

logger = get_logger(__name__)


def play_sound_effect(filename: str) -> None:
    """Play a sound effect file from assets/audio/sfx/ asynchronously via Pygame mixer."""
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
        sound = pygame.mixer.Sound(str(sfx_path))
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

    # 2. Match sound substring in item (e.g. ch.wav for 'chip', dge.wav for 'bridge', bl.wav for 'blue')
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
) -> bool:
    """Play a WAV audio file using Pygame mixer.

    Returns True if aborted during playback, False otherwise.
    """
    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                return False

        sound = pygame.mixer.Sound(str(wav_path))
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


