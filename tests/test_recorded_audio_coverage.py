import json
from pathlib import Path
import subprocess
import sys

from ella_bot.services.sound_effects import resolve_level1_playback


ROOT = Path(__file__).resolve().parents[1]


def _check_recordings(tmp_path, pools):
    config = tmp_path / "level_pools.json"
    config.write_text(json.dumps(pools), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_recorded_audio.py"), "--config", str(config)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )


def test_check_recordings_reports_missing_level2_word(tmp_path):
    result = _check_recordings(tmp_path, {"1a": ["a"], "2b": ["missing-test-word"]})

    assert result.returncode == 1
    assert "2B: missing-test-word" in result.stdout
    assert "1A: a" not in result.stdout


def test_check_recordings_handles_phonics_and_excludes_tts_levels(tmp_path):
    result = _check_recordings(
        tmp_path, {"1g": ["bl (blue)"], "2a": ["go"], "3": ["unrecorded phrase"]}
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Checked 2 items" in result.stdout


def test_level2c_pilgrimage_has_a_recording():
    path = resolve_level1_playback("2c", "pilgrimage")

    assert path is not None
    assert path.name == "pilgrimage.wav"
    assert path.is_file()
