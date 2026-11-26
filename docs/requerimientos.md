# Requisitos y su cobertura

Cada requisito indica su fuente, qué parte del código lo cubre, qué prueba lo comprueba y en qué estado está. Las fuentes son el HTML del reto, el repositorio del docente (`vendor/granprix`, que **manda**), la referencia del reto (**Ref.** = [`referencia_del_reto.md`](referencia_del_reto.md), el detalle que estaba en el README inicial; secciones 6, 7, 8, 13 y 15) y la división del equipo v1.3. Una prueba que pasa en simulación **no** demuestra que el requisito se cumpla en el robot: por eso hay una columna de estado separada.

**Estados:** *Verificado* = lógica con pruebas automáticas que pasan · *Simulado* = solo contra un modelo, una cámara o un brazo sintéticos · *Configurado* = existe como dato pero ningún programa lo usa todavía · *Pendiente* = no existe · *Abierto* = falta definición del docente.

## 1. Reglas de la carrera y del pit

| ID | Requisito | Fuente | Cobertura | Prueba | Estado |
|---|---|---|---|---|---|
| RQ-01 | Cuatro vueltas consecutivas en 12 min como máximo | Ref. §7 | `planificador.tiempo_vuelta`: 116.57 s por vuelta con pit de 6 s, 466.27 s las cuatro, sin aceleración ni reintentos | `tests/carrito/test_planificador.py` | Simulado (cota ideal) |
| RQ-02 | Pit ≤ 10 s, desde que el carrito frena hasta que arranca | Ref. §7 | `estacion.yaml: tiempo_max_s` (8 s, propio, ≤ 10 s por el cargador); `scripts/jetcobot_v01/cronometro_ciclo.py` | `tests/estacion/test_configuracion.py` | **Pendiente medir.** Con duraciones de ejemplo E2/E3 tardan 15.4 s |
| RQ-03 | Tolerancia de posición ≤ 4 cm | Ref. §7 | `planificador.acople_valido`; `estrategia`; el cargador rechaza tolerancias mayores | `test_planificador.py`, `tests/estacion/` | Verificado (lógica) |
| RQ-04 | Tolerancia angular ≤ 6° (ambas a la vez) | Ref. §7 | idem | idem | Verificado (lógica) |
| RQ-05 | Máximo 2 reintentos automáticos de acople por parada | Ref. §7, doc. 03 | `acople.acoplar` (`1 + reintentos` correcciones; el cargador y `ConfigAcople` rechazan más de 2) | `test_acople.py` | Simulado. **Abierto:** si los 2 reintentos incluyen la primera corrección |
| RQ-06 | Velocidad ≤ 0.20 m/s y ≤ 0.8 rad/s | Ref. §7 | `comandar`, `EjecutorMovimiento.iniciar` y el recorte de `_publicar`; el cargador de `movimiento.yaml` | `test_ejecutor.py`, `test_planificador.py`, `test_configuracion.py` | Verificado (lógica) |
| RQ-07 | Referencia de velocidad 0.10 m/s y 0.5 rad/s | Ref. §7 | `movimiento.yaml` y `V_REF`/`W_REF` | `test_configuracion.py` (YAML = código) | Verificado |
| RQ-08 | Docks D1 (0.40, 0.40, −90°), D2 (2.40, 0.40, 0°), D3 (2.40, 2.40, +90°), D4 (0.40, 2.40, 180°) | HTML / Ref. §6 | `docks.DOCKS_HTML` | `test_docks.py` | Verificado |
| RQ-09 | Giro `φ = wrap(atan2(dy, dx) − θ)`, distancia `L = hypot(dx, dy)`, ejecución en lazo abierto como `φ/ca` y `L/cd` | Ref. §8 | `planificar_tramo`, `comandar` | `test_planificador.py`; `test_equivalencia_html.py` (18 casos, 288 llegadas, 1e-9 contra el JavaScript original) | Verificado |
| RQ-10 | Estimador `escala_nueva = escala + α·(medido/comandado − escala)`, α = 0.35 de referencia, paso limitado | Ref. §8 | `actualizar_escalas`, `EstimadorEscalas` | `test_calibracion.py`, `test_equivalencia_html.py` | Simulado. Las protecciones numéricas son del equipo |
| RQ-11 | Error posterior menor que el anterior en ≥ 70 % de las paradas | Ref. §13 (Pit) | `evaluar_reduccion` y `CalibradorTramo.evaluacion` (error normalizado propio) | `test_calibracion.py`, `test_calibracion_tramo.py` | Verificado (cálculo). **Abierto:** cómo cuentan las paradas ya dentro de tolerancia |
| RQ-12 | Escalas convergentes | Ref. §13 (Pit) | `EstimadorEscalas.convergio()` (4 actualizaciones, diferencia < 0.01) | `test_calibracion.py` | Simulado. Umbral provisional |
| RQ-13 | Orden del pit: medir → acoplar → solicitar → resultado → medir → reset → recalibrar | Ref. §8, doc. 03 | `maquina_pit.py` (secuencia de estados fijada por una prueba) | `test_maquina_pit.py` | Simulado de punta a punta (4 vueltas). **Falta** probarlo con ROS, el curso y el robot |
| RQ-14 | Reset de pose (`map → odom`) con la pose medida | Ref. §8 | `transformacion_camara_dock.py` (cámara → dock) y `ResetPose` | `test_transformacion_camara_dock.py`, `test_reset_pose.py`, `test_gestor_reset.py`, `test_marcos_imagen.py`, `test_nodo_reset_pose.py`, `test_tag_emulado.py` | Simulado. El nodo ROS 2 se probó solo con un sustituto de `rclpy`. **Falta** medir el montaje de la cámara y probarlo con ROS real |
| RQ-15 | Cada parada guarda el error antes y después | Ref. §8 | `CalibradorTramo.cerrar_parada` y `exportar_paradas` (error normalizado, reintentos, escalas); `EstimadorEscalas.exportar_csv` (razones) | `test_calibracion_tramo.py`, `test_calibracion.py` | Parcial: faltan el tiempo de pit y la pieza (máquina de estados) |

