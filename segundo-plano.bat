@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" mando.py >> "%USERPROFILE%\.mando-pc\mando.log" 2>&1
