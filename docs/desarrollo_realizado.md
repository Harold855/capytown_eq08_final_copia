# Registro del desarrollo (rama `claude/compassionate-goldberg-konorb`)

Qué se construyó en este repositorio, con qué evidencia, qué se descubrió y qué falta. Está escrito para que alguien del equipo que no vio las conversaciones pueda continuar. **Todo lo que aquí se afirma se comprobó con las pruebas automáticas del repositorio o se marca como no verificado.** Ningún código de este repositorio se ha ejecutado todavía contra el ROSCar, un JetCobot, una cámara real, ROS 2 ni un broker MQTT real.

Otros documentos: arquitectura en [`arquitectura.md`](arquitectura.md), requisitos y su cobertura en [`requerimientos.md`](requerimientos.md), índice de toda la documentación en [`README.md`](README.md).

## 0. Cómo leer los estados

| Estado | Significa |
|---|---|
| **Verificado** | tiene pruebas automáticas que pasan (`bash scripts/ejecutar_pruebas.sh`) |
| **Simulado** | verificado solo contra un modelo o una cámara/brazo sintéticos: no demuestra comportamiento físico |
| **Sin verificar** | existe el código o el texto, pero nada lo ha ejecutado en su entorno real |
| **Supuesto** | decisión nuestra sobre algo que el docente aún no publicó; está marcada donde se usa |
| **Pendiente** | no existe |

## 1. Resumen

| Bloque | Qué hay | Estado |
|---|---|---|
| Análisis y contexto | `docs/contexto_analisis.md`, README de entrada y `docs/referencia_del_reto.md` (el detalle del reto), división v1.3 como guía | Documentos |
| Repositorio del docente | `vendor/granprix/` (89 archivos, sin modificar, commit `285c829`) | Verificado: 126 pruebas de `pc-race` y 24 de la herramienta AprilTag (familia `tag36h11`) pasan |
| ROSCar: base de laboratorio | `scripts/roscar_v01/` (v0.1 entregada + registro, análisis, contrato y diagnóstico), `scripts/historicos/` (RC-0 y RC-1), procedimiento de laboratorio | Verificado en lo puro; el código que usa `rclpy` **sin verificar** |
| ROSCar: planificador | `carrito/granprix_carrito/planificador.py`, `docks.py` | Verificado; equivale al `simulate()` del HTML a 1e-9 |
| ROSCar: ejecutor de movimiento | `carrito/granprix_carrito/ejecutor.py` | Simulado (reloj falso y robot ideal) |
| ROSCar: estimadores `cd` y `ca` | `carrito/granprix_carrito/calibracion.py` | Simulado |
| ROSCar: cámara → dock y reset de pose | `carrito/granprix_carrito/transformacion_camara_dock.py`, `reset_pose.py`, `config/marcos.yaml`, `scripts/roscar_v01/pose_dock.py` | Simulado; **falta medir el montaje de la cámara** |
| Configuración YAML | 6 archivos + cargador estricto `comun/yaml_estricto.py` | Verificado |
| MQTT | `integracion/configuracion/mqtt.yaml`, `mqtt_config.py`, `scripts/roscar_v01/mensajes_contrato.py` | Verificado contra el contrato del docente; **sin broker real** |
| Estación (JetCobot) | `estacion/` estrategia, roles, compensación, poses, brazo simulado; `scripts/jetcobot_v01/` | Simulado; **nunca contra un brazo** |
| Visión sin robot | `vision/`, `simulacion/*sintetico.py`, calibración con regla y con damero, `medir_tag.py` | Simulado (cámara sintética); **nunca con la cámara real** |
| ROSCar: acople fino y calibración por tramo | `carrito/granprix_carrito/acople.py`, `calibracion_tramo.py`, `config/acople.yaml`, `simulacion/robot_simulado.py`, `scripts/roscar_v01/prueba_acople.py`, `prueba_calibracion_adaptativa.py`, `analizar_acople.py` | Simulado; **el ensayo con el robot está preparado, sin ejecutar** |
| Pruebas | 791 propias en 8 carpetas | Verificado |
| Entorno | `scripts/preparar_entorno.sh`, `requirements-*.txt` | Verificado en Linux, Python 3.13 |

**Lo que NO existe:** nodos ROS 2 del carrito (`control_odometria`, `camara_apriltag`, `maquina_pit`), el adaptador ROS 2 del ejecutor, la máquina de estados del pit, el tablero web, la cinemática y manipulación reales del brazo, y cualquier medición física. La lógica de arriba está lista para conectarse a ellos, pero conectarla es trabajo pendiente.

## 2. Línea de tiempo (commits de la rama)

