#!/usr/bin/env bash
# Ejecuta las pruebas de software del repositorio (no mueven ningún robot ni abren la red).
# Las pruebas del contrato necesitan pydantic (pip install pydantic); si falta, se omiten.
# Las de configuración YAML necesitan PyYAML (pip install pyyaml).
# Las de visión (tests/vision) necesitan OpenCV y pupil-apriltags (--vision en preparar_entorno.sh); si faltan, se omiten.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
rc=0
for d in tests/roscar_v01 tests/integracion tests/geometria_dock tests/estacion tests/jetcobot_v01 tests/carrito tests/comun tests/vision; do
  [ -d "$d" ] || continue
  echo "=== $d"
  python3 -m unittest discover -s "$d" -v 2>&1 | tail -n 6
  [ "${PIPESTATUS[0]}" -eq 0 ] || rc=1
done
[ "$rc" -eq 0 ] && echo "TODO OK" || echo "HAY FALLAS"
exit $rc
