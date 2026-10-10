@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
uv run --offline --no-project python -m control_resonant_save_editor
if errorlevel 1 pause
