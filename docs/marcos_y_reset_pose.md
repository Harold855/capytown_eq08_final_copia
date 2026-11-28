# Cámara → dock y reset de pose

Lógica en `carrito/granprix_carrito/transformacion_camara_dock.py` y `reset_pose.py`, configuración en `carrito/config/marcos.yaml` y script `scripts/roscar_v01/pose_dock.py`. Es Python puro y se probó **en simulación** (escena física en 3D y, aparte, imágenes renderizadas pasadas por el detector); **nunca con el robot ni con una cámara real**. Falta el adaptador ROS 2 que publique el TF `map → odom`.

## Archivos
| Archivo | Función |
|---|---|
| `carrito/granprix_carrito/transformacion_camara_dock.py` | Convertir la medición visual a la pose del ROSCar (en el dock y en el mapa). |
| `carrito/granprix_carrito/reset_pose.py` | Corregir la localización global (`map → odom`). |
| `carrito/nodos/tag_emulado.py` | Emular el AprilTag con el simulador RC-1 (a partir de `/sim/pose`). |
| `carrito/nodos/camara_apriltag_node.py` | Integrar las mediciones con ROS 2 (imagen → `/tag/pose`). |
| `tests/carrito/test_transformacion_camara_dock.py` | Verificar signos, unidades y transformaciones. |
| `tests/carrito/test_reset_pose.py` | Validar matemáticamente la corrección. |

Además: `pose_dock.py` (`PoseDock`, `LocalizadorDock`), `gestor_reset.py` (odometría en el tiempo, tag fresco) y `nodos/nodo_reset_pose.py` (TF `map → odom` y servicio), con sus pruebas (`test_localizador_dock.py`, `test_gestor_reset.py`, `test_nodo_reset_pose.py`, `test_tag_emulado.py`, `test_camara_apriltag_node.py`, `tests/vision/test_marcos_imagen.py`) y `scripts/roscar_v01/pose_dock.py`.

## Convenciones
- Todo en el plano, con `T_A_B` = coordenadas de B expresadas en A (`geometria_dock.transformaciones`). Robot: x adelante, y a la izquierda, ángulo antihorario.
- Pose del tag que entrega `medir_tag.py`: sistema de la cámara (x derecha, y abajo, z adelante), metros y `dth` en grados.
- Marco del dock: origen en el centro del dock, x en el rumbo de llegada, y a la izquierda. **Sigue siendo un supuesto** hasta que el docente publique `dock_frames.yaml`; si cambia, se sustituye el diccionario de docks, no el código.
- La salida es la pose del robot en el dock `(dx, dy, dth)` —lo que va en la `solicitud`— y en el mapa.

## Cadena
`pose_en_dock = T_dock_tag ∘ inv(T_robot_camara ∘ T_camara_tag)`, con `T_camara_tag = (z·cosα − y·sinα, −x, −dth)` (α = inclinación de la cámara hacia abajo).

Se necesitan dos cosas físicas que **nadie ha medido**, ambas en `marcos.yaml` (mientras sean `null` la carga falla):
- `camara_en_robot`: posición `x, y` y giro `yaw` respecto del centro del robot, e inclinación.
- `tag_en_dock`: posición del centro del tag en el marco del dock y su giro (0 = de frente al carrito). Opcionalmente uno distinto por estación (`por_dock: {E2: ...}`).

Hipótesis del modelo: el tag está vertical y el eje óptico no tiene alabeo; la inclinación se compensa solo en posición (el error angular que deja es de décimas de grado).

## Cómo obtener el montaje
Colocar el robot con exactitud sobre la marca del dock, medir el tag con la cámara calibrada y medir con regla dónde está el tag en el dock:
```bash
python3 scripts/camara/medir_tag.py una --camara-yaml cam.yaml --tag-id 2 | \
    python3 scripts/roscar_v01/pose_dock.py montaje --tag-en-dock 0.38,0,0 --robot-en-dock 0,0,0
```
Imprime el bloque para `marcos.yaml`. Absorbe juntos los errores del montaje y del tag, pero **hereda el error con que se colocó el robot** sobre la marca (1 cm de error de colocación = 1 cm de error en la pose). Repetir en varios docks y colocaciones, y comparar.

Sensibilidad (simulación; máximo sobre 27 poses en la zona de acople):