| Commit | Contenido |
|---|---|
| `b3e8c59`, `6c72c11` | Contexto del análisis de retos previos; README ampliado (reglas, pit, MQTT, evidencia, rúbrica) |
| `9d28080`, `f4622a0`, `9a2ecdb` | Contexto de división v1.1 y v1.2 según el repositorio del docente; README y análisis alineados |
| `bbb6f48` | Copia del repositorio del docente en `vendor/` y división v1.3 (la del equipo) |
| `539656a`, `b331c49` | ROSCar v0.1 tal como se entregó, y mejoras (registro, análisis, contrato, pruebas) |
| `5179d4c` | Diagnóstico del JetCobot y plantilla de estrategia de la estación |
| `197ba7a`, `65cb3bc`, `55aecf9` | Copias históricas de RC-0 y RC-1, procedimiento de laboratorio, material docente de RC-1 |
| `24729bb` | Entorno de desarrollo reproducible |
| `82a9e72` | Diagnóstico del ROSCar con veredicto |
| `db1ae2c` | Planificador matemático |
| `7f1f7ab` | Ejecutor de movimiento |
| `c613af0` | Estimadores de escala `cd` y `ca` |
| `7675048` | Configuraciones YAML |
| `3ffad03` | AprilTag sin robot |
| `7431e04` | Calibración de la cámara con regla y tag |
| `a0862cb` | Calibración de la cámara con damero |
| `8444c39` | Documentación completa: registro, arquitectura, requisitos e índice |
| `1f965ea` | `medir_tag.py`: medición de la pose del tag con la cámara calibrada |

`b503baf`, `37eabf9` y `ccd47aa` son anteriores y del equipo. No se abrió ningún PR.

## 3. Mapa del repositorio

```
README.md                      página de entrada: equipo, datos, resumen del reto, estado
contexto_division_reto_final.md  división del equipo v1.3 (del equipo, guía del desarrollo)
docs/                          documentación (índice en docs/README.md)
vendor/granprix/               copia fija del repositorio del docente (NO se edita)
carrito/                       lógica del ROSCar en Python puro
  nodos/                       nodo_reset_pose.py, tag_emulado.py, camara_apriltag_node.py (rclpy; sin verificar con ROS)
  granprix_carrito/            docks, planificador, ejecutor, calibracion, acople, calibracion_tramo, configuracion
  config/                      movimiento.yaml, calibracion.yaml, acople.yaml
estacion/                      estrategia de cambio de pieza del JetCobot
  src/app_equipo/              puerto, roles, compensacion_pose, posiciones, estrategia, brazo_simulado, configuracion
  config/                      estacion.yaml, poses.plantilla.yaml
geometria_dock/                transformaciones 2D compartidas (carrito y estación)
comun/                         cargador YAML estricto
integracion/                   configuración MQTT (mqtt.yaml + lector)
vision/                        herramienta AprilTag del docente, calibración de cámara (regla y damero)
simulacion/                    modelo del simulador del HTML, barridos, imágenes sintéticas
scripts/
  roscar_v01/                  inicio del ROSCar: preflight, diagnóstico, prueba de movimiento, registro, análisis
  jetcobot_v01/                diagnóstico (solo lectura) y cronómetro del JetCobot
  camara/                      calibrar_focal.py (regla), calibrar_damero.py y medir_tag.py
  historicos/                  copias de RC-0 y RC-1 (referencia, sin modificar)
  preparar_entorno.sh, ejecutar_pruebas.sh
tests/                         una carpeta por paquete (791 pruebas)
experimentos/                  plantillas de evidencia (vacío de mediciones reales)
requirements-dev.txt, requirements-vision.txt
```

## 4. Módulos

### 4.1 Análisis, contexto y alineación con el docente
- `docs/contexto_analisis.md` reúne el análisis de los repositorios previos (Reto 2, Gran Reto, RC-0, `microrospi5-sim_capytown_G8`, el zip del Reto 1), del HTML oficial y del repositorio del docente. Marca cada afirmación con su nivel de evidencia.
- El README y el análisis se alinearon con el repositorio del docente (`9a2ecdb`) porque este "manda" sobre el HTML (el docente lo indicó). La división del equipo v1.3 se adoptó como guía.
- `vendor/granprix/` es una copia fija (no un submódulo): ver `vendor/README.md`.

### 4.2 ROSCar: base de laboratorio (`scripts/roscar_v01/`, `scripts/historicos/`)
- v0.1 del equipo (`matematica.py`, `preflight.sh`, `prueba_movimiento.py`) más: `registrar_medicion.py` (valida filas de `mediciones_fisicas.csv`, rechaza centímetros donde van metros), `analizar_movimientos.py`, `mensajes_contrato.py` y `diagnostico_roscar.py`.
- `diagnostico_roscar.py` es de **solo lectura** y da veredicto OK/AVISO/FALLA: entorno ROS, un solo `/odom_corrector`, `/cmd_vel`, frecuencia de `/odom`, batería, qué calibración está activa (si es la de RC-1, la de otro grupo o la equivocada), cámara, disco y hora. Probado con `--simular ok|mal`; la parte que consulta ROS (`recolectar`) **no se ha ejecutado**.
- `scripts/historicos/rc0` y `rc1` son copias sin modificar de lo que se usó en RC-0 y RC-1. Se excluyó el `wheel_params.yaml` de RC-0 (era de otro robot) y se conservó `scripts/historicos/rc1/wheel_params_g8.yaml`. No se aplican parámetros históricos a robots distintos.
- `docs/procedimiento_laboratorio_roscar.md` y `docs/material_docente_rc1.md` documentan cómo se corrió en RC-0/RC-1.

