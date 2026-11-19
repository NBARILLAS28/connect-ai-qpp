@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto sinpython
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if not exist ".venv\.listo" (
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto error
  echo listo> ".venv\.listo"
)
".venv\Scripts\python.exe" mando.py %*
goto fin
:sinpython
echo No encontre Python. Instalalo desde https://www.python.org/downloads/ (marca "Add Python to PATH") y abre este archivo otra vez.
goto fin
:error
echo Error instalando las dependencias. Revisa tu conexion a internet.
:fin
pause
