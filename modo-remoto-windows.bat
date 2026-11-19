@echo off
chcp 65001 >nul
rem MODO REMOTO (Windows): la laptop no se suspende, no se duerme al cerrar la tapa
rem y no pide contrasena al despertar, para poder controlarla desde el celular.
rem Solo aplica cuando esta CONECTADA a la corriente. Para deshacerlo: modo-remoto-windows.bat quitar
if /i "%~1"=="quitar" goto quitar
echo.
echo  Activando modo remoto (solo con la laptop conectada a la corriente)...
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 0
powercfg /setactive SCHEME_CURRENT
reg add "HKCU\Control Panel\Desktop" /v ScreenSaverIsSecure /t REG_SZ /d 0 /f >nul
echo.
echo  Listo:
echo   - No se suspende ni hiberna con la corriente conectada.
echo   - Cerrar la tapa no hace nada (ojo: no la metas en la mochila asi).
echo   - Ya no pide contrasena al despertar ni al salir del protector de pantalla.
echo.
echo  Pendiente a mano: en Configuracion ^> Cuentas ^> Opciones de inicio de sesion,
echo  pon "Requerir inicio de sesion si estuviste ausente" en "Nunca".
echo  Si bloqueas tu mismo con Win+L, Windows no deja controlarla hasta que la desbloquees.
echo.
where tailscale >nul 2>nul
if errorlevel 1 (
  echo  Para entrar desde fuera de casa necesitas Tailscale (gratis^).
  choice /c SN /m "  Instalarlo ahora"
  if not errorlevel 2 (
    winget install -e --id Tailscale.Tailscale || start "" "https://tailscale.com/download/windows"
  )
)
goto fin
:quitar
powercfg /change standby-timeout-ac 30
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1
powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE CONSOLELOCK 1
powercfg /setactive SCHEME_CURRENT
echo Modo remoto desactivado: suspension a los 30 min, tapa = suspender, contrasena al despertar.
:fin
pause
