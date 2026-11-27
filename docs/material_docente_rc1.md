# Material del docente usado en RC-1 (no versionado) y ensayo en el simulador

Dos archivos `.zip` del docente se usaron en RC-1. **No se suben a este repositorio**: son material del curso (el repositorio de RC-1 excluyó `scripts_pdi/` por la misma razón). Si se quieren versionar, pedir permiso al docente. Este documento solo registra qué son y cómo sirven para el GranPrix.

## 1. `scripts_pdi` (nodo y herramientas de la clase)

Verificado el 25-nov-2026 contra los hashes que RC-1 registró para comprobar que el nodo era el original:

| Archivo | `sha256` (prefijo) | Coincide con RC-1 |
|---|---|---|
| `cuadrado_controller.py` | `d618e71722c4153d` | Sí |
| `core_cuadrado.py` | `a45a46afa2d36913` | Sí |

Contenido relevante:
- **`cuadrado_controller.py`**: nodo ROS 2 `/odom` → línea virtual y PID → `/cmd_vel`. Experimentos `recta`, `giro90`, `cuadrado` y **`cuadrado_abierto`**. Si `/odom` tarda más de 0.5 s publica ceros; al salir publica un `Twist()` en cero (pero con Ctrl+C o `timeout` ese cero puede no salir: el robot conservó la última orden en RC-1).
- **`core_cuadrado.py`**: lógica sin ROS (`Runner`, simulador de la planta, métricas).
- Resto (`01` a `11`, `heading_controller.py`, `core_pid.py`, `epuck_seguidor_sim.py`): apoyo de la clase RC-2 (carril, HSV, EKF). No aplican al GranPrix.
- Faltan en el zip `lane_controller.py` y `lane_detector.py`, que su README menciona.

**Qué aprovechar para el GranPrix:**
- `cuadrado_abierto` es el equivalente más cercano a nuestro ejecutor en lazo abierto: avanza `side / v` segundos y gira `(π/2) / (turn_w · turn_scale)` segundos. **`turn_scale` es el análogo de nuestra escala de giro `ca`** (se define como `1/χ`).
- Dato de RC-1 para el día de caracterización: en 3A (`turn_w = 0.8 rad/s`, `turn_scale = 1.0`) la primera esquina giró ≈ 115°; con otras corridas se había medido un giro 7–11 % mayor de lo ordenado. [Probable] La relación entre el giro físico y el ordenado **depende de la velocidad angular**. Caracterizar a la velocidad que se usará en carrera (referencia 0.5 rad/s, máximo 0.8), no solo a una.
- Puede usarse como prueba de cordura el día 3 (un cuadrado en lazo abierto da el cierre físico, que refleja `cd` y `ca`). No es la navegación del GranPrix.

## 2. `microrospi5pc` (simulador del carrito)

Es el espacio de trabajo `yahboomcar_ws` del simulador `yahboomcar_sim` del docente. Comparado con el repositorio base del curso (`codeplai/microrospi5-sim`): **mismo contenido**; solo cambian los finales de línea (CRLF), cachés y un nombre de archivo con caracteres chinos. El paquete `yahboomcar_sim` es idéntico al de RC-1. No añade nada que no tengamos.

## 3. Ensayar nuestros scripts contra el simulador antes del día 3

Nuestros scripts de ROS (`prueba_movimiento.py`) **nunca se han ejecutado contra ROS 2**. El simulador usa los mismos nombres de tópicos que el robot (`/cmd_vel`, `/odom`) y publica además la pose real en `/sim/pose`, así que sirve para probarlos sin carrito. Requiere Ubuntu 22.04 con ROS 2 Humble (WSL2 en las laptops; ver `SIMULACION.md` de RC-1 y `instalar_en_wsl.sh`).

```bash
# Terminal 1: simulador
ros2 launch yahboomcar_sim sim.launch.py world:=arena_rc1 start:=1.0,1.0,0.0 robot_radius:=0.14 noise:=none

# Terminal 2: nuestro script (solo cálculo y luego ejecución)
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25 --ejecutar --zona-segura

# Verdad del simulador, antes y después:
ros2 topic echo /sim/pose --once
ros2 service call /sim/reset std_srvs/srv/Empty
```

Qué se comprueba: que el script detecta `/odom`, publica y frena con ceros, escribe el CSV y rechaza correr si hay otro publicador de `/cmd_vel` (p. ej. `teleop_twist_keyboard` abierto). Con `noise:=none` (no `off`) el movimiento real debe coincidir con lo ordenado, de modo que `registrar_medicion.py --auto` y `analizar_movimientos.py` se pueden probar de punta a punta con `/sim/pose` como "cinta".

Límites: el simulador **no modela** el derrape de las 4 ruedas ni el retardo de `/odom`; no sirve para estimar `cd` ni `ca` del robot real. Con varias pruebas en paralelo la CPU se satura y los resultados se falsean.