## 2. Comunicación y contrato

| ID | Requisito | Fuente | Cobertura | Prueba | Estado |
|---|---|---|---|---|---|
| RQ-16 | Mensajes MQTT v1 (`v`, `ts`, `equipo`, `dock`, `pose{dx, dy, dth}`...) con metros y **grados** en `dth` | doc. 00 | `scripts/roscar_v01/mensajes_contrato.py` | `tests/integracion/test_contrato_carrito.py` contra los modelos `pydantic` del docente | Verificado. Sin broker real |
| RQ-17 | Tópicos, QoS, retenidos y quién publica | doc. 00 | `integracion/configuracion/mqtt.yaml` | `test_mqtt_config.py` (contra el módulo y la tabla del docente) | Verificado. Sin broker real |
| RQ-18 | Telemetría de hasta 5 Hz | doc. 00 | tope en `mqtt.yaml` (el cargador rechaza más) | `test_mqtt_config.py` | **Configurado**: nadie publica telemetría aún |
| RQ-19 | Race Control marca OFFLINE tras 3 s sin telemetría | `monitor_latidos.py` del docente | `mqtt.yaml: offline_tras_s` | `test_mqtt_config.py` | **Configurado**; no hay latido implementado |
| RQ-20 | ROS 2 local: `ROS_DOMAIN_ID=8`, `ROS_LOCALHOST_ONLY=1`; entre máquinas solo MQTT | doc. 00 y 03 | avisos en `preflight.sh` y `diagnostico_roscar.py` | `tests/roscar_v01/test_diagnostico_roscar.py` (con `--simular`) | Verificado en el script; sin robot |
| RQ-21 | Ningún secreto en el repositorio; la contraseña MQTT va en `GRANPRIX_MQTT_CLAVE` | doc. 00 | `comun/yaml_estricto.py` rechaza claves con aspecto de secreto; `.gitignore` | `tests/comun`, `test_mqtt_config.py` | Verificado |
| RQ-22 | El curso posee `puente_mqtt`, `vigilante_red`, `grabador`: no se reescriben | doc. 03 | no se copian ni se reescriben | — | Cumplido por omisión |

## 3. Visión

