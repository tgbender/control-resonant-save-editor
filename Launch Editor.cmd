@echo off
cd /d "%~dp0"
uv run --offline --no-project python editor_gui.py
if errorlevel 1 pause
