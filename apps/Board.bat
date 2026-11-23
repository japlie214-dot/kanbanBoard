@echo off
setlocal
echo Starting Kanban Board Viewer...
if exist "%~dp0..\viewer.py" (
    python "%~dp0..\viewer.py" --port 7890
) else (
    python "%~dp0..\kb.py" serve --port 7890
)
if errorlevel 1 pause
