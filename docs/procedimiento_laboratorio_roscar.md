# Procedimiento de laboratorio con el ROSCar (histórico, de RC-0 y RC-1)

Recopila lo que **ya funcionó** en el ROSCar 4 en los retos anteriores. No sustituye la verificación en el robot asignado al GranPrix: cada paso debe comprobarse antes de fiarse de él.

Fuentes: `RC-0_MicroRos_Pi5` (`README.md`, `setup_log.txt`, `scripts/`) y RC-1, rama `claude/sleepy-knuth-kc6wex`, archivo `docs/rc1_g8/avance_parteE.txt` (sección 4). Copias del código usado: `scripts/historicos/`.

## 1. Antes de encender
- Batería ≥ 70 (valor crudo de `/battery`; la unidad no está confirmada). Con la batería agotada el Pi se apaga y se pierden la hora y el bringup.
- Zona libre y plana, persona con la mano en el interruptor y otra lista para tomar el robot. Cinta, transportador y regla.
- Cargador desconectado durante las corridas.

## 2. Hora del Pi (cada sesión)
El Pi no guarda la hora: los CSV y los bags salen con fecha equivocada si no se corrige. En el host del Pi:
```bash
sudo timedatectl set-time "AAAA-MM-DD HH:MM:SS"
date -Is ; docker exec ros2_dev date -Is     # el del contenedor sale en UTC; deben coincidir
```

## 3. Bringup con la calibración propia
Terminal 1, déjala abierta (si se cierra, se apaga):
```bash
docker exec -it ros2_dev bash        # en RC-0 también: bash ~/ros2_humble.sh
source /opt/ros/humble/setup.bash ; source /root/yahboomcar_ws/install/setup.bash ; export ROS_DOMAIN_ID=8
ros2 launch capytown_esan bringup.launch.py wheel_params:=/root/wheel_params_g8.yaml
```
El log debe decir `b_eff=0.2138` y `k_ang=1.0863` (ROSCar 4). `wheel_params_g8.yaml` está en `scripts/historicos/rc1/`. **Solo vale para el ROSCar 4**: si el robot asignado es otro, no aplicarla. En RC-1 el robot llegó con la calibración de otro grupo (`r=0.0316`, `b_eff=0.2332`).

## 4. Llevar el repositorio al contenedor
El repositorio que hay en el Pi puede ser viejo. Desde la PC: `scp -r` del clon al Pi y luego, en el host del Pi, `docker cp` al contenedor. Los commits se hacen desde la PC, nunca desde el Pi.

## 5. Comprobaciones antes de cada corrida
```bash
ros2 node list                       # /YB_Car_Node y UN solo /odom_corrector
ros2 topic info /cmd_vel -v          # nadie más publicando (teleop_key cerrado)
ros2 topic hz /odom                  # ≈ 11 Hz en RC-0/RC-1
ros2 topic echo /battery --once
```
Con nuestro repositorio: `bash scripts/roscar_v01/preflight.sh` y `python3 scripts/roscar_v01/diagnostico_roscar.py` (da un veredicto OK/AVISO/FALLA; no seguir si hay FALLA).

## 6. Errores que ya ocurrieron
1. **Cortar el nodo antes de que termine** (Ctrl+C o `timeout`): el robot conservó la última orden y siguió girando. Siempre publicar ceros a continuación y tener a alguien en el interruptor.
2. **Dos `/odom_corrector` a la vez** (un bringup congelado seguía publicando): comprobar con `ros2 node list`.
3. **Reloj del Pi mal** (apareció julio de 2026).
4. **Sobrescribir corridas** por olvidar cambiar el nombre del CSV.
5. **Cinta adhesiva dentro del círculo de las ruedas:** el robot se atasca al girar. Las marcas de rumbo van a ≥ 25 cm del centro.
6. **Medir el ángulo con el transportador sobre el robot:** la dispersión de 75° a 95° era del método. Con líneas cruzadas y transportador circular bajó a ≈ ±3.5°.
7. **Bags vacíos:** en RC-1, 2 de 3 bags oficiales salieron sin mensajes. Comprobar con `ros2 bag info` el conteo de `/odom` y `/cmd_vel`.
8. **Superficie:** sobre caucho con uniones el cierre fue de 34–100 cm; sobre cerámica, de 10–36 cm. Caracterizar sobre la base de cartón real.

## 7. Lo que NO está en ningún repositorio y hay que sacar del robot
Los nodos del curso del paquete `capytown_esan` no están en los repositorios del equipo: `odom_corrector.py`, `calibrate_beff.py`, `teleop_key`, `fake_robot`, `error_odom`, `run_square` y `bringup.launch.py`. Viven en el contenedor, normalmente en `/root/yahboomcar_ws/src/capytown_esan/`. También pueden estar ahí las copias de trabajo de RC-0 (`/root/yahboomcar_ws/rc0_v2`, `rc0_rama`) y de RC-1 (`/root/microrospi5-sim_capytown_G8`), con los archivos que el README de RC-0 cita y que no están en GitHub (`respaldar_bags.sh`, `instalar_rosbag2.sh`, `generar_tablas_informe.py`, `validacion.csv`, `bitacora_*.csv`).

Respaldar fuera del repositorio, sin hacer commit hasta confirmar con el docente si pueden publicarse:
```bash
docker cp ros2_dev:/root/yahboomcar_ws/src/capytown_esan ~/respaldo_capytown_esan
docker exec ros2_dev ls -la /root /root/yahboomcar_ws
docker exec ros2_dev sha256sum /root/yahboomcar_ws/src/capytown_esan/capytown_esan/odom_corrector.py
```

## 8. Con los scripts de este repositorio
1. `bash scripts/roscar_v01/preflight.sh` y revisar el archivo.
2. `python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25` (solo cálculo) y luego con `--ejecutar --zona-segura`.
3. Medir y registrar: `scripts/roscar_v01/registrar_medicion.py … --auto`; con 5 corridas por condición, `analizar_movimientos.py`.
4. Anotar la sesión en `docs/bitacora_laboratorio.md`.

Los scripts de `roscar_v01` **nunca se han ejecutado contra ROS 2 real**. Como alternativa probada en el robot existe `scripts/historicos/rc0/capytown_esan/secuencia_rc0.py` (simulación por defecto, cuenta atrás, escribir `MOVER`, parada por odometría).
