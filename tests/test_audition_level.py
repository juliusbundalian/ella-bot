import json

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
        ("c", "stop"),
        ("d", "stop"),
        ("g", "stop"),
        ("j", "stop"),
        ("k", "stop"),
        ("p", "stop"),
        ("t", "stop"),
        ("f", "continuous"),
        ("h", "continuous"),
        ("l", "continuous"),
        ("m", "continuous"),
        ("n", "continuous"),
        ("r", "continuous"),
        ("s", "continuous"),
        ("v", "continuous"),
        ("w", "continuous"),
        ("y", "continuous"),
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

    model_path = tmp_path / "en_US-hfc_female-medium.onnx"
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
            str(tmp_path / "en_US-hfc_female-medium.onnx"),
        ]
    )

    assert result == 2
    assert "Piper model not found" in capsys.readouterr().err


def test_compare_rejects_wrong_piper_model_identity_before_loading(monkeypatch, capsys, tmp_path):
    model_path = tmp_path / "another-voice.onnx"
    model_path.touch()
    monkeypatch.setattr(
        audition_level,
        "load_piper_voice",
        lambda path: (_ for _ in ()).throw(AssertionError("wrong model must not load")),
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

    captured = capsys.readouterr()
    assert result == 2
    assert "another-voice.onnx" in captured.err
    assert "en_US-hfc_female-medium.onnx" in captured.err
    assert "Level 1b Piper comparison" not in captured.out


def test_compare_accepts_expected_model_name_from_another_path(capsys, tmp_path):
    model_path = tmp_path / "other-model-directory" / "en_US-hfc_female-medium.onnx"
    model_path.parent.mkdir()
    model_path.touch()

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
    assert "b [current]" in capsys.readouterr().out


def test_compare_reports_invalid_model_load_before_banner_or_playback(monkeypatch, capsys, tmp_path):
    model_path = tmp_path / "en_US-hfc_female-medium.onnx"
    model_path.touch()
    monkeypatch.setattr(
        audition_level,
        "load_piper_voice",
        lambda path: (_ for _ in ()).throw(RuntimeError("invalid ONNX graph")),
    )
    monkeypatch.setattr(
        audition_level,
        "play_piper_variant",
        lambda *args: (_ for _ in ()).throw(AssertionError("playback must not start")),
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

    captured = capsys.readouterr()
    assert result == 2
    assert "Piper model could not be loaded: invalid ONNX graph" in captured.err
    assert "Level 1b Piper comparison" not in captured.out


@pytest.mark.parametrize(
    ("items", "overrides", "target", "message"),
    [
        (["a"], {"a": "phonemes:a."}, "a", "unsupported"),
        ([None], {}, "None", "unsupported"),
        (["b", "c"], {"b": "phonemes:b."}, "c", "missing pronunciation override"),
        (["b"], {"b": "bee"}, "b", "not a phoneme override"),
        (["b"], {"b": None}, "b", "not a phoneme override"),
        (["b"], {"b": "phonemes:   "}, "b", "empty phoneme payload"),
    ],
)
@pytest.mark.parametrize(
    "extra_args",
    [pytest.param(["--dry-run"], id="dry-run"), pytest.param([], id="live")],
)
def test_compare_preflights_every_target_before_output(
    monkeypatch,
    capsys,
    tmp_path,
    items,
    overrides,
    target,
    message,
    extra_args,
):
    pools_path = tmp_path / "level_pools.json"
    overrides_path = tmp_path / "pronunciation_overrides.json"
    model_path = tmp_path / "en_US-hfc_female-medium.onnx"
    pools_path.write_text(json.dumps({"1b": items}), encoding="utf-8")
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    model_path.touch()

    def fail_live_dependency(*args, **kwargs):
        raise AssertionError("model loading and playback must not start")

    monkeypatch.setattr(audition_level, "load_piper_voice", fail_live_dependency)
    monkeypatch.setattr(audition_level, "play_piper_variant", fail_live_dependency)

    result = audition_level.main(
        [
            "1b",
            "--compare-piper",
            "--pools",
            str(pools_path),
            "--overrides",
            str(overrides_path),
            "--piper-model",
            str(model_path),
            *extra_args,
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert target in captured.err
    assert message in captured.err.lower()
    assert "Level 1b Piper comparison" not in captured.out


def test_compare_reports_target_and_variant_when_playback_fails(monkeypatch, capsys, tmp_path):
    model_path = tmp_path / "en_US-hfc_female-medium.onnx"
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

    samples = audition_level.play_piper_variant(voice, "phonemes:b", variant)

    assert voice.phonemes == list("b")
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
