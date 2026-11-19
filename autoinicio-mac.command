#!/usr/bin/env bash
# Mac: Mando PC arranca solo al iniciar sesión (LaunchAgent).
# Para quitarlo:  ./autoinicio-mac.command --quitar
cd "$(dirname "$0")" || exit 1
AQUI="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/com.mandopc.agente.plist"

if [ "$1" = "--quitar" ]; then
  launchctl unload "$PLIST" 2>/dev/null
  rm -f "$PLIST"
  echo "Listo: Mando PC ya no arranca solo."
  exit 0
fi

if [ ! -x .venv/bin/python ]; then
  echo "Primero abre iniciar.command una vez (instala lo necesario) y vuelve a correr este archivo."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.mando-pc"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.mandopc.agente</string>
  <key>ProgramArguments</key><array>
    <string>$AQUI/.venv/bin/python</string><string>$AQUI/mando.py</string>
  </array>
  <key>WorkingDirectory</key><string>$AQUI</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$HOME/.mando-pc/mando.log</string>
  <key>StandardErrorPath</key><string>$HOME/.mando-pc/mando.log</string>
</dict></plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "Listo: Mando PC arrancará solo cada vez que inicies sesión."
echo "La primera vez macOS pedirá permisos de Grabación de pantalla y Accesibilidad para Python: acéptalos."
echo "Para quitarlo: ./autoinicio-mac.command --quitar"
