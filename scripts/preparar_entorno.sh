#!/usr/bin/env bash
# Prepara el entorno de desarrollo en la PC: entorno virtual .venv y dependencias de requirements-dev.txt.
# Con --pc-race instala también Race Control del docente (vendor/granprix/pc-race) para pruebas de integración.
# Uso:  bash scripts/preparar_entorno.sh [--pc-race]
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY=${PYTHON:-python3}
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "ERROR: se necesita Python 3.10 o superior (hay $("$PY" --version 2>&1))"; exit 1; }
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements-dev.txt
if [ "${1:-}" = "--pc-race" ]; then
  "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
    || { echo "AVISO: pc-race pide Python 3.12 o superior; no se instala."; }
  python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
    && python -m pip install -q -e "vendor/granprix/pc-race[dev]"
fi
echo "Entorno listo. Activar con:  source .venv/bin/activate"
echo "Probar con:  bash scripts/ejecutar_pruebas.sh"
