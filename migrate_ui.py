import shutil

# Copy the UI files to the new locations
shutil.copy("ella_bot/ui/console_ui.py", "src/ella_bot/ui/console/console_ui.py")
shutil.copy("ella_bot/ui/gui_pygame.py", "src/ella_bot/ui/pygame_gui/app.py")
shutil.copy("ella_bot/ui/avatar_animator.py", "src/ella_bot/ui/pygame_gui/animator.py")
shutil.copy("ella_bot/ui/gui_config.py", "src/ella_bot/ui/pygame_gui/config.py")

# Create temporary adapters in old locations
with open("ella_bot/ui/console_ui.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.ui.console.console_ui import *\n')

with open("ella_bot/ui/gui_pygame.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.ui.pygame_gui.app import *\n')

with open("ella_bot/ui/avatar_animator.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.ui.pygame_gui.animator import *\n')

with open("ella_bot/ui/gui_config.py", "w") as f:
    f.write('"""Backward-compatible re-export adapter."""\n')
    f.write('from src.ella_bot.ui.pygame_gui.config import *\n')

print("UI migration complete.")
