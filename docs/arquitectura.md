# Arquitectura del código del equipo

Cómo está organizado lo que se construyó y cómo encaja con la arquitectura del curso (`vendor/granprix/docs/arquitectura/00`–`04`, que **manda** sobre el HTML). Lo que es del curso no se reescribe aquí. Estado de cada pieza en [`desarrollo_realizado.md`](desarrollo_realizado.md).

## 1. Principios de diseño

1. **Núcleo puro, adaptadores aparte.** La lógica (planificador, ejecutor, estimadores, estrategia, cargadores) es Python sin ROS, sin red y sin hardware. ROS, MQTT y el brazo se conectan a través de interfaces pequeñas. Así casi todo se prueba en una PC sin robots, y lo que depende del hardware queda aislado y explícito.
2. **Dependencias inyectadas.** El ejecutor recibe el reloj y una `Salida`; la estrategia recibe el `brazo` y su reloj; la captura de cámara recibe la cámara. Ninguna prueba espera tiempo real.
3. **Falla cerrada.** Sin configuración, la estación no se mueve (`NO_CONFIGURADO`). Un YAML con una clave desconocida, un valor fuera de límites o un secreto no se carga. Una validación que no puede medir devuelve `None`, no una conjetura.
4. **Una configuración no puede aflojar el reto.** Los límites de velocidad, tolerancia y tiempo están en el cargador, no solo en el YAML.
5. **Una sola fuente de verdad por dato**, igual que el curso: el estado de la carrera es de Race Control, la pose del carrito es del carrito, el estado del brazo es de la estación.
6. **Unidades SI** dentro del código (m, rad, s); grados y milímetros solo donde el contrato o el brazo lo exigen, y cada módulo lo dice.

## 2. Vista de máquinas (según el curso)

```
                     +-------------------------------+
                     |  PC Race Control (curso)      |
                     |  pc-race, ledger, tablero     |
                     +---------------+---------------+
                                     | MQTT (Mosquitto 192.168.50.10:1883)
         +---------------------------+---------------------------+
         |                           |                           |
 +-------+---------+        +--------+--------+         +--------+--------+
 | Pi5 del ROSCar  |        | Jetson E1..E4   |         |   otros equipos |
 | 192.168.50.108  |        | .21 .. .24      |         |                 |
 | ROS 2 LOCAL     |        |  supervisor     |         +-----------------+
 | (DOMAIN_ID=8,   |        |  (curso)        |
 |  LOCALHOST=1)   |        |  app_equipo     |
 +-----------------+        |  (equipo)       |
                            |  BrazoJetCobot  |
                            |  (curso)        |
                            +-----------------+
```
Entre máquinas solo hay MQTT, HTTP y SSH. ROS 2 vive dentro del Pi5. `twist_mux` arbitra el mando de ruedas y el vigilante de red del curso tiene prioridad máxima (manda cero si no hay broker por 1.5 s).

## 3. Quién es dueño de qué y qué hay hecho

### Carrito (Pi5)
| Nodo del curso | Dueño | Nuestra pieza | Estado |
|---|---|---|---|
| `control_odometria` | Equipo | `carrito/granprix_carrito/`: `planificador`, `ejecutor`, `calibracion` | Lógica **simulada**. No es un nodo ROS aún |
| `camara_apriltag` | Equipo (base del curso) | `vision/` (medición, calibración, corrector de distorsión) | Medición (`vision/medicion.py`, `scripts/camara/medir_tag.py`), calibración y corrección de distorsión **simuladas**. Falta el nodo y `/tag/pose` |
| `maquina_pit` | Equipo | usa `planificar_acople`, `acople_valido`, `EstimadorEscalas`, `evaluar_reduccion` | **Pendiente** la máquina de estados |
| `puente_mqtt`, `vigilante_red`, `tablero_web`, `grabador` | Curso | `integracion/` solo describe la conexión y los tópicos | Sin verificar con un broker real |
| `placa_micro_ros` | Yahboom | `scripts/roscar_v01/` la diagnostica (solo lectura) | Sin verificar en el robot |

### Estación (Jetson)
| Componente del curso | Dueño | Nuestra pieza | Estado |
|---|---|---|---|
| `supervisor_estacion` | Curso | — | No publicado |
| `app_equipo` (`EstrategiaDeCambio.cambiar(pose, pieza_trae)`) | Equipo | `estacion/src/app_equipo/` (`EstrategiaCambio`) | **Simulada**; firma compatible, puerto del brazo **supuesto** |
| `BrazoJetCobot` (puerto) | Curso | `puerto.py` lo define como `Protocol` supuesto; `brazo_simulado.py` lo implementa | Supuesto |

## 4. Paquetes Python y sus dependencias

Extraído de los `import` reales (solo dependencias internas; `A -> B` = A importa de B):

```
geometria_dock        (sin dependencias)           transformaciones 2D compartidas
comun                 (sin dependencias)           yaml_estricto

carrito.granprix_carrito
  docks            -> geometria_dock
  planificador     -> docks, geometria_dock
  ejecutor         -> planificador
  calibracion      -> planificador, comun, geometria_dock
  configuracion    -> calibracion, ejecutor, planificador, comun
  marcos           -> docks, comun, geometria_dock       (cámara -> dock; cargar_marcos)
  reset_pose       -> geometria_dock                     (map -> odom)

app_equipo (estacion/src)
  puerto           (sin dependencias)
  roles            -> puerto
  compensacion_pose-> puerto, geometria_dock
  posiciones       -> roles, comun (solo al leer .yaml)
  estrategia       -> compensacion_pose, posiciones, puerto, roles
  brazo_simulado   -> puerto
  configuracion    -> compensacion_pose, posiciones, comun, geometria_dock

integracion.mqtt_config -> comun

vision
  herramienta           -> vendor/granprix/estacion/herramientas (sin modificar)
  calibracion_focal     -> comun            (matemática pura y archivo YAML; no necesita OpenCV)
  calibrar              -> herramienta, calibracion_focal
  calibracion_damero    -> herramienta, calibracion_focal
  medicion              -> herramienta, calibracion_focal      (CamaraTag, agregar, FiltroMediana, evidencia)

simulacion
  modelo_granprix       -> carrito.docks, carrito.planificador, geometria_dock
  lente                 (sin dependencias)
  apriltag_sintetico    -> vision.herramienta, lente
  damero_sintetico      -> vision.calibracion_damero, lente
```
No hay ciclos. Los paquetes que se despliegan en la Jetson (`app_equipo`, `geometria_dock`, `comun`) no dependen de OpenCV ni del carrito; esa independencia es deliberada. Python: carrito 3.10 o superior; estación, integración y `comun` apuntan a 3.8 (probado solo en 3.13).

