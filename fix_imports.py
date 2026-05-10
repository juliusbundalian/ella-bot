import os
import glob

replacements = {
    "ella_bot.validation.text_validation": "ella_bot.validation.validators",
    "ella_bot.feedback.feedback_engine": "ella_bot.validation.feedback",
    "ella_bot.speech.offline_asr": "ella_bot.speech.asr.vosk_engine", # roughly
    "ella_bot.speech.tts_offline": "ella_bot.speech.tts.factory", # roughly
    "ella_bot.ui.console_ui": "ella_bot.ui.console.console_ui",
    "ella_bot.ui.gui_config": "ella_bot.ui.pygame_gui.config",
    "ella_bot.ui.gui_pygame": "ella_bot.ui.pygame_gui.app",
    "ella_bot.ui.avatar_animator": "ella_bot.ui.pygame_gui.animator"
}

# Special handling for TTS/ASR imports which might be specific classes
# We will just do textual replace, but some might need manual fix if they import SimulatedASR from vosk_engine
# Since we copied the whole file to vosk_engine.py and factory.py, everything is in there for now.

for root, _, files in os.walk("src/ella_bot"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = new_content.replace(old, new)
            
            if new_content != content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated {path}")

print("Import fixing complete.")