### 4.3 ROSCar: planificador (`carrito/granprix_carrito/planificador.py`, `docks.py`)
- Los cuatro docks del reto: D1 (0.40, 0.40, −90°), D2 (2.40, 0.40, 0°), D3 (2.40, 2.40, +90°), D4 (0.40, 2.40, 180°).
- `planificar_tramo` (giro y distancia a un destino), `comandar` (compensado: `phi_cmd = phi/ca`, `L_cmd = L/cd`, con duraciones y límites de 0.20 m/s y 0.8 rad/s), `planificar_vuelta`, `tiempo_vuelta`.
- Acople: `acople_valido` (≤ 4 cm **y** ≤ 6°, con tolerancia numérica de 1e-9) y `planificar_acople` con giros y avances (el carrito no se mueve de lado; sin reversa por defecto).
- **Evidencia:** `simulacion/modelo_granprix.py` es un port a Python del `simulate()` del HTML que usa este planificador. Reproduce 18 casos y 288 llegadas del JavaScript original (ejecutado con Node.js) a 1e-9, incluido el caso semilla 7: 479.653 s, `cd` 1.011667, `ca` 0.985804. Con llegadas ideales una vuelta dura 116.57 s con un pit de 6 s, y cuatro vueltas 466.27 s (sin aceleración ni reintentos).

### 4.4 ROSCar: ejecutor de movimiento (`ejecutor.py`)
- Máquina de estados no bloqueante, con reloj y salida inyectados: giro → pausa en ceros → avance → asentamiento en ceros. Se maneja llamando a `paso()` a unos 20 Hz.
- Rechaza comandos fuera de límites, no finitos o de más de 60 s. Aborta con ceros ante parada externa, odometría perdida, hueco de más de 0.25 s entre llamadas, reloj que retrocede, error de la salida o tiempo máximo. No reanuda solo. Rampa de aceleración opcional (solo limita acelerar).
- `comando_efectivo` devuelve lo realmente enviado (Σ v·dt y Σ w·dt): es lo que debe recibir el estimador de escalas.
- **Límite que no puede cubrir:** si el nodo ROS muere, nadie llama a `paso()` y el firmware conserva la última orden `/cmd_vel` (dato heredado de RC-1). La protección es el *timeout* de la entrada de `twist_mux`, **sin verificar** en el robot.
- **Placeholders:** `pausa_s = 0.30` y `asentamiento_s = 0.50` no son mediciones; el retardo de `/odom` de 0.5–0.65 s sugiere que 0.5 s se queda corto.
- **Falta** el adaptador ROS 2 (Twist, `/odom`, reloj).

### 4.5 ROSCar: estimadores `cd` y `ca` (`calibracion.py`)
- `EstimadorEscalas`: la fórmula del HTML (`c += α·(medido/comandado − c)`, α = 0.35) con registro por observación, rechazos por escala (tramo corto, giro fuera de 20°–150°, razón fuera de [0.5, 1.5], tag ausente, congelado, velocidad distinta), paso máximo de 0.05, congelado de escalas, criterio de convergencia (4 actualizaciones usadas con diferencia < 0.01), exportación a CSV y archivo de estado YAML ligado al robot.
- **No mezcla velocidades distintas:** RC-1 midió un giro 7–11 % mayor que el ordenado según ω. Es una inferencia con pocos datos.
- `evaluar_reduccion`: fracción de paradas con error posterior menor que el previo (umbral 70 % de la evaluación oficial). Cómo cuenta la rúbrica las paradas ya dentro de tolerancia **no está confirmado**; la función informa ambas versiones.
- `simulacion/barrido_alpha.py` compara valores de α con el modelo del HTML: α = 0.35 es el mejor compromiso (ver §5).

### 4.5 bis ROSCar: cámara → dock y reset de pose (`transformacion_camara_dock.py`, `reset_pose.py`)
- `transformacion_camara_dock.py` convierte la pose del tag (sistema de la cámara, la que entrega `medir_tag.py`) en pose del robot en el dock `(dx, dy, dth)` y en el mapa, componiendo transformaciones 2D con el montaje de la cámara y la posición del tag en el dock. `montaje_desde_referencia` obtiene el montaje de una medición con el robot sobre su marca.
- `ResetPose` calcula `map → odom` y `pose_mapa(odom)`; exige inicialización explícita, robot quieto, salto acotado y pose cerca del dock, y un rechazo no cambia su estado.
- `pose_dock.py` (`LocalizadorDock`, `PoseDock`) es la interfaz que consumirá el pit: la pose del ROSCar respecto al dock desde el tag (para acoplar y para la `solicitud`) o desde la odometría con el último reset (cuando el tag no se ve), con su error frente a 4 cm y 6° y el formato del contrato.
- `gestor_reset.py` y `nodos/nodo_reset_pose.py`: el adaptador ROS 2 del reset (TF `map → odom`, servicio `Trigger`, odometría interpolada en el instante de la medición para sortear su retardo). La lógica es Python puro y está probada; el nodo se probó **solo contra un sustituto de `rclpy`**, nunca con ROS.
- `nodos/tag_emulado.py` emula el AprilTag a partir de `/sim/pose` del simulador RC-1 (que no dibuja tags), con visibilidad y ruido; `nodos/camara_apriltag_node.py` integra la medición con ROS 2 (imagen → `/tag/pose`, sin `cv_bridge`). Ambos, como el nodo del reset, se probaron **solo contra un sustituto de `rclpy`**. El marco base por defecto es `base_footprint` (el de RC-1 y del simulador).
- `scripts/roscar_v01/pose_dock.py convertir | montaje` lo expone por línea de comandos sobre la salida de `medir_tag.py`.
- **Simulado:** escena física 3D independiente (2 mm y 0.2° en la zona de acople) y del píxel a la pose (p95 0.35 cm y 0.44°, con el montaje conocido). Los errores del montaje pasan 1 a 1 a la pose.
- **Falta medir** el montaje de la cámara y la posición del tag en el dock (`marcos.yaml` falla mientras haya `null`), y el publicador ROS 2 del TF. Detalle: [`marcos_y_reset_pose.md`](marcos_y_reset_pose.md).

