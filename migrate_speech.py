import shutil

# Copy the entire files to the new locations first
shutil.copy("ella_bot/speech/offline_asr.py", "src/ella_bot/speech/asr/vosk_engine.py")
shutil.copy("ella_bot/speech/offline_asr.py", "src/ella_bot/speech/asr/simulated.py")
shutil.copy("ella_bot/speech/offline_asr.py", "src/ella_bot/speech/asr/base.py")

shutil.copy("ella_bot/speech/tts_offline.py", "src/ella_bot/speech/tts/base.py")
shutil.copy("ella_bot/speech/tts_offline.py", "src/ella_bot/speech/tts/factory.py")

# Create temporary adapters in old locations
with open("ella_bot/speech/offline_asr.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.speech.asr.vosk_engine import *\n')

with open("ella_bot/speech/tts_offline.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.speech.tts.factory import *\n')

print("Speech migration complete.")
