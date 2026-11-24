# Contexto del análisis — retos previos y GranPrix Delivery Semiautónomo

**Proyecto CapyTown · Grupo 8 · Fecha del análisis: 24 de noviembre de 2026**

Este documento resume la revisión de los cinco antecedentes del grupo (RC-0, RC-1, Reto 1, Reto 2 y Gran Reto del JetCobot) y del documento oficial del reto final. Complementa al `contexto.md` del equipo; no lo reemplaza.

**Etiquetas de confianza:** [Seguro] leído en el código, en los datos o ejecutado · [Probable] inferencia fuerte · [Especulando] hipótesis sin verificar.

**Fuentes de verdad, en orden (v1.2):** (1) lo que el docente indique por escrito; (2) su repositorio `codeplai/GranPrix` (commit `285c829`), que según el docente **manda sobre el HTML** en lo que programa cada parte (ver sección 9); (3) el HTML oficial del reto, pestañas Reto y Simulador, que sigue siendo la referencia de las reglas de carrera, la rúbrica (a confirmar) y la predicción firmada; (4) los manuales de Yahboom; (5) los retos previos, que son históricos y deben volver a comprobarse; (6) este documento, que contiene propuestas.

---

## 1. Repositorios de los retos previos (rama `main`)

| Reto | Robot | Repositorio | Nota |
|---|---|---|---|
| RC-0 · Arranque y calibración | ROSCar (MicroROS-Pi5) | https://github.com/Harold855/RC-0_MicroRos_Pi5/tree/main | |
| RC-1 · Control PID | ROSCar | https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/main | **`main` está desactualizada.** E6 y E7 reales solo están en la rama `claude/sleepy-knuth-kc6wex`: https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/claude/sleepy-knuth-kc6wex |
| RC-1 · Simulador base del curso | ROSCar | https://github.com/codeplai/microrospi5-sim/tree/main | El `yahboomcar_ws` del grupo es idéntico a este |
| Reto 2 · El Turno del Brazo | JetCobot | https://github.com/Harold855/Reto_2-El_Turno_del_Brazo/tree/main | |
| Gran Reto del JetCobot | JetCobot | https://github.com/Harold855/El-Gran-Reto-de-JetCobot---Grupo-8/tree/main | |
| Reto 1 · Domina la API del JetCobot | JetCobot | Sin repositorio (se entregó como `.zip` con plantillas, informe `.docx` y presentación `.pptx`) | Única evidencia de pick and place físico completo |
| **GranPrix · repositorio del docente** | ROSCar y JetCobot | https://github.com/codeplai/GranPrix/tree/main | Parcial. Manda sobre el HTML en lo que programa cada parte (ver sección 9) |

Manuales: JetCobot https://www.yahboom.net/study/JetCobot · MicroROS-Pi5 https://www.yahboom.net/study/MicroROS-Pi5

---

## 2. Resumen de cada antecedente

### 2.1 RC-0 — Arranque y calibración del ROSCar 4

- **Qué hay:** cadena placa → micro-ROS → ROS 2 verificada, dominio 8 escrito en la placa (venía en 20), calibración de `r` y `b_eff`.
- **Valores calibrados:** `r = 0.03145 m`, `b_eff = 0.2138 m` (firmware: `r0 = 0.0325`, `b0 = 0.24`). [Seguro]
- **Tópicos:** `/cmd_vel`, `/odom_raw` (firmware, ≈11 Hz), `/odom` (`odom_corrector`), `/imu` (≈24 Hz), `/scan`, `/battery` (`UInt16`, no `BatteryState`), `/servo_s1`, `/servo_s2`, `/beep`, `/odom_reset`, `/tf`. [Seguro]
- **Problemas encontrados:**
  - `config/wheel_params.yaml` del repo **no tiene los valores calibrados** (dice `0.0230` / `0.1350`). El archivo correcto está en RC-1: `wheel_params_g8.yaml`. [Seguro]
  - Falta la Parte D (validación), no hay bags reales, y las gráficas y el `rqt_graph` se reconstruyeron con IA. El `rqt_graph` muestra enlaces que la captura original no tenía. [Seguro]
  - `setup_log.txt` es del RosCar 8, no del 4. [Seguro]
  - La calibración de `b_eff` está dentro del ruido de medición: las estimaciones de las iteraciones 9–12 van de 0.2066 a 0.2173. [Probable]