### 4.5 ter ROSCar: acople fino y calibración por tramo (`acople.py`, `calibracion_tramo.py`)
- `acoplar(medir, mover, cfg, escalas)` repite medir → corregir → medir con control proporcional hasta quedar dentro de una tolerancia interna (3 cm y 4°), con `1 + reintentos` correcciones como máximo. Reutiliza `planificar_acople`, `comandar` y `EjecutorMovimiento`; añade marcha atrás corta para sobrepasos (desactivada por defecto en el ejecutor), presupuesto de tiempo, alcance y motivos de parada. Tras un movimiento fallido no afirma ninguna pose.
- `CalibradorTramo` garantiza que el estimador reciba la pose de llegada **anterior** a cualquier corrección (la toma del resultado del acople), el comando realmente enviado y nunca los movimientos del acople; guarda errores antes y después (criterio normalizado propio) y los exporta a CSV.
- `MedidorTag` filtra las lecturas anteriores al reposo y devuelve la mediana; `mover_con_ejecutor` lo avisa al terminar cada movimiento.
- Scripts: `prueba_acople.py` (simulado y ensayo físico preparado), `prueba_calibracion_adaptativa.py` (circuito simulado o repetición con tramos medidos), `analizar_acople.py` (resumen y SVG).
- **Simulado:** Monte Carlo del acople y circuitos de 8 vueltas con el robot de `simulacion/robot_simulado.py` (cifras en `acople.md`). El modo `ensayo` se probó solo contra un `rclpy` sustituto con un mundo simulado; **nunca con el robot**. 12 errores introducidos a propósito en el código (signo, reintentos, pose posterior al acople, marcha atrás, etc.) fueron detectados por las pruebas.
- **Hallazgo:** una corrección cuesta ≈ 4–5 s; con un intercambio de 6 s casi no cabe una dentro del pit de 10 s. Detalle y límites: [`acople.md`](acople.md).

### 4.5 quater ROSCar: máquina de la misión (`maquina_pit.py`, `mision.py`, `nodos/adaptador_ros.py`)
- `MaquinaPit` implementa los diez estados (ESPERA → … → SALIENDO → NAVEGANDO, FIN y FALLA) con `paso()` a 20 Hz en un solo hilo; estados, plazos y seguridad viven dentro del mismo archivo. Reutiliza el acople (como generador), el ejecutor, el planificador y `CalibradorTramo`. `Mision` lleva estaciones, vueltas, piezas y el registro de pits (`pits.csv`).
- Seguridad: todo `Twist` pasa por `SalidaSegura`; sin turno, con bandera roja, sin enlace o con un intercambio en curso sale cero; los estados quietos, `FIN` y `FALLA` publican ceros cada paso; un error inesperado termina en `FALLA`. No sustituye al vigilante del curso ni a la parada física.
- `adaptador_ros.py` conecta el núcleo con ROS 2 (los nombres de tópicos del curso son provisionales).
- **Simulado:** misión de 4 vueltas contra una planta continua y una estación que valida con la pose verdadera (`simulacion/mision_simulada.py`): 30 de 30 completas con escalas caracterizadas, 537 s de media. 21 errores introducidos a propósito en el código fueron detectados por las pruebas.
- **Hallazgos:** el pit solo cabe en 10 s sin corrección (7.6 s; con corrección 14.8 s de media) y el 54 % de los pits simulados necesita una; con escalas sin caracterizar casi no se completa la misión. Detalle y límites: [`mision.md`](mision.md). **Nunca se ejecutó con ROS, el curso ni el robot.**

### 4.5 quinquies Evidencia, métricas y panel (`eventos_mision.py`, `cronometro.py`, `metricas.py`, `evidencia/`, `tablero/`)
- La máquina registra sus eventos en JSONL; de ahí salen el cronómetro (vueltas, sectores, tramos, pits) y las métricas; el panel (prototipo estático) las muestra.
- `verificar_evidencias.py` comprueba video (por cajas MP4), rosbag2 (cuenta cada mensaje en el SQLite: evita los bags vacíos de RC-1) y CSV, y la cobertura temporal con `eventos.jsonl`. `registro_experimental.py` guarda las pruebas de laboratorio con cadena de hashes.
- **Verificado:** 22 errores introducidos a propósito en verificador y registro, todos detectados; el bug de un argumento duplicado en un evento lo atrapó la prueba de seguridad (la máquina cayó en `FALLA`, no siguió a ciegas).
- **No verificado:** el layout real del `grabador`, los nombres de tópicos reales, `mcap`, el JavaScript del panel con pruebas automáticas y la integración con el tablero del curso. Detalle: [`tablero_y_evidencia.md`](tablero_y_evidencia.md).

