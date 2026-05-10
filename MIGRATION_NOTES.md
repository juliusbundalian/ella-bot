# Migration Notes

This codebase has been migrated from a flat structure to a modern `src/` layout. 
The architectural redesign splits the original monolithic files into clean domain layers.

## Key Changes
- **Source Layout**: All application code lives in `src/ella_bot/`.
- **Packaging**: The project is now an installable python package via `pyproject.toml`.
- **CLI Entrypoint**: `python main.py` is deprecated. Use the new console command `ella-bot` after installing.
- **Path Resolution**: Paths to `models`, `config`, and `assets` are now resolved relative to the package root automatically.

## Installation
If you are developing or running the project, you must install the package locally using pip:

```bash
# In the project root where pyproject.toml is located
pip install -e .
```

This makes the `ella-bot` command available globally inside your virtual environment.

## Running the Application
Instead of using `python main.py`, simply run:

```bash
ella-bot --gui
```

If you prefer using the python module syntax, you can also use:
```bash
python -m ella_bot.cli.main --gui
```
