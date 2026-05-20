import configparser

from ella_bot.config import app_config


def test_load_settings_maps_ini_sections(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    ini = config_dir / "settings.ini"
    ini.write_text(
        "[System]\nstart_level = 2a\n"
        "[Speech]\nuse_mic = true\nlisten_seconds = 6\n"
        "[TTS]\naudio_feedback = true\ntts_rate = 170\n"
        "[GUI]\nfullscreen = false\ngui_width = 800\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_config, "get_project_root", lambda: tmp_path)

    settings = app_config.load_settings()

    assert settings["start_level"] == "2a"
    assert settings["use_mic"] is True
    assert settings["listen_seconds"] == 6
    assert settings["audio_feedback"] is True
    assert settings["tts_rate"] == 170
    assert settings["fullscreen"] is False
    assert settings["gui_width"] == 800


def test_load_settings_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "get_project_root", lambda: tmp_path)
    assert app_config.load_settings() == {}


def test_load_settings_maps_sample_rate(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    ini = config_dir / "settings.ini"
    ini.write_text(
        "[Speech]\nuse_mic = true\nsample_rate = 16000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(app_config, "get_project_root", lambda: tmp_path)

    settings = app_config.load_settings()

    assert settings.get("sample_rate") == 16000
