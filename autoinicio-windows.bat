@echo off
rem Hace que Mando PC arranque solo (y oculto) cada vez que inicias sesion en Windows.
set "DEST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MandoPC.vbs"
> "%DEST%" echo CreateObject("Wscript.Shell").Run "cmd /c ""%~dp0segundo-plano.bat""", 0
echo Listo. Mando PC arrancara solo al iniciar sesion. Para quitarlo borra:
echo %DEST%
pause