- **Desvío lateral en lazo abierto:** 1.0–2.2 cm por metro a 0.10 m/s, es decir 2–4.4 cm en un lado de 2 m. [Seguro]
- **Reutilizable:** `capytown_esan/odom_utils.py` (yaw, unwrap, desplazamiento, segmentación, detección de reinicios), el patrón de seguridad de `secuencia_rc0.py`, `preflight.sh`, `grabar_bag.sh`, `analizar_bag.py`.

### 2.2 RC-1 — Control PID: del simulador al robot real

- **Estado:** el trabajo más completo y mejor documentado del grupo, pero lo final está en la rama de trabajo, no en `main`.
- **Datos medidos en el ROSCar 4** [Seguro]:
  - `/odom` a ≈11 Hz y retardo efectivo de motores + odometría de **≈0.5–0.65 s**.
  - Giro de 90° con las ganancias del simulador (`kp_yaw` 10): oscila ±15–20°. Con `kp_yaw` 1.0: `FIN` en 5–9 s.
  - Dispersión física del giro (7 medidas con transportador): media 88.1°, **±3.5°**.
  - El robot gira **7–11 % más** de lo ordenado en lazo abierto (el firmware usa `b0 = 0.24`).
  - 3A (lazo abierto): cierre 107.9 cm; primera esquina ≈115°.
  - 3B (PID sobre `/odom`): sobre cerámica 10–36 cm de cierre por vuelta (7 medidas, media ≈24 cm); sobre caucho con uniones 34–100 cm. En el giro físico, algunas esquinas se pasaban 10–15° mientras `/odom` marcaba 90°.
  - **El robot real conserva la última orden de `/cmd_vel`** si el nodo muere: el firmware no tiene watchdog.
- **Ganancias finales del robot real:** línea `kp 1.0 / ki 0.1 / kd 8.0`; giro `kp_yaw 1.0 / ki_yaw 0 / kd_yaw 0.3`; `max_angular 1.0`; `linear_speed 0.10`.
- **Problemas de integridad** [Seguro]:
  - Las corridas oficiales de 3B se reasignaron después de ver los resultados: el commit `b3f7a8f` declaraba oficiales las de caucho (media > 70 cm) y el `91ced9d` las cambió por los intentos 8–10 en cerámica (media 17.7 cm). La predicción previa fijaba como oficiales las tres primeras.
  - Dos de los tres bags oficiales de 3B están vacíos (0 mensajes) y el tercero no tiene `/tf`. El verificador del grupo los da por buenos porque solo comprueba que exista `metadata.yaml`.
  - Faltan integrantes en el README y en el informe, y el tag `v1.0-rc1`.
- **Reutilizable:** `wheel_params_g8.yaml`, el patrón de `scripts/rc1_correr.sh` (hash del nodo, un solo `odom_corrector`, ceros al terminar), `rc1_analiza_real.py`, y los datos medidos de arriba.

### 2.3 Reto 1 — Domina la API del JetCobot (zip)

- **Contenido:** 5 niveles con `pymycobot` (diagnóstico, coreografía, dibujo, pick and place A/B, visión + pick and place por color).
- **Evidencia física:** los videos de la presentación muestran ciclos completos de pick and place (Nivel 4, 22 s) y de visión + depósito en la casilla R (Nivel 5, 21 s). [Probable, visto en fotogramas]
- **Valores probados:** pinza abierta 100 / cerrada 14, velocidad 20–30, agarre en una pose fija `[240.7, -1.3, 134.5, 167.77, 8.41, -48.7]`, y destinos por color que después copió el Gran Reto en `zonas_trabajo.json`.
- **Problemas** [Seguro]:
  - La presentación no coincide con el código: coordenada de recogida, rangos HSV, número de posiciones de búsqueda y un "centrado visual" que el código no tiene (`cx`, `cy` se calculan y no se usan).
  - Reglas de seguridad incumplidas: el Nivel 5 no vuelve a HOME; los niveles 3 y 4 envían coordenadas calculadas sin validar; no se importa `conexion.py`.
  - El Nivel 4 no abre la pinza antes de bajar; el Nivel 5 detecta cierre en vacío pero entrega igual.
