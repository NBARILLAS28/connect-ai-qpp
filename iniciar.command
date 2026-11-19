#!/usr/bin/env bash
# Mac / Linux: instala lo necesario la primera vez y arranca Mando PC.
cd "$(dirname "$0")"
[ -f requirements.txt ] && [ -f mando.py ] || { echo "Faltan archivos: descomprime el ZIP completo (doble clic en el ZIP) y abre iniciar desde la carpeta nueva."; exit 1; }
PY=$(command -v python3) || { echo "Instala Python 3 (https://www.python.org/downloads/)"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
if [ ! -f .venv/.listo ]; then
  .venv/bin/pip install -q -r requirements.txt && touch .venv/.listo || { echo "Error instalando dependencias"; exit 1; }
fi
exec .venv/bin/python mando.py "$@"