| Error del montaje | Posición | Ángulo |
|---|---|---|
| cámara 1 cm adelante o a un lado | 1.0 cm | 0.07° |
| cámara con 1° de giro | 0.2 cm | 1.07° |
| cámara con 3° de giro | 0.6 cm | 3.07° |
| inclinación 8° sin modelar | 0.7 cm | 0.07° |
| inclinación con 2° de error | 0.1 cm | 0.07° |
| tag 1 cm corrido en el dock | 1.0 cm | 0.07° |
| tag con 1° de giro en el dock | 0.8 cm | 1.04° |

Los errores de posición y de ángulo pasan **1 a 1**: con tolerancias de 4 cm y 6° hay que conocer el montaje a ≈ 1 cm y ≈ 1°.

## Reset de pose (`ResetPose`)
Calcula `T_map_odom = T_map_base ∘ inv(T_odom_base)` con la pose medida y la odometría, y `pose_mapa(odom)` da la pose creída para planificar el siguiente tramo. Es lo que se publicaría como TF `map → odom` (REP-105).

Diseño defensivo (umbrales provisionales y ajustables):
- **Sin referencia no hay pose:** `pose_mapa` falla hasta `inicializar` (el odom arranca en el origen y el primer reset puede ser un salto grande legítimo; ese primero no se compara).
- **El robot debe estar quieto:** si se dan `odom_ini` y `odom_fin` de la ventana de medición y se movió más de 5 mm o 0.5°, se rechaza (`ROBOT_NO_QUIETO`); la odometría llega con 0.5–0.65 s de retardo, así que no se debe usar una odometría posterior a la medición sin comprobarlo.
- **Salto sospechoso:** una corrección de más de 15 cm o 20° se rechaza (`SALTO_EXCESIVO`).
- **Fuera del dock:** una pose a más de 30 cm o 45° del centro del dock se rechaza (`FUERA_DE_DOCK`): tag mal leído o dock equivocado.
- `cerca` es un argumento **obligatorio** de `inicializar` y `actualizar` (se pasa `PoseRobot.cerca`): olvidarlo es un error, no una protección omitida.
- Un rechazo **no cambia el estado**: se conserva la referencia anterior.

## Pose del ROSCar respecto al dock (`pose_dock.py`)
`LocalizadorDock` es la interfaz para la máquina del pit; devuelve un `PoseDock` (`dx`, `dy` en m, `dth` en rad, `dth_deg`, la pose en el mapa, la fuente y si está cerca del dock).

| Método | Cuándo | Qué hace |
|---|---|---|
| `pose_desde_tag(medicion)` | al acoplar y para la `solicitud` | pose desde una medición de `medir_tag.py`; no cambia ningún estado |
| `aplicar_reset(pose, odom_ini, odom_fin)` | tras el intercambio, con el robot quieto | inicializa o actualiza `ResetPose`; solo acepta poses del tag; devuelve el resultado con su motivo |
| `pose_desde_odom(estacion, odom)` | entre mediciones, cuando el tag no se ve | pose respecto al dock indicado desde la odometría y el último reset; falla si nunca hubo reset |

`PoseDock.error` da `(m, °)` respecto a la cruz, `en_tolerancia` es la condición del acople (≤ 4 cm **y** ≤ 6°) y `a_contrato()` da `dx`, `dy` en m y `dth` en grados, igual que la `solicitud`. `desplazamiento_odom_m` es lo que se movió la odometría desde el último reset: **es una distancia, no una incertidumbre calculada**, pero sirve para decidir cuánto confiar (en simulación, una odometría que avanza 5 % de más acumula ≈ 5 mm en 10 cm, y un nuevo reset con el tag lo elimina).

## Adaptador ROS 2 (`carrito/nodos/nodo_reset_pose.py`)
**Estado: escrito y probado solo contra un sustituto mínimo de `rclpy`** (`tests/carrito/test_nodo_reset_pose.py`). Eso prueba el cableado (parámetros, suscripciones, servicio, TF), no que la API real de ROS 2 esté bien usada: **nunca se ejecutó con ROS**. La lógica está en `gestor_reset.py` (Python puro, 19 pruebas) y el nodo es delgado.

Interfaz (los nombres son **nuestros**, provisionales hasta que el curso publique la plantilla; todos son parámetros salvo el servicio):