- **Lección para el GranPrix:** la cámara solo clasificaba el color; el agarre era siempre en el mismo punto. En el GranPrix la cuna llega con hasta ±4 cm y ±6° de error, así que hay que compensar la pose. Un ciclo completo duró ≈21 s.

### 2.4 Reto 2 — El Turno del Brazo

- **Qué hay:** tabla DH y `fk(q)` del JetCobot, y un broker ROS 2 de acceso exclusivo al brazo (admisión con FK, cola FIFO/Round Robin, worker único).
- **Bien hecho:** el diseño del broker (grupos de callbacks, reserva de cupo bajo lock, segunda validación del paso al ejecutar).
- **Problemas** [Seguro]:
  - La FK tiene un **sesgo constante de ≈5.9 mm** frente a `get_coords()` del firmware (Δz ≈ +5.5 mm en todas las poses). No se validó con regla externa.
  - El ítem 4 (auditoría de IK) es un solo punto; las evidencias de los ítems 2 y 4 se reconstruyeron.
  - El ítem 3 (comparación FIFO vs Round Robin) nunca se midió; la README cita archivos que no existen.
  - El broker arranca con `q_actual = [0]*6` en lugar de leer la pose real.
- **Reutilizable:** el patrón de worker único y exclusión mutua, simplificado (en el GranPrix cada estación atiende a un solo cliente).

### 2.5 Gran Reto del JetCobot

- **Qué hay:** P1 (interpretación con LAYA), P2 (broker con `/pick_place`, cinemática, visión HSV, calibración), P3 (voz → transcripción).
- **Problemas** [Seguro]:
  - **Nunca se hizo un pick and place real:** las poses de recogida de `zonas_trabajo.json` están en `null` y los destinos con `validada: false`.
  - **23 de 93 pruebas fallan** por una sola causa: se agregó la regla "el cubo debe ir a la zona de su mismo color" en `pick_and_place.py` sin actualizar las pruebas. El README dice 109 pruebas, pero las 16 de `transcriptor_voz/test/` no existen.
  - El código que corrió en el laboratorio (`~/rb2_ws` del Jetson) no está en el repositorio.
  - `fk.py` (DH) y `cinematica_urdf.py` difieren en 46.7 mm constantes; hay dos tablas DH distintas (`d5` 75.05 y 75.55).
  - El modelo píxel → robot ajusta una matriz 2×2 con 2 puntos: error 0 por construcción.
- **Reutilizable:** la estructura de `jetcobot/pick_and_place.py` (`ejecutar_secuencia` con percepción, movimiento y pinza inyectables; resultado estructurado; nunca da por bueno un agarre sin confirmar), `PinzaMyCobot`, `posiciones.py` (validación de esquema) y `ejecutor_real.py` (falla cerrado). Antes de reutilizar hay que arreglar las pruebas rotas.

### 2.6 Patrón común de los cinco antecedentes

- **Fuerte:** ingeniería de software y seguridad (validaciones, fallar cerrado, confirmaciones, pruebas sin hardware, buena documentación del estado).
- **Débil:** evidencia física escasa, parcial o reconstruida; documentación que promete más de lo que hay en el repositorio; selección de corridas a posteriori.
- **Consecuencia para el GranPrix:** el criterio es completar vueltas válidas en pista y entregar evidencia que pase el validador. El cuello de botella es el tiempo de laboratorio y la verificación física.

---

## 3. GranPrix Delivery Semiautónomo — lo determinante del documento oficial

### 3.1 Reglas que fijan el diseño