### 4.6 Configuración YAML (`docs/configuracion.md`)
Seis archivos, cada uno con su lector validado, más un cargador estricto compartido (`comun/yaml_estricto.py`):

| Archivo | Lo lee |
|---|---|
| `carrito/config/movimiento.yaml` | `carrito.granprix_carrito.configuracion.cargar_movimiento` |
| `carrito/config/calibracion.yaml` | `EstimadorEscalas.cargar` / `cargar_carrito` |
| `carrito/config/marcos.yaml` | `carrito.granprix_carrito.transformacion_camara_dock.cargar_marcos` |
| `estacion/config/estacion.yaml` | `app_equipo.configuracion.cargar_estacion` |
| `estacion/config/poses.plantilla.yaml` | `app_equipo.posiciones.cargar` |
| `integracion/configuracion/mqtt.yaml` | `integracion.mqtt_config.cargar_mqtt` |

Reglas que el cargador hace cumplir: una configuración **no puede aflojar el reto** (0.20 m/s y 0.8 rad/s, 4 cm y 6°, 10 s, 5 Hz); claves desconocidas, faltantes o duplicadas son error (PyYAML por sí solo acepta duplicados y gana la última); tipos exactos; ningún secreto en el archivo (la contraseña MQTT va en `GRANPRIX_MQTT_CLAVE`). No se crearon `dock_frames.yaml`, `camara.yaml` (semilla), `almacenes.yaml` ni `manipulacion.yaml`: no hay datos reales ni el docente publicó el esquema.

### 4.7 MQTT (`integracion/`, `scripts/roscar_v01/mensajes_contrato.py`)
- `mqtt.yaml` (broker `192.168.50.10:1883`, equipo 8, diez tópicos con QoS y retenido) se compara en pruebas con el módulo de tópicos y la tabla del documento del docente: si el contrato cambia, falla una prueba.
- `mensajes_contrato.py` construye los mensajes del carrito (unidades internas SI; `dth` en grados en el contrato) y se prueba contra los modelos `pydantic` del docente.
- **Sin verificar:** ejecución contra un Mosquitto real. El usuario `carrito08` es una deducción del patrón `carritoNN`.

### 4.8 Estación / JetCobot (`estacion/`, `scripts/jetcobot_v01/`)
- Estrategia de cambio por rol (E1 carga A, E2 retira A y coloca B, E3 retira B y coloca C, E4 retira C), con compensación de la cuna, poses enseñadas en el laboratorio y brazo simulado. **Falla cerrada:** sin poses devuelve `NO_CONFIGURADO` y no llama al brazo; valida pieza, tolerancia, alcance y bandeja antes de mover; un fallo detiene la secuencia.
- `diagnostico_jetcobot.py` (solo lectura; una prueba comprueba que el archivo no contiene órdenes de movimiento, pinza ni apagado) y `cronometro_ciclo.py` (cronómetro manual por fases).
- **Supuestos:** la firma del puerto `BrazoJetCobot`, el marco del dock, el significado de `pieza_dejo`. Ver `estacion/README.md`.
- **Hallazgo de tiempo (con duraciones de EJEMPLO):** la secuencia tarda 8.2 s en E1/E4 y 15.4 s en E2/E3 (13 movimientos y 6 maniobras de pinza); con un tope propio de 8 s, E2 no cabe. Hay que medir el brazo real.

### 4.9 Visión sin robot (`vision/`, `simulacion/`, `scripts/camara/`)
- `vision/herramienta.py` envuelve la herramienta AprilTag del docente (sin modificarla): un solo detector por proceso, `pose_tag`, y `Corrector` / `pose_tag_calibrada` para cámaras con distorsión.
- `simulacion/apriltag_sintetico.py` y `damero_sintetico.py` renderizan un tag o un damero con pose, cámara y distorsión conocidas (`lente.py`), para medir el error contra la verdad.
- **Calibración con regla** (`calibrar_focal.py capturar | calcular | validar`): ajusta la focal y el desfase de la regla con una regresión sobre varias distancias, sin damero. Rechaza ajustes incoherentes y valida también fuera del eje. Procedimiento: [`procedimiento_calibracion_camara.md`](procedimiento_calibracion_camara.md).
- **Calibración con damero** (`calibrar_damero.py crear | capturar | calcular | validar`): focal, punto principal y distorsión. Captura automática, rechazo automático de imágenes atípicas, validación cruzada. Procedimiento: [`procedimiento_calibracion_damero.md`](procedimiento_calibracion_damero.md). Se usa solo si la validación fuera del eje de la regla falla.
- **Medición** (`medir_tag.py una | continuo | comparar | resumen`, núcleo en `vision/medicion.py`): corrige la distorsión, rechaza las detecciones dudosas (`sin_tag`, `otro_id`, `varios_tags`, `hamming`, `margen_bajo`...), agrega varios cuadros con mediana y dispersión, y solo entrega pose si la medición es aceptada. `comparar` guarda en un CSV la comparación con regla y transportador (también lo que falla) y `resumen` la evalúa. La pose es en el **sistema de la cámara**, no en el marco del dock. Umbrales de calidad **provisionales**. Procedimiento: [`procedimiento_medir_tag.md`](procedimiento_medir_tag.md).
- Detalle y cifras: [`apriltag_sin_robot.md`](apriltag_sin_robot.md).

