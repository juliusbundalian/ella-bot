import os

dirs = [
    'src/ella_bot',
    'src/ella_bot/core',
    'src/ella_bot/speech',
    'src/ella_bot/speech/asr',
    'src/ella_bot/speech/tts',
    'src/ella_bot/speech/tts/engines',
    'src/ella_bot/validation',
    'src/ella_bot/ui',
    'src/ella_bot/ui/console',
    'src/ella_bot/ui/pygame_gui',
    'src/ella_bot/ui/pygame_gui/components',
    'src/ella_bot/services',
    'src/ella_bot/config',
    'src/ella_bot/utils',
    'src/ella_bot/cli'
]
for d in dirs:
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, '__init__.py'), 'w') as f:
        f.write('')

files = [
    'src/ella_bot/core/models.py',
    'src/ella_bot/core/exceptions.py',
    'src/ella_bot/core/constants.py',
    'src/ella_bot/speech/interfaces.py',
    'src/ella_bot/speech/asr/base.py',
    'src/ella_bot/speech/asr/vosk_engine.py',
    'src/ella_bot/speech/asr/simulated.py',
    'src/ella_bot/speech/asr/factory.py',
    'src/ella_bot/speech/tts/base.py',
    'src/ella_bot/speech/tts/engines/espeak.py',
    'src/ella_bot/speech/tts/engines/pyttsx3.py',
    'src/ella_bot/speech/tts/engines/mac_say.py',
    'src/ella_bot/speech/tts/engines/respeaker.py',
    'src/ella_bot/speech/tts/factory.py',
    'src/ella_bot/validation/validators.py',
    'src/ella_bot/validation/alignment.py',
    'src/ella_bot/validation/feedback.py',
    'src/ella_bot/validation/confidence.py',
    'src/ella_bot/ui/interfaces.py',
    'src/ella_bot/ui/console/console_ui.py',
    'src/ella_bot/ui/pygame_gui/app.py',
    'src/ella_bot/ui/pygame_gui/animator.py',
    'src/ella_bot/ui/pygame_gui/config.py',
    'src/ella_bot/ui/pygame_gui/components/menu.py',
    'src/ella_bot/ui/pygame_gui/components/button.py',
    'src/ella_bot/ui/pygame_gui/components/dialog.py',
    'src/ella_bot/services/app_service.py',
    'src/ella_bot/services/session_manager.py',
    'src/ella_bot/config/base.py',
    'src/ella_bot/config/defaults.py',
    'src/ella_bot/config/loader.py',
    'src/ella_bot/utils/file_utils.py',
    'src/ella_bot/utils/audio.py',
    'src/ella_bot/utils/logging.py',
    'src/ella_bot/cli/main.py'
]
for f in files:
    with open(f, 'w') as file:
        file.write('"""Placeholder"""\npass\n')
print('Scaffolding complete.')