- Cuadrado de 2.0 m (docks D1 (40,40), D2 (240,40), D3 (240,240), D4 (40,240) cm), sentido antihorario E1 → E2 → E3 → E4 → E1. Rumbo nominal al llegar: E1 −90°, E2 0°, E3 +90°, E4 180°.
- **4 vueltas, máximo 12 min. Pit máximo 10 s "desde que frena hasta que arranca".** Acople válido: ≤4 cm y ≤6°. Hasta 2 reintentos automáticos de acople.
- Orden del pit: **medir → acoplar → solicitar → reset de pose → recalibrar**. La solicitud va después del acople.
- Ejecutor oficial: giro y avance **en lazo abierto** con escalas estimadas (`φ/ca`, `L/cd`). Estimador `escala = medido/comandado` con filtro exponencial α.
- ROS 2 solo dentro de cada máquina (`ROS_DOMAIN_ID=8`, `ROS_LOCALHOST_ONLY=1`); entre máquinas solo MQTT con Mosquitto en Race Control (192.168.50.10:1883). Carrito eq08: 192.168.50.108; estaciones .21–.24.
- Vigilante: detener si se pierde el broker 1.5 s o llega la bandera roja.
- Estación (según el HTML): **un solo programa con el rol por parámetro**, worker único, cinemática inversa y **MoveIt2**, comandos a través del **guardián** del curso, compensando `(dx, dy, dθ)`. **v1.2:** según el repositorio del docente, el supervisor es del curso y el equipo escribe solo la estrategia de cambio (sección 9).
- Tag AprilTag 36h11 de 6 cm, ID = número de estación, en el borde de la zona y de frente al carrito, a ≈28 cm de la cámara al llegar.
- Cuna cónica en ménsula derecha de 8 × 8 cm, a 11 cm del centro del carrito, altura 9–12 cm declarada en el README. Cubos de 25 mm, A rojo, B verde, C azul.
- Mesa en voladizo: cara superior a 15.8 cm, 14 cm libres debajo; eje del brazo a 29 cm del centro del dock; cuna a 18 cm del eje (14–22 cm con ±4 cm).
- Velocidades máximas: 0.20 m/s y 0.8 rad/s.

### 3.2 Rúbrica (20 pts)

| Componente | Pts | Depende de la carrera |
|---|---:|---|
| Tanda (vueltas válidas) | 4 | Sí |
| Pit (medición, acople, reset, recalibración; error post < pre en ≥70 % de paradas; escalas convergen) | 3 | Sí |
| Estación (`deploy.sh`; pieza correcta en ≥90 / 75 / 50 %) | 3 | Sí |
| Autonomía (0 / 1–2 / 3–5 / ≥6 intervenciones) | 3 | Sí |
| Evidencia (video por vuelta, bag completo, 5 CSV) | 3 | No |
| Tablero web (todos los bloques) | 2 | No |
| Informe (2 páginas) | 1 | No |
| Defensa (video sorteado) | 1 | No |

Bono +1 por odometría visual documentada. El ganador se define solo por intervenciones.

### 3.3 El simulador oficial (pestaña Simulador)

Ejecuté el modelo `simulate()` del HTML con Node.js, 200 corridas por escenario, 4 vueltas. [Seguro]

| Escenario (modo `recal`) | Fuera de tolerancia | Error medio |
|---|---|---|
| Valores por defecto (giro ±0.4°, `sa` −1.2 %) | 21 % | 2.8 cm |
| Giro ±1° | 41 % | 4.0 cm |
| Giro ±2°, tramo 1 % | 69 % | 7.0 cm |
| **Como RC-1: giro ±3.5°, `sa` +9 %, tramo 1 %** | **84 %** | **13.1 cm** |
| Giro ±1°, `sa` +9 %, escalas iniciales = valores medidos | 47 % | 4.3 cm |
| Giro ±0.3°, `sa` +9 %, escalas iniciales = valores medidos | 24 % | 3.0 cm |

Para los dos últimos escenarios modifiqué una línea del modelo (`let cd = p.cd0||1, ca = p.ca0||1`) para poder arrancar con escalas distintas de 1. Con los valores por defecto reproduce las cifras del contexto del equipo (2.8 cm, 21 %, 119 s/vuelta).

**Conclusiones** [Probable]:
1. El acople fino será la operación normal: incluso con giros excelentes, uno de cada cuatro pits necesita corrección. A 2 m, **1° de error de rumbo son ≈3.5 cm** de desvío lateral.
2. Iniciar `cd`/`ca` con valores medidos en laboratorio reduce el error de la primera vuelta. El error real de giro (+7–11 %) sale del rango del deslizador del simulador (máximo +6 %).
3. El modelo es optimista: el reacople deja al robot a ±0.6 cm sin coste real de maniobra, supone 6 s de intercambio en todas las estaciones, solo modela un reintento y decide la validez con la pose verdadera.
4. La predicción firmada debe usar parámetros **medidos** en el robot, no los valores por defecto.

### 3.4 Los dos cuellos de botella

