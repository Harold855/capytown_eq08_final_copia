# GranPrix Delivery Semiautónomo — Contexto de división y desarrollo del reto final

**Proyecto:** CapyTown · Robótica · Grupo 8 (eq08)  
**Fecha prevista de presentación:** 7 de diciembre de 2026  
**Versión del documento:** 1.2 — 24 de noviembre de 2026 (adaptada al repositorio del docente `codeplai/GranPrix`, commit `285c829`; cambios en la sección 12)  
**Estado:** planificación y desarrollo inicial; no acredita pruebas realizadas.  
**Repositorio experimental ROSCar:** [capytown_eq08_final_copia](https://github.com/Harold855/capytown_eq08_final_copia/tree/main). Los documentos nuevos están en la rama `claude/compassionate-goldberg-konorb` hasta que se integren a `main`.  
**Repositorio de integración del equipo:** `capytown_eq08_final`.

## 0. Propósito, fuentes y metodología

Este documento establece la organización interna del Grupo 8 para desarrollar el reto, asignar responsabilidades, identificar archivos, registrar avances y comprobar los requisitos oficiales. Complementa `README.md`, `contexto.md` y `contexto_reto_final.md`; no sustituye el HTML del docente.

**Fuentes y precedencia (v1.2):** (1) lo que el docente indique por escrito; (2) su repositorio `codeplai/GranPrix`, que según el docente **manda** sobre el HTML en lo que programa cada parte; (3) `GranPrix Delivery Semiautónomo.html`, pestañas Reto (secciones oficiales 1–12) y Simulador, que sigue siendo la referencia para las reglas de carrera, las intervenciones, la rúbrica (a confirmar) y la predicción firmada. El documento original no divide el trabajo en partes A–F ni en los tres bloques de este plan. La numeración que sigue es una propuesta interna. Las denominaciones de módulos, pruebas, rutas y metas intermedias son propuestas y podrán adaptarse a las plantillas del curso. El contrato, el guardián y los docks oficiales no se modifican: cualquier cambio requiere el procedimiento del docente.

**Actualización del montaje comunicada por el docente al equipo:** la base del circuito será de cartón y estará ligeramente elevada para facilitar la manipulación de cubos. La altura exacta, el soporte, las uniones, los bordes, las alturas de cámara/tag/cuna y la geometría respecto a las mesas aún deben comprobarse. Las dimensiones nominales del HTML se conservan como referencia, no como confirmación del montaje actualizado.

**Riesgo del montaje elevado (propuesto, por confirmar con el docente):** el tablero de la mesa del brazo deja 14 cm libres sobre el piso y el ROSCar mide 12.4 cm con antena y LiDAR. Si la base de cartón sube más de ≈1.6 cm y las mesas no suben lo mismo, el carrito no entra bajo la mesa. Medir la elevación real y confirmar si las mesas se elevan igual antes de fijar cualquier altura de cuna, cámara o tag.

### 0.1. Organización adoptada

| Bloque | Secciones | Responsable principal |
|---|---|---|
| 1. ROSCar | 1.1–1.6 (6) | Subgrupo carrito. **1.6 (tablero y registro)** lo lleva el responsable de integración y evidencias; su código vive en `carrito/` porque corre en el Pi5 |
| 2. JetCobot | 2.1–2.6 (6) | Subgrupo estación |
| 3. Integración del sistema | 3.1–3.7 (7) | Coordinador y ambos subgrupos |

**19 secciones en total.** La numeración es identificativa, no un orden de ejecución obligatorio. La integración comienza desde el inicio, con interfaces y contrapartes simuladas; no espera a que ambos robots estén terminados. Se respetan dependencias de datos y seguridad para cerrar las pruebas, no una secuencia rígida para escribir código.

Con cinco integrantes (v1.2, con el alcance que deja el repositorio del docente, ver 0.5):

| Rol | Trabajo | Secciones |
|---|---|---|
| A. Control del carrito | `control_odometria`: ruta, `cd` y `ca`, reset de pose, protección de `/cmd_vel` ante la caída de nuestro nodo | 1.1, 1.2, 1.5 |
| B. Visión y acople | `camara_apriltag` y `maquina_pit`: tag, pose en el dock, acople fino, solicitud y reintentos | 1.3, 1.4 |
| C. Estrategia de cambio, roles E1 y E4 | `EstrategiaDeCambio`, compensación de la pose, brazo simulado | 2.1–2.4 |
| D. Estrategia de cambio, roles E2 y E3 | Doble intercambio dentro del pit y pruebas de tiempo con el brazo real | 2.3, 2.5 |
| E. Integración y evidencias | `pc-race` local, contrato, extensión del tablero, registros y evidencias | 3.1–3.6, 1.6 |

3.3 y 3.4 son de todos, con un responsable designado por día para la prueba física. 3.5 (predicción) lo lleva A con apoyo de B; 3.7 lo lleva E con todos. La estación casi no tiene infraestructura que escribir (la hace el curso), pero sí exige tiempo con un brazo compartido: por eso C y D la reparten por rol y por hardware. Con cuatro: A y B siguen separados, C y D se funden en una persona y E se divide entre ambos pares con un coordinador designado, **sin dejar sin dueño la seguridad ni la evidencia**. Cada responsable necesita un suplente: en la defensa se sortea un video y puede explicarlo cualquiera. Es posible trabajar en horarios distintos si el laboratorio lo autoriza; cada turno registra versión, cambios, pruebas, fallos, siguiente acción y estado seguro del hardware. Un único responsable controla cada robot durante una prueba física.

### 0.2. Estados y criterios de cierre

| Estado | Significado |
|---|---|
| Pendiente | No iniciado o sin evidencia. |
| En desarrollo | Trabajo de diseño o implementación iniciado. |
| Implementado | Código o documento disponible, aún no validado. |
| Pruebas parciales | Pruebas unitarias, simuladas o físicas parciales con evidencia identificada. |
| Validado | Se satisfacen los criterios aplicables con evidencia revisada y versión reproducible. |

Registrar los bloqueos como atributo adicional, no como sustituto del estado. Una prueba simulada no demuestra precisión, tiempo ni seguridad física. Una sección documental puede cerrarse sin hardware si no depende de mediciones reales. No asignar puntos de rúbrica por la mera existencia de archivos. Toda prueba debe indicar si es unitaria, simulada, física o integrada.

## 0.3. Requisitos transversales del HTML

- 10 equipos, un ROSCar por equipo, cuatro JetCobot compartidos; un equipo en pista a la vez. Cada equipo programa el carrito y un único programa de estación con cuatro roles.
- Circuito nominal antihorario de 2 m por lado, zona 2,8 × 2,8 m; D1=(0,4;0,4), D2=(2,4;0,4), D3=(2,4;2,4), D4=(0,4;2,4) en metros. Orientaciones nominales de llegada: −90°, 0°, 90°, 180°. Confirmar `dock_frames.yaml` oficial.
- E1 carga A roja; E2 retira A y coloca B verde; E3 retira B y coloca C azul; E4 retira C; retorno vacío a E1. Cuatro vueltas, cuatro paradas por vuelta (16 en una tanda completa). Cubos de 25 mm y hasta 30 g.
- AprilTag 36h11 de 6 cm, ID 1–4; enfoque nominal a unos 28 cm. Acople válido: error de posición ≤4 cm y angular ≤6°. Hasta dos reintentos automáticos; si se agotan, FALLA.
- Límites del ROSCar: 0,20 m/s y 0,8 rad/s. Referencia inicial del reto: 0,10 m/s y 0,5 rad/s. La navegación principal es giro y avance en lazo abierto con compensación de escalas; el acople fino es proporcional con el tag. Odometría visual en rectas es opcional.
- Pit máximo 10 s desde frenado hasta arranque, no solamente duración del Pick & Place. Tanda máxima 12 min; calentamiento 3 min; cambio y despliegue 3 min. Al menos tres vueltas válidas para clasificar. Objetivo de ingeniería: cuatro vueltas válidas sin intervenciones.
- ROS 2 local en cada máquina (`ROS_DOMAIN_ID=8`, `ROS_LOCALHOST_ONLY=1` para eq08); entre máquinas, MQTT. Tablero HTTP y reloj NTP. Watchdog de pérdida del broker de 1,5 s y parada ante bandera roja.
- El equipo con turno es el único que puede solicitar operaciones a estaciones. Race Control administra turno, banderas, reloj, registro y ranking. No transmitir comandos ROS 2 distribuidos entre robots.
- Evidencias oficiales en el Pi5: cinco CSV, bag de toda la tanda, video por vuelta; entregar repositorio etiquetado, predicción firmada, informe de dos páginas y defensa.

## 0.4. Prioridades y recortes (v1.2)

Las 19 secciones suman unas 130 subtareas, y con el repositorio del docente varias pasan a ser del curso (ver 0.5). La nota y el ranking dependen de completar vueltas válidas.

| Nivel | Qué incluye | Criterio |
|---|---|---|
| **P0 — cadena crítica de la vuelta válida** | 1.1 (versión mínima), 1.2, 1.3, 1.4, 1.5 (lo que es nuestro), 2.1, 2.3, 2.4, 2.5 (la estrategia), 3.1 (cumplir el contrato), 3.3 | Sin esto no hay una vuelta válida |
| **P1 — puntos que no dependen de la pista** | 1.6 (extensión del tablero), 3.5, 3.6, 3.7 | Tablero, evidencia, predicción, informe y defensa |
| **P2 — solo si hay margen** | Simulador ROS 2 adaptado, 10 rectas y 10 giros, odometría visual (bono +1), pulido visual del tablero | No afecta a la rúbrica base |

Recortes adoptados:
- 1.1: **5 corridas por tipo**, no 10.
- 3.2: se usa `pc-race` con su simulador de carritos; el simulador ROS 2 de RC-1 queda en P2.
- 1.6: primero los bloques de la sección oficial 8 con datos reales; la estética al final.
- Odometría visual solo si el día 8 ya hay una vuelta limpia.
- 2.2 y 2.6: reducidas a lo que exponga el puerto `BrazoJetCobot` y el supervisor del curso (ver sus bloques de alcance).

**Puerta del pit (fecha fija):** al final del día 3 debe estar medido el ciclo de E2 en el brazo real. Con el supervisor del curso, medirlo con él en cuanto exista. Si no cabe en los 10 s totales, avisar al docente **ese día**.

## 0.5. Qué cambia con el repositorio del docente (v1.2)

Estado del repositorio `codeplai/GranPrix` (commit `285c829`, 24-nov): **parcial**. Tiene Race Control (`pc-race/`, 126 pruebas pasan), la herramienta AprilTag y los documentos de arquitectura. **No existen todavía:** código del carrito, `supervisor_estacion`, `plantilla_equipo`, el puerto `BrazoJetCobot`, `dock_frames.yaml`, el guardián, `deploy` ni el validador de evidencia. Tampoco aparece el nombre `granprix-esan`: confirmar con el docente si es el mismo proyecto antes de añadirlo como submódulo `vendor/granprix`.

| Parte | HTML original | Repositorio del docente (manda) | Efecto en este plan |
|---|---|---|---|
| Programa de la estación | Un solo programa del equipo: MQTT, turno, worker único, guardián, IK y MoveIt2 | `supervisor_estacion` (curso) valida y congela el brazo. El equipo escribe solo `EstrategiaDeCambio.cambiar(pose, pieza_trae)` sobre un puerto `BrazoJetCobot` | 2.5 y 2.6 se reducen; 2.2 depende del puerto |
| Carrito | El equipo programa puente, vigilante, tablero y registro | Curso: `puente_mqtt`, `vigilante_red` (con `twist_mux`), `tablero_web` (el equipo extiende) y `grabador`. Equipo: `control_odometria`, `camara_apriltag`, `maquina_pit` | 1.5, 1.6 y parte de 3.1 se reducen |
| Despliegue | `deploy.sh` y `git pull` del tag | Race Control copia por SSH la carpeta del equipo a las estaciones; opción B pendiente | 2.6.5, 2.6.6 y 3.7.3 |
| Banco de pruebas | Lo construye el equipo | `pc-race` y `simulador_carritos.py` | 3.2 |
| `solicitud` | equipo, vuelta, id, pose | equipo, dock, pose, pieza_trae. **Sin `id` ni `vuelta`** | Hay que tolerar duplicados QoS 1 |
| `resultado` | id, ok, piezas, tiempo de pit | equipo, ok, `pieza_dejo`, `t_cambio`. Sin id y sin motivo | `t_cambio` no es el tiempo de pit |
| Estados de la estación | libre, acoplando, intercambiando, falla | `LIBRE`, `ESPERANDO`, `CAMBIANDO`, `LISTA`, `OFFLINE` | Adaptar el tablero |
| Banderas | verde, amarilla, roja, cuadros | Solo verde y roja | Amarilla y cuadros son locales del tablero |
| Unidades de la pose | dx, dy, dθ | `dx`, `dy` en m y `dth` en **grados** | Conversión solo en el borde MQTT |

**Sigue vigente del HTML** (salvo que el docente diga otra cosa): el circuito y las reglas de la carrera, el pit de 10 s con acople ≤ 4 cm y ≤ 6° y 2 reintentos, los límites de velocidad, el conteo de intervenciones y el ranking, el estimador de escalas y el reset de pose, la predicción firmada con el simulador, el informe, la defensa y el bono de odometría visual.

**Riesgos nuevos que trae el contrato real:**
1. Sin `id`, Race Control empareja `solicitud` y `resultado` por equipo y estación; un duplicado QoS 1 puede pasar inadvertido.
2. La validez de una vuelta depende de nuestro mensaje `vuelta`: los 4 pits `ok` deben caer entre su `t_inicio` y `t_fin`.
3. El carrito pasa a `OFFLINE` tras 3 s sin telemetría: debe seguir publicando durante el pit y el acople.
4. Todo lo que el curso aún no publica es una dependencia: se avanza con lógica pura y pruebas contra `pc-race`.
5. El brazo **no usa cámara** (decisión D3 del repositorio): la compensación depende por completo de la pose que reporta el carrito.

# Bloque 1 — Desarrollo del ROSCar

**Objetivo:** disponer de un carrito que navegue, mida su pose, corrija errores, se recalibre, coordine intercambios y registre su misión. Referencia oficial: secciones 2–4, 7–9.

## 1.1. Diagnóstico y caracterización del ROSCar

> **Alcance v1.2:** sin cambios, es del equipo. Añadir al diagnóstico la versión de ROS 2 de la imagen del Pi5 y confirmar qué nodos del curso (`puente_mqtt`, `vigilante_red`, `grabador`) estarán en el robot cuando salga la plantilla.

**Actividades**

- 1.1.1 Preparar el repositorio y entorno ROS 2; comprobar distribución, agente microROS, workspace, dominio y método de acceso autorizado.
- 1.1.2 Inventariar nodos, tópicos, tipos, QoS, frecuencia y publicadores/suscriptores. Identificar los marcos TF y el driver de movimiento.
- 1.1.3 Comprobar encoders, IMU, cámara, LiDAR, batería y actuación. Verificar parada segura antes de mover.
- 1.1.4 Revisar la odometría instalada y parámetros de ruedas. No aplicar automáticamente parámetros históricos a un robot distinto. Evitar duplicar correctores o confundir corrección odométrica con escalas de mando.
- 1.1.5 Realizar rectas: primero desplazamientos pequeños en zona despejada; después 2 m a velocidad de referencia, si las condiciones son seguras.
- 1.1.6 Realizar giros: primero ángulos pequeños; después 90° en ambos sentidos cuando proceda. Medir giro físico y odométrico.
- 1.1.7 Repetir caracterización sobre la plataforma real de cartón; comprobar estabilidad, fricción, uniones, bordes y holguras. Las pruebas en otro piso son preliminares.
- 1.1.8 (v1.1) Fabricar y montar la cuna cónica y la ménsula en el ROSCar; fijar la cámara y el tag a la altura de trabajo y **medir y declarar la altura real de la cuna** (9–12 cm). Sin la cuna montada no se pueden probar E1–E4 con el carrito real. Responsable: A, con C para el alcance.

**Orden de trabajo (v1.1):** antes de 1.1.5 y 1.1.6 debe existir la versión mínima de 1.3.4–1.3.5 con la precisión del tag medida (1.3.8). Se usa **el tag como instrumento de medición** del giro y de la recta, con cinta como verificación. En RC-1 el transportador aportó una dispersión de ±3.5° que impidió separar el error del robot del error de medición.

**Desarrollo:** recuperar utilidades de RC-0 y RC-1; utilizar `scripts/roscar_v01/preflight.sh` y los ensayos iniciales del ZIP v0.1 si ya fueron incorporados. Comandos de diagnóstico: `ros2 node list`, `ros2 topic list -t`, `ros2 topic info /cmd_vel -v`, `ros2 topic hz /odom`, `ros2 param dump /odom_corrector` (solo si existe). No cambiar la configuración del agente activo sin verificar compatibilidad. Registrar muestras físicas independientes de la odometría; proponer 5 rectas y 5 giros por condición (10 de cada uno es P2; el HTML no exige cantidad). Medir el giro por tiempo, con `/odom` y con IMU para decidir el tipo de ejecutor. Calcular sesgo, dispersión, error lateral y retardo; identificar condiciones de ensayo. Confirmar el tipo del tópico de batería: en retos previos existió `/battery`, no asumir que ya existe `/battery_state`.

**Archivos:** `diagnostico.py`, `odom_utils.py`, `preflight.sh`, `prueba_recta.py`, `prueba_giro.py`, `wheel_params_g8.yaml` si corresponde al robot verificado. **Resultados:** `diagnostico_roscar.md`, `rectas.csv`, `giros.csv`, `caracterizacion.yaml`, bags y gráficos en `experimentos/bloque_01_roscar/1.1/`.

**Sin robot:** scripts, cálculos y plantillas. **Dependencias para cerrar:** ROSCar asignado, superficie final, medición física. **Cierre:** hardware y parada verificados, datos reproducibles y parámetros medidos con incertidumbre identificada.

## 1.2. Planificación y ejecución de movimiento

> **Alcance v1.2:** vive en `control_odometria` (equipo). Nuestro ejecutor publica en una entrada de `twist_mux`; el `vigilante_red` del curso tiene prioridad máxima vía `/cmd_vel_vigilante`. Ya no somos "el único publicador final de `/cmd_vel`": lo es `twist_mux`, y debemos configurar el timeout de nuestra entrada y comprobar en el robot que al vencer sale cero.

- 1.2.1 Cargar coordenadas y orientaciones de docks desde configuración, reemplazable por la oficial.
- 1.2.2 Calcular el tramo desde la pose creída: `dx = x_dock - x`, `dy = y_dock - y`, `L = hypot(dx, dy)`.
- 1.2.3 Calcular `phi = wrap(atan2(dy, dx) - theta)`; normalizar ángulos y tratar destinos coincidentes sin giro arbitrario.
- 1.2.4 Ejecutar giros en lazo abierto con `phi_cmd = phi/ca`.
- 1.2.5 Ejecutar avances en lazo abierto con `L_cmd = L/cd`.
- 1.2.6 Aplicar escalas positivas, finitas y verificadas, límites de velocidad y temporización monotónica; registrar comandos realmente ejecutados.
- 1.2.7 Validar trayectorias, signos de giro, tiempos y parada.

**Desarrollo:** separar matemáticas puras de ROS 2. Probar el cálculo de los cuatro tramos nominales, poses perturbadas, ángulos cercanos a ±π y entradas inválidas. Implementar el ejecutor con duración y publicación periódica, pero con el vigilante como único publicador final de `/cmd_vel`; abortar ante fallos, sin depender de un PID de RC-1 para la navegación principal. Validar en el simulador RC-1 antes de pruebas físicas autorizadas. No habilitar movimiento real por defecto.

**Archivos:** `planificador.py`, `ejecutor.py`, `odom_utils.py`, `movimiento.yaml`, `test_planificador.py`, `test_ejecutor.py`. **Resultados:** trayectorias, CSV de órdenes y tiempos, errores de llegada, pruebas unitarias y bags. **Sin robot:** casi toda la lógica y simulación. **Cierre:** tramo simulado y físico repetible, con compensación correcta y límites respetados. Depende de 1.1 y 1.5 para ensayos físicos; de 1.3–1.4 para el funcionamiento adaptativo.

## 1.3. Visión artificial y localización

> **Alcance v1.2:** `camara_apriltag` es del equipo con una base del curso. Punto de partida: `estacion/herramientas/herramienta_apriltag.py` (usa `pupil-apriltags`; su pose es respecto a la cámara y `dth` en grados). **Falta probarla con cámara real** (lo dice el propio repositorio). El paso al marco del dock depende de `dock_frames.yaml`, que aún no existe. Salida prevista: `/tag/pose` (`geometry_msgs/PoseStamped`). El módulo compartido de transformaciones sigue siendo útil, porque la estrategia de la estación compone la pose recibida con la geometría del brazo.

- 1.3.1 Captura de imágenes con propietario único de la cámara, marcas de tiempo y distribución de cuadros al detector y grabador.
- 1.3.2 Calibración intrínseca (matriz K y distorsión) de la cámara real.
- 1.3.3 Calibración extrínseca cámara–base del ROSCar; fijar orientación del soporte si es móvil.
- 1.3.4 Detectar AprilTags auténticos de familia 36h11, IDs 1–4, lado 0,06 m.
- 1.3.5 Estimar pose con `solvePnP`, verificar correspondencia de esquinas, profundidad positiva y error de reproyección; rechazar mediciones inválidas u obsoletas.
- 1.3.6 Convertir la pose al marco del dock para obtener `(dx, dy, dtheta)` en m y rad, usando el convenio oficial.
- 1.3.7 Implementar reset `map → odom` según REP-105 sin reiniciar arbitrariamente `odom → base`.
- 1.3.8 (v1.1) **Medir la precisión de la pose del tag a ≈28 cm contra cinta** (posición y ángulo, varias poses e iluminaciones) y publicar el resultado. Es el instrumento de medición de 1.1 y 1.4; B lo entrega primero.

**Desarrollo:** empezar con imágenes sintéticas, tags válidos impresos y cámara de laptop; utilizar parámetros sintéticos únicamente para pruebas. Verificar transformaciones con poses conocidas. Con convención `T_A_B` que transforma coordenadas de B a A, `T_map_odom = T_map_base_medido @ inv(T_odom_base)` para el mismo instante. Identificar el marco base real (`base_link` o `base_footprint`) y el publicador de TF para evitar duplicidades. En laboratorio medir con la cámara final, validar enfoque a ~28 cm y repetir con distintas poses e iluminaciones. No usar `/sim/pose` como si fuera un tag real: es una medición emulada en simulación.

**Archivos:** `camara.py`, `vision_tag.py`, `reset_pose.py`, `camara.yaml`, tests de visión y transformaciones. Las transformaciones **no se duplican**: viven en el módulo compartido `granprix_comun/transformaciones.py` (ver 6), con la convención de signos acordada con C en 2.4. **Resultados:** calibración de cámara, imágenes anotadas, CSV de error visual, TF y `/pit/medicion`. **Cierre:** ID y pose comprobados contra referencias físicas; precisión suficiente para decidir tolerancia con margen, sin falsas aceptaciones conocidas en el conjunto de prueba. Dependencia: geometría final y contrato de marcos (3.1).

## 1.4. Acople fino y calibración adaptativa

> **Alcance v1.2:** es nuestro. El repositorio asigna el acople, la solicitud y el reset a `maquina_pit`, y las escalas `cd` y `ca` a `control_odometria`. Secuencia del repositorio: medir, corregir hasta ≤ 4 cm y 6°, publicar la solicitud, esperar el resultado, **medir otra vez**, reset y recalibración, salir. Preguntar si esa segunda medición cuenta como "error después del pit" y si entra en los 10 s.

- 1.4.1 Evaluar `hypot(dx, dy) ≤ 0.04` y `abs(wrap(dtheta)) ≤ 6°`.
- 1.4.2 Diseñar control proporcional de acople realizable por tracción diferencial (giros y avances, no movimiento lateral directo); comprobar zona libre y límites.
- 1.4.3 Medir nuevamente después de cada corrección, hasta dos reintentos; si no converge o vence el plazo, detener y marcar FALLA.
- 1.4.4 Estimar escala de distancia `cd = distancia_medida / distancia_comandada`.
- 1.4.5 Estimar escala de giro `ca = giro_medido / giro_comandado`, con signos y ángulos coherentes.
- 1.4.6 Actualizar cada escala por filtro exponencial `c_nueva = c_anterior + alpha*(c_medida - c_anterior)`; limitar variaciones y rechazar observaciones sin movimiento suficiente o inválidas.
- 1.4.7 Evaluar convergencia, ruido, número de reintentos y reducción del error antes/después.

**Desarrollo:** guardar pose visual de salida del pit anterior, pose previa al reacople actual y movimientos comandados por separado; estimar el tramo anterior sin mezclar las correcciones del acople. No actualizar la escala de giro con comandos casi nulos ni aplicar doble compensación al driver. Probar α=0,35 como referencia inicial del HTML, no como ajuste definitivo. Probar errores de posición, ángulo, tag ausente, dos reintentos fallidos y escalas anómalas. Medir antes y después con el mismo criterio; no introducir correcciones innecesarias solo para mejorar una métrica.

**Archivos:** `acople_fino.py`, `calibracion.py`, `calibracion.yaml`, `test_calibracion.py`, `test_acople.py`. **Resultados:** `/pit/calibracion`, errores antes/después, escalas por pit, reintentos y gráficos. **Cierre:** acople físico válido, reset comprobado (1.3), estimador estable y evidencia de mejora; la evaluación oficial exige reducción del error en ≥70 % de paradas y convergencia. Consultar al docente cómo se contabilizan paradas ya dentro de tolerancia. Depende de 1.2, 1.3 y 1.5 para cierre integrado.

## 1.5. Autonomía y seguridad

> **Alcance v1.2:** **del curso:** `puente_mqtt` y `vigilante_red` (parada si se pierde el broker 1,5 s, bandera roja). **Nuestro:** la máquina de estados (`maquina_pit` y la lógica de misión), la protección de `/cmd_vel` ante la caída de nuestro nodo (el firmware conserva la última orden), los plazos de cada estado y el pit de 10 s. Las subtareas 1.5.5 y 1.5.6 se limitan a integrarnos con el vigilante del curso y a probar que frena (apagar el broker en plena vuelta).

- 1.5.1 Máquina de estados: NAVEGANDO, ACOPLANDO, ESPERANDO, INTERCAMBIO, SALIENDO y FALLA; añadir espera inicial y fin si conviene.
- 1.5.2 Gestión de vuelta, sector y estación; cuatro servicios por vuelta y retorno vacío tras E4.
- 1.5.3 Inventario lógico de pieza; actualizar solo ante resultado válido y correlacionado.
- 1.5.4 Plazos de estados, pit global de 10 s, tanda máxima de 12 min y finalización.
- 1.5.5 Vigilante independiente: pérdida de broker durante 1,5 s, bandera roja, órdenes caducadas, estado incompatible y fallos.
- 1.5.6 E-stop siempre accesible y parada segura; sin reanudación inesperada tras reconexión.
- 1.5.7 Gestión de fallos, duplicados, resultados incorrectos, reinicios y registro de intervenciones.

**Desarrollo:** implementar transiciones testeables con reloj inyectable. Empezar con resultados de estación ficticios. Separar órdenes de navegación/acople de la salida final a motores; un solo nodo autorizado publica `/cmd_vel` y exige frescura. Durante manipulación mantener velocidad cero. No salir ante timeout o resultado incierto; coordinar estado seguro con estación. Verificar parada física en zona segura antes de ensayar navegación, y estudiar watchdog de bajo nivel autorizado: un nodo ROS no protege por sí solo ante caída total del Pi5 o firmware que conserva el último comando.

**Archivos:** `maquina_estados.py`, `mision.py`, `vigilante.py`, `mqtt_bridge.py`, tests de FSM y seguridad. **Resultados:** trazas de transiciones, matriz de fallos, tiempos de parada, eventos. **Cierre:** transiciones y fallos ensayados, parada física comprobada y ningún arranque sin autorización. Contrato común en 3.1; el adaptador ROSCar reside aquí, sin duplicar lógica de interfaz en integración.

## 1.6. Tablero web y registro local

> **Alcance v1.2:** el curso entrega `tablero_web` (Iniciar, reiniciar, declarar intervención por `/granprix/orden`) y `grabador` (video por vuelta, rosbag2 y CSV de eventos de pit). **Nuestro:** extender el tablero hasta cubrir los bloques de la sección oficial 8 y verificar que el `grabador` produce lo que exige la sección 9 (cinco CSV, bag con los tópicos pedidos, video 640×480 a 15 fps). Hasta que el curso publique esos nodos, 1.6.6 y 1.6.7 quedan en espera: **no construir un grabador propio** sin confirmar.

**Responsable (v1.1):** E (integración y evidencias). **Prioridad P1.** Primero los seis bloques de la sección oficial 8 con datos reales; la estética al final.

- 1.6.1 Servidor HTTP en Pi5, puerto 8080; URL prevista `http://192.168.50.108:8080`.
- 1.6.2 Controles Iniciar (solo con turno), Reset carrito, Reiniciar vuelta y E-stop rojo siempre visible; acciones conectadas a la FSM, no a motores directamente.
- 1.6.3 Telemetría: pieza, cd/ca, v/ω, batería, latencia y video en vivo solo para equipo autorizado.
- 1.6.4 Cronómetro, vuelta n/4, última/mejor vuelta, delta, tiempos de cuatro sectores y colores morado/verde/amarillo; estados de E1–E4, reintentos, tiempos de pit y errores antes/después; banderas de carrera.
- 1.6.5 Contador y bitácora de intervenciones con hora, tipo y origen; publicación de evento.
- 1.6.6 Generar los cinco CSV y grabar bag completo; verificar mensajes reales, no solo existencia del archivo.
- 1.6.7 Grabar video por vuelta con número y tiempo superpuestos, mínimo 640×480 a 15 fps; almacenar en Pi5, sin difundir video indiscriminadamente.

**Desarrollo:** comenzar con telemetría simulada claramente marcada; interfaz actualizada ≥2 Hz. Implementar backend local (tecnología libre; por ejemplo FastAPI o Flask) y frontend; MQTT de telemetría ≤5 Hz. Registrar timestamps sincronizados, usar reloj monotónico para duraciones. Adaptar batería real al tópico `/battery_state` requerido sin inventar unidades. Evitar que grabación o web bloqueen percepción y control. Validar espacio de disco, rendimiento y cierre de archivos.

**Archivos:** `web_server.py`, `registro.py`, `grabador_video.py`, `battery_adapter.py`, `web/index.html`, `web/css/estilos.css`, `web/js/dashboard.js`. **Resultados:** capturas, tests de permisos/controles, CSV y bags de prueba, videos simulados o reales identificados. **Cierre:** todos los bloques de la sección oficial 8 funcionan, frecuencia comprobada y registros completos. La verificación final de entrega pertenece a 3.6.

# Bloque 2 — Desarrollo del JetCobot

**Objetivo:** un programa de estación parametrizable en cuatro roles, seguro, capaz de compensar la pose de la cuna y realizar intercambios. No se requieren cuatro programas independientes. Referencia oficial: secciones 2–4, 7, 10–11.

## 2.1. Diagnóstico y caracterización del JetCobot

> **Alcance v1.2:** sin cambios en lo que hay que medir. El acceso a las Jetson durante el desarrollo sigue sin definir; en la carrera, Race Control las despliega por SSH.

- 2.1.1 Acceder a Jetson por el método autorizado; inventariar entorno y versiones.
- 2.1.2 Comprobar API, driver y comunicaciones, inicialmente de solo lectura.
- 2.1.3 Leer articulaciones y coordenadas reales; no asumir HOME ni articulaciones a cero.
- 2.1.4 Verificar pinza, apertura/cierre y capacidad de detectar agarre.
- 2.1.5 Identificar límites del guardián y restricciones del fabricante.
- 2.1.6 Inspeccionar espacio de trabajo, fijaciones, plataforma de cartón y alcance de la cuna.
- 2.1.7 (v1.1) Confirmar con el docente **cuántas horas y qué ventanas de acceso a los brazos** tiene el equipo antes de la tanda, y el método de acceso a las Jetson. De esto depende el ritmo de todo el bloque 2.

**Desarrollo:** reutilizar rutinas de diagnóstico del Reto 1, no copiar posiciones históricas como seguras. Confirmar modelo y hardware de cada brazo. Ensayar movimiento solo bajo control autorizado y guardián correspondiente. **Archivos:** `diagnostico.py`, `preflight_jetcobot.sh`, `estacion.yaml`. **Resultados:** inventario, lecturas iniciales, fotos del montaje y tabla de alcance. **Cierre:** hardware y pinza operativos con límites conocidos; dimensiones reales verificadas.

## 2.2. Cinemática y planificación de movimientos

> **Alcance v1.2:** el equipo **no habla con el brazo directamente**: usa solo el objeto `brazo` (puerto `BrazoJetCobot`: mover, abrir y cerrar la pinza, soltar torque), cuya firma aún no existe. Si `mover` es cartesiano vía firmware, el "IK y MoveIt2" del HTML deja de aplicar y esta sección se reduce a calcular poses y trayectorias seguras. **Pregunta de mayor impacto:** qué expone `mover`. Mientras tanto, trabajar con un `brazo_simulado` propio y con `send_coords` en el brazo real solo para medir.

- 2.2.1 Revisar parámetros DH y unidades.
- 2.2.2 Contrastar URDF con el brazo real y sus marcos.
- 2.2.3 Recuperar cinemática directa y validar posiciones.
- 2.2.4 Implementar cinemática inversa con límites, detección de soluciones no válidas y singularidades.
- 2.2.5 Integrar MoveIt2 con el modelo, planificación y guardián oficiales.
- 2.2.6 Validar trayectorias libres de colisiones, puntos de aproximación y retirada.

**Corrección v1.1:** ningún antecedente tiene cinemática inversa propia. El Reto 2 solo tiene FK (su ítem 4 audita la IK del firmware vía `send_coords`); el Gran Reto tiene FK en tres versiones (DH, URDF, PoE) y un envoltorio de MoveIt2 probado solo con dobles. Los antecedentes traen problemas conocidos: sesgo de ≈5.9 mm entre la FK y `get_coords()`, 46.7 mm entre DH y URDF, dos tablas DH distintas (`d5` 75.05 y 75.55) y 23 de 93 pruebas rotas. **Tratar 2.2 como la sección más incierta del bloque**, no como reutilización. El día 1 preguntar si `granprix-esan` entrega el modelo y la configuración de MoveIt2; si es así, el trabajo es integrarlos, no escribir la IK desde cero.

**Desarrollo:** reutilizar solo como punto de partida la FK y el modelo del Gran Reto JetCobot, comprobando consistencia entre DH, URDF y API y corrigiendo los problemas de arriba antes de depender de ellos. Usar m/rad internamente y convertir a mm/grados exclusivamente donde la API lo requiera. Comparar FK e IK en poses alcanzables, incluyendo extremos del espacio de la cuna. Probar primero en simulación. El HTML exige cinemática inversa y MoveIt2; no sustituirlos unilateralmente por coordenadas fijas o control directo del actuador.

**Archivos:** `cinematica.py`, `integration_moveit.py`, `posiciones.py`, tests FK/IK y trayectorias. **Resultados:** tablas de errores, gráficos, configuración MoveIt2 y poses verificadas. **Cierre:** soluciones y trayectorias correctas en el área de trabajo real, con guardián y límites respetados.

## 2.3. Manipulación de piezas

> **Alcance v1.2:** es el centro del trabajo de la estación. Se programa dentro de `EstrategiaDeCambio`, y su resultado (`ok`, `pieza_dejo`, `t_cambio`, `error`) lo publica el supervisor. E2 y E3 hacen retirar y colocar en un mismo pit; el pit total son 10 s, incluida la latencia del supervisor y del contrato.

- 2.3.1 Calibrar apertura y cierre de pinza para cubos de 25 mm.
- 2.3.2 Diseñar Pick & Place: aproximar, agarrar, elevar, trasladar, depositar y retirar de forma segura.
- 2.3.3 Confirmar agarre y liberación por señales disponibles y verificación experimental; no devolver éxito si falló la operación.
- 2.3.4 Calibrar posiciones de almacenes y bandejas de recepción, índices de piezas por vuelta y zonas de retirada.
- 2.3.5 Cronometrar carga, descarga y doble intercambio de E2/E3.
- 2.3.6 Optimizar trayectorias dentro de límites autorizados, no incrementar velocidad para eludir el guardián.

**Desarrollo:** reutilizar secuencias parametrizables del Reto 1 y Gran Reto Parcial; introducir resultados estructurados, fallos y timeout. Probar cada fase primero con objetivos conocidos; luego el ciclo completo. E2 y E3 son críticos porque retiran una pieza y colocan otra. Medir desde las fases iniciales: el pit global es 10 s, no hay 10 s exclusivos para el brazo. Si el presupuesto resulta inviable, informar al docente antes de asumir que se pueden cambiar límites o geometría.

**Archivos:** `pick_and_place.py`, `control_pinza.py`, `almacenes.yaml`, `manipulacion.yaml`. **Resultados:** `tiempos_manipulacion.csv`, videos experimentales, tasa de éxito y fallos. **Cierre:** carga/descarga/intercambio repetibles y confirmados, con retirada segura de la zona de paso; tiempo compatible con el presupuesto medido de 3.3.

## 2.4. Compensación de pose de la cuna

> **Alcance v1.2:** la estrategia recibe `PoseDock` (`dx`, `dy` en m y `dth` en grados, ya en el marco del dock). La compensación y el offset de la cuna se componen dentro de la estrategia. El brazo no usa cámara (decisión D3): no hay segunda verificación visual. Falta la transformación dock–brazo (`dock_frames.yaml`).

- 2.4.1 Definir marcos base del brazo, dock, base ROSCar y cuna.
- 2.4.2 Obtener transformación dock–brazo del archivo oficial.
- 2.4.3 Medir transformación ROSCar–cuna considerando ménsula derecha y altura declarada.
- 2.4.4 Convertir `(dx, dy, dtheta)` a pose de recogida/depósito compensada.
- 2.4.5 Verificar límites de alcance, altura, aproximación y colisiones.
- 2.4.6 Probar posiciones nominales y extremos admitidos, con ROSCar real o plantilla física equivalente autorizada.

**Desarrollo:** adoptar el convenio `T_B_C = T_B_D @ T_D_R @ T_R_C`, siendo B base del brazo, D dock, R ROSCar y C cuna. Acordar signos con 1.3 y 3.1; comprobar transformaciones con casos sintéticos y extremos de ±4 cm/±6°. El montaje de cartón cambia potencialmente la altura relativa: no confiar solo en cotas nominales. Si la pose está fuera de tolerancia o alcance, no iniciar manipulación.

**Archivos:** `compensacion_pose.py`, `test_compensacion.py`, configuración de cuna. Importa `granprix_comun/transformaciones.py` (módulo único compartido con 1.3; B y C acuerdan la convención de signos y escriben las pruebas con **los mismos casos** para ambos lados). Un signo distinto entre el carrito y el brazo hace que el brazo corrija en sentido contrario. **Resultados:** matriz de casos, errores de compensación, fotos y tiempos. **Cierre:** depósito y recogida seguros y correctos en el rango operativo medido. Depende de geometría y marcos definitivos; se puede iniciar con poses ficticias.

## 2.5. Programa único de estación

> **Alcance v1.2 (reducida):** `supervisor_estacion` (curso) se encarga de MQTT, turno, validación de la solicitud (estación en `ESPERANDO`, equipo con turno, pose en tolerancia, sin bandera roja), estados `LIBRE`/`ESPERANDO`/`CAMBIANDO`/`LISTA`/`OFFLINE` y del congelado del brazo. **2.5.6, 2.5.7 y 2.5.8 pasan al curso.** Nuestro: 2.5.1 a 2.5.5, es decir, la estrategia para los roles E1 a E4. Preguntar cómo recibe la estrategia su rol y la ranura de la bandeja, porque la firma `cambiar(pose, pieza_trae)` no incluye el dock ni la vuelta.

- 2.5.1 Parametrizar rol E1–E4 e identidad de equipo autorizado.
- 2.5.2 E1 carga A; 2.5.3 E2 retira A y carga B; 2.5.4 E3 retira B y carga C; 2.5.5 E4 descarga C.
- 2.5.6 Validar turno, estación, solicitud, pose y disponibilidad antes de operar.
- 2.5.7 Publicar estado (`libre`, `acoplando`, `intercambiando`, `falla`) y resultado correlacionado conforme al contrato.
- 2.5.8 Worker único y deduplicación por ID; impedir doble manipulación ante retransmisión QoS 1, controlar simultaneidad y reconciliar resultados inciertos.

**Desarrollo:** una sola implementación, diferencias de rol en configuración. Utilizar el cliente MQTT de prueba de 3.2 antes de recibir un carrito real. Ensayar secuencia de cuatro vueltas e índices de bandeja; validar que la pieza entrante/saliente es la esperada. Mantener un registro de solicitudes procesadas para no repetir un movimiento por duplicados; un reinicio no debe causar repetición automática de una acción física de resultado desconocido. Publicar éxito solo al concluir y dejar libre la zona del carrito.

**Archivos:** `station_worker.py`, `validar_turno.py`, `idempotencia.py`, `mqtt_bridge.py`, `roles.yaml`. **Resultados:** tests por rol, mensajes de prueba, tabla de intercambios y fallos. **Cierre:** cuatro roles probados con solicitudes válidas e inválidas, sin actuaciones fuera de turno ni duplicadas. Depende de 2.3–2.4 y contrato 3.1 para cierre físico.

## 2.6. Seguridad, validación y despliegue

> **Alcance v1.2 (reducida):** el guardián y la bandera roja los aplica el supervisor (2.6.1 a 2.6.3 pasan al curso; en el repositorio no aparecen límites de articulación ni caja de trabajo: preguntar dónde están). El despliegue lo hace Race Control por SSH (`/opt/granprix/equipos/eqNN/`, con manifiesto `sha256`, opción B pendiente), así que 2.6.5 y 2.6.6 cambian: **entregar una carpeta de equipo que arranque como servicio** `app-equipo` y probarla en una estación. Nuestro: capturar excepciones y límites de tiempo dentro de la estrategia (el supervisor congela, pero no sustituye una buena estrategia) y devolver `ok: false` con motivo ante un agarre fallido.

- 2.6.1 Integrar el cliente con guardián oficial; toda orden física debe pasar por él.
- 2.6.2 Gestionar bandera roja y detener conforme a las reglas oficiales; no reanudar automáticamente.
- 2.6.3 Validar límites articulares, velocidad, caja de trabajo y trayectorias.
- 2.6.4 Gestionar agarre fallido, timeout, pérdida de comunicación y estado incierto sin maniobras peligrosas.
- 2.6.5 Preparar `deploy.sh` siguiendo plantilla del curso y verificar selección de rol, versión y arranque.
- 2.6.6 Validar despliegue del tag en las cuatro Jetson y cambio de equipo dentro de 3 min.

**Desarrollo:** separar ejecutor simulado y real; la lógica de estación no debe eludir el guardián. Desplegar desde versión identificada; verificar que se detiene el programa anterior y no quedan workers concurrentes. Pruebas de parada bajo supervisión, con zona despejada. No modificar archivos de `vendor/granprix` ni asumir acceso remoto o credenciales de las Jetson.

**Archivos:** `guardian_client.py`, `ejecutor_real.py`, `ejecutor_simulado.py`, `deploy.sh`, launch y tests de seguridad. **Resultados:** registro de despliegue por Jetson, versiones, rol, tiempos y pruebas de parada. **Cierre:** cuatro despliegues reales verificados, guardián operativo y cambio reproducible. Bloqueado parcialmente hasta recibir herramientas oficiales y acceso a estaciones.

# Bloque 3 — Integración del sistema GranPrix

**Objetivo:** garantizar compatibilidad entre módulos desde el primer día y progresar desde pruebas virtuales hasta la carrera real. Referencia oficial: secciones 2–12.

## 3.1. Arquitectura, red y contrato de comunicación

> **Alcance v1.2:** el contrato **ya está definido** en `pc-race/contrato/` (modelos pydantic) y en `docs/arquitectura/00-contrato-mqtt.md`. No lo redefinimos: lo importamos para validar nuestros mensajes. Tópicos adicionales respecto al HTML: `granprix/estacion/<n>/turno` y `granprix/eqNN/turno`. Ver las diferencias en 0.5. 3.1.4 se reduce a un adaptador de unidades y nombres.

- 3.1.1 Definir interfaces, responsabilidades de publicación, marcos, unidades, tiempos, errores y estados.
- 3.1.2 Configurar red de pruebas separada de la oficial. Red final `GranPrix-ESAN` 5 GHz, subred 192.168.50.0/24, Race Control .10, E1–E4 .21–.24, eq08 .108.
- 3.1.3 Broker MQTT Mosquitto local para ensayos; oficial 192.168.50.10:1883.
- 3.1.4 Definir adaptadores de mensajes según la tabla del HTML y luego los esquemas versionados del docente.
- 3.1.5 Identificación eq08 y aislamiento ROS 2 local en cada máquina.
- 3.1.6 Gestionar estado y banderas de Race Control; autorización de inicio y solicitudes.
- 3.1.7 Sincronizar NTP antes de cada tanda (error máximo 50 ms) y timestamp `t` de mensajes.

| Tópico MQTT | Contenido resumido | QoS |
|---|---|---|
| `granprix/carrera/estado` | fase, turno, vueltas, inicio, t | 1 retenido |
| `granprix/carrera/bandera` | verde, amarilla, roja, cuadros | 1 |
| `granprix/eq08/telemetria` | pose, velocidades, batería, vuelta, estado, pieza, escalas, t | 0, ≤5 Hz |
| `granprix/eq08/evento` | t, tipo, origen, detalle | 1 |
| `granprix/eq08/vuelta` | vuelta, tiempos y validez | 1 |
| `granprix/estacion/<n>/solicitud` | equipo, vuelta, id, pose en dock | 1 |
| `granprix/estacion/<n>/estado` | estado de estación | 1 retenido |
| `granprix/estacion/<n>/resultado` | id, ok, piezas, tiempo de pit | 1 |

Todos los mensajes llevan hora según el HTML. Esta tabla resume campos, **no es un esquema JSON definitivo**. No fijar nombres o tipos adicionales como oficiales. Los puentes de ROSCar y estación se implementan en sus paquetes respectivos; aquí se define y verifica compatibilidad. Probar permisos de turno, pérdida de broker, mensajes repetidos, antiguos, inválidos y de otro equipo. No publicar mensajes de prueba en Race Control oficial sin autorización.

**Archivos:** `docs/arquitectura.md`, `docs/interfaces.md`, `integracion/configuracion/mqtt.yaml`, `test_contrato.py`. **Cierre:** contrato oficial incorporado sin cambios, interoperabilidad y reloj verificados. Sin robot: arquitectura y MQTT local; acceso a infraestructura oficial pendiente.

## 3.2. Entorno de simulación y pruebas independientes

> **Alcance v1.2:** el banco de pruebas es `pc-race` más `simulador_carritos.py` (hasta 10 carritos y las 4 estaciones falsos, contra Mosquitto). 3.2.3 y 3.2.4 se cubren con eso. El `brazo_simulado` vendrá en `plantilla_equipo` (pendiente). Pasos: instalar `pc-race` (Python 3.12+), levantar Mosquitto, ejecutar `pc-race` y el simulador, crear una tanda desde el tablero del juez. El simulador ROS 2 de RC-1 queda en P2.

- 3.2.1 (P2) Recuperar simulador ROS 2 de RC-1 en WSL Ubuntu 22.04 / Humble (verificar versiones reales).
- 3.2.2 (P2) Adaptar escenario y pose inicial al GranPrix; usar `/cmd_vel`, `/odom`, `/sim/pose` y `/sim/reset` según disponibilidad real. Emular medición de tag con ruido configurable.
- 3.2.3 Utilizar estaciones simuladas de curso cuando estén disponibles; antes, dobles de prueba propios con interfaces provisionales.
- 3.2.4 Crear Race Control de pruebas, separado de la infraestructura oficial.
- 3.2.5 Ejecutar broker local y configuraciones reproducibles.
- 3.2.6 Probar solicitudes, estados y resultados entre módulos, primero un pit y después cuatro roles.
- 3.2.7 Inyectar fallos, retardos, pérdida de tag/broker, duplicados, turno incorrecto y bandera roja.

**Orden (v1.1):** primero pruebas unitarias con reloj inyectable y un doble MQTT mínimo de la estación (3.2.3, 3.2.5–3.2.7); la adaptación del simulador ROS 2 solo si no basta.

**Desarrollo:** distinguir simulación matemática HTML (3.5) de simulación ROS 2 (este apartado). Preparar fixtures deterministas, semillas y tests automáticos con reloj controlable. Si RC-1 no es compatible, crear adaptador o doble sencillo sin alterar el antecedente. Ninguna prueba debe enviar órdenes reales por defecto. **Archivos:** `sim_roscar.py`, `sim_estacion.py`, `sim_race_control.py`, `cliente_pruebas.py`, configuración y tests de integración. **Resultados:** logs MQTT, trazas, trayectorias y matriz de fallos. **Cierre:** intercambio simulado reproducible y fallos esperados controlados, luego compatibilidad con estación simulada oficial.

## 3.3. Integración del pit

> **Alcance v1.2:** `t_cambio` del resultado mide solo el cambio de pieza. **El tiempo del pit (frenado a arranque) lo medimos nosotros** con marcas propias, incluyendo acople, MQTT, supervisor, estrategia, segunda medición, reset y recalibración.

- 3.3.1 Solicitud MQTT al llegar y detenerse; correlación única por equipo, vuelta, estación e ID según contrato.
- 3.3.2 Transferencia de pose visual con marcos y unidades comunes.
- 3.3.3 Confirmación de tolerancia tras acople y reintentos; no enviar solicitud de manipulación fuera del rango válido.
- 3.3.4 Intercambio de pieza por estación, ROSCar inmóvil y brazo dentro del guardián.
- 3.3.5 Validación de resultado, pieza, ID y zona libre; fallo implica parada, no salida a ciegas.
- 3.3.6 Reset de pose y recalibración con datos anteriores al reacople; siguiente tramo desde pose medida.
- 3.3.7 Medir tiempo total desde frenado hasta arranque, incluyendo detección, acople, comunicación, manipulación, reset y recalibración.

**Desarrollo:** comenzar con un pit virtual, luego ROSCar real + estación simulada o cliente simulado + brazo real, finalmente ambos reales. Definir presupuesto temporal medido por fase; priorizar E2/E3. Mantener plazo global incluso con reintentos; al vencer, detener de forma segura y reconciliar el estado del brazo. No aproximar robots activos antes de verificar holgura y alcance. **Archivos:** `test_pit_integrado.py`, `scripts/integracion/prueba_pit.sh`. **Resultados:** `pits_prueba.csv`, cronometraje por fase, mensajes, video y reducción del error. **Cierre:** pit físico válido y seguro en ≤10 s con operación correcta y salida autorizada, repetido en los roles aplicables. No exige terminar previamente todas las pruebas independientes.

## 3.4. Integración de la carrera

> **Alcance v1.2:** Race Control aporta el tablero del juez, el ledger SQLite y el ranking. Nuestro tablero muestra el estado del carrito; no sustituye al oficial.

- 3.4.1 Integrar cuatro estaciones con el mismo programa y roles distintos.
- 3.4.2 Verificar ciclo A → B → C → vacío e inventario por vuelta.
- 3.4.3 Validar turno e inicio único con cuenta regresiva 3-2-1, y fin por cuatro vueltas, 12 min o E-stop.
- 3.4.4 Conectar el tablero a telemetría, eventos y controles reales autorizados.
- 3.4.5 Completar una vuelta con sus cuatro servicios y retorno.
- 3.4.6 Escalar a dos y cuatro vueltas, sin reiniciar manualmente entre tramos.
- 3.4.7 Probar fallos controlados de red, estación y movimiento, incluyendo bandera roja y recuperación autorizada.

**Desarrollo:** mantener pruebas virtuales rápidas y ensayos físicos escalonados. Registrar versión, superficie, parámetros, resultados y fallos; no ocultar corridas fallidas. Controlar seguridad y almacenamiento de evidencia. **Archivos:** `test_carrera_integrada.py`, scripts de inicio/ensayo, launch de integración. **Resultados:** vueltas, sectores, intervenciones y estados de piezas. **Cierre:** ensayo integral de cuatro vueltas con cuatro estaciones reales, dentro del tiempo y sin acciones inseguras; objetivo cero intervenciones. Resultados de ensayo no se presentan como tanda oficial.

## 3.5. Experimentación, simulación y predicción

> **Alcance v1.2:** sin cambios: el simulador del HTML sigue siendo la base de la predicción firmada. Usar parámetros medidos en el robot, no los valores por defecto.

- 3.5.1 Revisar el HTML original y su modelo de movimiento y ruido; conservarlo sin modificaciones.
- 3.5.2 Comparar las tres estrategias: sin pit, pit con reset, pit con reset y recalibración. Es una recomendación de análisis, no obligación de probar las tres físicamente.
- 3.5.3 Introducir sesgos de distancia/giro y dispersión medidos sobre cartón, y ruido visual medido en cámara real; usar tiempo de intercambio medido.
- 3.5.4 Analizar α y estabilidad de escalas; fijar parámetros antes de la tanda.
- 3.5.5 Comparar errores de llegada, reintentos, tiempos de pit/vuelta y limitaciones del modelo.
- 3.5.6 Entregar predicción firmada de reintentos totales y tiempo por vuelta antes de la tanda oficial; conservar parámetros, semilla, cuatro vueltas y fecha.
- 3.5.7 Bono opcional: odometría visual para sostener rumbo; declarar en README y comparar desviación lateral por tramo con y sin ella. Priorizar el sistema obligatorio antes del bono.

**Desarrollo:** usar valores sintéticos solo para exploración preliminar. El HTML no certifica límites físicos, guardián, colisiones, red ni cumplimiento de 10 s por pit; porcentaje de llegadas fuera de tolerancia no equivale a intervenciones ni vueltas inválidas. Si valores medidos quedan fuera de rangos del simulador, consultar al docente y separar cualquier copia experimental. No alterar el original ni firmar una predicción con valores ficticios.

**Archivos:** `simulacion/GranPrix Delivery Semiautónomo.html`, `parametros/`, `resultados/`, `graficos/`, `predicciones/`. **Cierre:** predicción documentada y firmada con parámetros reales, previa a la tanda; bono solo si se demuestra experimentalmente.

## 3.6. Evidencias y validación integral

> **Alcance v1.2:** confirmar qué producen el `grabador` del carrito y el ledger de Race Control (SQLite exportable a CSV) y qué debemos generar nosotros de los cinco CSV, el bag y los videos. **El validador de evidencia no está en el repositorio.** Hasta saberlo, no escribir generadores duplicados.

- 3.6.1 Verificar cinco CSV y coherencia temporal y de contenido.
- 3.6.2 Verificar bag completo, tópicos y conteo de mensajes (`ros2 bag info`).
- 3.6.3 Verificar reproducción, resolución, fps y overlay de videos.
- 3.6.4 Sincronizar timestamps entre Pi5, Jetson, MQTT y Race Control; contrastar intervenciones.
- 3.6.5 Aplicar rúbrica a ensayos, identificando criterios cumplidos y faltantes.
- 3.6.6 Ensayo general reproducible, incluyendo pérdida de comunicación y seguridad en pruebas separadas de la tanda.
- 3.6.7 Ejecutar `vendor/granprix/evaluacion/validador_evidencia.py` según instrucciones oficiales y guardar resultado.

| Evidencia oficial | Contenido y frecuencia mínima |
|---|---|
| `sensores.csv` | t, x, y, θ odom, v, ω, aceleraciones, giro IMU, batería; 10 Hz |
| `vueltas.csv` | vuelta, inicio, fin, tiempo, cuatro sectores, intervenciones y validez; una fila/vuelta |
| `pits.csv` | vuelta, estación, llegada, tiempo de pit, errores de posición/ángulo antes/después, reintentos, escalas y pieza; una fila/parada |
| `intervenciones.csv` | tiempo, tipo, origen web/juez, descripción; una fila/intervención |
| `mensajes.csv` | publicaciones y recepciones MQTT, tópico, hora y contenido; toda la tanda |
| `bags/tanda/` | `/odom /cmd_vel /tf /imu /battery_state /pit/medicion /pit/calibracion` y `/scan` si hay LiDAR; toda la tanda |
| `videos/lapNN.mp4` | un video por vuelta con vuelta y tiempo superpuestos, 640×480 a 15 fps como mínimo |

Los nombres de columnas exactos deben verificarse con el contrato y validador del docente. Registrar `/scan` si hay LiDAR según la sección 9. Guardar todo durante la tanda en Pi5 y copiar al repositorio al terminar. No mezclar datos ficticios con resultados oficiales. Una tanda sin intervenciones puede tener CSV de intervenciones con encabezado y ninguna fila, según el formato oficial; no inventar eventos.

**Archivos:** `scripts/integracion/validar_evidencias.sh`, `tests/integracion/test_evidencias.py`, `docs/bloque_03_integracion/3.6_validacion.md`. **Cierre:** evidencias completas, válidas y trazables a la versión ensayada; comprobación manual además del validador automático.

## 3.7. Carrera oficial, entrega y sustentación

> **Alcance v1.2:** el despliegue lo hace Race Control. La entrega oficial pide un fork de `granprix-esan` con `vendor/granprix` como submódulo: confirmar si `codeplai/GranPrix` ocupa ese lugar y qué estructura de carpetas exige para `carrito/` y `estacion/`.

- 3.7.1 Integrar repositorio final, fork de `granprix-esan`, con `vendor/granprix` como submódulo sin modificaciones.
- 3.7.2 Etiquetar versión estable `v1.0-final` y verificar checkout reproducible.
- 3.7.3 Probar `deploy.sh` en las cuatro Jetson, red, reloj, guardián y tablero. Comprobar acceso al repositorio durante cambio de equipo.
- 3.7.4 Ejecutar tanda oficial con calentamiento, turno, inicio único y supervisión por tablero.
- 3.7.5 Analizar predicción vs resultados, vueltas, tiempos, errores, escalas e intervenciones; distinguir fallos de curso y de equipo.
- 3.7.6 Elaborar `informe.pdf` de dos páginas: predicción contra resultado, causa raíz de cada intervención y prevención, errores antes/después y evolución de escalas, propuesta de mejora.
- 3.7.7 Preparar defensa de cualquier vuelta sorteada y explicar decisiones y fallos con evidencia; compartir conocimiento entre integrantes.

**Reglas clave:** inicio, observación, ajustes antes del inicio, pausas del juez y bandera roja de Race Control no cuentan como intervención. Toques físicos, controles web, teleoperación y reinicios/cambios de software durante carrera cuentan según sección 6; acciones en menos de 10 s sobre el mismo problema se agrupan según regla general; una intervención no declarada descubierta en video suma 3. El ganador se ordena por menos intervenciones, luego más vueltas válidas, menor tiempo promedio y menor error de pose medio. Fallas de hardware de brazo, red o Race Control imputables al curso se gestionan por el juez; una falla de nuestro programa de estación es nuestra responsabilidad.

**Entregables:** README con integrantes, IP y URL del tablero, sensores, uso de odometría visual y altura de cuna; código, tag, despliegue, predicción firmada, registros oficiales e informe. **Cierre:** entrega completa y defensa realizada; no confundir un ensayo con resultados de la tanda oficial.

# 4. Correspondencia con la rúbrica oficial

| Criterio | Puntos | Requisito oficial para máximo | Secciones internas |
|---|---:|---|---|
| Tanda | 4 | 4 vueltas válidas (3 → 3 pts, 2 → 1 pt, menos de 2 → 0) | 1.2, 1.5, 3.3, 3.4 |
| Pit | 3 | Medición, acople, reset y recalibración; error post menor que pre en ≥70 % de paradas y escalas convergentes | 1.3, 1.4, 2.4, 3.3 |
| Estación | 3 | Despliegue con `deploy.sh`; intercambio correcto ≥90 % (75 % → 2, 50 % → 1) | 2.2–2.6, 3.3 |
| Tablero web | 2 | Todos los bloques de sección oficial 8 operativos | 1.6, 3.4 |
| Evidencia | 3 | Video por vuelta, bag completo y cinco CSV | 1.6, 3.6 |
| Autonomía | 3 | 0 intervenciones (1–2 → 2, 3–5 → 1, ≥6 → 0) | 1.5, 2.6, 3.4 |
| Informe | 1 | Dos páginas según sección oficial 10 | 3.5, 3.7 |
| Defensa | 1 | Explicar video sorteado de una vuelta | 3.7 |
| **Total** | **20** | | |
| Bono | +1 | Odometría visual documentada, sin superar 20 | 3.5.7 |

**Nota v1.2:** confirmar con el docente si los criterios Estación (que hoy habla de `deploy.sh`), Tablero web y Evidencia se mantienen tal cual o cambian porque el curso aporta supervisor, tablero base y grabador.

La nota y el ranking son distintos. Para clasificar al ranking hacen falta ≥3 vueltas válidas; el criterio principal del ganador es menor número de intervenciones. No existe puntuación oficial asignada individualmente a las 19 secciones internas. Para seguimiento se puede calcular el número de secciones validadas sobre 19, dejando claro que no representa la nota ni el esfuerzo restante.

# 5. Estrategia de integración incremental y dependencias

| Nivel | ROSCar | Estación | Objetivo |
|---|---|---|---|
| I — Virtual | Simulado | Simulada | Verificar contrato, FSM, resultados, fallos y registros. |
| II — Mixto móvil | Real | Simulada | Validar movimiento, visión, acople y flujo de intercambio sin brazo activo. |
| III — Mixto brazo | Cliente simulado | Real | Validar roles, compensación, manipulación y tiempo con guardián. |
| IV — Físico | Real | Real | Pit completo; luego cuatro estaciones, vuelta y tanda completa. |

**v1.2:** el nivel I usa `pc-race` y su simulador de carritos; la estación simulada de nivel I/II será el supervisor y el `brazo_simulado` del curso cuando existan.

II y III no tienen orden obligatorio y pueden ejecutarse en paralelo. Para pasar a integración física conjunta se exige una interfaz común estable, parada y guardián verificados, montaje seguro, poses alcanzables, y validación de que el carrito no se mueve durante manipulación. La integración virtual no exige terminar la calibración real.

Dependencias principales para el cierre (no para el inicio):

- 1.1 → validación física de 1.2; 1.5 (seguridad mínima) → cualquier prueba de movimiento.
- **v1.1:** 1.3.4–1.3.5 y 1.3.8 (tag mínimo y su precisión) → 1.1.5–1.1.6 (el tag mide el giro y la recta). 1.1.8 (cuna montada) → pruebas de E1–E4 con el carrito real.
- **v1.1:** respuesta sobre MoveIt2 en `granprix-esan` → alcance real de 2.2.
- 1.3 + 1.2 → 1.4 (estimación y acople físicos).
- 2.1 + 2.2 → 2.3; 1.3/3.1 + geometría → 2.4; 2.3 + 2.4 + 2.6 → ejecución física de 2.5.
- 3.1 ↔ interfaces de 1.5 y 2.5; 3.2 permite probarlas desde el inicio.
- 3.3 → 3.4 para carrera real; 1.6 ↔ 3.4 para tablero operativo.
- 1.1 + 1.3 + 2.3 + 3.3 → parámetros reales para 3.5.
- 1.6 + 3.4 → 3.6; 3.5 + 3.6 + 2.6 → entrega 3.7, que se completa tras la tanda oficial.

# 6. Estructura propuesta del repositorio

> **v1.2:** las carpetas del equipo deben ajustarse a la plantilla del curso cuando exista. Por ahora, la guía son `docs/arquitectura/02` (estación: `plantilla_equipo/src/app_equipo/estrategia.py`) y `03` (carrito: `granprix_carrito/{control_odometria,camara_apriltag,maquina_pit}`). Lo que el curso entrega (`puente_mqtt`, `vigilante_red`, `grabador`, `supervisor_estacion`) **no se copia ni se reescribe**. Los módulos del árbol de abajo que correspondan a esos nodos son informativos.

La organización lógica por bloques no obliga a mover los paquetes ROS 2. Conservar `carrito/`, `estacion/`, `vendor/granprix` y los nombres exigidos para la entrega. Los scripts auxiliares, pruebas y documentación se agrupan por bloque. Los archivos mostrados son **rutas propuestas**, no un inventario de archivos existentes ni una orden de crear módulos vacíos. Ajustar a plantillas oficiales antes de integrarlos.

```text
capytown_eq08_final/
├── README.md
├── contexto.md
├── contexto_reto_final.md
├── contexto_division_reto_final.md     # Este documento
├── .gitignore
├── .gitmodules                       # Cuando exista submódulo oficial
├── carrito/                          # Bloque 1: paquete ROS 2
│   ├── package.xml
│   ├── setup.py
│   ├── setup.cfg
│   ├── resource/granprix_carrito
│   ├── granprix_carrito/
│   │   ├── __init__.py
│   │   ├── diagnostico.py             # 1.1
│   │   ├── odom_utils.py              # 1.1, 1.2
│   │   ├── planificador.py            # 1.2
│   │   ├── ejecutor.py                # 1.2
│   │   ├── camara.py                  # 1.3
│   │   ├── vision_tag.py               # 1.3
│   │   │                               # (transformaciones: ver comun/)
│   │   ├── reset_pose.py               # 1.3
│   │   ├── acople_fino.py              # 1.4
│   │   ├── calibracion.py              # 1.4
│   │   ├── maquina_estados.py          # 1.5
│   │   ├── mision.py                   # 1.5
│   │   ├── vigilante.py                # 1.5
│   │   ├── mqtt_bridge.py              # 1.5 / 3.1
│   │   ├── web_server.py               # 1.6
│   │   ├── registro.py                 # 1.6
│   │   ├── battery_adapter.py          # 1.6
│   │   └── grabador_video.py           # 1.6
│   ├── config/
│   │   ├── carrito.yaml
│   │   ├── movimiento.yaml
│   │   ├── camara.yaml
│   │   └── calibracion.yaml
│   ├── launch/
│   │   ├── diagnostico.launch.py
│   │   └── carrito.launch.py
│   └── web/
│       ├── index.html
│       ├── css/estilos.css
│       └── js/dashboard.js
├── estacion/                         # Bloque 2: paquete ROS 2
│   ├── package.xml
│   ├── setup.py
│   ├── setup.cfg
│   ├── resource/granprix_estacion
│   ├── granprix_estacion/
│   │   ├── __init__.py
│   │   ├── diagnostico.py              # 2.1
│   │   ├── cinematica.py               # 2.2
│   │   ├── integration_moveit.py       # 2.2
│   │   ├── posiciones.py               # 2.2, 2.3
│   │   ├── pick_and_place.py           # 2.3
│   │   ├── control_pinza.py            # 2.3
│   │   │                               # (transformaciones: ver comun/)
│   │   ├── compensacion_pose.py        # 2.4
│   │   ├── station_worker.py          # 2.5
│   │   ├── validar_turno.py            # 2.5
│   │   ├── idempotencia.py             # 2.5
│   │   ├── mqtt_bridge.py              # 2.5 / 3.1
│   │   ├── guardian_client.py          # 2.6
│   │   ├── ejecutor_real.py            # 2.6
│   │   └── ejecutor_simulado.py        # 2.6
│   ├── config/
│   │   ├── estacion.yaml
│   │   ├── roles.yaml
│   │   ├── almacenes.yaml
│   │   ├── manipulacion.yaml
│   │   └── cuna.yaml
│   └── launch/estacion.launch.py
├── comun/                            # v1.1: paquete compartido por carrito y estacion
│   └── granprix_comun/
│       ├── __init__.py
│       └── transformaciones.py        # una sola convención de signos
├── integracion/                      # Bloque 3: herramientas comunes
│   ├── configuracion/
│   │   ├── mqtt.yaml
│   │   └── mosquitto_pruebas.conf
│   ├── simuladores/
│   │   ├── sim_roscar.py
│   │   ├── sim_estacion.py             # Provisional; usar oficial al recibirlo
│   │   ├── sim_race_control.py         # Solo pruebas aisladas
│   │   └── cliente_pruebas.py
│   └── pruebas/                      # Escenarios/fixtures de integración
├── scripts/
│   ├── roscar/
│   │   ├── preflight.sh
│   │   ├── prueba_recta.py
│   │   └── prueba_giro.py
│   ├── jetcobot/
│   │   ├── preflight_jetcobot.sh
│   │   └── prueba_manipulacion.py
│   └── integracion/
│       ├── prueba_pit.sh
│       ├── ensayo_carrera.sh
│       └── validar_evidencias.sh
├── tests/
│   ├── roscar/                       # Planificador, visión, reset, escalas, FSM
│   ├── jetcobot/                     # FK/IK, compensación, roles, guardián
│   └── integracion/                  # Contrato, pit, carrera, evidencia
├── docs/
│   ├── arquitectura.md
│   ├── interfaces.md
│   ├── plan_desarrollo.md
│   ├── bitacora_laboratorio.md
│   ├── bloque_01_roscar/             # 1.1–1.6: diagnóstico, diseño, conclusiones
│   ├── bloque_02_jetcobot/           # 2.1–2.6
│   └── bloque_03_integracion/        # 3.1–3.7
├── experimentos/
│   ├── bloque_01_roscar/
│   │   ├── 1.1/                     # Rectas, giros, diagnóstico
│   │   ├── 1.2/                     # Trayectorias y comandos
│   │   ├── 1.3/                     # Visión y TF
│   │   ├── 1.4/                     # Acople y escalas
│   │   ├── 1.5/                     # Seguridad y FSM
│   │   └── 1.6/                     # Tablero y registro de prueba
│   ├── bloque_02_jetcobot/           # Subcarpetas 2.1–2.6 según necesidad
│   └── bloque_03_integracion/        # Subcarpetas 3.1–3.7 según necesidad
├── simulacion/
│   ├── GranPrix Delivery Semiautónomo.html
│   ├── parametros/
│   ├── resultados/
│   ├── graficos/
│   └── predicciones/
├── vendor/
│   └── granprix/                    # Oficial, sin modificar
├── deploy.sh                         # Exigido para las 4 Jetson
├── sensores.csv                       # Solo evidencia de tanda oficial
├── vueltas.csv
├── pits.csv
├── intervenciones.csv
├── mensajes.csv
├── videos/lapNN.mp4                    # Un archivo por vuelta
├── bags/tanda/                        # Tanda completa
└── informe.pdf                        # Dos páginas
```

Los CSV, bags, videos, predicción firmada y el informe final se incorporan cuando exista evidencia real. No crear archivos oficiales falsos ni subir bags de simulación a `bags/tanda/`. Si se mantienen scripts iniciales `scripts/roscar_v01/` y `tests/roscar_v01/`, no eliminarlos hasta migrar y comprobar su funcionamiento. Las carpetas de simuladores propios son auxiliares y no sustituyen el código oficial del curso.

## 6.1. Convenciones para experimentos y documentación

Ejemplo de una corrida real de caracterización (nombre ilustrativo):

```text
experimentos/bloque_01_roscar/1.1/20261124_recta_run01/
├── metadata.yaml    # Responsable, fecha, robot, commit, parámetros, superficie, tipo de prueba
├── datos.csv
├── bags/
├── plots/
└── conclusiones.md
```

En cada sección identificar objetivo, hipótesis si aplica, método, parámetros, resultados, fallos, conclusiones y tareas pendientes. No duplicar código entre carpetas de experimentos; referenciar el commit y configuración utilizada. Registrar evidencias grandes siguiendo la estrategia de almacenamiento del docente y límites de GitHub; evitar subir `build/`, `install/`, `log/`, caches, entornos virtuales, tokens, contraseñas y archivos de configuración privada. No ignorar globalmente los formatos CSV, MP4 o bags exigidos en la entrega.

## 6.2. Flujo de Git y colaboración

**Un solo repositorio activo (v1.1):** en cuanto exista el fork oficial `capytown_eq08_final`, pasar todo el trabajo allí y dejar la copia como archivo. Trasladar cambios entre dos historiales con cherry-pick falla con facilidad; hasta entonces, usar la copia como entorno experimental del ROSCar. El repositorio principal integra el código de todos; el repo oficial del curso es otra entidad. Ramas sugeridas: `main` (estable), `develop` (integración), `feature/roscar-navegacion`, `feature/roscar-vision`, `feature/jetcobot-cinematica`, `feature/jetcobot-manipulacion`, `feature/integracion`. No es obligatorio que exista cada rama antes de comenzar.

Ejemplo de commit: `feat(1.2.2): implementar planificador de tramos`; ejemplo de registro: `test(3.3.7): medir tiempo del pit simulado`. Transferir cambios revisados mediante PR, cherry-pick cuando historiales y commits lo permitan, o copia selectiva a una rama de integración. Nunca sobrescribir todo el repositorio principal con la copia experimental. Actualizar submódulo solamente según la versión oficial aprobada. Etiquetar `v1.0-final` tras validar la versión de competencia.

# 7. Plan flexible para nueve días de laboratorio

Las ventanas son objetivos de trabajo, no requisitos oficiales ni fechas rígidas. Avanzar lo que permita la disponibilidad real y coordinar diariamente.

| Ventana | Carrito (A, B) | Estación (C, D) | Integración (E) | Criterio de salida (propuesto, a validar) |
|---|---|---|---|---|
| Días 1–2 | Protección de `/cmd_vel` con `twist_mux`, 1.1 mínima, tag con cámara real y su precisión (1.3.8), cuna montada (1.1.8) | 2.1 diagnóstico y acceso; medir el ciclo con `send_coords`; pedir la firma de `BrazoJetCobot` | `pc-race` y su simulador funcionando con Mosquitto local; contrato importado | El robot frena si cae nuestro nodo; precisión del tag medida contra cinta; `pc-race` con un carrito falso nuestro |
| Días 2–4 | Ejecutor y estimador de escalas; 1.1.5–1.1.6 con el tag; maquina_pit contra el simulador | Estrategia E1 y E4 con `brazo_simulado`; E2 y E3 en el brazo real | Mensajes del carrito validados contra el contrato; extensión del tablero | **Ciclo E2 medido (puerta del día 3)**; tramo de 2 m acoplado; una vuelta falsa contra `pc-race` |
| Días 4–6 | Reset de pose, acople fino real, FSM completa | Estrategia por rol con compensación; trabajar con el supervisor del curso cuando salga | Pit físico, primera vuelta | Pit físico válido dentro de los 10 s totales; vuelta completa sin tocar el robot |
| Días 6–8 | Varias vueltas, recuperación | Optimización de tiempos, estrategia robusta | Evidencias, predicción con parámetros medidos | Cuatro vueltas seguidas; evidencia lista para el validador |
| Días 8–9 | Estabilización y regresión | Prueba del despliegue por Race Control en las cuatro estaciones | Ensayo general, congelar versión | Ensayo de 12 min sin intervención |
| Tanda oficial | Supervisión | Estaciones desplegadas | Análisis, entrega y defensa | — |

Prioridades críticas: guardián y parada del ROSCar desde las primeras pruebas; visión confiable; medir pronto el tiempo de E2/E3; contrato común desde el comienzo; preservar evidencias desde la primera corrida. La integración virtual y los registros no deben quedar para el último día.

# 8. Seguimiento de las 19 secciones

Estado inicial de esta plantilla: **por verificar**, no presupone que el código esté ausente ni que las pruebas estén hechas. Actualizar después de inspeccionar el repositorio y las evidencias. El ZIP v0.1 constituye un antecedente de implementación, no certificación física.

| ID | Sección | Responsable | Estado | Evidencia/commit | Bloqueo o siguiente acción |
|---|---|---|---|---|---|
| 1.1 | Diagnóstico y caracterización del ROSCar | Por asignar | Por verificar | — | — |
| 1.2 | Planificación y ejecución de movimiento | Por asignar | Por verificar | — | — |
| 1.3 | Visión artificial y localización | Por asignar | Por verificar | — | — |
| 1.4 | Acople fino y calibración adaptativa | Por asignar | Por verificar | — | — |
| 1.5 | Autonomía y seguridad | Por asignar | Por verificar | — | — |
| 1.6 | Tablero web y registro local | Por asignar | Por verificar | — | — |
| 2.1 | Diagnóstico y caracterización del JetCobot | Por asignar | Por verificar | — | — |
| 2.2 | Cinemática y planificación de movimientos | Por asignar | Por verificar | — | — |
| 2.3 | Manipulación de piezas | Por asignar | Por verificar | — | — |
| 2.4 | Compensación de pose de la cuna | Por asignar | Por verificar | — | — |
| 2.5 | Programa único de estación | Por asignar | Por verificar | — | — |
| 2.6 | Seguridad, validación y despliegue | Por asignar | Por verificar | — | — |
| 3.1 | Arquitectura, red y contrato de comunicación | Por asignar | Por verificar | — | — |
| 3.2 | Entorno de simulación y pruebas independientes | Por asignar | Por verificar | — | — |
| 3.3 | Integración del pit | Por asignar | Por verificar | — | — |
| 3.4 | Integración de la carrera | Por asignar | Por verificar | — | — |
| 3.5 | Experimentación, simulación y predicción | Por asignar | Por verificar | — | — |
| 3.6 | Evidencias y validación integral | Por asignar | Por verificar | — | — |
| 3.7 | Carrera oficial, entrega y sustentación | Por asignar | Por verificar | — | — |

## 8.0. Avance por etapas de la cadena crítica (v1.1)

El conteo de "secciones validadas sobre 19" pesa igual a 1.6 que a 1.4. Medir además el avance por etapas:

| Etapa | Estado | Evidencia |
|---|---|---|
| Protección de `/cmd_vel` probada (el robot frena si cae nuestro nodo) | Pendiente | — |
| Mensajes del carrito validados contra `contrato/` de `pc-race` | Pendiente | — |
| Carrito completa una vuelta falsa contra `pc-race` | Pendiente | — |
| Precisión del tag medida | Pendiente | — |
| Primer tramo de 2 m acoplado sin tocar el robot | Pendiente | — |
| Primer pit completo (doble, contra el doble MQTT) | Pendiente | — |
| Ciclo E2 medido en el brazo real | Pendiente | — |
| Primer pit físico válido | Pendiente | — |
| Primera vuelta completa | Pendiente | — |
| Cuatro vueltas en ensayo | Pendiente | — |
| Evidencia que pasa el validador | Pendiente | — |

## 8.1. Formato de bitácora por sesión

```markdown
### Fecha / día de laboratorio / horario
- Responsable y bloque/sección:
- Robot o entorno simulado:
- Objetivo y tipo de prueba:
- Rama y commit:
- Parámetros y condiciones (superficie, montaje, batería):
- Actividades y cambios:
- Resultado medido y criterio de aceptación:
- Evidencias (rutas):
- Fallos y bloqueos:
- Siguiente actividad y responsable:
- Estado seguro del robot al finalizar:
```

# 9. Pendientes que condicionan el desarrollo

| Pendiente | Acción mientras se resuelve |
|---|---|
| Repositorio oficial `granprix-esan`, plantillas, contrato JSON, guardián, `deploy.sh` y validador | Programar lógica independiente y adaptadores provisionales. No afirmar compatibilidad oficial. |
| Acceso al hardware y horarios | Trabajar con simuladores, coordinar pruebas físicas autorizadas. |
| Montaje elevado de cartón, dimensiones y posiciones finales | Inspeccionar plataforma, holguras, alcance y foco; no fijar calibraciones definitivas antes de medir. |
| Configuración del ROSCar asignado, cámara, odometría y batería | Diagnóstico no invasivo y caracterización. |
| Red oficial, permisos de acceso remoto y despliegue | Broker local aislado y configuraciones reproducibles. |
| Interpretación del 70 % de reducción del error cuando ya está dentro de tolerancia, inicialización de cd/ca y detalle del tiempo de pit | Consultar al docente; conservar criterios oficiales y documentar las decisiones. |
| (v1.1) Horas y ventanas de acceso a los brazos antes de la tanda | Preguntar esta semana; mover trabajo a pruebas unitarias mientras tanto. |
| (v1.1) Elevación de la base de cartón frente a los 14 cm libres bajo la mesa y los 12.4 cm del ROSCar | Medir la elevación y preguntar si las mesas se elevan igual. |
| (v1.1) ¿`granprix-esan` trae el modelo y la configuración de MoveIt2 y el guardián? | Preguntar el día 1; condiciona el alcance de 2.2. |
| (v1.1) Quién fabrica la cuna y la ménsula y con qué materiales | Asignado a A (1.1.8); confirmar restricciones con el docente. |
| (v1.1) Si el giro de salida y la medición con tag en movimiento cuentan dentro de los 10 s | Preguntar; cambia el presupuesto del pit. |
| (v1.2) ¿Qué secciones del HTML simplifica el repositorio y se mantiene la rúbrica? | Preguntar el texto exacto; hasta entonces mantener la rúbrica del HTML. |
| (v1.2) Firma del puerto `BrazoJetCobot` (articulaciones o cartesiano) y si hay guardián con límites y caja de trabajo | Preguntar; condiciona 2.2 y 2.6. |
| (v1.2) Plantilla del carrito, `supervisor_estacion`, `plantilla_equipo` y `dock_frames.yaml`: fecha de publicación | Avanzar con lógica pura y `pc-race`; no inventar sus interfaces. |
| (v1.2) ¿`id` y `vuelta` en `solicitud` y `resultado`? ¿Campo de motivo en `resultado`? | Pedir; hoy el emparejamiento es por equipo y estación. |
| (v1.2) Cómo recibe la estrategia su rol, el dock y la ranura de bandeja | Preguntar; la firma `cambiar(pose, pieza_trae)` no los incluye. |
| (v1.2) Opción A, B o C de despliegue y quién asigna el turno de cada estación | Preguntar; está abierto en `04-despliegue-ssh.md`. |
| (v1.2) ¿`codeplai/GranPrix` equivale a `granprix-esan` y es el fork/submódulo que se entrega? | Preguntar antes de crear `.gitmodules`. |
| (v1.2) Qué evidencia produce el `grabador` y cuál debemos generar; dónde está el validador | Preguntar; evitar duplicar. |

# 10. Referencias y reutilización de antecedentes

- Documento original: `GranPrix Delivery Semiautónomo.html` (secciones 1–12 y pestaña Simulador).
- [Repositorio del docente `codeplai/GranPrix`](https://github.com/codeplai/GranPrix) (commit `285c829`): Race Control, herramienta AprilTag y `docs/arquitectura/00`–`04`. **Manda sobre el HTML** en lo que programa cada parte, según indicó el docente.
- Documentos internos: `README.md`, `contexto.md`, `contexto_reto_final.md`.
- [CapyTown RC-0](https://github.com/Harold855/RC-0_MicroRos_Pi5): utilidades odométricas, diagnóstico y grabación; verificar parámetros del robot asignado.
- [CapyTown RC-1](https://github.com/Harold855/microrospi5-sim_capytown_G8): simulación, análisis de errores, ejecución segura y evidencia histórica. No sustituir el ejecutor en lazo abierto exigido por el PID del cuadrado anterior.
- [Simulador base RC-1](https://github.com/codeplai/microrospi5-sim): entorno auxiliar ROS 2, distinto del simulador HTML oficial GranPrix.
- Reto 1 JetCobot: API y secuencias de manipulación, sujetas a nueva geometría y guardián.
- [Reto 2 — El Turno del Brazo](https://github.com/Harold855/Reto_2-El_Turno_del_Brazo): FK, IK y conceptos de worker único.
- [Gran Reto JetCobot — Grupo 8](https://github.com/Harold855/El-Gran-Reto-de-JetCobot---Grupo-8): modelos, MoveIt2 y secuencias parametrizadas; verificar pruebas y posiciones no validadas.
- Manuales del fabricante: [MicroROS Pi5](https://www.yahboom.net/study/MicroROS-Pi5) y [JetCobot](https://www.yahboom.net/study/JetCobot).

**Principio final:** avanzar por bloques en paralelo, integrar desde el primer día, cerrar cada sección con evidencia verificable y no considerar el sistema listo para la carrera hasta validar su comportamiento físico e integrado bajo las reglas oficiales.

# 11. Registro de cambios de la versión 1.1

Revisión de criterio del 24-nov-2026. Motivos y efectos:

| Cambio | Motivo |
|---|---|
| Sección 0.4: prioridades P0/P1/P2, recortes y puerta del pit (día 3) | 130 subtareas no caben en 9 días con igual peso; se prioriza la vuelta válida |
| 2.2: corregida la premisa "FK/IK del Reto 2" | Ningún antecedente tiene IK propia; la FK trae sesgos conocidos |
| 1.1: orden de trabajo con el tag como instrumento; 5 corridas por tipo; 1.3.8 | En RC-1 el transportador (±3.5°) impidió separar el error del robot del error de medición |
| `granprix_comun/transformaciones.py` único para 1.3 y 2.4 | Evitar signos distintos entre el carrito y el brazo |
| 1.6 pasa a E (integración y evidencias); reparto para 5 | Equilibrar la carga: el bloque ROSCar tenía visión, calibración, FSM, seguridad, tablero y registro |
| 1.1.8: fabricar y montar la cuna y la ménsula | Nadie tenía la tarea; sin ella no se prueba E1–E4 con el carrito real |
| 2.1.7 y pendientes: acceso a los brazos y riesgo del montaje elevado | El ritmo del bloque 2 y el paso libre bajo la mesa dependen de ello |
| 3.2: simulador ROS 2 pasa a P2; primero pruebas unitarias y doble MQTT | Costo alto de adaptar RC-1 frente a su beneficio |
| 6.2: un solo repositorio activo tras el fork | Evitar desincronización entre dos historiales |
| Sección 7: criterios de salida; 8.0: avance por etapas | Las ventanas no tenían condición de aprobado; el conteo de secciones engaña |

# 12. Registro de cambios de la versión 1.2

Adaptación al repositorio del docente (`codeplai/GranPrix`, commit `285c829`, 24-nov-2026), que según el docente manda sobre el HTML.

| Cambio | Motivo |
|---|---|
| Fuentes y precedencia en la sección 0; nueva sección 0.5 (qué cambia con el repositorio, diferencias con el HTML y riesgos del contrato real) | El repositorio redefine quién programa qué y el formato real de los mensajes |
| Bloque "Alcance v1.2" al inicio de cada sección | Marca lo que pasa al curso y lo que sigue siendo nuestro, sin borrar el texto original |
| 2.5 y 2.6 reducidas; 2.2 depende de `BrazoJetCobot` | El supervisor, el guardián y el despliegue son del curso; el equipo escribe la estrategia de cambio |
| 1.5 y 1.6 reducidas; 3.2 y 3.1 simplificadas | Puente, vigilante, tablero base y grabador son del curso; `pc-race` y su simulador sustituyen al banco de pruebas propio |
| Reparto A–E y prioridades reescritos | Menos infraestructura que escribir; el peso pasa a la precisión del acople y al tiempo de cambio en E2 y E3 |
| Sección 7 y 8.0 ajustadas; 9 con 9 pendientes nuevos | Criterios de salida, avance y preguntas al docente alineados con el nuevo alcance |
