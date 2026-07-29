from argparse import Namespace
import importlib
from unittest.mock import MagicMock


def test_run_gui_does_not_recover_level_from_history(tmp_path, monkeypatch):
    cli_main = importlib.import_module("ella_bot.cli.main")

    log = tmp_path / "sessions.jsonl"
    log.write_text('{"type":"sublevel","level":"2a","passed":true}\n')
    args = Namespace(
        session_log=str(log),
        start_level="1a",
        gui_width=1280,
        gui_height=720,
        fullscreen=False,
        audio_feedback=False,
        pronunciation_overrides="missing.json",
    )
    monkeypatch.setattr(cli_main, "build_asr", lambda value: object())
    monkeypatch.setattr(cli_main, "build_tts_if_enabled", lambda value: None)
    monkeypatch.setattr(cli_main, "load_pronunciation_overrides", lambda value: {})
    app_class = MagicMock()
    monkeypatch.setattr(cli_main, "EllaGUIApp", app_class)

    cli_main.run_gui(args)

    assert app_class.call_args.kwargs["start_level"] == "1a"