| Qué | Nombre por defecto | Tipo | Nota |
|---|---|---|---|
| entrada | `/odom` | `nav_msgs/Odometry` | marcos esperados `odom` → `base_footprint` (el de RC-1 y del simulador); si no coinciden se descarta |
| entrada | `/tag/pose` | `geometry_msgs/PoseStamped` | pose del tag en el sistema óptico de la cámara; se supone que solo llega si el tag fue aceptado y con la hora de captura |
| entrada | `/pit/dock` | `std_msgs/Int32` | estación actual (1 a 4), la fija la máquina del pit |
| servicio | `/reset_pose/aplicar` | `std_srvs/Trigger` | aplica el reset con el último tag; `message` trae un JSON con el motivo |
| salida | TF `map` → `odom` | — | solo después del primer reset aceptado; **debe ser el único publicador de esta transformación** |
| salida | `/reset_pose/estado` | `std_msgs/String` | JSON con el estado, tras cada llamada al servicio |

Cómo evita los problemas conocidos de la odometría (retardo de 0.5–0.65 s medido en RC-1):
- No usa "la última odometría" sino la **interpolada en el instante de la medición** (`retardo_odom_s` la desplaza) y exige que el robot haya estado quieto en la ventana previa (`ventana_quieto_s`, 0.3 s). Con la odometría retrasada 0.5 s y `retardo_odom_s = 0`, un robot que ya se detuvo se rechaza como "en movimiento" (`ROBOT_NO_QUIETO`); con 0.5 se acepta (hay una prueba de cada caso).
- Si la odometría aún no llegó hasta ese instante responde `ODOM_INSUFICIENTE`: **el servicio no espera, quien lo llama debe reintentar** a los pocos décimos de segundo.
- Otros motivos: `SIN_TAG`, `TAG_VIEJO` (más de `edad_max_tag_s` = 1 s), `TAG_FUTURO`, `ESTACION_INVALIDA`, `ODOM_NO_CUBRE`, y los del reset (`ROBOT_NO_QUIETO`, `SALTO_EXCESIVO`, `FUERA_DE_DOCK`).
- Sin referencia no se publica TF; con una referencia vieja se sigue publicando la última (un rechazo no la cambia).

Arranque (fallará con un mensaje claro si falta el montaje medido):
```bash
cd <repositorio> && python3 -m carrito.nodos.nodo_reset_pose --ros-args -p marcos_yaml:=carrito/config/marcos.yaml
ros2 service call /reset_pose/aplicar std_srvs/srv/Trigger
ros2 run tf2_ros tf2_echo map odom
```
Los parámetros decimales se pasan con punto decimal (`-p retardo_odom_s:=0.5`, no `0`): ROS rechaza un entero para un parámetro de tipo real.

**Qué hay que comprobar en el robot** (el sustituto no lo puede garantizar):
1. Los marcos reales de `/odom` (parámetro `base_frame`; `wheel_params_g8.yaml` de RC-1 usa `base_footprint`).
2. Si las marcas de tiempo de `/odom` están en el mismo reloj que las del tag (el micro-ROS puede tener su propio reloj): si no, `odom_sello_llegada:=true` y `tag_sello_llegada:=true` usan la hora de llegada.
3. El retardo real de `/odom` en este robot (`retardo_odom_s`).
4. Que nadie más publique `map` → `odom` (`ros2 topic info /tf -v`).
5. Que algún nodo publique `/tag/pose` con ese formato: `camara_apriltag_node.py` (cámara real, sin verificar) o `tag_emulado.py` (simulador).
6. Los QoS: las suscripciones usan `qos_profile_sensor_data` (aceptan publicadores confiables y *best effort*).

## Emulación del tag con el simulador RC-1 (`nodos/tag_emulado.py`)
La cámara del simulador (`yahboomcar_sim`, 160×120) ve el piso y **no dibuja AprilTags**; por eso hace falta emular la medición. El nodo toma la pose real `/sim/pose` (`PoseStamped` en `map`), calcula lo que mediría la cámara (la cadena de `transformacion_camara_dock.py` al revés), decide si el tag es visible (campo de visión, distancia 0.10–0.60 m y ángulo de visión del tag ≤ 60°), le añade ruido (σ 1 mm y 0.5° por defecto, pérdidas opcionales) y publica `/tag/pose` con la **hora de la pose** y el mismo formato que el nodo de cámara real. Opcionalmente publica `/pit/dock` (emula a la máquina del pit).

- Es una **medición emulada**, no un tag real: sirve para ejercitar el reset y el flujo del pit sin cámara, no para medir la precisión de la visión (para eso, `medir_tag.py comparar`).
- Se contrastó con la escena física 3D independiente de las pruebas (2 mm y 0.2°) y la cadena emulador → reset recupera la pose a menos de 1 cm con ruido.
- Montaje del simulador: `carrito/config/marcos_sim.yaml` (cámara 10 cm adelante, 20.05° hacia abajo, tag a 28 cm de la cámara en el dock). **No es el del robot real.** El simulador usa el marco base `base_footprint`.