1. **Precisión de llegada.** Con la dispersión de giro de RC-1 (±3.5°), 84 % de llegadas fuera de tolerancia. Hay que bajar la dispersión a ≈1° o menos (giro cerrado con giroscopio, si se permite) y sostener el rumbo en las rectas.
2. **Tiempo del pit en E2/E3.** Hacen dos pick and place (retirar de la cuna y dejar en recepción; tomar del almacén y dejar en la cuna). Un solo ciclo del Reto 1 duró ≈21 s; el pit es de 10 s e incluye medir, acoplar y la comunicación MQTT.

---

## 4. Preguntas abiertas para el docente

1. ¿El giro de salida en el dock (≈3 s a 0.5 rad/s) cuenta dentro de los 10 s del pit?
2. ¿Qué es exactamente "error después del pit"? Si el carrito llega dentro de tolerancia y no se corrige, antes = después y no cuenta como "menor". El ejemplo del tablero (3.4 → 0.6 cm) sugiere que hay que corregir siempre.
3. ¿El ejecutor puede cerrar el giro con el giroscopio o `/odom` y seguir estimando `ca`, o debe ser estrictamente por tiempo?
4. ¿Se permite iniciar `cd`/`ca` con valores calibrados antes de la tanda?
5. ¿Se puede medir el tag en movimiento durante la aproximación sin que empiece a correr el pit?
6. ¿Dónde están el almacén y la bandeja de recepción? La placa de 32 × 19 cm casi llena la mesa de 36 × 22 cm.
7. ¿El brazo puede pre-posicionarse sobre la cuna antes de que llegue el carrito?
8. ¿Quién fabrica la cuna y la ménsula?
9. ¿Es obligatorio MoveIt2 o se acepta la IK del firmware (`send_coords`) a través del guardián?
10. ¿Cómo se señala el fin al llegar a E1 tras la cuarta vuelta?
11. (v1.2) ¿Qué secciones del HTML simplifica el repositorio y se mantiene la rúbrica? ¿`codeplai/GranPrix` equivale a `granprix-esan`?
12. (v1.2) ¿Qué expone `BrazoJetCobot.mover`? ¿Hay guardián con límites y caja de trabajo, o solo lo que hace el supervisor?
13. (v1.2) ¿Cuándo salen la plantilla del carrito, el supervisor, `plantilla_equipo` y `dock_frames.yaml`?
14. (v1.2) ¿Se agrega `id`, `vuelta` y un motivo a `solicitud` y `resultado`?
15. (v1.2) ¿Cómo recibe la estrategia su rol, el dock y la ranura de la bandeja?
16. (v1.2) ¿Qué evidencia produce el `grabador` del curso y dónde está el validador?
17. (v1.2) ¿Opción A, B o C de despliegue y quién asigna el turno de cada estación?

---

## 5. Riesgos físicos no destacados en el documento oficial

- **Altura del cubo bajo la mesa** [Probable]: cuna de 9–12 cm + cubo de 2.5 cm puede llegar a 14.5 cm, y bajo la mesa hay 14 cm. Con ±4 cm de error hacia la mesa podría rozar el borde. Conviene una cuna de ≈9–10 cm.
- **Cámara en pan/tilt** [Probable]: `/servo_s1` y `/servo_s2` parecen mover la cámara. Fijarlos en cada arranque o la calibración extrínseca deja de valer.
- **Sin watchdog de `/cmd_vel` en el firmware** [Seguro, RC-1]: el vigilante debe ser el único publicador de `/cmd_vel` y publicar ceros si no recibe órdenes en ≈0.3 s.
- **Red**: en RC-0 el carrito era punto de acceso (`10.42.0.1`). Pasarlo a cliente de `GranPrix-ESAN` sin una vía de acceso alternativa puede dejar sin SSH.
- **Bags**: comprobar el conteo de mensajes al iniciar la grabación (lección de RC-1).
- **Nombres de tópicos**: el bag oficial pide `/battery_state` e `/imu`; el robot publica `/battery` (`UInt16`). Hará falta un adaptador.
- **Calibración ajena**: en RC-1 el robot llegó con la calibración de otro grupo (0.0316 / 0.2332). Cargar siempre `wheel_params_g8.yaml` y comprobarlo en el log.

---

## 6. Propuesta de trabajo

**Principio:** medir primero los dos números críticos y decidir la arquitectura según los resultados.

### Fase 0 — sin laboratorio