### 4.10 Entorno y pruebas
- `bash scripts/preparar_entorno.sh [--pc-race] [--vision]` crea `.venv` e instala dependencias; `bash scripts/ejecutar_pruebas.sh` corre las ocho carpetas y devuelve distinto de 0 si algo falla. Ver `docs/entorno_desarrollo.md`.

## 5. Hallazgos con cifras

| # | Hallazgo | Fuente y estado |
|---|---|---|
| 1 | α = 0.35 da el menor error de llegada (2.6 cm, 83 % de llegadas válidas) con un robot simulado que gira +9 % y avanza +1 %. α = 0.10 tarda 17 pits en estabilizar `ca` y una carrera tiene 16 | `simulacion/barrido_alpha.py`; simulado |
| 2 | Con α = 0.35, `ca` tarda unos 5 pits en estabilizarse (más de una vuelta): conviene **sembrar las escalas con valores caracterizados** en vez de arrancar con 1.0 | mismo barrido; simulado |
| 3 | El estimador debe recibir lo **enviado**, no lo nominal: con lo nominal converge a ≈ la raíz de la escala real (1.044 en vez de 1.09) | prueba en `tests/roscar_v01`; verificado |
| 4 | Con rampa de aceleración, estimar con el comando nominal sesga `cd` cerca de 1 %; con `comando_efectivo` no | `tests/carrito/test_calibracion.py`; simulado |
| 5 | La distancia `z` del tag es la magnitud frágil: un campo de visión supuesto con 6 % de error da **2 cm** de error; con 60° real y 70° supuestos, **4.9 cm** (más que la tolerancia de 4 cm). Un tag impreso con 3–5 % de error en tamaño suma 1–1.4 cm | `docs/apriltag_sin_robot.md`; simulado |
| 6 | El error angular del tag (`dth`) es peor con el tag **de frente**: p95 de 1.0–1.7° con 640×480 y máximo de hasta 3.7° con 320×240 (tolerancia 6°) | `simulacion/barrido_apriltag.py`; simulado |
| 7 | La distorsión de barril no cambia la focal ajustada ni el error del ajuste con regla; solo se ve **fuera del eje**: con `k1 = −0.4`, 1.7 cm de error en `z` a 10 cm del centro. Con el damero baja a menos de 0.7 cm | `tests/vision/test_calibracion_damero.py`; simulado |
| 8 | El error de reproyección del damero **no valida la escala**: un 10 % de error en la focal pasa. La escala solo se valida con distancias medidas | misma prueba; simulado |
| 9 | Una sola imagen del damero con esquinas mal localizadas desvía la focal más de 1 % (hasta ~3 %); el cálculo las descarta solas, pero con 10 imágenes no puede: hacen falta 20 o más | misma prueba; simulado |
| 10 | `pupil-apriltags 1.0.4` aborta el proceso con corrupción de memoria al usar `tag25h9` en la prueba parametrizada del docente. `tag36h11` (el del reto) funciona: 24 pruebas pasan | `docs/apriltag_sin_robot.md`; verificado, causa sin investigar |
| 11 | Con duraciones de ejemplo, la estación tarda 15.4 s en E2/E3 y el pit total es de 10 s | `estacion/README.md`; **placeholders**, no medición |
| 12 | Datos heredados de RC-1 (no son de este reto): el robot gira 7–11 % más de lo ordenado, con dispersión de ±3.5°; `/odom` ≈ 11 Hz con retardo de 0.5–0.65 s; el firmware conserva la última orden si el nodo muere | `docs/contexto_analisis.md`; medidos en otro robot |
| 13 | En simulación una detección sana da margen de decisión de 105 a 120, con poco contraste 23–47 y movida ~53, y la pose sale exacta en todos los casos: el margen sirve para rechazar falsas detecciones, no predice el error de pose. Los umbrales de `medir_tag` (margen 30, hamming 0) son provisionales | medición ad hoc con `simulacion/apriltag_sintetico.py`; simulado |
| 14 | Una medición completa (con corrección de distorsión) tarda ~20–30 ms por cuadro en una PC de 4 núcleos; en el Pi 5 no está medido y cuenta contra los 10 s del pit | medición ad hoc, sin script; **sin verificar** en el robot |

## 6. Errores propios y correcciones

Se listan porque cada uno cambió una decisión o una cifra.

