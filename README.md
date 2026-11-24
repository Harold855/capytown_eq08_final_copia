# GranPrix Delivery Semiautónomo – Grupo 8

**Proyecto final de Robótica – CapyTown**

> **Estado (24-nov-2026): planificación inicial.** Aún no hay código del carrito ni de la estación, ni corridas reales del GranPrix. El docente publicó [`codeplai/GranPrix`](https://github.com/codeplai/GranPrix) (parcial: Race Control, herramienta AprilTag y documentos de arquitectura) y **manda sobre el HTML** en lo que programa cada parte. Los valores marcados como *propuesto* o *histórico* deben comprobarse antes de usarse. Detalle en [`docs/contexto_analisis.md`](docs/contexto_analisis.md) y [`contexto_division_reto_final.md`](contexto_division_reto_final.md).
>
> **Precedencia de fuentes:** (1) lo que el docente indique por escrito; (2) su repositorio; (3) el HTML oficial, que sigue siendo la referencia de las reglas de carrera, la rúbrica (a confirmar) y la predicción firmada. Donde el repositorio y el HTML difieren, este README lo señala.

## 1. Descripción del proyecto

El proyecto GranPrix Delivery Semiautónomo tiene como finalidad desarrollar un sistema robótico colaborativo entre un robot móvil Yahboom MicroROS Pi5 (ROSCar) y cuatro estaciones de manipulación equipadas con brazos robóticos Yahboom JetCobot.

El ROSCar deberá recorrer una trayectoria cuadrada de 2 metros por lado, dentro de una zona de 2.8 × 2.8 metros, realizando operaciones de carga, intercambio y descarga de piezas en cada estación.

El sistema utilizará ROS 2 para la comunicación interna de cada robot y MQTT para la comunicación entre dispositivos. Asimismo, incorporará visión artificial mediante AprilTags, estimación de pose, calibración adaptativa y un tablero web de supervisión.

La finalidad principal es completar cuatro vueltas válidas con la menor cantidad posible de intervenciones humanas. Compiten 10 equipos (uno por tanda) y los 4 brazos son del curso: los usa el equipo que tiene el turno. **Gana el equipo con menos intervenciones humanas** entre los que completan al menos 3 vueltas válidas.

## 2. Objetivos

- Desarrollar la navegación semiautónoma del ROSCar.
- Implementar la estimación de pose mediante AprilTags y solvePnP.
- Implementar el reset de pose y la calibración adaptativa de distancia y giro.
- Desarrollar un programa único de control para las cuatro estaciones JetCobot.
- Integrar los robots mediante comunicación MQTT.
- Implementar un tablero web de supervisión y control.
- Registrar evidencias experimentales mediante CSV, ROS Bags y videos.
- Minimizar las intervenciones humanas durante la carrera.

## 3. Hardware

- Yahboom MicroROS Pi5 – ROSCar (23.8 × 15.3 cm; altura máxima 12.5 cm con antena).
- Cuatro brazos robóticos Yahboom JetCobot (del curso), cada uno sobre una mesa en voladizo.
- Raspberry Pi 5.
- NVIDIA Jetson de las estaciones.
- Cámara del ROSCar.
- Encoders, IMU y LiDAR, sujetos a la configuración final del robot.

## 4. Tecnologías

- ROS 2 Humble.
- Python.
- MQTT y Mosquitto.
- OpenCV.
- AprilTag 36h11.
- TF2.
- MoveIt2.
- HTML, CSS y JavaScript.
- Git y GitHub.

## 5. Configuración prevista del Grupo 8

| Parámetro | Valor |
|---|---|
| Equipo | `eq08` |
| ROS_DOMAIN_ID | `8` |
| ROS_LOCALHOST_ONLY | `1` |
| IP del ROSCar | `192.168.50.108` |
| IP de las estaciones E1 / E2 / E3 / E4 | `192.168.50.21` / `.22` / `.23` / `.24` |
| Broker MQTT (Race Control) | `192.168.50.10` |
| Puerto MQTT | `1883` |
| Tablero web | `http://192.168.50.108:8080` |
| Red | `GranPrix-ESAN` (5 GHz, `192.168.50.0/24`) |
| Reloj | NTP de Race Control, error máximo 50 ms antes de cada tanda |
| Telemetría MQTT | hasta 5 Hz; tablero ≥ 2 Hz |

**Regla de red:** ROS 2 solo dentro de cada máquina; entre máquinas, únicamente MQTT. No usar descubrimiento DDS/multicast entre robots. El carrito nunca depende de la red para moverse: si pierde el broker durante 1.5 s, se detiene. La laptop del equipo solo abre el tablero; no ejecuta nodos de autonomía.

## 6. Estaciones y circuito

Sentido antihorario: E1 → E2 → E3 → E4 → E1. Tras E4 el carrito regresa vacío a E1. Coordenadas en metros, x al este, y al norte; los marcos definitivos salen de `docks/dock_frames.yaml` del curso.

| Estación | Operación | Dock (x, y) | Rumbo nominal al llegar | Carga al salir |
|---|---|---|---|---|
| E1 – Largada | Carga de pieza A | (0.40, 0.40) | −90° | A (roja) |
| E2 – Pit 1 | Intercambio A → B | (2.40, 0.40) | 0° | B (verde) |
| E3 – Pit 2 | Intercambio B → C | (2.40, 2.40) | +90° | C (azul) |
| E4 – Meta | Descarga de pieza C | (0.40, 2.40) | 180° | vacío |

Cubos de 25 mm y máximo 30 g. Almacenes: 4 piezas A en E1, 4 B en E2, 4 C en E3; E2, E3 y E4 tienen bandeja de recepción para 4 piezas. E2 y E3 son los roles críticos: hacen dos *pick and place* dentro del mismo pit.

**Escenario físico:**
- AprilTag 36h11 de 6 cm, ID = número de estación, en el borde de la zona y de frente al carrito, a unos 28 cm de la cámara (verificar el enfoque).
- Cuna cónica en una ménsula lateral derecha de 8 × 8 cm, a 11 cm del centro del carrito y a una altura de 9 a 12 cm que **se declara en este README** (ver sección 15).
- Mesa del brazo en voladizo: cara superior a 15.8 cm del piso y 14 cm libres debajo. El eje del brazo queda a 29 cm del centro del dock; la cuna, a 18 cm del eje (14 a 22 cm con ±4 cm de error de pose).

## 7. Restricciones principales

- Cuatro vueltas consecutivas.
- Tiempo máximo de tanda: 12 minutos.
- Tiempo máximo por pit: 10 segundos, medidos desde que el carrito frena hasta que arranca.
- Tolerancia de posición: 4 cm.
- Tolerancia angular: 6°.
- Máximo de dos reintentos automáticos de acople por parada (no cuentan como intervención).
- Velocidad lineal máxima: 0.20 m/s.
- Velocidad angular máxima: 0.8 rad/s. Referencia de RC-1: 0.10 m/s y 0.5 rad/s.
- Mínimo de tres vueltas válidas para clasificar.
- Una vuelta es **válida** con las cuatro paradas completas (acople válido y pieza entregada y recibida); es **limpia** si además no hubo intervención humana. No son lo mismo.
- Cambio de equipo: 3 min, en los que las 4 Jetson hacen `git pull` del tag del equipo y lanzan la estación con `deploy.sh`. Si el despliegue falla, el tiempo corre.

## 8. El pit

En cada parada, dentro de los 10 s y en este orden:

1. **Medir:** la cámara lee el tag del dock y calcula la pose real del carrito (solvePnP, en el marco del dock).
2. **Acoplar:** si está fuera de 4 cm o 6°, corrige con el tag (máximo 2 reintentos).
3. **Solicitar:** publica `(dx, dy, dθ)` en `granprix/estacion/<n>/solicitud`. La estación valida el turno, cambia la pieza y compensa esa pose.
4. **Reset de pose:** corrige `map → odom` con la pose medida (REP-105); el siguiente tramo parte de esa pose.
5. **Recalibrar:** compara lo comandado con lo medido en el tramo anterior y actualiza las escalas de distancia (`cd`) y de giro (`ca`) con paso limitado.

Cada parada guarda el error antes y después. Planificador y ejecutor oficiales: giro `φ = wrap(atan2(dy, dx) − θ)` y distancia `L = hypot(dx, dy)`, ejecutados en lazo abierto como `φ / ca` y `L / cd`; estimador `escala_nueva = escala + α·(medido/comandado − escala)`.

> **Cuello de botella previsto:** el pit de 10 s en E2/E3. Un intercambio de 6 s más un reintento de 4 s consume todo el presupuesto. Hay que cronometrar por separado visión, acople, MQTT, movimientos del brazo, reset y salida. *(Análisis del equipo; no es una regla oficial.)* Según `docs/arquitectura/03` del repositorio del docente, tras un `resultado` ok el carrito mide otra vez antes del reset y la recalibración: confirmar si esa medición es el "error después del pit" y si entra en los 10 s. El `t_cambio` que publica la estación mide solo el cambio de pieza; el tiempo del pit (frenado a arranque) lo medimos nosotros.

## 9. Máquina de estados y reparto de módulos

Estados oficiales del pit: `NAVEGANDO`, `ACOPLANDO`, `ESPERANDO`, `INTERCAMBIO`, `SALIENDO` y `FALLA`, con tiempo límite en cada uno.

**Quién programa qué, según el repositorio del docente** (`docs/arquitectura/02` y `03`; el HTML decía otra cosa en varias filas):

| Pieza | Dueño | Notas |
|---|---|---|
| `control_odometria` (ruta en lazo abierto, escalas `cd` y `ca`, reset de pose) | **Equipo** | Planificador y ejecutor con `φ/ca` y `L/cd` |
| `camara_apriltag` (pose respecto al tag) | **Equipo**, con base del curso | Base: `estacion/herramientas/herramienta_apriltag.py`; falta probarla con cámara real |
| `maquina_pit` (acople fino, solicitud, reintentos, reset) | **Equipo** | Máximo 2 reintentos; 4 cm y 6° |
| `puente_mqtt` | Curso | Único nodo con red |
| `vigilante_red` | Curso | Detiene las ruedas si no hay broker 1.5 s; actúa por `twist_mux` |
| `tablero_web` | Curso, el equipo lo extiende | Debe cubrir todos los bloques de la sección 12 |
| `grabador` | Curso | Video, rosbag2 y CSV de eventos de pit |
| `supervisor_estacion` | Curso | Valida turno y solicitud, estados de la estación, congela el brazo |
| `EstrategiaDeCambio` de la estación | **Equipo** | `cambiar(pose, pieza_trae)`; solo usa el objeto `brazo` |
| `BrazoJetCobot` (puerto) | Curso | Mover, abrir y cerrar la pinza, soltar torque; aún no definido |
| Despliegue en las estaciones | Curso (Race Control, SSH) | Opción B pendiente |

**Se mantiene un riesgo propio:** el firmware del ROSCar conserva la última orden de `/cmd_vel`. El vigilante del curso cubre la pérdida de red, no la caída de **nuestro** nodo de control. Debemos configurar un timeout corto en nuestra entrada de `twist_mux` y comprobar en el robot que al vencer sale cero.

**Cambios respecto al HTML:** ya no escribimos el puente MQTT, el vigilante de red, el tablero base ni el registro; y la estación no es un programa completo del equipo, sino la estrategia de cambio dentro del supervisor del curso. El brazo **no usa cámara** (decisión D3 del repositorio): toda la compensación depende de la pose que reporta el carrito.

**Decisiones propuestas** (por validar): un solo bloque de lógica de pit en `maquina_pit`; el tablero no controla motores directamente, solo pasa por la máquina de estados; no relanzar una manipulación cuyo resultado es desconocido.

## 10. Intervenciones y ranking

Una intervención es una acción humana separada después del inicio; varias acciones seguidas en menos de 10 s sobre el mismo problema cuentan como una.

| Tipo | Ejemplos | Cuenta |
|---|---|---|
| Física | Tocar o mover el carrito, un brazo, un cable o una pieza | 1 por episodio |
| Web | Reset del carrito, reiniciar vuelta, E-stop del equipo | 1 por clic |
| Teleoperación | Teclas, joystick o web | 1 por episodio |
| Software | Reiniciar un nodo, relanzar un launch, cambiar un parámetro | 1 por acción |
| No cuenta | Pulsar «Iniciar», mirar el tablero, ajustes antes del inicio, pausa del juez, bandera roja de Race Control | 0 |

Una intervención no declarada y descubierta en el video suma 3. Desempates: más vueltas válidas, menor tiempo promedio por vuelta, menor error de pose medio en los pits. **Nunca evitar una parada de emergencia por temor a la penalización.**

## 11. Tópicos MQTT

El contrato real está en `pc-race/contrato/` del repositorio del docente (modelos pydantic) y en `docs/arquitectura/00-contrato-mqtt.md`. **No inventar campos.** QoS 1 puede duplicar mensajes y el contrato actual no trae `id`: Race Control empareja `solicitud` y `resultado` por equipo y estación.

| Tópico | Publica | QoS |
|---|---|---|
| `granprix/carrera/estado` | Race Control (tanda, fase, equipos) | 1, retenido |
| `granprix/carrera/bandera` | Race Control (**verde o roja**) | 1 |
| `granprix/estacion/<n>/turno` | Race Control (equipo con el turno) | 1, retenido |
| `granprix/eq08/turno` | Race Control (autorizado o no) | 1, retenido |
| `granprix/eq08/telemetria` | Carrito (pose, batería, velocidad; hasta 5 Hz) | 0 |
| `granprix/eq08/evento` | Carrito (`intervencion`, `pit_ok`, `reintento`) | 1 |
| `granprix/eq08/vuelta` | Carrito (número, `t_inicio`, `t_fin`, estaciones) | 1 |
| `granprix/estacion/<n>/solicitud` | Carrito (equipo, dock, pose, `pieza_trae`) | 1 |
| `granprix/estacion/<n>/estado` | Estación (`LIBRE`, `ESPERANDO`, `CAMBIANDO`, `LISTA`, `OFFLINE`) | 1, retenido |
| `granprix/estacion/<n>/resultado` | Estación (equipo, ok, `pieza_dejo`, `t_cambio`) | 1 |

Unidades de la pose: `dx` y `dy` en metros, `dth` en **grados**; internamente trabajamos en radianes y convertimos solo en el borde MQTT.

**Diferencias con el HTML original:** la `solicitud` no lleva `id` ni `vuelta`; el `resultado` no lleva `id` ni motivo; los estados de la estación son otros; solo hay bandera verde y roja (la amarilla y los cuadros son locales del tablero); aparecen los tópicos de turno.

**Detalles que condicionan nuestro diseño:**
- Una vuelta es válida si los 4 pits `ok` caen entre el `t_inicio` y el `t_fin` de nuestro mensaje `vuelta`.
- Un carrito pasa a `OFFLINE` tras 3 s sin telemetría: debe seguir publicando durante el pit y el acople.
- Race Control usa el error de pose de la `solicitud` (`dx`, `dy`) para el desempate.

## 12. Evidencia y tablero

**Evidencia** (se guarda en el Pi5 durante la tanda). El HTML menciona un validador `evaluacion/validador_evidencia.py`, que **todavía no aparece** en el repositorio del docente. Tampoco está definido qué parte genera el `grabador` del curso y qué parte debemos generar nosotros; hasta saberlo, no escribir generadores duplicados:

| Archivo | Contenido | Mínimo |
|---|---|---|
| `videos/lapNN.mp4` | Video de la cámara del carrito, un archivo por vuelta, con vuelta y tiempo superpuestos | 640 × 480, 15 fps |
| `bags/tanda/` | `/odom /cmd_vel /tf /imu /battery_state /pit/medicion /pit/calibracion` y `/scan` si hay LiDAR | Toda la tanda |
| `sensores.csv` | t, x, y, θ de odom, v, ω, aceleraciones y giro de la IMU, batería | 10 Hz |
| `vueltas.csv` | Vuelta, inicio, fin, tiempo, 4 tiempos de sector, intervenciones, válida | Una fila por vuelta |
| `pits.csv` | Vuelta, estación, llegada, tiempo de pit, errores antes/después, reintentos, escalas, pieza | Una fila por parada |
| `intervenciones.csv` | Tiempo, tipo, origen (web o juez), descripción | Una fila por intervención |
| `mensajes.csv` | Todo lo publicado y recibido por MQTT | Toda la tanda |

**Tablero de Pits** (Pi5, puerto 8080, ≥ 2 Hz): Control (Iniciar solo con turno, Reset carrito, Reiniciar vuelta, E-stop rojo siempre visible), Cronometraje (vuelta n/4, última, mejor, delta y 4 sectores con colores F1), Estaciones (estado, tiempo de pit, error antes/después), Carrito (pieza, escalas, v, ω, batería, latencia, video en vivo), Banderas e Intervenciones (contador y bitácora).

## 13. Entregables y rúbrica (20 puntos)

Entregables (según el HTML): repositorio `capytown_eq08_final` (fork de `granprix-esan`, con `vendor/granprix` como submódulo sin modificar) con el tag `v1.0-final`; `deploy.sh` probado en las 4 Jetson (según el repositorio del docente, el despliegue lo hace Race Control por SSH: confirmar qué se entrega); este README; la predicción firmada con la pestaña Simulador; la evidencia; e `informe.pdf` de 2 páginas.

| Componente | Criterio | Pts |
|---|---|---:|
| Tanda | 4 vueltas válidas → 4; 3 → 3; 2 → 1; menos de 2 → 0 | 4 |
| Pit | Medición, acople, reset y recalibración; error posterior menor que el anterior en ≥ 70 % de las paradas y escalas convergentes | 3 |
| Estación | `deploy.sh` y pieza entregada y recibida en ≥ 90 % → 3; ≥ 75 % → 2; ≥ 50 % → 1 | 3 |
| Autonomía | 0 intervenciones → 3; 1–2 → 2; 3–5 → 1; ≥ 6 → 0 | 3 |
| Evidencia | Un video por vuelta, bag completo y cinco CSV | 3 |
| Tablero web | Todos los bloques operativos | 2 |
| Informe | Dos páginas | 1 |
| Defensa | Explicar un video de vuelta sorteado | 1 |

Bono: +1 por odometría visual documentada (sin pasar de 20). 7 de los 20 puntos (evidencia, tablero, informe y defensa) no dependen del resultado de la carrera.

> **Por confirmar:** si los criterios Estación (que habla de `deploy.sh`), Tablero web y Evidencia se mantienen igual ahora que el curso aporta supervisor, tablero base y grabador. Mientras tanto, rige la rúbrica del HTML.

## 14. Antecedentes del grupo

Se reutilizarán componentes de los retos previos, pero **no** se copian proyectos completos. Todo valor histórico debe volver a comprobarse en el robot y la superficie del GranPrix.

| Reto | Repositorio (rama `main`) | Qué aporta |
|---|---|---|
| RC-0 · Calibración del ROSCar | [RC-0_MicroRos_Pi5](https://github.com/Harold855/RC-0_MicroRos_Pi5/tree/main) | `odom_utils.py`, scripts de preflight y grabación de bags |
| RC-1 · Control PID | [microrospi5-sim_capytown_G8](https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/main) (**`main` está desactualizada:** lo final está en la rama [`claude/sleepy-knuth-kc6wex`](https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/claude/sleepy-knuth-kc6wex)) | Datos medidos del robot real, `wheel_params_g8.yaml`, patrón de `rc1_correr.sh` |
| RC-1 · Simulador base del curso | [codeplai/microrospi5-sim](https://github.com/codeplai/microrospi5-sim/tree/main) | Simulador 2D de ROS 2 |
| Reto 2 · El Turno del Brazo | [Reto_2-El_Turno_del_Brazo](https://github.com/Harold855/Reto_2-El_Turno_del_Brazo/tree/main) | Patrón de worker único del brazo |
| Gran Reto del JetCobot | [El-Gran-Reto-de-JetCobot---Grupo-8](https://github.com/Harold855/El-Gran-Reto-de-JetCobot---Grupo-8/tree/main) | `ejecutar_secuencia` (percepción, movimiento y pinza inyectables) |
| Reto 1 · API del JetCobot | Sin repositorio (se entregó como `.zip`) | Valores de pinza y única evidencia de *pick and place* físico |

**Datos históricos que condicionan el diseño** (ROSCar 4, RC-0/RC-1):
- Calibración histórica: `r = 0.03145 m`, `b_eff = 0.2138 m` (firmware: `r0 = 0.0325`, `b0 = 0.24`). No confundir con las escalas `cd` y `ca` del GranPrix.
- `/odom` a ≈ 11 Hz y retardo efectivo de ≈ 0.5–0.65 s.
- Dispersión del giro de 90° de ±3.5° y el robot gira 7–11 % más de lo ordenado en lazo abierto.
- Cierre del cuadrado con PID sobre `/odom`: 10–36 cm sobre cerámica.
- **El firmware conserva la última orden de `/cmd_vel`** si el nodo muere (no hay watchdog).
- Un ciclo completo de *pick and place* del Reto 1 duró ≈ 21 s.

**Hallazgo del simulador oficial** (modelo del HTML ejecutado con Node.js; resultados simulados, no mediciones): con los valores por defecto (giro ±0.4°) la estrategia de reset + recalibración deja ≈ 21 % de llegadas fuera de tolerancia. Con la dispersión de giro medida en RC-1 (±3.5° y +9 % de escala de giro) sube a ≈ 84 %. A 2 m, 1° de error de rumbo son ≈ 3.5 cm. Por eso la precisión del giro y del primer acople es crítica. La predicción firmada debe usar parámetros medidos, no los por defecto.

## 15. Riesgos y preguntas abiertas

**Riesgos principales:**
- Precisión de llegada al dock (tolerancia de 4 cm y 6°) con un giro que hoy tiene ±3.5° de dispersión.
- Duración del pit en E2/E3 frente al límite de 10 s.
- Altura del cubo bajo la mesa: cuna de 9–12 cm + cubo de 2.5 cm frente a 14 cm libres.
- La cámara tiene servos (`/servo_s1`, `/servo_s2`); si se mueven, la calibración extrínseca deja de valer.
- Cambio de red: en RC-0 el carrito era punto de acceso (`10.42.0.1`); mantener un acceso alternativo para SSH.
- Bags vacíos: en RC-1 dos de tres bags oficiales salieron sin mensajes; comprobar el conteo al grabar.
- El robot publica `/battery` (`UInt16`), no `/battery_state`: hace falta un adaptador.

**Preguntas pendientes para el docente** (lista completa en [`docs/contexto_analisis.md`](docs/contexto_analisis.md)), por orden de impacto:
1. ¿Qué secciones del HTML simplifica su repositorio y se mantiene la rúbrica? ¿`codeplai/GranPrix` es el `granprix-esan` del HTML?
2. ¿Qué expone `BrazoJetCobot.mover` (articulaciones o pose cartesiana)? ¿Hay guardián con límites de articulación y caja de trabajo?
3. ¿Cuándo salen la plantilla del carrito, el `supervisor_estacion`, `plantilla_equipo` y `dock_frames.yaml`?
4. ¿Se agrega `id` (y `vuelta`) a `solicitud` y `resultado`, y un motivo al `resultado`?
5. ¿Cómo recibe la estrategia su rol, el dock y la ranura de la bandeja? La firma `cambiar(pose, pieza_trae)` no los incluye.
6. ¿El giro de salida en el dock y la segunda medición con el tag cuentan dentro de los 10 s? ¿Qué es exactamente "error después del pit"?
7. ¿Se permite cerrar el giro con IMU u odometría o debe ser estrictamente por tiempo? ¿Se puede iniciar `cd` y `ca` con valores calibrados?
8. ¿Qué evidencia produce el `grabador` y cuál debemos generar? ¿Dónde está el validador?
9. ¿Opción A, B o C de despliegue y quién asigna el turno de cada estación?
10. ¿Cuántas horas de acceso a los brazos tenemos antes de la tanda y cómo se accede a las Jetson?

## 16. Organización del repositorio

- `carrito/`: nodos del equipo (`control_odometria`, `camara_apriltag`, `maquina_pit`) y la extensión del tablero. **No se copian ni se reescriben** los nodos del curso (`puente_mqtt`, `vigilante_red`, `grabador`).
- `estacion/`: la estrategia de cambio de pieza (`app_equipo`). El supervisor es del curso.
- `vendor/`: repositorio del curso como submódulo, **sin modificar**. Falta confirmar si `codeplai/GranPrix` es el submódulo esperado antes de crear `.gitmodules`.
- `simulacion/`: simulaciones y predicciones.
- `scripts/`: automatización y diagnóstico.
- `tests/`: pruebas unitarias y de integración (primero contra `pc-race` y su simulador de carritos).
- `experimentos/`: pruebas experimentales, separadas de la evidencia oficial.
- `docs/`: documentación técnica. Incluye `contexto_analisis.md`.
- `contexto_division_reto_final.md`: reparto del equipo, prioridades y plan por ventanas.
- `videos/` y `bags/`: evidencia de la tanda.

Las carpetas del equipo se ajustarán a la plantilla del curso cuando exista; por ahora se guían por `docs/arquitectura/02` y `03` del repositorio del docente. Este repositorio es provisional: no es un fork de `granprix-esan`.

## 17. Datos por declarar (requeridos en el README final)

| Dato | Estado |
|---|---|
| Integrantes y rol de cada uno | Pendiente |
| IP del carrito y URL del tablero | Previstos (sección 5) |
| Sensores utilizados | Pendiente |
| ¿Se usó odometría visual? | Pendiente |
| Altura real de la cuna (9–12 cm) | Pendiente: medir en el ROSCar asignado |
| ROSCar asignado y calibración vigente | Pendiente: confirmar |
| Reparto del equipo (roles A a E) | Propuesto en `contexto_division_reto_final.md`; por confirmar |
| Estructura de carpetas de la plantilla del curso | Pendiente: el curso aún no la publica |

## 18. Referencias

- [Documentación oficial Yahboom JetCobot](https://www.yahboom.net/study/JetCobot)
- [Documentación oficial Yahboom MicroROS Pi5](https://www.yahboom.net/study/MicroROS-Pi5)
- [Repositorio CapyTown RC-0](https://github.com/Harold855/RC-0_MicroRos_Pi5)
- Documento oficial GranPrix Delivery Semiautónomo.
- [Repositorio del docente `codeplai/GranPrix`](https://github.com/codeplai/GranPrix): Race Control, herramienta AprilTag y `docs/arquitectura/00`–`04`.
- [REP-105](https://www.ros.org/reps/rep-0105.html), [AprilTag](https://github.com/AprilRobotics/apriltag), [OpenCV solvePnP](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html), [Eclipse Mosquitto](https://mosquitto.org/documentation/), [MoveIt 2](https://moveit.picknik.ai/).
