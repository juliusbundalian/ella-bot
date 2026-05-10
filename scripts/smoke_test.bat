@echo off
echo Running smoke tests for E.L.L.A. Migration...

echo Test 1: Help command via ella-bot
call ella-bot --help > nul
if %errorlevel% neq 0 (
    echo [FAILED] ella-bot --help failed.
    exit /b 1
)
echo [PASS] ella-bot --help

echo Test 2: Help command via python module
call python -m ella_bot.cli.main --help > nul
if %errorlevel% neq 0 (
    echo [FAILED] python -m ella_bot.cli.main --help failed.
    exit /b 1
)
echo [PASS] python -m ella_bot.cli.main --help

echo All smoke tests passed successfully!
