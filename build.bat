@echo off
rem ShadowPlay Notifier - single EXE build
rem Messages are ASCII on purpose: cmd.exe misparses this file when the
rem console code page does not match the file encoding.
setlocal
cd /d "%~dp0"

set NAME=ShadowPlayNotifier
set ICON=
if exist "app.ico" set ICON=--icon app.ico

where pyinstaller >nul 2>&1
if errorlevel 1 (
    set BUILDER=python -m PyInstaller
) else (
    set BUILDER=pyinstaller
)

%BUILDER% --onefile --noconsole --name %NAME% %ICON% shadowplay_notifier.py
if errorlevel 1 goto fail

echo.
echo Build finished: dist\%NAME%.exe
echo config.json is created next to the EXE on first run.
echo Runtime messages go to monitor.log next to the EXE.
endlocal
exit /b 0

:fail
echo.
echo Build failed. Install PyInstaller first:
echo   python -m pip install pyinstaller
endlocal
exit /b 1