| Qué pasó | Corrección |
|---|---|
| Afirmé que ningún repositorio previo hizo un pick and place físico; el zip del Reto 1 mostraba videos reales | Corregido en el análisis: la ausencia vale solo para el repositorio del Gran Reto |
| Atribuí el aborto de las pruebas AprilTag a "crear el detector" | Es `tag25h9` dentro de la prueba parametrizada; con `tag36h11` no ocurre |
| El ejecutor perdía hasta `v·0.05` m por segmento (duraciones medidas con reloj absoluto) | Cada segmento se mide desde su primer envío y el último paso se escala |
| La rampa del ejecutor no actuaba en el primer envío; con `asentamiento_s = 0` quedaba el último valor fraccionado | Corregido; ahora siempre cierra con ceros |
| El criterio de convergencia del ajuste de focal (`k` a 1e-6) era más estricto que el ruido numérico del detector | Tolerancia de 0.1 % |
| Mis imágenes sintéticas tenían un error de convención de píxel (0.5 px): parecía que la calibración con damero funcionaba mal | Corregido en ambos renderizadores; se recalcularon todas las cifras documentadas |
| La tolerancia de 1 px de la validación del damero aceptaba ignorar una distorsión de `k1 = −0.3` (0.89 px) | 0.7 px |
| El damero por defecto (25 mm) medía 300×225 mm y no cabía en una hoja A4 | 20 mm (240×180 mm) |
| La estación fallaba E2 con el tope por defecto de 8 s | No era un error: es el hallazgo 11; las pruebas pasan `tiempo_max_s` donde no importa |
| Un test del estimador esperaba el valor nominal, pero con lo nominal converge a otra cosa | Prueba reescrita; el comportamiento es el hallazgo 3 |
| Menores: el ejecutor de pruebas usaba `-t .` y rompía el descubrimiento; la tolerancia exacta de 4 cm fallaba por ruido de coma flotante (se añadió 1e-9); una prueba del JetCobot marcaba `is_power_on` como `power_on`; la expresión del segundo giro del acople; el port del HTML registraba el reintento después de actualizar | Corregidos y cubiertos por pruebas |

## 7. Verificación

```bash
bash scripts/preparar_entorno.sh --vision          # una vez (--pc-race para Race Control)
bash scripts/ejecutar_pruebas.sh                   # "TODO OK" si pasan
```

| Carpeta | Pruebas | Cubre |
|---|---|---|
| `tests/roscar_v01` | 68 | v0.1, registro, análisis, diagnóstico con `--simular`, conversión cámara → dock y scripts del acople (el modo `ensayo` con `rclpy` sustituto) |
| `tests/integracion` | 20 | mensajes y `mqtt.yaml` contra el contrato del docente (necesita `pydantic`) |
| `tests/geometria_dock` | 6 | transformaciones 2D |
| `tests/estacion` | 38 | estrategia, compensación, poses, configuración |
| `tests/jetcobot_v01` | 11 | diagnóstico y cronómetro |
| `tests/carrito` | 418 | docks, planificador, equivalencia con el HTML, ejecutor, estimadores, configuración, cámara → dock, reset, nodos con `rclpy` sustituto, acople, calibración por tramo, máquina de la misión y su adaptador |
| `tests/evidencia` | 63 | registro experimental y verificador de evidencia (MP4, rosbag2, CSV, cobertura) |
| `tests/comun` | 15 | cargador YAML estricto |
| `tests/vision` | 152 | AprilTag sintético, calibración con regla y con damero, medición con `medir_tag` (≈ 45 s; se omiten si falta OpenCV) |
| **Total propias** | **791** | |

Además, las del docente: `pc-race` (126, en el entorno con `--pc-race`) y la herramienta AprilTag (24 con `-k "not tag25h9 and not tag16h5"`).

**Sin verificar en este repositorio:**
- Cualquier cosa que use `rclpy`, ROS 2 o un robot (`diagnostico_roscar.recolectar`, `prueba_movimiento.py`).
- Un broker MQTT real, y el usuario y la contraseña del curso.
- Python en la Jetson (el código de estación e integración evita sintaxis nueva y apunta a 3.8; solo se probó en 3.13) y PyYAML allí.
- La cámara real, el OpenCV del Pi 5 y de la Jetson, y un damero impreso.
- `pymycobot` y el brazo.

## 8. Supuestos y decisiones abiertas

| Tema | Supuesto actual | Dónde |
|---|---|---|
| Puerto del brazo `BrazoJetCobot` | `mover_coords`, `abrir_pinza`, `cerrar_pinza`, `soltar_torque` | `estacion/src/app_equipo/puerto.py` |
| Marco del dock | origen en el centro, x en el rumbo de llegada, y a la izquierda; falta `dock_frames.yaml` | `estacion.yaml`, `docks.py` |
| Montaje | cuna a 11 cm a la derecha del centro del carrito; brazo a 29 cm; alcance 14–22 cm | `estacion.yaml` |
| `pieza_dejo` | la pieza que queda en la cuna (`None` en E4) | `estacion/README.md` |
| Protecciones del estimador | [0.5, 1.5], paso 0.05, tramo ≥ 10 cm, giro 20°–150°: son nuestras, el HTML no fija números | `carrito/README.md` |
| Pausa y asentamiento | 0.30 s y 0.50 s: placeholders | `movimiento.yaml` |
| Escalas iniciales | 1.0 = sin caracterizar | `calibracion.yaml` |
| Perfil de velocidad | 0.10 m/s y 0.50 rad/s | `movimiento.yaml` |
| Usuario MQTT | `carrito08` | `mqtt.yaml` |

