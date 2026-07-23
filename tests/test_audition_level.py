import numpy as np
import pytest

from scripts import audition_level
from scripts.audition_level import (
    PiperVariant,
    comparison_variants,
    consonant_class,
    validate_compare_request,
)


@pytest.mark.parametrize(
    ("letter", "expected"),
    [
        ("b", "stop"),
        ("j", "stop"),
        ("f", "continuous"),
        ("z", "continuous"),
        ("q", "sequence"),
        ("x", "sequence"),
    ],
)
def test_consonant_class_identifies_tuning_group(letter, expected):
    assert consonant_class(letter) == expected


def test_consonant_class_rejects_unknown_target():
    with pytest.raises(ValueError, match="Unsupported level 1B consonant"):
        consonant_class("a")


@pytest.mark.parametrize(
    ("letter", "class_rate"),
    [("b", 170), ("f", 125), ("x", 145)],
)
def test_comparison_variants_have_exact_audition_settings(letter, class_rate):
    assert comparison_variants(letter) == (
        PiperVariant("current", 190, 0.667, 0.8, True, 0),
        PiperVariant("clean", 190, 0.3, 0.3, False, 0),
        PiperVariant("relaxed", 145, 0.3, 0.3, False, 200),
        PiperVariant("class-tuned", class_rate, 0.2, 0.2, False, 250),
    )


@pytest.mark.parametrize(
    ("level", "engine", "items", "message"),
    [
        ("1a", "piper", ["a"], "--compare-piper is only available for level 1b"),
        ("1b", "espeak", ["b"], "--compare-piper requires --engine piper"),
        ("1b", "piper", [], "--only did not match any level 1b target"),
    ],
)
def test_validate_compare_request_rejects_invalid_combinations(level, engine, items, message):
    assert validate_compare_request(level, engine, items) == message


def test_validate_compare_request_accepts_level_1b_piper_target():
    assert validate_compare_request("1b", "piper", ["b"]) is None


def test_compare_dry_run_does_not_load_piper_or_open_audio(monkeypatch, capsys, tmp_path):
    def fail_load(*args, **kwargs):
        raise AssertionError("Piper must not load during a dry run")

    def fail_live_dependency(*args, **kwargs):
        raise AssertionError("Piper/audio playback must not initialize during a dry run")

    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    monkeypatch.setattr(audition_level, "load_piper_voice", fail_load)
    monkeypatch.setattr(audition_level, "_create_synthesis_config", fail_live_dependency)
    monkeypatch.setattr(audition_level, "_apply_warmth", fail_live_dependency)
    monkeypatch.setattr(audition_level, "_play_audio", fail_live_dependency)

    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(model_path),
            "--dry-run",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "b [current]" in output
    assert "b [clean]" in output
    assert "b [relaxed]" in output
    assert "b [class-tuned]" in output


def test_compare_reports_missing_model(capsys, tmp_path):
    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(tmp_path / "missing.onnx"),
        ]
    )

    assert result == 2
    assert "Piper model not found" in capsys.readouterr().err


def test_compare_reports_target_and_variant_when_playback_fails(monkeypatch, capsys, tmp_path):
    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    monkeypatch.setattr(audition_level, "load_piper_voice", lambda path: object())
    monkeypatch.setattr(
        audition_level,
        "play_piper_variant",
        lambda voice, spoken, variant: (_ for _ in ()).throw(RuntimeError("no output device")),
    )

    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--only",
            "b",
            "--piper-model",
            str(model_path),
        ]
    )

    assert result == 1
    assert "Comparison failed for b [current]: no output device" in capsys.readouterr().err


class _FakeVoice:
    class _Config:
        sample_rate = 1000

    config = _Config()

    def __init__(self):
        self.phonemes = None
        self.syn_config = None

    def phonemes_to_ids(self, phonemes):
        self.phonemes = phonemes
        return [1, 2, 3]

    def phoneme_ids_to_audio(self, phoneme_ids, syn_config):
        assert phoneme_ids == [1, 2, 3]
        self.syn_config = syn_config
        return np.ones(100, dtype=np.int16) * 1000


class _FakeSynthesisConfig:
    def __init__(self, **kwargs):
        self.length_scale = kwargs["length_scale"]
        self.noise_scale = kwargs["noise_scale"]
        self.noise_w_scale = kwargs["noise_w_scale"]
        self.volume = kwargs["volume"]


def test_play_relaxed_variant_uses_exact_config_and_padding(monkeypatch):
    voice = _FakeVoice()
    played = {}
    variant = PiperVariant("relaxed", 145, 0.3, 0.3, False, 200)

    monkeypatch.setattr(
        audition_level,
        "_create_synthesis_config",
        lambda **kwargs: _FakeSynthesisConfig(**kwargs),
    )
    monkeypatch.setattr(
        audition_level,
        "_play_audio",
        lambda pcm, sample_rate: played.update(pcm=pcm.copy(), samplerate=sample_rate),
    )

    samples = audition_level.play_piper_variant(voice, "phonemes:b.", variant)

    assert voice.phonemes == list("b.")
    assert voice.syn_config.length_scale == pytest.approx(200 / 145)
    assert voice.syn_config.noise_scale == 0.3
    assert voice.syn_config.noise_w_scale == 0.3
    assert played["samplerate"] == 1000
    assert len(played["pcm"]) == 500
    assert np.all(played["pcm"][:200] == 0)
    assert np.all(played["pcm"][-200:] == 0)
    assert samples == 500


def test_current_variant_uses_existing_warmth_filter(monkeypatch):
    voice = _FakeVoice()
    warmth_calls = []
    variant = PiperVariant("current", 190, 0.667, 0.8, True, 0)

    monkeypatch.setattr(
        audition_level,
        "_apply_warmth",
        lambda pcm: warmth_calls.append(pcm.copy()) or pcm,
    )
    monkeypatch.setattr(
        audition_level,
        "_create_synthesis_config",
        lambda **kwargs: _FakeSynthesisConfig(**kwargs),
    )
    monkeypatch.setattr(audition_level, "_play_audio", lambda pcm, sample_rate: None)

    samples = audition_level.play_piper_variant(voice, "phonemes:f.", variant)

    assert len(warmth_calls) == 1
    assert samples == 100