| ID | Requisito | Fuente | Cobertura | Prueba | Estado |
|---|---|---|---|---|---|
| RQ-23 | AprilTag `tag36h11` de 6 cm; pose medida por el carrito en el marco del dock | Ref. §8, doc. 03 | `vision/herramienta.py` y `vision/medicion.py` (`medir_tag.py`, `nodos/camara_apriltag_node.py`) sobre la herramienta del docente; `simulacion/apriltag_sintetico.py` | `test_apriltag_sintetico.py`, `test_medicion.py`, `test_camara_apriltag_node.py` | Simulado. **Falta** el marco del dock (`dock_frames.yaml`) y probar el nodo de cámara con ROS real |
| RQ-24 | Precisión de la pose suficiente para decidir con margen una tolerancia de 4 cm y 6° | división §1.3 | calibración de cámara con regla y con damero; barridos de precisión | `tests/vision/` | Simulado. Hallazgo: con un campo de visión supuesto 6 % mal, `z` falla 2 cm. **Pendiente** medir con la cámara real |
| RQ-25 | No hay falsas aceptaciones: ante dos tags, otro id, poca calidad o inestabilidad no se entrega pose | división §1.3 | `CamaraTag.medir` y `agregar`: la medición no válida lleva el motivo (`sin_tag`, `otro_id`, `varios_tags`, `hamming`, `margen_bajo`, `inestable_*`...) y **sin pose** | `test_medicion.py`, `test_apriltag_sintetico.py` | Verificado (lógica). Umbrales de margen, hamming y dispersión **provisionales** |
| RQ-26 | Corregir la distorsión del lente si la hay | división §1.3 | `Corrector`, `pose_tag_calibrada`, `calibrar_damero.py` | `test_calibracion_damero.py` | Simulado |

## 4. Estación

| ID | Requisito | Fuente | Cobertura | Prueba | Estado |
|---|---|---|---|---|---|
| RQ-27 | `EstrategiaDeCambio.cambiar(pose, pieza_trae)` devuelve `ResultadoCambio` (`ok`, `pieza_dejo`, `t_cambio`, `error`) y solo usa el objeto `brazo` | doc. 02 | `estacion/src/app_equipo/estrategia.py` | `tests/estacion/test_estacion.py` | Simulado. Puerto del brazo **supuesto** |
| RQ-28 | Falla cerrada: sin poses enseñadas no se mueve nada | división §2.6 | `NO_CONFIGURADO`; `posiciones` sin valores por defecto | `test_estacion.py` | Verificado |
| RQ-29 | Validar antes de mover: pieza, tolerancia, alcance, bandeja | división §2.5 | `PIEZA_INESPERADA`, `FUERA_DE_TOLERANCIA`, `FUERA_DE_ALCANCE`, `BANDEJA_AGOTADA` | `test_estacion.py` | Verificado (lógica) |
| RQ-30 | Un fallo detiene la secuencia y termina en una pose libre | división §2.6 | `estrategia.py` | `test_estacion.py` | Verificado (lógica) |
| RQ-31 | Roles E1 a E4 (carga A / A→B / B→C / descarga C) | HTML | `roles.py` | `test_estacion.py` | Verificado (lógica). Bandeja de 4 piezas: **supuesto** |
| RQ-32 | Diagnóstico del brazo de solo lectura | división §2.1 | `diagnostico_jetcobot.py` | `tests/jetcobot_v01/` (el archivo no contiene órdenes de movimiento, pinza ni apagado) | Verificado; **nunca contra un brazo** |
| RQ-33 | Compensación de la pose de la cuna | división §2.4 | `compensacion_pose.py` | `test_estacion.py` | Simulado. Marcos supuestos |

## 5. Seguridad y autonomía

