#!/usr/bin/env bash
# MODO REMOTO (Mac): evita que la Mac se duerma para poder controlarla desde el celular.
# Para deshacerlo:  ./modo-remoto-mac.command quitar
if [ "$1" = "quitar" ]; then
  sudo pmset -a disablesleep 0
  sudo pmset -c sleep 10
  echo "Modo remoto desactivado."
  exit 0
fi
echo "Activando modo remoto (te pedira tu contrasena de la Mac)..."
sudo pmset -c sleep 0 disksleep 0
sudo pmset -a disablesleep 1
echo
echo "Listo: la Mac no se duerme (tampoco al cerrar la tapa)."
echo "OJO: no la metas en la mochila asi; se calienta. Para deshacerlo: ./modo-remoto-mac.command quitar"
echo
echo "Pendiente a mano: Ajustes del Sistema > Pantalla bloqueada > 'Requerir contrasena...'"
echo "ponlo en Nunca (o lo mas largo posible), y el protector de pantalla en Nunca."
echo "Si bloqueas tu mismo (Ctrl+Cmd+Q), macOS no deja controlarla hasta que la desbloquees."
if ! command -v tailscale >/dev/null && [ ! -d /Applications/Tailscale.app ]; then
  echo
  echo "Para entrar desde fuera de casa necesitas Tailscale (gratis). Abriendo la descarga..."
  open "https://tailscale.com/download/mac"
fi
