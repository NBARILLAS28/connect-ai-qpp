#!/usr/bin/env bash
# Abre la pagina para vincular otro celular (Mando PC debe estar corriendo).
open "http://localhost:8765/pair" 2>/dev/null || xdg-open "http://localhost:8765/pair"