> **v1.2:** instalar `pc-race` del repositorio del docente (Python 3.12+) y su `simulador_carritos.py` contra Mosquitto local: es el banco de pruebas de integración. Importar los modelos de `pc-race/contrato/` para validar nuestros mensajes. No construir un Race Control propio.
- Pedir `granprix-esan` y resolver las preguntas de la sección 4.
- Programar en Python puro, con pruebas automáticas, lo que no depende del contrato: planificador, estimador de escalas, `wrap`, transformaciones (reset `map → odom`, compensación de la cuna), máquina de estados con tiempos límite, mux de seguridad y escritores de CSV.
- MQTT detrás de un adaptador, para ajustarlo cuando llegue el contrato.

### Días 1–2 de laboratorio — mediciones que deciden

| Medición | Decide |
|---|---|
| Precisión de la pose del tag a 28 cm contra cinta | Si el tag sirve como instrumento de medición para todo lo demás |
| Dispersión del giro de 90°: por tiempo, con `/odom` y con IMU (10 de cada uno) | Ejecutor por tiempo o cerrado con giroscopio |
| Deriva lateral en 2 m a la velocidad elegida | Si hace falta sostener el rumbo (bono) |
| Ciclo E2 completo en el brazo real, a la velocidad del guardián | Si los 10 s son viables; si no, avisar al docente ese día |

### Días 3–9
- Días 3–6: primer pit con la estación simulada, luego con una estación real, luego una vuelta completa. Registro de evidencia desde la primera corrida.
- Días 7–9: varias vueltas seguidas, predicción firmada con parámetros medidos, ensayo general de 12 min.

### Arquitectura propuesta del carrito

> **v1.2:** esta lista es la del HTML. Según el repositorio del docente, `puente_mqtt`, `vigilante_red`, `tablero_web` (base) y `grabador` son del curso. El equipo escribe `control_odometria`, `camara_apriltag` y `maquina_pit`, y extiende el tablero. Nuestro vigilante propio se reduce a proteger `/cmd_vel` ante la caída de nuestro nodo, mediante el timeout de nuestra entrada de `twist_mux`.
1. Nodo de cámara (único dueño de la cámara) → imagen para el detector de tags y el grabador de video.
2. Detector de tag → `/pit/medicion`.
3. Nodo de misión: máquina de estados, planificador, ejecutor, estimador y reset `map → odom`.
4. Mux de seguridad (vigilante): único publicador de `/cmd_vel`; ceros ante timeout, pérdida de broker, bandera roja o E-stop.
5. Puente MQTT (y registro de `mensajes.csv`).
6. Servidor web en el puerto 8080.
7. Registro: CSV, video por vuelta y bag con verificación de conteo.
8. Adaptador `/battery` → `/battery_state`.

### Estación
> **v1.2:** MQTT, validación de turno, estados, deduplicación y congelado del brazo son del `supervisor_estacion` del curso. El equipo escribe `EstrategiaDeCambio.cambiar(pose, pieza_trae)` sobre el puerto `BrazoJetCobot`. Lo que sigue describe la parte que sí es nuestra.

Estrategia de cambio por rol: compensación de la cuna por composición de transformaciones rígidas y secuencia de pick and place. Base: la estructura de `ejecutar_secuencia` del Gran Reto, con los valores probados del Reto 1 y lo que faltaba (abrir la pinza antes de bajar, abortar si cierra en vacío, volver a una pose segura).

### Qué no reutilizar
El PID del cuadrado como controlador principal (el algoritmo oficial es otro), LAYA, voz y colas multicliente. Tampoco reescribir lo que el curso entrega: puente MQTT, vigilante de red, grabador, supervisor, Race Control.

---

## 7. Presupuesto de tiempo de referencia

A 0.10 m/s y 0.5 rad/s: 32 m → 320 s; 16 giros de 90° → ≈50 s; 16 pits de 6 s → 96 s. Total ≈466 s (7 min 46 s), margen ≈4 min frente a 12 min. El margen de la tanda no es el problema; el límite de 10 s por pit sí.

---

## 8. Correcciones al contexto del equipo

- La recta "0.9299 m de odometría, 0.963 m física" del §2.1 no aparece en ningún CSV del RC-0. El dato real de la corrida 2 es 0.9453 / 0.963 m. [Seguro]
- No menciona el Reto 1 del JetCobot, única evidencia de manipulación física.
- No menciona la falta de watchdog de `/cmd_vel` en el firmware.

---

