# Código histórico de RC-0 y RC-1 (copias sin modificar)

Herramientas que **ya se ejecutaron en el ROSCar** en los retos anteriores. Se conservan como referencia y para reutilizar durante la migración. **No son código nuevo del GranPrix y no se editan aquí**: si hace falta cambiar algo, se copia a `scripts/roscar_v01/` y se adapta allí.

| Origen | Commit | Carpeta |
|---|---|---|
| [RC-0_MicroRos_Pi5](https://github.com/Harold855/RC-0_MicroRos_Pi5) (`main`) | `751b5fb` (2026-11-05) | `rc0/` (conserva su estructura de carpetas, porque los scripts se llaman entre sí con rutas relativas a esa raíz) |
| [microrospi5-sim_capytown_G8](https://github.com/Harold855/microrospi5-sim_capytown_G8), rama `claude/sleepy-knuth-kc6wex` | `a42b5a1` (2026-11-20) | `rc1/wheel_params_g8.yaml` |

## Qué es cada cosa

| Archivo (en `rc0/`) | Qué hace | Estado |
|---|---|---|
| `scripts/preflight.sh` | Comprobaciones de solo lectura antes de mover (dominio, nodos, `/cmd_vel`, `/odom`, `r` y `b_eff`, batería, disco) | Usó el robot real |
| `scripts/grabar_bag.sh` | Graba odometría, `/cmd_vel`, `/tf` y `/battery` con nombre único | Usó el robot real |
| `scripts/corrida.sh` | Corrida guiada: preflight, bag, movimiento con confirmación, medición y CSV | Usó el robot real |
| `scripts/aplicar_param.sh` | Cambia `wheel_radius` o `wheel_separation` en caliente, con validación y registro | Usó el robot real |
| `scripts/parteA_contenedor.sh`, `parteA_host.sh` | Diagnóstico de solo lectura del contenedor y del host | Usó el robot real |
| `scripts/fijar_bag_final.sh` | Copia un bag al nombre final de entrega | Usó el robot real |
| `capytown_esan/secuencia_rc0.py` | Recta o giro con tope de velocidad, simulación por defecto, cuenta atrás, escribir `MOVER` y parada por odometría | Usó el robot real |
| `capytown_esan/odom_utils.py` | Yaw, desenvolvimiento del ángulo, desplazamiento, segmentación y detección de reinicios | Solo matemática |
| `capytown_esan/analizar_bag.py`, `plot_odom.py` | Del bag a los números de los CSV y a las gráficas | Necesitan `rosbag2_py` |
| `config/atajos_rc0.sh`, `entorno_rc0.sh` | Comandos cortos y dominio 8 | Usó el robot real |
| `test/` | 88 pruebas de RC-0 (**87 pasan; 1 falla desde antes**: `test_elegir_topic_ambiguo_exige_indicarlo`) | Sin robot |
| `rc1/wheel_params_g8.yaml` | Calibración del ROSCar 4: `r = 0.03145 m`, `b_eff = 0.2138 m` | Histórica |

Qué **no** se copió y por qué:
- `RC-0/config/wheel_params.yaml`: **tiene valores equivocados** (`0.0230` y `0.1350`, los de una prueba de sensibilidad). Usar `rc1/wheel_params_g8.yaml`.
- Los scripts de RC-1 (`rc1_correr.sh`, `rc1_analiza_real.py`, ...): dependen del nodo del curso `cuadrado_controller.py`, que no se versiona.
- Las gráficas reconstruidas con IA, los CSV de resultados y los bags vacíos.

## Qué hay que adaptar antes de usarlos en el GranPrix
1. **Rutas del Pi5:** asumen el contenedor `ros2_dev` y `/root/yahboomcar_ws/install/setup.bash`. Comprobar que existen en el robot asignado.
2. **Calibración:** `rc1/wheel_params_g8.yaml` solo vale para el ROSCar 4. Si el robot asignado es otro, no aplicarla; en RC-1 el robot llegó con la calibración de otro grupo.
3. **Nodos:** esperan `odom_corrector` y publicar en `/cmd_vel` directamente. Con el `twist_mux` y el `vigilante_red` del curso habrá que apuntar a la entrada que indique la plantilla.
4. **Bags:** verificar el conteo de mensajes con `ros2 bag info` (en RC-1, 2 de 3 bags oficiales salieron vacíos).
5. **Reloj del Pi5:** no guarda la hora; ponerla a mano cada sesión.

Las pruebas de `rc0/test/` se ejecutan desde `scripts/historicos/rc0/` con `python3 -m pytest -q test` (necesitan `pytest`; las de gráficas se omiten si falta `matplotlib`). No están en `scripts/ejecutar_pruebas.sh` para no mezclar la falla heredada con las pruebas nuevas.
