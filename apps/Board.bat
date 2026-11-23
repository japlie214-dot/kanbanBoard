@echo off
setlocal
echo Starting Kanban Board Viewer...
python "%~dp0..\kb.py" serve --port 7890
if errorlevel 1 pause