## 9. Repositorio del docente (`codeplai/GranPrix`, commit `285c829`)

Revisado el 24-nov-2026. El docente indicó que su repositorio **manda** sobre el HTML y que simplifica algunas secciones. Es **parcial**: un solo commit, 89 archivos.

**Qué contiene:**

| Parte | Estado | Comprobado |
|---|---|---|
| `pc-race/` (Race Control: dominio, ledger SQLite, gateway MQTT, API web, tablero del juez, simulador de carritos) | Pasos 1 a 4 hechos | 126 pruebas pasan y `ruff` sale limpio. No corrí `mypy` ni el simulador (no hay Mosquitto en el entorno) |
| `docs/arquitectura/00` a `04` | Escritos | Contrato, Race Control, estación, carrito y despliegue por SSH |
| `estacion/herramientas/herramienta_apriltag.py` | Hecha | Sus pruebas abortaron en mi entorno al crear el detector (`pupil_apriltags`); causa desconocida. El propio repositorio dice que falta probarla con cámara real |
| Supervisor, plantilla del equipo, código del carrito, `BrazoJetCobot` | **Pendiente** | No existen |
| Guardián, `dock_frames.yaml`, `deploy`, validador de evidencia | **No aparecen** | Tampoco hay menciones |

El nombre `granprix-esan` del HTML no aparece en el repositorio.

**Reparto de trabajo según el repositorio:**
- **Curso:** Race Control, `supervisor_estacion`, `BrazoJetCobot`, `puente_mqtt`, `vigilante_red`, `tablero_web` (base), `grabador` y el despliegue por SSH.
- **Equipo, carrito:** `control_odometria` (ruta y escalas `cd`/`ca`), `camara_apriltag` (con base del curso) y `maquina_pit` (acople, solicitud, reset).
- **Equipo, estación:** `EstrategiaDeCambio.cambiar(pose, pieza_trae)`, usando solo el objeto `brazo`. El brazo no usa cámara (decisión D3).

**Diferencias del contrato frente al HTML:**

| Tema | HTML | Repositorio |
|---|---|---|
| `solicitud` | equipo, vuelta, id, pose | equipo, dock, pose, `pieza_trae`; **sin id ni vuelta** |
| `resultado` | id, ok, piezas, tiempo de pit | equipo, ok, `pieza_dejo`, `t_cambio`; sin id ni motivo |
| Estados de estación | libre, acoplando, intercambiando, falla | `LIBRE`, `ESPERANDO`, `CAMBIANDO`, `LISTA`, `OFFLINE` |
| Banderas | verde, amarilla, roja, cuadros | verde y roja |
| Tópicos extra | — | `estacion/<n>/turno` y `eqNN/turno` |
| Pose | dx, dy, dθ | `dx`, `dy` en m y `dth` en grados |
| Despliegue | `deploy.sh` y `git pull` del tag | Race Control copia por SSH a `/opt/granprix/equipos/eqNN/` (opción B abierta) |

**Detalles que condicionan nuestro diseño:**
1. Sin `id`, Race Control empareja `solicitud` y `resultado` por equipo y estación; un duplicado QoS 1 puede pasar inadvertido.
2. La validez de una vuelta depende de nuestro mensaje `vuelta`: los 4 pits `ok` deben caer entre su `t_inicio` y su `t_fin`.
3. Un carrito pasa a `OFFLINE` tras 3 s sin telemetría.
4. El pit de 10 s incluye latencia que no controlamos (supervisor, MQTT, puerto del brazo). La medición del ciclo de E2 debe hacerse con el supervisor cuando exista.
5. Según `docs/arquitectura/03`, tras el `resultado` ok el carrito mide otra vez antes del reset. Falta confirmar si esa es la medición del "error después del pit".
6. Si `BrazoJetCobot.mover` es cartesiano por firmware, el "IK y MoveIt2" del HTML deja de aplicar.

**Qué hacer:**
1. Instalar `pc-race` y su simulador como banco de pruebas, e importar `pc-race/contrato/` para validar nuestros mensajes.
2. Avanzar con lógica pura y pruebas: planificador, estimador de escalas, FSM del pit, conversión de unidades en el borde MQTT.
3. Probar la herramienta AprilTag con cámara real y medir la precisión contra cinta.
4. Enviar al docente la lista de preguntas 11 a 17 de la sección 4.
