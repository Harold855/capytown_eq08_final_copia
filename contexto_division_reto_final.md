# GranPrix Delivery Semiautónomo — Contexto de división y desarrollo del reto final

**Proyecto:** CapyTown · Robótica · Grupo 8 (eq08)  
**Fecha prevista de presentación:** 7 de diciembre de 2026  
**Versión del documento:** 1.3 — 24 de noviembre de 2026 (consolidada; repositorio docente `codeplai/GranPrix`, commit `285c82966a2de1d3b4eb39a64bad1415a14212db`; cambios en sección 13)  
**Estado:** planificación y desarrollo inicial; no acredita pruebas realizadas.  
**Repositorio experimental ROSCar:** [capytown_eq08_final_copia](https://github.com/Harold855/capytown_eq08_final_copia/tree/main). Los documentos nuevos están en la rama `claude/compassionate-goldberg-konorb` hasta que se integren a `main`.  
**Repositorio de integración del equipo:** `capytown_eq08_final`.

## 0. Propósito, fuentes y metodología

Este documento establece la organización interna del Grupo 8 para desarrollar el reto, asignar responsabilidades, identificar archivos, registrar avances y comprobar los requisitos oficiales. Complementa `README.md`, `contexto.md` y `contexto_reto_final.md`. En conflictos técnicos prevalece el repositorio del docente; los documentos internos no son especificaciones oficiales.

**Fuentes y precedencia:** (1) indicaciones actualizadas del docente, incluida la instrucción comunicada el 24 de noviembre de que el repositorio manda; (2) `codeplai/GranPrix` en la versión identificada, fuente principal para arquitectura, interfaces y reparto de trabajo; (3) `GranPrix Delivery Semiautónomo.html`, referencia complementaria para requisitos no sustituidos, incluyendo reglas, rúbrica y predicción, sujetos a confirmación. Una descripción de arquitectura no equivale a código publicado. Si dos documentos oficiales discrepan o falta una interfaz, registrar el bloqueo y consultar; no inventar un requisito. El documento original no divide el trabajo en partes A–F ni en los tres bloques de este plan. La numeración que sigue es una propuesta interna. Las denominaciones de módulos, pruebas, rutas y metas intermedias son propuestas y podrán adaptarse a las plantillas del curso. No modificar contrato, supervisor, componentes de seguridad ni geometría oficial; elevar discrepancias al docente.

**Actualización del montaje comunicada por el docente al equipo:** la base del circuito será de cartón y estará ligeramente elevada para facilitar la manipulación de cubos. La altura exacta, el soporte, las uniones, los bordes, las alturas de cámara/tag/cuna y la geometría respecto a las mesas aún deben comprobarse. Las dimensiones nominales del HTML se conservan como referencia, no como confirmación del montaje actualizado.

**Riesgo del montaje elevado (propuesto, por confirmar con el docente):** el tablero de la mesa del brazo deja 14 cm libres sobre el piso y el ROSCar mide 12.4 cm con antena y LiDAR. Si la base de cartón sube más de ≈1.6 cm y las mesas no suben lo mismo, el carrito no entra bajo la mesa. Medir la elevación real y confirmar si las mesas se elevan igual antes de fijar cualquier altura de cuna, cámara o tag.

### 0.1. Organización adoptada

| Bloque | Secciones | Responsable principal |
|---|---|---|
| 1. ROSCar | 1.1–1.6 (6) | Subgrupo carrito. **1.6 (tablero y registro)** lo lleva el responsable de integración y evidencias; su código vive en `carrito/` porque corre en el Pi5 |
| 2. JetCobot | 2.1–2.6 (6) | Subgrupo estación |
| 3. Integración del sistema | 3.1–3.7 (7) | Coordinador y ambos subgrupos |

**19 secciones en total.** La numeración es identificativa, no un orden de ejecución obligatorio. La integración comienza desde el inicio, con interfaces y contrapartes simuladas; no espera a que ambos robots estén terminados. Se respetan dependencias de datos y seguridad para cerrar las pruebas, no una secuencia rígida para escribir código.

Con cinco integrantes (reparto propuesto, ver 0.5):

| Rol | Trabajo | Secciones |
|---|---|---|
| A. Control del carrito | `control_odometria`: ruta, `cd` y `ca`, reset de pose, verificación de la parada ante la caída de nuestro nodo | 1.1, 1.2, 1.4 (escalas), 1.5 |
| B. Visión y acople | `camara_apriltag` y `maquina_pit`: tag, pose en el dock, acople fino, solicitud y reintentos | 1.3, 1.4 (acople), 1.5 |
| C. Estrategia de cambio, roles E1 y E4 | `EstrategiaDeCambio`, compensación de la pose, brazo simulado | 2.1–2.4, 2.5 (E1/E4), 2.6 |
| D. Estrategia de cambio, roles E2 y E3 | Doble intercambio dentro del pit y pruebas de tiempo con el brazo real | 2.3, 2.5 (E2/E3), 2.6 |
| E. Integración y evidencias | `pc-race` local, contrato, extensión del tablero, registros y evidencias | 3.1–3.6, 1.6 |

3.3 y 3.4 son de todos, con un responsable designado por día para la prueba física. 3.5 (predicción) lo lleva A con apoyo de B; 3.7 lo lleva E con todos. La estación casi no tiene infraestructura que escribir (la hace el curso), pero sí exige tiempo con un brazo compartido: por eso C y D la reparten por rol y por hardware. Con cuatro: A y B siguen separados, C y D siguen como los dos responsables de estación, y E se reparte entre ambos pares con un coordinador designado, **sin dejar sin dueño la seguridad ni la evidencia**. Cada responsable necesita un suplente: en la defensa se sortea un video y puede explicarlo cualquiera. Es posible trabajar en horarios distintos si el laboratorio lo autoriza; cada turno registra versión, cambios, pruebas, fallos, siguiente acción y estado seguro del hardware. Un único responsable controla cada robot durante una prueba física.

### 0.2. Estados y criterios de cierre

| Estado | Significado |
|---|---|
| Pendiente | No iniciado o sin evidencia. |
| En desarrollo | Trabajo de diseño o implementación iniciado. |
| Implementado | Código o documento disponible, aún no validado. |
| Pruebas parciales | Pruebas unitarias, simuladas o físicas parciales con evidencia identificada. |
| Validado | Se satisfacen los criterios aplicables con evidencia revisada y versión reproducible. |

Registrar los bloqueos como atributo adicional, no como sustituto del estado. Una prueba simulada no demuestra precisión, tiempo ni seguridad física. Una sección documental puede cerrarse sin hardware si no depende de mediciones reales. No asignar puntos de rúbrica por la mera existencia de archivos. Toda prueba debe indicar si es unitaria, simulada, física o integrada.

## 0.3. Requisitos transversales y vigencia

**Referencia técnica vigente (repositorio):** ROS 2 local (`ROS_DOMAIN_ID=8`, `ROS_LOCALHOST_ONLY=1`); entre máquinas MQTT, HTTP y SSH. Mensajes MQTT v1 con `ts` en segundos Unix y reloj NTP. Race Control posee el estado de carrera, el carrito su pose y la estación su estado. El carrito mide la pose; el brazo no usa cámara. Supervisor y puente MQTT son del curso. `twist_mux` arbitra el mando, vigilante de red del curso con parada tras 1,5 s de pérdida de broker. Acople ≤4 cm y ≤6°, máximo dos reintentos, objetivo de pit ≤10 s. Reset y escalas por `control_odometria` tras segunda medición.

**Referencia complementaria del HTML, mientras no sea sustituida:**

- Circuito nominal antihorario de 2 m por lado, zona 2,8 × 2,8 m; D1=(0,4;0,4), D2=(2,4;0,4), D3=(2,4;2,4), D4=(0,4;2,4) m; orientaciones nominales −90°, 0°, 90°, 180°. Confirmar marcos y geometría del montaje de cartón.
- E1 carga A roja; E2 retira A y coloca B verde; E3 retira B y coloca C azul; E4 retira C; retorno vacío a E1. Meta de cuatro vueltas y 16 servicios; cubos de 25 mm y hasta 30 g.
- AprilTag 36h11 de 60 mm, IDs 1–4; foco nominal ~28 cm. Los IDs 0–3 del repositorio son ejemplos, no la asignación de carrera.
- Límites nominales 0,20 m/s y 0,8 rad/s; referencia inicial 0,10 m/s y 0,5 rad/s. Giro y avance en lazo abierto compensado como punto de partida; cualquier cambio de estrategia debe respetar lo que indique el docente.
- Tanda de hasta 12 min, calentamiento 3 min; tres vueltas válidas para clasificar; objetivo cuatro válidas y cero intervenciones. Predicción firmada, informe de dos páginas, defensa y bono opcional de odometría visual: conservar mientras no se comunique sustitución.
- Red nominal GranPrix-ESAN, subred 192.168.50.0/24, Race Control .10, estaciones .21–.24, carrito eq08 .108; comprobar configuración y permisos reales. NTP: objetivo de desfase máximo 50 ms del HTML.

**Diferencias abiertas:** el HTML describe un equipo a la vez y cambio en 3 min, mientras Race Control admite varios equipos por tanda y el diseño SSH aún no resuelve el reparto de estaciones. No asumir carrera simultánea ni turno exclusivo permanente: obedecer autorizaciones reales. Evidencias: el repositorio prevé video, rosbag2 y CSV de eventos **por vuelta**; el HTML pedía cinco CSV y un bag de toda la tanda. Formato de entrega, rúbrica actualizada, tag/fork/submódulo y procedimiento de despliegue por confirmar. No duplicar grabador ni imponer `deploy.sh` como implementación del equipo.

## 0.4. Prioridades y recortes

| Nivel | Qué incluye | Criterio |
|---|---|---|
| P0 — cadena crítica | 1.1 mínima y parada, 1.2–1.5, 2.1–2.5 (2.2 según puerto), 2.6 seguridad mínima, 3.1, 3.2 pruebas virtuales mínimas, 3.3 y primera vuelta 3.4 | Sin ello no hay misión segura y válida |
| P1 — consolidación | 1.6 extensión y registros, 3.4 varias vueltas y robustez, 3.5 predicción, 3.6 evidencias, 3.7 entrega; compatibilidad de despliegue | Completar evaluación y estabilizar sistema; iniciar documentación y registros desde el primer día |
| P2 — opcional | Adaptación completa RC-1, más corridas, odometría visual, pulido visual | No sustituye requisitos básicos |

Recortes internos: cinco rectas y cinco giros iniciales por condición, ampliables si hay dispersión; adaptación completa del simulador ROS 2 de RC-1 solo si aporta valor; doble mínimo de odometría, tag y estación en P0. Usar `pc-race` para comunicación, no para validar movimiento. Primero funcionalidad del tablero; estética después. Odometría visual solo si hay margen tras una vuelta limpia.

**Puerta de decisión del día 3 (meta interna):** medir el doble intercambio E2 con brazo real y procedimiento autorizado, si hay acceso; usar supervisor cuando esté disponible. Si no cabe en el presupuesto de pit o no existe acceso, informar ese día al docente y registrar el bloqueo. No alterar límites de seguridad ni simular resultados para cumplir la meta.

## 0.5. Alcance oficial y estado de publicación

Fuente inspeccionada: `GranPrix-main.zip`, commit `285c82966a2de1d3b4eb39a64bad1415a14212db`. El README y los documentos `docs/arquitectura/00`–`04` fijan el reparto. No se acredita una validación de hardware.

| Componente | Dueño | Estado en el ZIP | Acción del Grupo 8 |
|---|---|---|---|
| `pc-race`, contrato MQTT v1, simulador de carritos | Curso | Código y tests disponibles | Instalar en entorno separado y probar |
| Herramienta `estacion/herramientas/herramienta_apriltag.py` | Curso | Código y ejemplos; cámara real pendiente | Reutilizar como base de visión |
| `control_odometria`, `camara_apriltag`, `maquina_pit` | Equipo (base de visión del curso) | Arquitectura, plantilla pendiente | Desarrollar lógica independiente |
| `granprix_msgs`, `puente_mqtt`, `vigilante_red`, `grabador` | Curso | Documentados, código pendiente | Integrar y verificar al publicarse |
| `tablero_web` | Curso + equipo | Base documentada, pendiente | Extender, no sustituir |
| `twist_mux` | Infraestructura ROS 2 | Previsto en arquitectura | Integrar y ensayar su configuración |
| `supervisor_estacion`, puerto `BrazoJetCobot` | Curso | Documentados, código pendiente | Consumir interfaz y verificar seguridad |
| `app_equipo`, `EstrategiaDeCambio`, `brazo_simulado` | Equipo sobre plantilla del curso | Firma de estrategia documentada, plantilla pendiente | Implementar estrategia, usar doble local en pruebas |
| Despliegue SSH/SFTP | Curso | Diseño, opciones A/B/C abiertas | Preparar artefacto compatible cuando se defina |
| Marcos y validador de evidencia | Por confirmar | No aparecen `dock_frames.yaml` ni validador en ZIP | Consultar; no fijar rutas ni esquemas ficticios |

Pruebas: la revisión anterior informó 42 pruebas de contrato, vueltas y ranking superadas y una ejecución parcial de la herramienta AprilTag (dependencias faltantes). La cifra de 126 pruebas superadas de la v1.2 no tiene un log adjunto en este documento; tratarla como no verificada aquí. Registrar comandos, versión, entorno y resultado de cualquier nueva ejecución.

Cambios vinculantes de arquitectura: solo el puente del curso comunica el ROSCar con MQTT; la aplicación de estación no habla con MQTT ni con el brazo directamente, usa el objeto `brazo` autorizado. Race Control no manda movimientos. No hay `id` ni `vuelta` en `SolicitudMsg`/`ResultadoMsg`; no hay motivo de error en `ResultadoMsg`, aunque `ResultadoCambio` de la estrategia documenta `error` opcional. `t_cambio` no es el tiempo total de pit. Solo banderas verde y roja en el contrato. `dth` está en grados; `dx`, `dy` en metros.

Riesgos: QoS 1 puede duplicar mensajes; no existe correlación inequívoca de solicitudes y respuestas repetidas. El carrito debe mantener telemetría durante el pit (monitor de latidos de Race Control, umbral 3 s). Los cuatro pits correctos deben pertenecer a la ventana de la vuelta reportada. El banco MQTT no verifica trayectoria física ni una manipulación real. Las preguntas sin resolver están en sección 9.

# Bloque 1 — Desarrollo del ROSCar

**Objetivo:** disponer de un carrito que navegue, mida su pose, corrija errores, se recalibre, coordine intercambios y registre su misión. Referencia oficial: secciones 2–4, 7–9.

## 1.1. Diagnóstico y caracterización del ROSCar

> **Alcance:** del equipo. Añadir al diagnóstico la versión de ROS 2 de la imagen del Pi5 y confirmar qué nodos del curso (`puente_mqtt`, `vigilante_red`, `grabador`) estarán en el robot cuando salga la plantilla.

**Actividades**

- 1.1.1 Preparar el repositorio y entorno ROS 2; comprobar distribución, agente microROS, workspace, dominio y método de acceso autorizado.
- 1.1.2 Inventariar nodos, tópicos, tipos, QoS, frecuencia y publicadores/suscriptores. Identificar los marcos TF y el driver de movimiento.
- 1.1.3 Comprobar encoders, IMU, cámara, LiDAR, batería y actuación. Verificar parada segura antes de mover.
- 1.1.4 Revisar la odometría instalada y parámetros de ruedas. No aplicar automáticamente parámetros históricos a un robot distinto. Evitar duplicar correctores o confundir corrección odométrica con escalas de mando.
- 1.1.5 Realizar rectas: primero desplazamientos pequeños en zona despejada; después 2 m a velocidad de referencia, si las condiciones son seguras.
- 1.1.6 Realizar giros: primero ángulos pequeños; después 90° en ambos sentidos cuando proceda. Medir giro físico y odométrico.
- 1.1.7 Repetir caracterización sobre la plataforma real de cartón; comprobar estabilidad, fricción, uniones, bordes y holguras. Las pruebas en otro piso son preliminares.
- 1.1.8 Confirmar responsable y materiales; fabricar/montar la cuna y ménsula si corresponde al equipo; fijar la cámara y coordinar la altura del tag de estación y **medir y declarar la altura real de la cuna** (9–12 cm). Sin la cuna montada no se pueden probar E1–E4 con el carrito real. Responsable: A, con C para el alcance.

**Orden flexible:** se permiten rectas y giros preliminares con cinta y referencia angular independiente, una vez verificada la parada. Para caracterización definitiva, contrastar con tag calibrado y referencias independientes, cuantificando incertidumbre; la precisión del tag (1.3.8) no bloquea el inicio de 1.1.5–1.1.6. La dispersión angular histórica de RC-1 es un antecedente, no una incertidumbre instrumental demostrada.

**Desarrollo:** recuperar utilidades de RC-0 y RC-1; utilizar `scripts/roscar_v01/preflight.sh` y los ensayos iniciales del ZIP v0.1 si ya fueron incorporados. Comandos de diagnóstico: `ros2 node list`, `ros2 topic list -t`, `ros2 topic info /cmd_vel -v`, `ros2 topic hz /odom`, `ros2 param dump /odom_corrector` (solo si existe). No cambiar la configuración del agente activo sin verificar compatibilidad. Registrar muestras físicas independientes de la odometría; proponer 5 rectas y 5 giros por condición (10 de cada uno es P2; el HTML no exige cantidad). Registrar giro comandado por tiempo, odometría, IMU y referencia externa para evaluar el ejecutor; no cambiar la estrategia de navegación sin confirmar requisitos. Calcular sesgo, dispersión, error lateral y retardo; identificar condiciones de ensayo. Confirmar el tipo del tópico de batería: en retos previos existió `/battery`, no asumir que ya existe `/battery_state`.

**Archivos:** `diagnostico.py`, `odom_utils.py`, `preflight.sh`, `prueba_recta.py`, `prueba_giro.py`, `wheel_params_g8.yaml` si corresponde al robot verificado. **Resultados:** `diagnostico_roscar.md`, `rectas.csv`, `giros.csv`, `caracterizacion.yaml`, bags y gráficos en `experimentos/bloque_01_roscar/1.1/`.

**Sin robot:** scripts, cálculos y plantillas. **Dependencias para cerrar:** ROSCar asignado, superficie final, medición física. **Cierre:** hardware y parada verificados, datos reproducibles y parámetros medidos con incertidumbre identificada.

## 1.2. Planificación y ejecución de movimiento

> **Alcance:** `control_odometria` (equipo). El ejecutor publica en la entrada autorizada de `twist_mux` (nombre por confirmar); el `vigilante_red` del curso tiene prioridad máxima vía `/cmd_vel_vigilante`. `twist_mux` es la salida final a `/cmd_vel`. Verificar expiración de comandos y parada real con la plantilla; el timeout por sí solo no garantiza que se publique cero ni que el firmware frene.

- 1.2.1 Cargar coordenadas y orientaciones de docks desde configuración, reemplazable por la oficial.
- 1.2.2 Calcular el tramo desde la pose creída: `dx = x_dock - x`, `dy = y_dock - y`, `L = hypot(dx, dy)`.
- 1.2.3 Calcular `phi = wrap(atan2(dy, dx) - theta)`; normalizar ángulos y tratar destinos coincidentes sin giro arbitrario.
- 1.2.4 Ejecutar giros en lazo abierto con `phi_cmd = phi/ca`.
- 1.2.5 Ejecutar avances en lazo abierto con `L_cmd = L/cd`.
- 1.2.6 Aplicar escalas positivas, finitas y verificadas, límites de velocidad y temporización monotónica; registrar comandos realmente ejecutados.
- 1.2.7 Validar trayectorias, signos de giro, tiempos y parada.

**Desarrollo:** separar matemáticas puras de ROS 2. Probar el cálculo de los cuatro tramos nominales, poses perturbadas, ángulos cercanos a ±π y entradas inválidas. Implementar el ejecutor con duración y publicación periódica, en la entrada autorizada del multiplexor, sin publicar directamente en `/cmd_vel`; abortar ante fallos, sin depender de un PID de RC-1 para la navegación principal. Validar con doble mínimo de movimiento; RC-1 es opcional. Antes de pruebas físicas autorizadas comprobar parada real, caducidad y ausencia de otros mandos. No habilitar movimiento real por defecto.

**Archivos:** `control_odometria/planificador.py`, `ejecutor.py`, `odometria.py`, `movimiento.yaml`, `test_planificador.py`, `test_ejecutor.py`. **Resultados:** trayectorias, CSV de órdenes y tiempos, errores de llegada, pruebas unitarias y bags. **Sin robot:** casi toda la lógica y simulación. **Cierre:** tramo simulado y físico repetible, con compensación correcta y límites respetados. Depende de 1.1 y 1.5 para ensayos físicos; de 1.3–1.4 para el funcionamiento adaptativo.

## 1.3. Visión artificial y localización

> **Alcance:** `camara_apriltag` es del equipo con una base del curso. Punto de partida: `estacion/herramientas/herramienta_apriltag.py` (usa `pupil-apriltags`; su pose es respecto a la cámara y `dth` en grados). **Falta probarla con cámara real** (lo dice el propio repositorio). El paso al marco del dock depende de `dock_frames.yaml`, que aún no existe. Salida prevista: `/tag/pose` (`geometry_msgs/PoseStamped`). El módulo de geometría del dock sigue siendo útil, porque la estrategia de la estación compone la pose recibida con la geometría del brazo.

- 1.3.1 Captura de imágenes con propietario único de la cámara, marcas de tiempo y distribución de cuadros al detector y grabador.
- 1.3.2 Calibración intrínseca (matriz K y distorsión) de la cámara real.
- 1.3.3 Calibración extrínseca cámara–base del ROSCar; fijar orientación del soporte si es móvil.
- 1.3.4 Detectar AprilTags auténticos de familia 36h11, IDs 1–4, lado 0,06 m.
- 1.3.5 Estimar pose con `pupil-apriltags` o `apriltag_ros` (alternativas del repositorio). `solvePnP` es alternativa si se justifica o lo exige el docente. Verificar correspondencia de esquinas, profundidad, calidad/reproyección según método y frescura; rechazar mediciones inválidas.
- 1.3.6 Convertir la pose al marco del dock para obtener `(dx, dy, dtheta)` en m y rad, usando el convenio oficial.
- 1.3.7 Diseñar y probar el cálculo de reset `map → odom` según REP-105; su aplicación y único publicador TF corresponderán a `control_odometria`, coordinado por `maquina_pit`. No reiniciar arbitrariamente `odom → base`.
- 1.3.8 **Medir la precisión de la pose del tag a ≈28 cm contra cinta** (posición y ángulo, varias poses e iluminaciones) y publicar el resultado. Es una referencia para caracterización definitiva de 1.1 y 1.4; B prioriza su validación, sin bloquear pruebas preliminares con instrumentos independientes.

**Desarrollo:** empezar con imágenes sintéticas, tags válidos impresos y cámara de laptop; utilizar parámetros sintéticos únicamente para pruebas. Verificar transformaciones con poses conocidas. Con convención `T_A_B` que transforma coordenadas de B a A, `T_map_odom = T_map_base_medido @ inv(T_odom_base)` para el mismo instante. Identificar el marco base real (`base_link` o `base_footprint`) y el publicador de TF para evitar duplicidades. En laboratorio medir con la cámara final, validar enfoque a ~28 cm y repetir con distintas poses e iluminaciones. No usar `/sim/pose` como si fuera un tag real: es una medición emulada en simulación.

**Archivos:** `camara_apriltag/camara.py`, `detector.py`, `estimacion_pose.py`, `camara.yaml`, tests de visión y transformaciones; `control_odometria/reset_pose.py`. Las transformaciones **no se duplican**: viven en el módulo compartido `geometria_dock/transformaciones.py` (ver 6), con la convención de signos acordada con C en 2.4. **Resultados:** calibración de cámara, imágenes anotadas, CSV de error visual, TF y `/tag/pose`; confirmar mensajes adicionales de evidencia al publicarse la plantilla. **Cierre:** ID y pose comprobados contra referencias físicas; precisión suficiente para decidir tolerancia con margen, sin falsas aceptaciones conocidas en el conjunto de prueba. Dependencia: geometría final y contrato de marcos (3.1).

## 1.4. Acople fino y calibración adaptativa

> **Alcance:** es nuestro. El repositorio asigna el acople, la solicitud y el reset a `maquina_pit`, y las escalas `cd` y `ca` a `control_odometria`. Secuencia del repositorio: medir, corregir hasta ≤ 4 cm y 6°, publicar la solicitud, esperar el resultado, **medir otra vez**, reset y recalibración, salir. Incluir esa segunda medición en el presupuesto total de 10 s; confirmar cómo se define el error posterior para la rúbrica.

- 1.4.1 Evaluar `hypot(dx, dy) ≤ 0.04` y `abs(wrap(dtheta)) ≤ 6°`.
- 1.4.2 Diseñar control proporcional de acople realizable por tracción diferencial (giros y avances, no movimiento lateral directo); comprobar zona libre y límites.
- 1.4.3 Medir nuevamente después de cada corrección, hasta dos reintentos; si no converge o vence el plazo, detener y marcar FALLA.
- 1.4.4 Estimar escala de distancia `cd = distancia_medida / distancia_comandada`.
- 1.4.5 Estimar escala de giro `ca = giro_medido / giro_comandado`, con signos y ángulos coherentes.
- 1.4.6 Actualizar cada escala por filtro exponencial `c_nueva = c_anterior + alpha*(c_medida - c_anterior)`; limitar variaciones y rechazar observaciones sin movimiento suficiente o inválidas.
- 1.4.7 Evaluar convergencia, ruido, número de reintentos y reducción del error antes/después.

**Desarrollo:** conservar tres mediciones actuales (preacople, postacople para la solicitud, postintercambio para reset) y la pose visual de salida del pit anterior; guardar movimientos comandados por separado; estimar el tramo anterior sin mezclar las correcciones del acople. No actualizar la escala de giro con comandos casi nulos ni aplicar doble compensación al driver. Probar α=0,35 como referencia inicial del HTML, no como ajuste definitivo. Probar errores de posición, ángulo, tag ausente, dos reintentos fallidos y escalas anómalas. Medir antes y después con el mismo criterio; no introducir correcciones innecesarias solo para mejorar una métrica.

**Archivos:** `maquina_pit/acople.py`, `control_odometria/calibracion.py`, `calibracion.yaml`, `test_calibracion.py`, `test_acople.py`. **Resultados:** registros de calibración (tópico definitivo pendiente), errores antes/después, escalas por pit, reintentos y gráficos. **Cierre:** acople físico válido, reset comprobado (1.3), estimador estable y evidencia de mejora; la evaluación oficial exige reducción del error en ≥70 % de paradas y convergencia. Consultar al docente cómo se contabilizan paradas ya dentro de tolerancia. Depende de 1.2, 1.3 y 1.5 para cierre integrado.

## 1.5. Autonomía y seguridad

**Alcance:** del equipo: lógica de misión y `maquina_pit`. Del curso: `puente_mqtt`, `vigilante_red`, mensajes propios y base de lanzamiento. Arbitraje con `twist_mux`. No programar reemplazos definitivos; se permiten dobles de prueba aislados.

- 1.5.1 Máquina de estados: espera, NAVEGANDO, ACOPLANDO, ESPERANDO, INTERCAMBIO, SALIENDO, FALLA y fin (nombres internos propuestos, no estados MQTT).
- 1.5.2 Gestionar vuelta, sector y estación; cuatro servicios por vuelta y retorno vacío tras E4.
- 1.5.3 Gestionar pieza; actualizar solo ante resultado válido y compatible con el estado esperado.
- 1.5.4 Plazos por estado y pit global ≤10 s, final de misión según autorización y reglas vigentes.
- 1.5.5 Integrar y comprobar el vigilante oficial (pérdida del broker 1,5 s, prioridad de parada); comprobar bandera roja, frescura de comandos y caducidad de entrada del multiplexor. No crear un vigilante MQTT paralelo.
- 1.5.6 Integrar parada de emergencia y órdenes de tablero según plantilla; inhibir arranques sin autorización y reanudación inesperada. Verificar parada de bajo nivel ante caída del controlador; consultar al docente si hace falta mecanismo adicional autorizado.
- 1.5.7 Probar fallos, mensajes duplicados, atrasados, reinicios y resultados inciertos; registrar intervenciones mediante interfaces del curso.

**Desarrollo:** FSM pura con reloj inyectable, entradas de pose, turno, orden y resultado; salida de intención de movimiento/solicitud y estado. Usar un adaptador ROS local cuando exista `granprix_msgs`. Mantener velocidad cero durante manipulación; no salir ante timeout o estado incierto. `twist_mux` es único publicador final hacia el driver; comprobar si al caducar una entrada realmente se emite cero y si el robot frena. No confiar solo en un proceso ROS para proteger ante caída total del Pi5 o firmware que conserva la última orden. Ensayar fallos físicos solo con autorización, espacio despejado, parada física disponible y un único controlador.

**Archivos del equipo:** `maquina_pit/estados.py`, `mision.py`, tests de FSM, seguridad y adaptadores locales. **Infraestructura oficial a integrar:** `puente_mqtt`, `vigilante_red`, `twist_mux`. **Resultados:** trazas de transiciones, matriz de fallos, tiempos de parada, eventos y versión/configuración del ensayo. **Sin robot:** lógica y pruebas con dobles. **Cierre:** autorización, parada física y transiciones verificadas; no se da por validada la seguridad hasta probar los componentes oficiales. Depende de 3.1 y disponibilidad de la plantilla.

## 1.6. Tablero web y registro local

**Alcance:** base `tablero_web` y `grabador` del curso, todavía no publicados. El equipo extiende el tablero y verifica evidencias. Responsable E con apoyo del subgrupo carrito. P1, pero registrar pruebas desde el inicio.

- 1.6.1 Verificar servidor local y puerto/URL definidos en plantilla (8080 y .108 son referencia del HTML).
- 1.6.2 Integrar Iniciar, reiniciar y declaración de intervención mediante `/granprix/orden`; validar autorización y parada. Controles adicionales del HTML se incorporan si siguen vigentes.
- 1.6.3 Mostrar métricas de nuestro control: pose, escalas, pieza, velocidad, batería y latencia cuando estén disponibles; no inventar campos MQTT ni unidades.
- 1.6.4 Extender cronómetro, vueltas, sectores, pit, errores y estados usando fuentes oficiales. Bandera MQTT solo verde/roja; colores de tiempos de vuelta son presentación local, no nuevas banderas.
- 1.6.5 Verificar registro de intervenciones y eventos, coherente con Race Control.
- 1.6.6 Comprobar registros de `grabador` por vuelta; determinar con el docente si se requieren exportaciones adicionales del HTML.
- 1.6.7 Verificar video por vuelta y condiciones de acceso/almacenamiento; confirmar resolución, fps, overlay y transmisión en vivo exigidos.

**Desarrollo:** prototipo de extensión con datos marcados como simulados; adaptar a la base oficial, no desarrollar servidor o grabador sustituto. El repositorio describe MP4, rosbag2 y CSV de eventos por vuelta; el HTML describe cinco CSV y bag de toda la tanda. Mantener pruebas de rendimiento, disco y marcas de tiempo; no bloquear control ni percepción. Telemetría MQTT hasta 5 Hz; actualización de tablero ≥2 Hz es referencia HTML a confirmar.

**Archivos propuestos:** `tablero_extension/` (componentes y métricas que falten), tests de permisos y verificación de registros. **Resultados:** capturas, trazas, inventario de archivos y comparación con especificación vigente. **Cierre:** extensión operativa con datos reales, controles seguros, evidencias verificadas; cierre integral en 3.6. No crear `web_server.py` o grabador propio como producto definitivo antes de ver la plantilla.

# Bloque 2 — Desarrollo del JetCobot

**Objetivo:** un programa de estación parametrizable en cuatro roles, seguro, capaz de compensar la pose de la cuna y realizar intercambios. No se requieren cuatro programas independientes. Referencia oficial: secciones 2–4, 7, 10–11.

## 2.1. Diagnóstico y caracterización del JetCobot

> **Alcance:** diagnóstico y medición del equipo. Acceso a Jetson durante desarrollo por confirmar; Race Control tiene un diseño de despliegue SSH aún sin código.

- 2.1.1 Acceder a Jetson por el método autorizado; inventariar entorno y versiones.
- 2.1.2 Comprobar API, driver y comunicaciones, inicialmente de solo lectura.
- 2.1.3 Leer articulaciones y coordenadas reales; no asumir HOME ni articulaciones a cero.
- 2.1.4 Verificar pinza, apertura/cierre y capacidad de detectar agarre.
- 2.1.5 Identificar límites y restricciones del fabricante, supervisor y puerto oficial cuando estén disponibles.
- 2.1.6 Inspeccionar espacio de trabajo, fijaciones, plataforma de cartón y alcance de la cuna.
- 2.1.7 Confirmar con el docente **cuántas horas y qué ventanas de acceso a los brazos** tiene el equipo antes de la tanda, y el método de acceso a las Jetson. De esto depende el ritmo de todo el bloque 2.

**Desarrollo:** reutilizar rutinas de diagnóstico del Reto 1, no copiar posiciones históricas como seguras. Confirmar modelo y hardware de cada brazo. Ensayar movimiento solo bajo control autorizado y protecciones del curso. **Archivos:** `diagnostico.py`, `preflight_jetcobot.sh`, `estacion.yaml`. **Resultados:** inventario, lecturas iniciales, fotos del montaje y tabla de alcance. **Cierre:** hardware y pinza operativos con límites conocidos; dimensiones reales verificadas.

## 2.2. Cinemática y planificación de movimientos

**Alcance:** la aplicación usa únicamente el objeto `brazo` (puerto `BrazoJetCobot`). Su firma de `mover` no está publicada. IK y MoveIt2 no son obligaciones confirmadas de la app bajo la nueva arquitectura: el alcance depende del puerto y de la indicación del docente. No usar acceso directo al actuador en la aplicación final.

- 2.2.1 Revisar marcos, unidades, parámetros DH y límites disponibles.
- 2.2.2 Contrastar URDF con hardware si resulta necesario para planificación.
- 2.2.3 Recuperar FK como referencia y verificar consistencia de posiciones.
- 2.2.4 Si el puerto requiere objetivos articulares, evaluar IK con límites, singularidades y soluciones inválidas; si es cartesiano, comprobar poses y restricciones del adaptador.
- 2.2.5 Integrar MoveIt2 solo si la interfaz o el docente lo exige; no crear un camino que eluda al supervisor.
- 2.2.6 Validar aproximación, retirada, trayectorias seguras y poses alcanzables.

**Antecedentes y riesgos:** la auditoría interna anterior señala que Reto 2 tiene FK y evalúa IK de firmware; el Gran Reto tiene FK DH/URDF/PoE y un envoltorio MoveIt2 no validado integralmente en hardware. Las discrepancias históricas de FK y URDF, tablas DH distintas y tests fallidos son antecedentes reportados, no mediciones nuevas; consultar registros originales antes de reutilizar. No asumir que exista IK propia validada.

**Desarrollo:** separar cálculo de objetivos y ejecución por puerto; probar con un doble de brazo que registre órdenes y fallos. Si `mover` es cartesiano, priorizar poses compensadas y trayectorias; si es articular, determinar necesidad de IK y planificación. Usar m/rad internamente, convertir en el borde según la firma real. No ejecutar `send_coords` directo salvo pruebas de laboratorio expresamente autorizadas, fuera de la app de competencia y sin eludir protecciones.

**Archivos:** `app_equipo/posiciones.py`, `cinematica.py` y `integration_moveit.py` solo si corresponden; tests de poses/trayectorias y doble de brazo. **Resultados:** tabla de alcance, errores, unidades y trayectorias validadas. **Cierre:** objetivos y ejecución compatibles con puerto oficial, límites y montaje; IK/MoveIt2 únicamente si se confirma su necesidad. **Bloqueo:** firma del puerto, geometría y acceso físico.

## 2.3. Manipulación de piezas

> **Alcance:** es el centro del trabajo de la estación. Se programa dentro de `EstrategiaDeCambio`, y devuelve `ResultadoCambio` (`ok`, `pieza_dejo`, `t_cambio`, `error` opcional); el supervisor publica `ResultadoMsg`, que hoy no tiene campo `error`. E2 y E3 hacen retirar y colocar en un mismo pit; el pit total son 10 s, incluida la latencia del supervisor y del contrato.

- 2.3.1 Calibrar apertura y cierre de pinza para cubos de 25 mm.
- 2.3.2 Diseñar Pick & Place: aproximar, agarrar, elevar, trasladar, depositar y retirar de forma segura.
- 2.3.3 Confirmar agarre y liberación por señales disponibles y verificación experimental; no devolver éxito si falló la operación.
- 2.3.4 Calibrar posiciones de almacenes y bandejas de recepción, índices de piezas por vuelta y zonas de retirada.
- 2.3.5 Cronometrar carga, descarga y doble intercambio de E2/E3.
- 2.3.6 Optimizar trayectorias dentro de límites autorizados, no incrementar velocidad para eludir el supervisor.

**Desarrollo:** reutilizar secuencias parametrizables del Reto 1 y Gran Reto Parcial; introducir resultados estructurados, fallos y timeout. Probar cada fase primero con objetivos conocidos; luego el ciclo completo. E2 y E3 son críticos porque retiran una pieza y colocan otra. Medir desde las fases iniciales: el pit global es 10 s, no hay 10 s exclusivos para el brazo. Si el presupuesto resulta inviable, informar al docente antes de asumir que se pueden cambiar límites o geometría.

**Archivos:** `pick_and_place.py`, `control_pinza.py`, `almacenes.yaml`, `manipulacion.yaml`. **Resultados:** `tiempos_manipulacion.csv`, videos experimentales, tasa de éxito y fallos. **Cierre:** carga/descarga/intercambio repetibles y confirmados, con retirada segura de la zona de paso; tiempo compatible con el presupuesto medido de 3.3.

## 2.4. Compensación de pose de la cuna

> **Alcance:** la estrategia recibe `PoseDock` (`dx`, `dy` en m y `dth` en grados, ya en el marco del dock). La compensación y el offset de la cuna se componen dentro de la estrategia. El brazo no usa cámara (decisión D3): la pose geométrica procede del carrito; la estrategia comprueba agarre y liberación por las señales autorizadas disponibles. Falta la transformación dock–brazo (`dock_frames.yaml`).

- 2.4.1 Definir marcos base del brazo, dock, base ROSCar y cuna.
- 2.4.2 Obtener transformación dock–brazo del archivo oficial.
- 2.4.3 Medir transformación ROSCar–cuna considerando ménsula derecha y altura declarada.
- 2.4.4 Convertir `(dx, dy, dtheta)` a pose de recogida/depósito compensada.
- 2.4.5 Verificar límites de alcance, altura, aproximación y colisiones.
- 2.4.6 Probar posiciones nominales y extremos admitidos, con ROSCar real o plantilla física equivalente autorizada.

**Desarrollo:** adoptar el convenio `T_B_C = T_B_D @ T_D_R @ T_R_C`, siendo B base del brazo, D dock, R ROSCar y C cuna. Acordar signos con 1.3 y 3.1; comprobar transformaciones con casos sintéticos y extremos de ±4 cm/±6°. El montaje de cartón cambia potencialmente la altura relativa: no confiar solo en cotas nominales. Si la pose está fuera de tolerancia o alcance, no iniciar manipulación.

**Archivos:** `compensacion_pose.py`, `test_compensacion.py`, configuración de cuna. Importa `geometria_dock/transformaciones.py` (módulo único compartido con 1.3; B y C acuerdan la convención de signos y escriben las pruebas con **los mismos casos** para ambos lados). Un signo distinto entre el carrito y el brazo hace que el brazo corrija en sentido contrario. **Resultados:** matriz de casos, errores de compensación, fotos y tiempos. **Cierre:** depósito y recogida seguros y correctos en el rango operativo medido. Depende de geometría y marcos definitivos; se puede iniciar con poses ficticias.

## 2.5. Aplicación del equipo y estrategia de cambio

**Alcance:** el equipo desarrolla `app_equipo` con una estrategia parametrizable para los cuatro roles. El supervisor del curso gestiona MQTT, autorización, estados, tolerancias, congelación y publicación del resultado; la app no accede directamente al broker o hardware. Firma documentada (no plantilla ejecutable):

```python
class EstrategiaDeCambio(Protocol):
    def cambiar(self, pose: PoseDock, pieza_trae: Pieza | None) -> ResultadoCambio: ...
```

- 2.5.1 Implementar la estrategia y su configuración de rol; confirmar cómo se inyectan `brazo`, dock, rol y ranura de bandeja (no están en la firma de `cambiar`).
- 2.5.2 E1: carga A en carrito vacío.
- 2.5.3 E2: retira A y carga B.
- 2.5.4 E3: retira B y carga C.
- 2.5.5 E4: descarga C y deja vacío.
- 2.5.6 Validar pieza esperada, pose/alcance y condiciones propias de manipulación; no sustituir validación de turno del supervisor.
- 2.5.7 Devolver `ResultadoCambio` con éxito real, pieza dejada, tiempo y error opcional; no publicar MQTT desde la app.
- 2.5.8 Ensayar los cuatro roles con doble de brazo, fallos, tiempos y secuencia de inventario; verificar comportamiento con supervisor oficial ante solicitudes repetidas o inciertas.

**Desarrollo:** aislar estrategia, compensación y secuencias de manipulación; usar el objeto `brazo` inyectado. Conservar resultado de cada fase y no devolver éxito si hubo agarre fallido o pieza incorrecta. No repetir automáticamente una operación física de resultado desconocido. Los estados oficiales del supervisor son `LIBRE`, `ESPERANDO`, `CAMBIANDO`, `LISTA`, `OFFLINE`. La deduplicación y autorización son responsabilidades de infraestructura; comprobarlas en integración, sin inventar ID MQTT ni programar un worker/supervisor alternativo.

**Archivos:** `app_equipo/estrategia.py`, `roles.py`, `pick_and_place.py`, `compensacion_pose.py`, `roles.yaml` provisional. **Resultados:** tests por rol, registros de operaciones, tasas de éxito y fallos, pruebas con doble y supervisor. **Cierre:** cuatro roles correctos, compatibles con la interfaz publicada y verificados de forma segura en hardware. Depende de 2.3, 2.4, 2.6 y 3.1; se puede iniciar sin ROSCar real.

## 2.6. Compatibilidad, seguridad y validación de la aplicación

**Alcance:** el supervisor y puerto `BrazoJetCobot` son del curso. El supervisor congela el brazo y gestiona bandera roja, pérdida del broker >3 s, timeout y excepciones. El equipo debe producir una estrategia segura y verificable, no implementar un supervisor paralelo. Despliegue SSH/SFTP de Race Control en diseño, sin código; opciones A/B/C pendientes. La opción B del documento 04 es una hipótesis, no decisión definitiva.

- 2.6.1 Verificar que toda orden de la estrategia pasa por el puerto oficial y respeta las restricciones.
- 2.6.2 Ensayar bandera roja, timeout y pérdida de broker con supervisor oficial y autorización; no reanudar por cuenta propia.
- 2.6.3 Comprobar límites, zonas libres, velocidad, alcance y retirada, según interfaz y montaje reales.
- 2.6.4 Gestionar agarre fallido, excepciones y resultados inciertos; devolver fallo y no iniciar maniobras no autorizadas.
- 2.6.5 Preparar la carpeta entregable de `app_equipo`, dependencias y configuración reproducibles cuando se publique la plantilla; no escribir `deploy.sh` o servicios systemd como infraestructura oficial.
- 2.6.6 Colaborar con pruebas de despliegue en las cuatro estaciones mediante Race Control cuando esté disponible; registrar versión, rol, tiempo y fallos.

**Desarrollo:** pruebas con doble del puerto, luego hardware autorizado bajo supervisor. No modificar supervisor ni credenciales, no usar API directa en la app. Ante un estado incierto, no repetir acciones ni permitir salida del carrito hasta confirmar seguridad. El límite de tiempo de cambio del supervisor es un parámetro aún por definir; la estrategia debe contribuir al objetivo de pit total ≤10 s.

**Archivos:** pruebas de `app_equipo`, doble `brazo_simulado` propio de laboratorio hasta recibir el oficial, documentación de dependencias y entrega. **Resultados:** matriz de seguridad, pruebas de fallo, registro de despliegue realizado por el curso. **Cierre:** estrategia compatible, seguridad mínima validada antes de operar y despliegue verificado cuando exista. Bloqueos: supervisor, puerto, plantilla, método de acceso y despliegue.

# Bloque 3 — Integración del sistema GranPrix

**Objetivo:** garantizar compatibilidad entre módulos desde el primer día y progresar desde pruebas virtuales hasta la carrera real. Referencia oficial: secciones 2–12.

## 3.1. Arquitectura, red y contrato de comunicación

**Alcance:** adoptar sin modificar `pc-race/contrato/modelos.py`, `topicos.py`, `esquemas.py` y `docs/arquitectura/00-contrato-mqtt.md`. El equipo no escribe puentes MQTT finales: usa las interfaces locales del curso. Los clientes MQTT propios son exclusivamente de laboratorio.

- 3.1.1 Documentar interfaces, propietario de cada dato, marcos, unidades y tiempos.
- 3.1.2 Configurar red de pruebas aislada; confirmar red oficial y direcciones de 0.3.
- 3.1.3 Levantar Mosquitto local y respetar ACL y credenciales del entorno autorizado.
- 3.1.4 Validar datos contra modelos/esquemas oficiales, adaptar nombres y unidades; no agregar campos al contrato por iniciativa propia.
- 3.1.5 Configurar identidad eq08 y aislamiento ROS 2 local.
- 3.1.6 Integrar turno, estado y bandera desde el puente oficial; ensayar mensajes válidos e inválidos en local.
- 3.1.7 Sincronizar reloj NTP y usar `ts` (segundos Unix) para mensajes; reloj monotónico para duraciones.

### Contrato MQTT v1 vigente en el commit revisado

Todos los modelos heredan `v` (predeterminado 1) y `ts`. La tabla distingue campos de mensaje de contenido de `pose`; consultar el código para tipos, opcionalidad y validaciones.

| Tópico | Publica | QoS | Retenido | Campos además de v, ts |
|---|---|---:|---|---|
| `granprix/carrera/estado` | Race Control | 1 | Sí | `tanda`, `fase`, `equipos`, `t_carrera` |
| `granprix/carrera/bandera` | Race Control | 1 | No | `bandera` (verde/roja) |
| `granprix/estacion/<n>/turno` | Race Control | 1 | Sí | `equipo` (o null) |
| `granprix/estacion/<n>/estado` | Supervisor | 1 | Sí | `estado` |
| `granprix/estacion/<n>/solicitud` | Puente del carrito | 1 | No | `equipo`, `dock`, `pose` (dx, dy, dth), `pieza_trae` |
| `granprix/estacion/<n>/resultado` | Supervisor | 1 | No | `equipo`, `ok`, `pieza_dejo`, `t_cambio` |
| `granprix/eq08/turno` | Race Control | 1 | Sí | `autorizado`, `tanda` |
| `granprix/eq08/telemetria` | Puente del carrito | 0 | No | `equipo`, `pose`, `bateria`, `velocidad` (hasta 5 Hz) |
| `granprix/eq08/evento` | Puente del carrito | 1 | No | `equipo`, `tipo`, `subtipo`, `declarada`, `estacion` |
| `granprix/eq08/vuelta` | Puente del carrito | 1 | No | `equipo`, `numero`, `t_inicio`, `t_fin`, `estaciones` (opcional) |

`pose` de telemetría es un diccionario de números sin claves fijadas. `tipo` de evento: `intervencion`, `pit_ok`, `reintento`; intervención requiere `subtipo` (`fisica`, `web`, `teleoperacion`, `software`). El modelo acepta extras ignorándolos; eso no convierte extras en campos del contrato. `SolicitudMsg`/`ResultadoMsg` no incluyen `id` ni `vuelta`, y `ResultadoMsg` no incluye motivo. La pose de solicitud usa m y grados; cálculos internos m/rad. Ejemplo ilustrativo de solicitud (no enviar al broker oficial):

```json
{"v":1,"ts":1795520000.0,"equipo":8,"dock":2,"pose":{"dx":0.021,"dy":-0.012,"dth":1.8},"pieza_trae":"A"}
```

### Entornos y compatibilidad

`pc-race/pyproject.toml` exige Python ≥3.12; el contrato usa `StrEnum` (Python ≥3.11) y Pydantic 2.6+. ROS 2 Humble habitual usa Python 3.10; verificar la imagen real del Pi5. No reemplazar Python del sistema ni forzar importación directa en Humble. Usar entorno 3.12 independiente para Race Control y pruebas de contrato; generar JSON Schema allí y usarlo para validación de fixtures/adaptadores de prueba compatibles. La adaptación ROS/MQTT final la entrega el curso. No modificar modelos para hacerlos compatibles unilateralmente.

**Archivos:** `docs/arquitectura.md`, `docs/interfaces.md`, `integracion/configuracion/mqtt.yaml`, `tests/integracion/test_contrato.py`. **Pruebas:** autorización, tipos, QoS, reloj, latidos (3 s para OFFLINE), duplicados, mensajes atrasados, bandera roja y aislamiento. **Cierre:** contrato v1 adoptado, esquemas y entorno registrados, interoperabilidad verificada con componentes oficiales cuando estén publicados. No publicar pruebas en Race Control oficial sin permiso.

## 3.2. Entorno de simulación y pruebas independientes

**Alcance:** reutilizar el banco oficial `pc-race` y `simulador_carritos.py`; no reescribir Race Control. Distinguir tres niveles de simulación: HTML (modelo matemático/predicción, 3.5), movimiento (doble de odometría/tag, RC-1 opcional), comunicación (Race Control local). El simulador de carritos genera poses aleatorias, tiempos ficticios y estaciones que devuelven B en todos los roles; no valida trayectoria, acople, secuencia de piezas ni seguridad real.

- 3.2.1 (P2) Recuperar/adaptar el simulador ROS 2 RC-1 si aporta valor; verificar Ubuntu/Humble.
- 3.2.2 (P0) Preparar doble mínimo de movimiento, odometría y pose visual con ruido, signos y tiempos controlables. No confundir `/sim/pose` con tag físico.
- 3.2.3 (P0) Probar cuatro roles con doble de estación y de brazo; reemplazar adaptadores por oficiales cuando estén disponibles.
- 3.2.4 (P0) Instalar y ejecutar `pc-race` en entorno Python ≥3.12; usar su tablero del juez y simulador para verificar tráfico y ledger.
- 3.2.5 Ejecutar Mosquitto local, aislado del broker del curso.
- 3.2.6 Probar solicitudes, resultados y vueltas contra modelos oficiales; verificar nuestras transiciones con dobles que sí implementen roles y fallos.
- 3.2.7 Inyectar retardos, pérdida de tag/broker, mensajes duplicados/atrasados, resultado erróneo, turno incorrecto y bandera roja.

**Desarrollo:** pruebas unitarias deterministas y reloj inyectable antes de hardware. Los clientes falsos no mueven robots ni prueban la lógica física. Seguir `pc-race/README.md`; instalar dependencias en entorno separado. Registrar resultados de tests sin asumir que todas las pruebas pasaron. No conectar simuladores a infraestructura de competencia.

**Archivos:** `integracion/simuladores/pose_simulada.py`, `estacion_simulada.py`, `brazo_simulado.py` (dobles provisionales), `integracion/clientes_prueba/`, tests y fixtures. No crear `sim_race_control.py` como sustituto. **Resultados:** logs MQTT, trazas de FSM, trayectorias simuladas, matriz de fallos. **Cierre:** comunicación local con Race Control y flujo de los cuatro roles reproducibles; validar compatibilidad oficial al recibir supervisor y plantilla.

## 3.3. Integración del pit

> **Alcance:** `t_cambio` del resultado mide solo el cambio de pieza. **El tiempo del pit (frenado a arranque) lo medimos nosotros** con marcas propias, incluyendo acople, MQTT, supervisor, estrategia, segunda medición, reset y recalibración.

- 3.3.1 Solicitud MQTT al llegar y detenerse; una sola solicitud en vuelo; registrar equipo, estación, tiempo y contexto local de vuelta. No existe ID de correlación en el contrato v1.
- 3.3.2 Transferencia de pose visual con marcos y unidades comunes.
- 3.3.3 Confirmación de tolerancia tras acople y reintentos; no enviar solicitud de manipulación fuera del rango válido.
- 3.3.4 Intercambio de pieza por estación, ROSCar inmóvil y brazo bajo control del supervisor.
- 3.3.5 Validar equipo, estación (tópico), estado de espera, frescura y pieza esperada; evitar transición duplicada. Confirmar zona libre según interfaz oficial; fallo o ambigüedad implica parada, no salida a ciegas.
- 3.3.6 Reset de pose y recalibración con datos anteriores al reacople; siguiente tramo desde pose medida.
- 3.3.7 Medir tiempo total desde frenado hasta arranque, incluyendo detección, acople, comunicación, manipulación, segunda medición, reset y recalibración.

**Desarrollo:** comenzar con un pit virtual, luego ROSCar real + estación simulada o cliente simulado + brazo real, finalmente ambos reales. Definir presupuesto temporal medido por fase; priorizar E2/E3. Mantener plazo global incluso con reintentos; al vencer, detener de forma segura y reconciliar el estado del brazo. Registrar un identificador interno de ensayo si sirve para evidencia, sin añadirlo al MQTT. Filtrar resultados atrasados y duplicados por contexto/ts; esto no garantiza correlación inequívoca. Si no puede distinguirse una respuesta antigua, no aceptar ni repetir manipulación automáticamente; consultar política del supervisor. No aproximar robots activos antes de verificar holgura y alcance. **Archivos:** `test_pit_integrado.py`, `scripts/integracion/prueba_pit.sh`. **Resultados:** `pits_prueba.csv`, cronometraje por fase, mensajes, video y reducción del error. **Cierre:** pit físico válido y seguro en ≤10 s con operación correcta y salida autorizada, repetido en los roles aplicables. No exige terminar previamente todas las pruebas independientes.

## 3.4. Integración de la carrera

> **Alcance:** Race Control aporta tablero del juez, ledger SQLite y ranking. Nuestro tablero no lo sustituye. La modalidad de uno o varios equipos por tanda y la asignación de turno de estaciones están pendientes de confirmación; la misión obedece las autorizaciones oficiales.

- 3.4.1 Integrar cuatro estaciones con el mismo programa y roles distintos.
- 3.4.2 Verificar ciclo A → B → C → vacío e inventario por vuelta.
- 3.4.3 Validar turno e inicio conforme a Race Control y reglas vigentes (HTML: cuenta regresiva 3-2-1, fin por cuatro vueltas, 12 min o E-stop, por confirmar).
- 3.4.4 Conectar el tablero a telemetría, eventos y controles reales autorizados.
- 3.4.5 Completar una vuelta con sus cuatro servicios y retorno.
- 3.4.6 Escalar a dos y cuatro vueltas, sin reiniciar manualmente entre tramos.
- 3.4.7 Probar fallos controlados de red, estación y movimiento, incluyendo bandera roja y recuperación autorizada.

**Desarrollo:** mantener pruebas virtuales rápidas y ensayos físicos escalonados. Registrar versión, superficie, parámetros, resultados y fallos; no ocultar corridas fallidas. Controlar seguridad y almacenamiento de evidencia. **Archivos:** `test_carrera_integrada.py`, scripts de inicio/ensayo, launch de integración. **Resultados:** vueltas, sectores, intervenciones y estados de piezas. **Cierre:** ensayo integral de cuatro vueltas con cuatro estaciones reales, dentro del tiempo y sin acciones inseguras; objetivo cero intervenciones. Resultados de ensayo no se presentan como tanda oficial.

## 3.5. Experimentación, simulación y predicción

> **Alcance:** sin cambios: el simulador del HTML sigue siendo la base de la predicción firmada. Usar parámetros medidos en el robot, no los valores por defecto.

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

**Alcance:** comprobar el `grabador` oficial cuando se publique y contrastar con el ledger SQLite de Race Control. No escribir un grabador duplicado. El repositorio no contiene todavía el validador de evidencia y modifica el formato respecto al HTML.

- 3.6.1 Inventariar CSV/eventos y verificar coherencia con ledger y rúbrica vigente.
- 3.6.2 Verificar bag(s), tópicos y conteo de mensajes (`ros2 bag info`), no solo existencia de carpetas.
- 3.6.3 Verificar reproducción de videos, número de vuelta y requisitos finales de resolución/overlay.
- 3.6.4 Contrastar timestamps NTP y registros de intervenciones entre máquinas.
- 3.6.5 Aplicar rúbrica de referencia a ensayos, registrar criterios pendientes de confirmación.
- 3.6.6 Ensayo general reproducible; pruebas de seguridad y fallos separadas de la tanda.
- 3.6.7 Ejecutar validador oficial si se publica; mientras tanto, comprobación manual y pruebas propias de consistencia, sin afirmar conformidad oficial.

| Fuente | Evidencia prevista |
|---|---|
| Repositorio, `03-microros-pi5-carrito.md` | Por vuelta: video MP4, rosbag2 (odometría, IMU, pose tag, escalas), CSV de eventos de pit |
| Race Control | Ledger SQLite exportable a CSV; contrastar con registros del carrito |
| HTML (referencia histórica pendiente de confirmación) | `sensores.csv` a 10 Hz; `vueltas.csv`; `pits.csv`; `intervenciones.csv`; `mensajes.csv`; `bags/tanda/` completo; `videos/lapNN.mp4` 640×480 a 15 fps con overlay |

Si se conservan los cinco CSV del HTML, documentar los contenidos originales: sensores (t, pose, velocidades, IMU, batería); vueltas (inicio/fin, sectores, intervenciones, validez); pits (llegada, duración, errores pre/post, escalas, reintentos, pieza); intervenciones (hora, tipo, origen, descripción); mensajes (tópico, hora, contenido y dirección). Los tópicos de bag del HTML eran `/odom /cmd_vel /tf /imu /battery_state /pit/medicion /pit/calibracion` y `/scan` si aplica; confrontarlos con interfaces reales (`/tag/pose`, etc.). No inventar datos ni asumir esquema o ubicación definitivos. Un registro sin intervenciones puede tener solo encabezado si el formato lo permite.

**Archivos:** `scripts/integracion/validar_evidencias.sh` (comprobaciones locales, no validador oficial), `tests/integracion/test_evidencias.py`, `docs/bloque_03_integracion/3.6_validacion.md`. **Cierre:** evidencia trazable, reproducible y verificada según especificación final; formato definitivo pendiente. Guardar pruebas desde el primer día, separadas de resultados oficiales.

## 3.7. Carrera oficial, entrega y sustentación

> **Alcance:** despliegue a cargo de Race Control (diseño pendiente). Confirmar modalidad de entrega, estructura, fork/submódulo, tag y reglas de evaluación. Los nombres `granprix-esan`, `vendor/granprix` y `deploy.sh` vienen del HTML, no son componentes publicados del ZIP.

- 3.7.1 Integrar repositorio final y referencia inalterada al commit oficial; confirmar modalidad de fork/submódulo antes de configurarla.
- 3.7.2 Identificar versión estable reproducible; usar `v1.0-final` si se mantiene el requisito del HTML.
- 3.7.3 Entregar carpeta de app según plantilla y colaborar en validación de despliegue oficial en cuatro Jetson; comprobar red, reloj, supervisor y tablero. No implementar despliegue del curso.
- 3.7.4 Ejecutar tanda oficial con calentamiento, turno, inicio único y supervisión por tablero.
- 3.7.5 Analizar predicción vs resultados, vueltas, tiempos, errores, escalas e intervenciones; distinguir fallos de curso y de equipo.
- 3.7.6 Elaborar `informe.pdf` de dos páginas: predicción contra resultado, causa raíz de cada intervención y prevención, errores antes/después y evolución de escalas, propuesta de mejora.
- 3.7.7 Preparar defensa de cualquier vuelta sorteada y explicar decisiones y fallos con evidencia; compartir conocimiento entre integrantes.

**Reglas del HTML como referencia complementaria, por confirmar:** inicio, observación, ajustes antes del inicio, pausas del juez y bandera roja de Race Control no cuentan como intervención. Toques físicos, controles web, teleoperación y reinicios/cambios de software durante carrera cuentan según sección 6; acciones en menos de 10 s sobre el mismo problema se agrupan según regla general; una intervención no declarada descubierta en video suma 3. El ganador se ordena por menos intervenciones, luego más vueltas válidas, menor tiempo promedio y menor error de pose medio. Fallas de hardware de brazo, red o Race Control imputables al curso se gestionan por el juez; una falla de nuestro programa de estación es nuestra responsabilidad.

**Entregables de referencia:** README con integrantes, IP y URL del tablero, sensores, uso de odometría visual y altura de cuna; código versionado, artefacto compatible con despliegue, predicción firmada, registros oficiales e informe según confirmación del docente. **Cierre:** entrega completa y defensa realizada; no confundir un ensayo con resultados de la tanda oficial.

# 4. Correspondencia con la rúbrica del HTML (referencia pendiente de confirmación)

| Criterio | Puntos | Requisito oficial para máximo | Secciones internas |
|---|---:|---|---|
| Tanda | 4 | 4 vueltas válidas (3 → 3 pts, 2 → 1 pt, menos de 2 → 0) | 1.2, 1.5, 3.3, 3.4 |
| Pit | 3 | Medición, acople, reset y recalibración; error post menor que pre en ≥70 % de paradas y escalas convergentes | 1.3, 1.4, 2.4, 3.3 |
| Estación | 3 | Intercambio correcto (HTML: despliegue con `deploy.sh`; adaptar a infraestructura oficial); ≥90 % (75 % → 2, 50 % → 1) | 2.2–2.6, 3.3 |
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
| III — Mixto brazo | Cliente simulado | Real | Validar roles, compensación, manipulación y tiempo con supervisor/protecciones oficiales. |
| IV — Físico | Real | Real | Pit completo; luego cuatro estaciones, vuelta y tanda completa. |

El nivel I combina `pc-race` para tráfico, dobles de movimiento/tag y una estación que reproduzca los cuatro roles. El supervisor y `brazo_simulado` del curso se integrarán cuando existan; el simulador MQTT actual no sustituye al doble de movimiento ni prueba el intercambio físico.

II y III no tienen orden obligatorio y pueden ejecutarse en paralelo. Para pasar a integración física conjunta se exige una interfaz común estable, parada y supervisor verificados, montaje seguro, poses alcanzables, y validación de que el carrito no se mueve durante manipulación. La integración virtual no exige terminar la calibración real.

Dependencias principales para el cierre (no para el inicio):

- 1.1 → validación física de 1.2; 1.5 (seguridad mínima) → cualquier prueba de movimiento.
- 1.3.4–1.3.5 y 1.3.8 (tag mínimo validado) → caracterización definitiva 1.1; no bloquea pruebas preliminares. 1.1.8 (cuna montada) → pruebas E1–E4 con carrito real.
- Firma de `BrazoJetCobot` y respuesta del docente → alcance real de 2.2.
- 1.3 + 1.2 → 1.4 (estimación y acople físicos).
- 2.1 + 2.2 → 2.3; 1.3/3.1 + geometría → 2.4; 2.3 + 2.4 + 2.6 → ejecución física de 2.5.
- 3.1 ↔ interfaces de 1.5 y supervisor; 2.5 usa el puerto/estrategia, no MQTT directo. 3.2 permite probar desde el inicio.
- 3.3 → 3.4 para carrera real; 1.6 ↔ 3.4 para tablero operativo.
- 1.1 + 1.3 + 2.3 + 3.3 → parámetros reales para 3.5.
- 1.6 + 3.4 → 3.6; 3.5 + 3.6 + 2.6 → entrega 3.7, que se completa tras la tanda oficial.

# 6. Estructura propuesta del repositorio

Árbol lógico de trabajo **provisional**, no inventario de archivos existentes ni obligación de crearlos vacíos. Ajustar empaquetado, mensajes y lanzamiento a la plantilla del curso. Arquitectura de referencia: `ws/src/granprix_carrito/{control_odometria,camara_apriltag,maquina_pit}` y `estacion/plantilla_equipo/src/app_equipo/estrategia.py`. El repositorio del equipo contiene solo su código y adaptadores autorizados; los componentes del curso se consumen sin reescribirlos. No asumir que estación sea un paquete ROS 2.

```text
capytown_eq08_final/
├── README.md
├── contexto.md
├── contexto_reto_final.md
├── contexto_division_reto_final.md
├── contexto_repo_docente.md           # Opcional: auditoría del commit
├── .gitignore
├── carrito/                          # Bloque 1; empaquetado según plantilla
│   ├── granprix_carrito/
│   │   ├── control_odometria/
│   │   │   ├── planificador.py       # 1.2
│   │   │   ├── ejecutor.py
│   │   │   ├── odometria.py
│   │   │   ├── calibracion.py        # 1.4
│   │   │   └── reset_pose.py         # 1.3/1.4, aplica TF
│   │   ├── camara_apriltag/
│   │   │   ├── camara.py
│   │   │   ├── detector.py
│   │   │   └── estimacion_pose.py    # 1.3
│   │   ├── maquina_pit/
│   │   │   ├── acople.py             # 1.4
│   │   │   ├── estados.py            # 1.5
│   │   │   └── mision.py
│   │   └── tablero_extension/        # 1.6, sobre base del curso
│   ├── config/                       # movimiento, cámara, escalas
│   └── launch/                       # extensiones autorizadas
├── estacion/                         # Bloque 2; estructura de app provisional
│   ├── src/app_equipo/
│   │   ├── estrategia.py             # 2.5, EstrategiaDeCambio
│   │   ├── roles.py
│   │   ├── posiciones.py             # 2.2/2.3
│   │   ├── pick_and_place.py
│   │   ├── control_pinza.py           # a través del puerto autorizado
│   │   ├── compensacion_pose.py       # 2.4
│   │   └── cinematica.py             # condicional al puerto
│   └── config/                       # roles, almacenes, cuna, manipulación
├── geometria_dock/                   # paquete de geometría del dominio
│   └── transformaciones.py           # única convención 1.3 y 2.4
├── integracion/                      # Bloque 3; solo pruebas y configuración
│   ├── configuracion/
│   │   ├── mqtt.yaml
│   │   └── mosquitto_pruebas.conf
│   ├── simuladores/                  # dobles propios, no infraestructura final
│   │   ├── pose_simulada.py
│   │   ├── estacion_simulada.py
│   │   └── brazo_simulado.py
│   ├── clientes_prueba/
│   └── pruebas_contrato/             # fixtures/JSON Schema oficiales sin cambios
├── scripts/
│   ├── roscar/                       # preflight, recta, giro
│   ├── jetcobot/                     # diagnóstico, manipulación autorizada
│   └── integracion/                  # ensayo, comprobación de evidencias
├── tests/
│   ├── roscar/                       # planificador, visión, reset, escalas, FSM
│   ├── jetcobot/                     # compensación, roles, fallos, alcance
│   └── integracion/                  # contrato, pit, carrera, registros
├── docs/
│   ├── arquitectura.md
│   ├── interfaces.md
│   ├── plan_desarrollo.md
│   ├── bitacora_laboratorio.md
│   ├── bloque_01_roscar/              # 1.1–1.6
│   ├── bloque_02_jetcobot/            # 2.1–2.6
│   └── bloque_03_integracion/         # 3.1–3.7
├── experimentos/
│   ├── bloque_01_roscar/              # 1.1/ ... 1.6/
│   ├── bloque_02_jetcobot/            # 2.1/ ... 2.6/
│   └── bloque_03_integracion/         # 3.1/ ... 3.7/
├── simulacion/
│   ├── GranPrix Delivery Semiautónomo.html
│   ├── parametros/
│   ├── resultados/
│   ├── graficos/
│   └── predicciones/
├── vendor/                          # opcional, modalidad por confirmar
│   └── granprix/                     # referencia oficial sin cambios, si procede
├── evidencias/                      # ubicación interna provisional
└── informe.pdf                      # solo al disponer de resultados
```

No incluir como implementación del equipo `puente_mqtt`, `vigilante_red`, `grabador`, `granprix_msgs`, supervisor, `BrazoJetCobot`, Race Control ni despliegue SSH. `twist_mux` se configura según plantilla. No crear módulos genéricos `utils/common` nuevos; conservar utilidades históricas durante migración. Empaquetar `geometria_dock` de modo que pueda instalarse tanto en Pi5 como en estación, sin dependencias ROS/MQTT; verificar que el artefacto final del brazo incluya las dependencias requeridas. Confirmar modalidad de dependencia oficial antes de crear `.gitmodules`. No mover ni eliminar scripts iniciales `scripts/roscar_v01/` y sus tests hasta migrar y verificar. Las evidencias oficiales se colocarán en rutas exigidas por el docente cuando se confirme el formato, aunque se usen rutas de laboratorio separadas antes. No crear datos ficticios de tanda.

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

**Un repositorio de integración activo:** usar `capytown_eq08_final` para integrar código compartido, manteniendo la copia como banco experimental transitorio. Tras transferir y validar cambios, evitar dos historiales activos de la misma funcionalidad. Confirmar si se exige fork oficial. Trasladar cambios entre dos historiales con cherry-pick falla con facilidad; hasta entonces, usar la copia como entorno experimental del ROSCar. El repositorio principal integra el código de todos; el repo oficial del curso es otra entidad. Ramas sugeridas: `main` (estable), `develop` (integración), `feature/roscar-navegacion`, `feature/roscar-vision`, `feature/jetcobot-cinematica`, `feature/jetcobot-manipulacion`, `feature/integracion`. No es obligatorio que exista cada rama antes de comenzar.

Ejemplo de commit: `feat(1.2.2): implementar planificador de tramos`; ejemplo de registro: `test(3.3.7): medir tiempo del pit simulado`. Transferir cambios revisados mediante PR, cherry-pick cuando historiales y commits lo permitan, o copia selectiva a una rama de integración. Nunca sobrescribir todo el repositorio principal con la copia experimental. Actualizar referencia oficial solamente tras revisar cambios; usar submódulo si lo confirma el docente. Etiquetar versión de competencia reproducible (`v1.0-final` si se mantiene ese requisito).

# 7. Plan flexible para nueve días de laboratorio

Ventanas propuestas, no fechas rígidas ni requisitos oficiales. Las actividades de todos los bloques se superponen; cualquier dependencia no publicada se registra como bloqueo. Revisar cada día acceso a hardware y versión del repositorio oficial.

| Ventana | ROSCar (A, B) | Estación (C, D) | Integración (E) | Criterio de salida propuesto |
|---|---|---|---|---|
| Días 1–2 | Diagnóstico, parada, rectas/giros preliminares, herramienta tag y planificador | Diagnóstico, alcance/cuna, definir roles, doble de brazo; confirmar puerto y acceso | Race Control local, contrato, Mosquitto, dobles mínimos | Pruebas unitarias y comunicación local; seguridad comprobada antes de movimiento |
| Días 2–4 | Caracterización con referencias independientes, escalas, acople y FSM | E1/E4 y E2/E3; medir doble intercambio si autorizado | Validar mensajes, roles y primer pit virtual; tablero simulado | Puerta E2 día 3: medición o bloqueo comunicado; pit virtual y tramo de prueba |
| Días 4–6 | Visión física, reset, acople y navegación | Compensación real; integrar supervisor cuando esté publicado | Integración mixta/física autorizada y primera vuelta | Pit seguro dentro de presupuesto y primera vuelta sin intervención, si hay recursos |
| Días 6–8 | Varias vueltas, pruebas de regresión | Optimizar tiempos dentro de límites | Registros y predicción con mediciones reales | Ensayo de cuatro vueltas; evidencias contrastadas con requisitos vigentes |
| Días 8–9 | Estabilización, no introducir cambios innecesarios | Validar despliegue con infraestructura del curso | Ensayo general y versión identificada | Ensayo completo y registro de bloqueos restantes |
| Tanda oficial | Supervisión | App compatible y desplegada por curso | Análisis, entrega y defensa | Según reglamento definitivo |

P0: seguridad desde la primera prueba física, precisión visual, tiempo E2/E3, contrato y primera vuelta. Preservar evidencia desde el inicio. No considerar hardware validado por una simulación. La fecha de presentación sigue siendo la comunicada al equipo.

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
| 2.5 | Aplicación del equipo y estrategia de cambio | Por asignar | Por verificar | — | — |
| 2.6 | Compatibilidad, seguridad y validación de la aplicación | Por asignar | Por verificar | — | — |
| 3.1 | Arquitectura, red y contrato de comunicación | Por asignar | Por verificar | — | — |
| 3.2 | Entorno de simulación y pruebas independientes | Por asignar | Por verificar | — | — |
| 3.3 | Integración del pit | Por asignar | Por verificar | — | — |
| 3.4 | Integración de la carrera | Por asignar | Por verificar | — | — |
| 3.5 | Experimentación, simulación y predicción | Por asignar | Por verificar | — | — |
| 3.6 | Evidencias y validación integral | Por asignar | Por verificar | — | — |
| 3.7 | Carrera oficial, entrega y sustentación | Por asignar | Por verificar | — | — |

## 8.0. Avance por etapas de la cadena crítica

El conteo de "secciones validadas sobre 19" pesa igual a 1.6 que a 1.4. Medir además el avance por etapas:

| Etapa | Estado | Evidencia |
|---|---|---|
| Protección de `/cmd_vel` probada (el robot frena si cae nuestro nodo) | Pendiente | — |
| Mensajes del carrito validados contra `contrato/` de `pc-race` | Pendiente | — |
| Carrito/estaciones simulados reportan vuelta a `pc-race` (solo tráfico) | Pendiente | — |
| Precisión del tag medida | Pendiente | — |
| Primer tramo de 2 m acoplado sin tocar el robot | Pendiente | — |
| Primer pit completo (doble, contra el doble MQTT) | Pendiente | — |
| Ciclo E2 medido en el brazo real | Pendiente | — |
| Primer pit físico válido | Pendiente | — |
| Primera vuelta completa | Pendiente | — |
| Cuatro vueltas en ensayo | Pendiente | — |
| Evidencia verificada; validador oficial si se publica | Pendiente | — |

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

| Pendiente real (commit revisado) | Acción mientras se resuelve |
|---|---|
| Plantilla del ROSCar, `granprix_msgs`, puente, vigilante, grabador y tablero base | Lógica pura, dobles de prueba, verificar interfaces al publicarse |
| Supervisor de estación, plantilla `app_equipo`, puerto `BrazoJetCobot` y doble de brazo | Estrategia desacoplada; confirmar firmas, límites, torque y condiciones de seguridad |
| `mover` cartesiano/articular, necesidad de IK y MoveIt2 | Resolver antes de invertir en IK propia; poses seguras y doble de brazo |
| Rol, dock, índice de bandeja y carga de configuración en estrategia | Parametrización local provisional, no inventar firma oficial |
| Correlación sin ID/vuelta, resultados atrasados y motivo de error no presente en `ResultadoMsg` | Pruebas y política de espera segura; consultar al docente, no modificar contrato |
| Modalidad de carrera, turno de estación y opciones de despliegue A/B/C | Race Control local; no asumir múltiples carritos ni exclusividad definitiva |
| Forma de entrega, relación `codeplai/GranPrix` con nombre histórico `granprix-esan`, fork/submódulo/tag | Mantener referencia al commit y repositorio del equipo; esperar instrucciones |
| Montaje de cartón, elevación, holgura bajo mesa, cuna/ménsula, marcos dock–tag–brazo y `dock_frames.yaml` | Medir, confirmar materiales y responsables; no fijar extrínsecas ni altura sin datos |
| Acceso a ROSCar/Jetson, ventanas de laboratorio y versiones ROS 2/Python | Diagnóstico autorizado, entornos separados, simulación |
| Red, permisos, NTP, frecuencia odom, tópico batería, entradas de `twist_mux` | Inventario y ensayos locales; comprobar parada al perder órdenes, no asumir cero |
| Qué entra en el presupuesto total de pit (incl. giro de salida), criterio 70 % cuando ya está en tolerancia, inicialización de escalas | Consultar; medir fases por separado y conservar datos pre/post |
| Formato de evidencias, grabador y validador ausente | Registrar pruebas, comprobar consistencia y evitar duplicación; reconciliar formato por vuelta del repo con HTML |
| Rúbrica definitiva, predicción y reglas de intervención/entrega que siguen vigentes | Mantener referencias HTML como complementarias hasta confirmación |

No tratar una ausencia de código como permiso para sustituir infraestructura del curso. Si cambia el repositorio, revisar diff y registrar commit y cambios de responsabilidades antes de actualizar el plan.

# 10. Referencias y reutilización de antecedentes

- Documento original: `GranPrix Delivery Semiautónomo.html` (secciones 1–12 y pestaña Simulador).
- [Repositorio del docente `codeplai/GranPrix`](https://github.com/codeplai/GranPrix) (commit `285c829`): Race Control, herramienta AprilTag y `docs/arquitectura/00`–`04`. **Manda sobre el HTML** en lo que programa cada parte, según indicó el docente.
- Documentos internos: `README.md`, `contexto.md`, `contexto_reto_final.md`.
- [CapyTown RC-0](https://github.com/Harold855/RC-0_MicroRos_Pi5): utilidades odométricas, diagnóstico y grabación; verificar parámetros del robot asignado.
- [CapyTown RC-1](https://github.com/Harold855/microrospi5-sim_capytown_G8): simulación, análisis de errores, ejecución segura y evidencia histórica. No sustituir la estrategia de giro/avance compensado por el PID del cuadrado anterior sin confirmar el alcance oficial.
- [Simulador base RC-1](https://github.com/codeplai/microrospi5-sim): entorno auxiliar ROS 2, distinto del simulador HTML oficial GranPrix.
- Reto 1 JetCobot: API y secuencias de manipulación, sujetas a nueva geometría y supervisor.
- [Reto 2 — El Turno del Brazo](https://github.com/Harold855/Reto_2-El_Turno_del_Brazo): FK, evaluación de IK de firmware y conceptos de worker único.
- [Gran Reto JetCobot — Grupo 8](https://github.com/Harold855/El-Gran-Reto-de-JetCobot---Grupo-8): modelos, MoveIt2 y secuencias parametrizadas; verificar pruebas y posiciones no validadas.
- Manuales del fabricante: [MicroROS Pi5](https://www.yahboom.net/study/MicroROS-Pi5) y [JetCobot](https://www.yahboom.net/study/JetCobot).

**Principio final:** avanzar por bloques en paralelo, integrar desde el primer día, cerrar cada sección con evidencia verificable y no considerar el sistema listo para la carrera hasta validar su comportamiento físico e integrado bajo las reglas oficiales.

# 11. Registro histórico de cambios de la versión 1.1 (no normativo)

Revisión de criterio del 24-nov-2026. Motivos y efectos:

| Cambio | Motivo |
|---|---|
| Sección 0.4: prioridades P0/P1/P2, recortes y puerta del pit (día 3) | 130 subtareas no caben en 9 días con igual peso; se prioriza la vuelta válida |
| 2.2: corregida la premisa "FK/IK del Reto 2" | Ningún antecedente tiene IK propia; la FK trae sesgos conocidos |
| 1.1: orden de trabajo con el tag como instrumento; 5 corridas por tipo; 1.3.8 | En RC-1 el transportador (±3.5°) impidió separar el error del robot del error de medición |
| `geometria_dock/transformaciones.py` único para 1.3 y 2.4 | Evitar signos distintos entre el carrito y el brazo |
| 1.6 pasa a E (integración y evidencias); reparto para 5 | Equilibrar la carga: el bloque ROSCar tenía visión, calibración, FSM, seguridad, tablero y registro |
| 1.1.8: fabricar y montar la cuna y la ménsula | Nadie tenía la tarea; sin ella no se prueba E1–E4 con el carrito real |
| 2.1.7 y pendientes: acceso a los brazos y riesgo del montaje elevado | El ritmo del bloque 2 y el paso libre bajo la mesa dependen de ello |
| 3.2: simulador ROS 2 pasa a P2; primero pruebas unitarias y doble MQTT | Costo alto de adaptar RC-1 frente a su beneficio |
| 6.2: un solo repositorio activo tras el fork | Evitar desincronización entre dos historiales |
| Sección 7: criterios de salida; 8.0: avance por etapas | Las ventanas no tenían condición de aprobado; el conteo de secciones engaña |

# 12. Registro histórico de cambios de la versión 1.2 (no normativo)

Adaptación al repositorio del docente (`codeplai/GranPrix`, commit `285c829`, 24-nov-2026), que según el docente manda sobre el HTML.

| Cambio | Motivo |
|---|---|
| Fuentes y precedencia en la sección 0; nueva sección 0.5 (qué cambia con el repositorio, diferencias con el HTML y riesgos del contrato real) | El repositorio redefine quién programa qué y el formato real de los mensajes |
| Bloque "Alcance v1.2" al inicio de cada sección | Marca lo que pasa al curso y lo que sigue siendo nuestro, sin borrar el texto original |
| 2.5 y 2.6 reducidas; 2.2 depende de `BrazoJetCobot` | El supervisor, el guardián y el despliegue son del curso; el equipo escribe la estrategia de cambio |
| 1.5 y 1.6 reducidas; 3.2 y 3.1 simplificadas | Puente, vigilante, tablero base y grabador son del curso; `pc-race` y su simulador sustituyen al banco de pruebas propio |
| Reparto A–E y prioridades reescritos | Menos infraestructura que escribir; el peso pasa a la precisión del acople y al tiempo de cambio en E2 y E3 |
| Sección 7 y 8.0 ajustadas; 9 con 9 pendientes nuevos | Criterios de salida, avance y preguntas al docente alineados con el nuevo alcance |


# 13. Registro de cambios de la versión 1.3

Consolidación de las 19 secciones sobre `GranPrix-main.zip` (commit `285c82966a2de1d3b4eb39a64bad1415a14212db`), con la precedencia indicada por el docente. Los registros 11–12 son históricos; no constituyen instrucciones actuales.

| Cambio | Efecto |
|---|---|
| 0.3–0.5 | Requisitos vigentes, complementarios y pendientes separados; inventario real de código vs arquitectura; prioridades P0/P1/P2 |
| 1.1–1.4 | Caracterización preliminar independiente; salida única `twist_mux`; detección según alternativas oficiales; reset en `control_odometria`; tres mediciones actuales separadas |
| 1.5–1.6 | FSM y extensiones propias, integración de seguridad/puente/grabador del curso; no duplicar infraestructura |
| 2.2–2.6 | IK/MoveIt2 condicionales; `EstrategiaDeCambio`, cuatro roles, uso exclusivo del puerto y compatibilidad con supervisor/despliegue |
| 3.1–3.3 | Diez tópicos del contrato v1, Python separado, dobles mínimos, correlación sin ID y parada ante incertidumbre |
| 3.4–3.7 | Autorizaciones oficiales, evidencia por vuelta frente al HTML, despliegue pendiente y entrega por confirmar |
| 4–9 | Rúbrica como referencia, dependencias flexibles, árbol de repositorio actualizado, cronograma y bloqueos trazables |

**Verificación de esta revisión:** contraste documental y de código fuente del ZIP, no ejecución de pruebas físicas ni actualización del repositorio GitHub. No acredita pruebas de equipo, no confirma cambios posteriores al commit ni reemplaza instrucciones futuras del docente.
