import importlib
import sys
from unittest.mock import MagicMock, patch

cli_main = importlib.import_module("ella_bot.cli.main")


def test_parse_args_supports_numeric_level_shorthand():
    with patch.object(sys, "argv", ["ella-bot", "--start-level", "1"]):
        args = cli_main.parse_args()
        assert args.start_level == "1"

    with patch.object(sys, "argv", ["ella-bot", "--start-level", "2"]):
        args = cli_main.parse_args()
        assert args.start_level == "2"


@patch.object(cli_main, "EllaGUIApp")
@patch.object(cli_main, "build_asr", return_value=MagicMock())
@patch.object(cli_main, "build_tts_if_enabled", return_value=None)
def test_explicit_start_level_overrides_past_progress(mock_tts, mock_asr, mock_app_class, tmp_path):
    log_file = tmp_path / "sessions.jsonl"
    log_file.write_text('{"type": "sublevel", "level": "1a", "passed": true}\n', encoding="utf-8")

    with patch.object(sys, "argv", ["ella-bot", "--start-level", "1", "--session-log", str(log_file)]):
        args = cli_main.parse_args()
        cli_main.run_gui(args)

    mock_app_class.assert_called_once()
    kwargs = mock_app_class.call_args.kwargs
    # Should be 1a (mapped from 1), NOT auto-resumed to 1b
    assert kwargs["start_level"] == "1a"