## 5. Flujo de un tramo (lo implementado)

```
pose creída ──► planificar_tramo ──► Tramo(phi, L)
                                        │
escalas (cd, ca) ──────────────► comandar ──► Comando(phi_cmd, L_cmd, v, w, t_giro, t_avance)
                                        │            phi_cmd = phi/ca,  L_cmd = L/cd
                                        ▼
reloj ──► EjecutorMovimiento.paso() cada ~50 ms ──► Salida.publicar(v, w) ──► [Twist en twist_mux] ──► robot
          giro → pausa en ceros → avance → asentamiento en ceros
          aborta con ceros: parada externa, odometría perdida, hueco de tiempo, reloj, error de salida
                                        │
                      comando_efectivo (lo realmente enviado)
                                        ▼
pose medida al salir + pose medida al llegar (antes de acoplar)
                                        ▼
                       EstimadorEscalas.observar ──► nuevas escalas ──► (siguiente tramo)
```
Lo que sigue **sin conectar**: la `Salida` real (publicador de Twist), la odometría (`odom_ok`), el reloj ROS y la medición de poses con el tag. Son los adaptadores del §7.

## 6. Flujo del pit (previsto; la máquina de estados está pendiente)

Orden del curso: medir → acoplar → solicitar → esperar resultado → medir otra vez → reset de pose y recalibración → salir (objetivo ≤ 10 s, acople ≤ 4 cm y ≤ 6°, máximo 2 reintentos).

| Paso | Función existente | Falta |
|---|---|---|
| medir la pose | `vision.medicion.CamaraTag.medir` y `agregar` (o `scripts/camara/medir_tag.py`), y `marcos.desde_medicion` (o `pose_dock.py`) | nodo de cámara y `/tag/pose`; montaje medido; marco del dock del docente |
| ¿está dentro de tolerancia? | `acople_valido`, `error_acople` | — |
| corregir | `planificar_acople` + `EjecutorMovimiento` | orquestarlo con reintentos |
| solicitud / resultado | constructores de `scripts/roscar_v01/mensajes_contrato.py`, tópicos de `mqtt.yaml` | publicarlos vía `puente_mqtt` |
| reset de pose | `marcos.pose_robot` y `ResetPose` (ver `marcos_y_reset_pose.md`) | medir el montaje de la cámara; publicar el TF `map → odom` |
| recalibrar | `EstimadorEscalas.observar` | alimentarlo con la pose previa al acople |

El estimador necesita la pose medida **antes** de cualquier acople, y el comando **realmente enviado**: de otro modo converge a un valor sesgado.

## 7. Adaptadores pendientes (aquí se conecta lo demás)
1. **Ejecutor → ROS 2:** una `Salida` que publique `Twist` en la entrada autorizada de `twist_mux`, un `odom_ok()` basado en `/odom`, un temporizador a 20 Hz que llame a `paso()`, y comprobar el *timeout* de `twist_mux`.
2. **Cámara → ROS 2:** un nodo que use `CamaraTag` (corrige la distorsión, filtra por calidad y agrega cuadros) y publique `/tag/pose`.
3. **Pit → MQTT:** publicar `solicitud` y `evento` y leer `resultado` y `turno` con los tópicos de `mqtt.yaml`, a través de `puente_mqtt` (del curso).
4. **Brazo:** implementar `BrazoJetCobot` según la firma que publique el docente y ajustar `puerto.py`.
5. **TF `map → odom`:** un publicador que use `ResetPose.map_odom` y lea `/odom` con su marca de tiempo (ver `marcos_y_reset_pose.md`).
6. **Diagnóstico:** `diagnostico_roscar.recolectar` y `prueba_movimiento.py` ya usan `rclpy` y nunca se ejecutaron.

## 8. Decisiones de diseño que conviene no deshacer
- **`comandado` es lo enviado, no lo nominal** (hay una prueba que lo documenta con números).
- **Los archivos `config/` son semillas a mano.** Los programas guardan su estado en la carpeta del experimento.
- **Un detector AprilTag por proceso:** la librería nativa corrompe memoria al mezclar familias.
- **`vendor/granprix` no se edita.** Si cambia el contrato, falla una prueba (`tests/integracion`) en lugar de divergir en silencio.
- **Las protecciones del estimador y los placeholders del ejecutor son nuestros**, no del curso: deben revisarse con datos medidos.

## 9. Estado seguro
Ningún script de este repositorio mueve un robot por defecto. El diagnóstico del JetCobot es de solo lectura (una prueba lo exige) y `prueba_movimiento.py` solo calcula salvo `--ejecutar --zona-segura`. El ejecutor termina siempre con ceros. Aun así, **si el proceso muere nadie envía el cero**: la protección real es el *timeout* de `twist_mux` y un medio de corte físico (ver `scripts/roscar_v01/README.md`).
