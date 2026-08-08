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
        "[GUI]\nfullscreen = false\ngui_width = 800\ngui_left_padding = 10\n",
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
    assert settings["gui_left_padding"] == 10


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


def test_save_setting_round_trip(tmp_path, monkeypatch):
    import configparser
    ini_dir = tmp_path / "config"
    ini_dir.mkdir()
    ini = ini_dir / "settings.ini"
    parser = configparser.ConfigParser()
    parser.add_section("Speech")
    parser.set("Speech", "listen_seconds", "5")
    with open(ini, "w") as f:
        parser.write(f)

    monkeypatch.setattr("ella_bot.config.app_config.get_project_root", lambda: tmp_path)

    from ella_bot.config.app_config import save_setting, load_settings
    save_setting("Speech", "listen_seconds", "9")
    settings = load_settings()
    assert settings.get("listen_seconds") == 9
