@echo off
setlocal
echo Starting Kanban Board Viewer...

set "BOARD_DIR="
if defined KANBAN_BOARD_ROOT (
    set "BOARD_DIR=%KANBAN_BOARD_ROOT%"
) else if exist "%~dp0..\board" (
    set "BOARD_DIR=%~dp0..\board"
)

if not "%~1"=="" set "BOARD_DIR=%~1"

if defined BOARD_DIR (
    echo Loading board from: %BOARD_DIR%
    python "%~dp0..\viewer.py" --port 7890 --board-root "%BOARD_DIR%"
) else (
    python "%~dp0..\viewer.py" --port 7890
)

if errorlevel 1 pause
