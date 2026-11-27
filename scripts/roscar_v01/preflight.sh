#!/usr/bin/env bash
# Diagnóstico de solo lectura: no cambia parámetros ni mueve el carrito.
set -u
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUT=${1:-"$ROOT/experimentos/dia01_roscar/diagnostico_$(date +%Y%m%d_%H%M%S).txt"}
mkdir -p "$(dirname "$OUT")"
exec > >(tee "$OUT") 2>&1
run(){ printf '\n$ '; printf '%q ' "$@"; printf '\n'; timeout 8s "$@"; local rc=$?; if ((rc!=0)); then echo "AVISO: salida $rc (revisar; 124 = tiempo límite)"; fi; return 0; }
echo "=== GranPrix G8: diagnóstico $(date -Is) ==="
run hostname
run hostname -I
printf 'ROS_DISTRO=%s\nROS_DOMAIN_ID=%s\nROS_LOCALHOST_ONLY=%s\n' "${ROS_DISTRO:-no definido}" "${ROS_DOMAIN_ID:-no definido}" "${ROS_LOCALHOST_ONLY:-no definido}"
[[ "${ROS_DOMAIN_ID:-}" == 8 ]] || echo 'AVISO: ROS_DOMAIN_ID no es 8 (valor del GranPrix para eq08)'
[[ "${ROS_LOCALHOST_ONLY:-}" == 1 ]] || echo 'AVISO: ROS_LOCALHOST_ONLY no es 1 (valor del GranPrix)'
run python3 --version
python3 -c 'import yaml; print("PyYAML", yaml.__version__)' 2>/dev/null || echo 'AVISO: este python3 no tiene PyYAML: las configuraciones YAML del carrito no se podrán cargar aquí (pip install pyyaml o apt install python3-yaml)'
if command -v docker >/dev/null; then run docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'; fi
run df -h .
run bash -c 'ls -l /dev/video* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true'
if ! command -v ros2 >/dev/null; then echo 'ERROR: ros2 no está disponible. Cargar el entorno autorizado. En RC-0/RC-1 ROS 2 estaba dentro del contenedor ros2_dev (bash ~/ros2_humble.sh).'; exit 1; fi
run ros2 node list
run ros2 topic list -t
run ros2 topic info /cmd_vel -v
for topic in /odom /odom_raw /imu /scan /battery /battery_state; do
  run ros2 topic info "$topic" -v
  # No imprime imágenes ni scans extensos; solo verifica metadatos de /scan.
  if [[ "$topic" != /scan ]]; then run ros2 topic echo "$topic" --once; fi
done
hz(){ printf '\n$ ros2 topic hz %s (6 s)\n' "$1"; PYTHONUNBUFFERED=1 timeout -s INT 6s ros2 topic hz "$1" 2>&1 | grep -E 'average rate|min:|does not appear' | tail -n 2; return 0; }
hz /odom
hz /imu
run ros2 param dump /odom_corrector
run ros2 topic info /tf -v
run ros2 topic list -t
echo "=== Fin. Archivo: $OUT ==="