| ID | Requisito | Fuente | Cobertura | Prueba | Estado |
|---|---|---|---|---|---|
| RQ-34 | Parar con ceros ante parada externa, odometría perdida, retraso del temporizador, reloj anómalo o error de salida | división §1.5 | `EjecutorMovimiento` | `test_ejecutor.py` | Simulado |
| RQ-35 | Parar el robot si el nodo muere | división §1.5 | **no lo puede cubrir el ejecutor**; depende del *timeout* de `twist_mux` | — | **Pendiente verificar** en el robot |
| RQ-36 | No aplicar parámetros de otro robot | división §1.1 | `EstimadorEscalas.cargar(robot_esperado)`; `diagnostico_roscar` identifica la calibración activa | `test_calibracion.py`, `test_diagnostico_roscar.py` | Verificado |
| RQ-44 | No hay movimiento sin turno autorizado, con bandera roja, sin enlace o durante un intercambio; toda velocidad pasa por una puerta | división §1.5 | `Seguridad`, `SalidaSegura`, ceros en estados quietos | `test_maquina_pit.py` (21 mutaciones del código detectadas) | Simulado. No sustituye al vigilante del curso ni a la parada física |
| RQ-45 | Plazo en cada estado y falla segura ante errores internos | división §1.5 | `_plazo`, `_fallar`, `FALLA` terminal hasta `reiniciar()` | `test_maquina_pit.py` | Simulado. Plazos provisionales |
| RQ-46 | Cuatro vueltas, piezas A→B→C y 16 pits; vuelta válida con sus cuatro paradas | Ref. §7 | `mision.py`, `mision.yaml` | `test_mision.py`, `test_maquina_pit.py` | Simulado |
| RQ-37 | Ningún programa mueve un robot sin pedirlo explícitamente | — | diagnósticos de solo lectura; `prueba_movimiento.py` calcula salvo `--ejecutar --zona-segura` | `tests/roscar_v01`, `tests/jetcobot_v01` | Verificado en los scripts |

## 6. Evidencia, entrega y reproducibilidad

| ID | Requisito | Fuente | Cobertura | Estado |
|---|---|---|---|---|
| RQ-38 | Evidencia por vuelta: video, bag completo, cinco CSV; sin bags vacíos | Ref. §13 | `evidencia/verificar_evidencias.py` comprueba video, rosbag2 y CSV del `grabador`; `eventos.jsonl`, `pits.csv`, `paradas.csv` y `tramos.csv` salen de nuestra lógica | `tests/evidencia/` | Verificador simulado. **Falta** el layout y los tópicos reales del `grabador`; no se generan `sensores.csv`, `vueltas.csv`, `intervenciones.csv` ni `mensajes.csv` |
| RQ-39 | Predicción firmada con la pestaña Simulador | Ref. §13 | `simulacion/modelo_granprix.py` (port verificado) y `barrido_alpha.py` | Herramientas listas; **falta la predicción** con parámetros medidos |
| RQ-40 | Tablero web con todos los bloques | Ref. §13 | `tablero/panel.*` (Cronometraje, Estaciones, Carrito, Banderas e intervenciones; Control solo con `?api=`) | `test_metricas.py` (contrato datos–panel) | Prototipo de solo lectura. **Falta** integrarlo al tablero base, video en vivo y el E-stop real |
| RQ-47 | Registro de las pruebas de laboratorio, incluidas las fallidas, sin poder editarse en silencio | división §8 | `evidencia/registro_experimental.py` (cadena de hashes, adjuntos con SHA-256) | `test_registro_experimental.py` | Simulado. No detecta borrar las últimas líneas |
| RQ-41 | Bitácora por sesión de laboratorio | división §8.1 | `docs/bitacora_laboratorio.md` (plantilla) | Plantilla lista, sin entradas |
| RQ-42 | Reproducibilidad: un comando prepara el entorno y otro corre las pruebas | división §3.2 | `scripts/preparar_entorno.sh`, `scripts/ejecutar_pruebas.sh` | Verificado (Linux, Python 3.13) |
| RQ-43 | Código de la Jetson compatible con su Python | doc. 02 | `estacion`, `integracion`, `comun` evitan sintaxis nueva (apuntan a 3.8) | **Sin verificar** en la Jetson |

## 7. Lo que no depende de nosotros
Quedan abiertas con el docente (Ref. §15): firma exacta de `BrazoJetCobot`, `dock_frames.yaml`, identificadores en `solicitud`/`resultado`, qué cuenta el presupuesto de 10 s (giro de salida, segunda medición), qué es "error después del pit", cómo se cuentan las paradas ya dentro de tolerancia en RQ-11, si se puede cerrar el giro con IMU u odometría, y si `cd` y `ca` pueden iniciarse con valores calibrados.