Preguntas para el docente que siguen abiertas (`referencia_del_reto.md` §15 las lista): firma exacta de `BrazoJetCobot`, `dock_frames.yaml`, si `solicitud` y `resultado` llevan identificadores, qué cuenta el presupuesto de 10 s (giro de salida, segunda medición), qué es "error después del pit", cómo se cuentan las paradas ya dentro de tolerancia en el criterio de 70 %, si se puede cerrar el giro con IMU u odometría, y si `cd` y `ca` pueden iniciarse con valores calibrados.

## 9. Trazabilidad con la división v1.3

| Sección | Cobertura |
|---|---|
| 1.1 Diagnóstico del ROSCar | Herramientas listas (`diagnostico_roscar`, `preflight`, registro, análisis, procedimiento). **Pendiente:** correrlas en el robot |
| 1.2 Planificación y ejecución | Planificador y ejecutor hechos (simulados). **Pendiente:** adaptador ROS 2, medir pausa y asentamiento |
| 1.3 Visión y localización | Medición del tag, calibración de cámara, conversión cámara → dock y reset de pose hechos (simulados). **Pendiente:** medir el montaje de la cámara y probar con ROS real el nodo de cámara y el del TF `map → odom` (escritos, **sin probar con ROS**) |
| 1.4 Acople y calibración adaptativa | Acople fino, calibración por tramo y estimadores `cd`/`ca` hechos (simulados; ensayo con el robot preparado, sin ejecutar). La máquina de estados del pit está hecha y simulada (`mision.md`); **pendiente** probarla con ROS y el curso |
| 1.5 Autonomía y seguridad | Condiciones de aborto del ejecutor y seguridad de la misión (autorización, bandera, enlace, intercambio, plazos; simulada). **Pendiente:** verificar `twist_mux`, la parada física y las interfaces reales del curso |
| 1.6 Tablero web y registro | Eventos, métricas, verificador de evidencia, registro experimental y panel prototipo (simulado). **Pendiente:** integrar con el tablero base y el `grabador` reales |
| 2.1 Diagnóstico del JetCobot | Scripts listos (sin brazo) |
| 2.2 Cinemática / 2.3 Manipulación | Sin iniciar (el brazo se simula) |
| 2.4 Compensación de la cuna | Hecha con marcos supuestos |
| 2.5 Estrategia de cambio / 2.6 Seguridad | Hechas y simuladas; falla cerrada |
| 3.1 Arquitectura y contrato | Configuración MQTT y mensajes verificados contra el docente |
| 3.2 Simulación y pruebas independientes | Entorno, 497 pruebas, modelo del HTML |
| 3.3 Integración del pit / 3.4 de la carrera | Sin iniciar (existe el tiempo ideal de una vuelta) |
| 3.5 Experimentación y predicción | Herramientas listas (modelo del HTML, barridos). **Pendiente:** predicción firmada con parámetros medidos |
| 3.6 Evidencias / 3.7 Carrera | Plantillas; sin evidencia real |
| 6.1 / 6.2 Convenciones y Git | Bitácora (`bitacora_laboratorio.md`); una sola rama, sin PR |

## 10. Qué sigue

**Con robot (día 3):**
1. `preflight.sh` y `diagnostico_roscar.py`; no seguir si hay FALLA.
2. Caracterización de rectas y giros (`prueba_movimiento.py`, `registrar_medicion.py`, `analizar_movimientos.py`) con las limitaciones de seguridad de su README. Sembrar `calibracion.yaml` con lo medido.
3. Medir `pausa_s`, `asentamiento_s` y el *timeout* de `twist_mux`.
4. Calibrar la cámara con regla y validar con el tag a los lados; si falla, damero. Después, `medir_tag.py comparar` con regla y transportador en decenas de puntos y `resumen`.
5. JetCobot: `diagnostico_jetcobot.py` y `cronometro_ciclo.py`; confirmar la API de `BrazoJetCobot`; ensayar el tiempo de E2.
6. Anotar todo en `docs/bitacora_laboratorio.md`, también lo que falle.

**Sin robot, por prioridad:**
1. Adaptador ROS 2 del ejecutor (Twist, `/odom`, reloj) y de `diagnostico_roscar`.
2. Máquina de estados del pit (medir → acoplar → solicitar → esperar resultado → medir → reset → recalibrar, con reintentos): usa lo ya hecho.
3. Probar con ROS real (y con el simulador RC-1) los nodos `camara_apriltag_node.py`, `tag_emulado.py` y `nodo_reset_pose.py`.
4. Prueba de integración contra `pc-race` con un Mosquitto real.
5. Fusionar *waypoints* de la estación una vez medidos los tiempos reales.
6. Predicción firmada con el modelo del HTML y los parámetros medidos.

## 11. Convenciones
- Unidades internas SI (m, rad, s). El contrato MQTT usa grados en `dth`; la estrategia usa mm y grados para las poses del brazo.
- Código del carrito: Python 3.10 o superior. Estación, integración y `comun`: apuntan a 3.8.
- Los archivos `config/` son semillas versionadas y editadas a mano: ningún programa escribe en ellas. Los resultados de calibración van a la carpeta del experimento.
- Todo valor medido se anota en la bitácora con su fuente; no se copian escalas ni poses de otro día o robot.
- Una prueba simulada no demuestra precisión, tiempo ni seguridad física.
