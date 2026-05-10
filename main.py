import sys
from ella_bot.cli.main import main

if __name__ == "__main__":
    print("WARNING: Running via main.py is deprecated. Use `ella-bot` or `python -m ella_bot.cli.main` instead.\n", file=sys.stderr)
    main()