Cómo ensayarlo (sin verificar: no se ejecutó con ROS ni con el simulador):
```bash
ros2 launch yahboomcar_sim sim.launch.py world:=<mundo> start:=2.42,0.38,0.05 noise:=none     # terminal 1
python3 -m carrito.nodos.tag_emulado --ros-args -p marcos_yaml:=carrito/config/marcos_sim.yaml -p publicar_dock:=true   # 2
python3 -m carrito.nodos.nodo_reset_pose --ros-args -p marcos_yaml:=carrito/config/marcos_sim.yaml                     # 3
ros2 service call /reset_pose/aplicar std_srvs/srv/Trigger          # con el robot quieto y el tag visible
ros2 run tf2_ros tf2_echo map odom                                   # comparar con /sim/pose y /odom
```
- El simulador publica su propio `map → odom` solo con `publish_map_to_odom:=true` o `odom_align` > 0 (apagados por defecto): **dejarlos apagados**, o habría dos publicadores. Con los valores por defecto el `map → odom` no existe hasta el primer reset aceptado, que es justo el caso del arranque.
- `start:=x,y,yaw` está en el marco `map`; hay que elegir un mundo cuyo mapa contenga esa zona (el `arena_rc1` de RC-1 puede no contenerla).

## Nodo de cámara (`nodos/camara_apriltag_node.py`)
Suscribe una imagen (`sensor_msgs/Image`; `mono8`, `rgb8` o `bgr8`, convertida **sin `cv_bridge`**), la mide con `CamaraTag` (corrige la distorsión, rechaza detecciones dudosas, filtra con mediana móvil) y publica `/tag/pose` con la hora de captura de la imagen. Parámetros: `camara_yaml` (obligatorio; con la calibración de damero también `tamano_mm`), `tag_id` (0 = **el tag de la estación que anuncia `/pit/dock`**; un valor fijo solo para pruebas con un dock), `dock_topic`, `image_topic`, `margen_min`, `hamming_max`, `ventana`. Publica `/camara_apriltag/estado` con un contador por motivo de rechazo.
- El `PoseStamped` lleva **solo el giro vertical** (`dth`) como cuaternión: es lo único que entrega el detector de forma fiable y lo único que consume el reset. No lleva el id del tag (la estación la da `/pit/dock`).
- **Sigue a `/pit/dock`:** el ID del tag es el número de estación, así que con `tag_id: 0` solo acepta el tag de la estación actual (otro ID cuenta como `otro_id`; dos del mismo ID, `varios_tags`) y **sin `/pit/dock` no mide** (falla cerrada, cuenta `sin_dock`). Al cambiar de estación reinicia el filtro. Solo publica cuando el cuadro actual es válido: un cuadro sin tag ya no republica la pose anterior con la hora nueva (error corregido).
- El tópico de imagen del ROSCar real **no se conoce**: el valor por defecto (`/camera/image_raw`) es el del simulador.
- Necesita OpenCV y `pupil-apriltags` en el Pi5 (no verificado) y la calibración de la cámara real; el simulador no sirve para probarlo porque no dibuja tags.

## Resultados en simulación
- Escena física en 3D (cámara con montaje e inclinación, tag con altura distinta): la conversión recupera la pose a 2 mm y 0.2° en la zona de acople (±4 cm y ±6°), y a 1e-9 sin inclinación.
- Del píxel a la pose en el dock (24 poses renderizadas con distorsión de lente, corregida, y montaje **conocido**): posición p95 0.35 cm y máximo 0.46 cm; ángulo p95 0.44° y máximo 0.72°.
- Con un reset real, una odometría que había derivado 9 cm vuelve a quedar a menos de 1.5 cm.
- Sin reset, una deriva de 7 cm y 4° cambia el giro planificado hacia el siguiente dock más de 2°; con reset, menos de 0.5°.

## Lo que falta
1. Medir el montaje y la posición del tag (arriba). Sin esto no hay pose en el dock.
2. Probar con ROS real los tres nodos (`nodo_reset_pose.py`, `tag_emulado.py`, `camara_apriltag_node.py`); todos están probados solo contra un sustituto de `rclpy`.
3. Decidir con el docente el marco del dock y si el reset debe ocurrir antes o después de la segunda medición del pit (README de referencia §15).
4. Con la cámara real, cuánto se aparta la medición de estas cifras (iluminación, foco, calibración).
