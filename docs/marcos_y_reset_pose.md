# Cámara → dock y reset de pose

Lógica en `carrito/granprix_carrito/marcos.py` y `reset_pose.py`, configuración en `carrito/config/marcos.yaml` y script `scripts/roscar_v01/pose_dock.py`. Es Python puro y se probó **en simulación** (escena física en 3D y, aparte, imágenes renderizadas pasadas por el detector); **nunca con el robot ni con una cámara real**. Falta el adaptador ROS 2 que publique el TF `map → odom`.

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

## Resultados en simulación
- Escena física en 3D (cámara con montaje e inclinación, tag con altura distinta): la conversión recupera la pose a 2 mm y 0.2° en la zona de acople (±4 cm y ±6°), y a 1e-9 sin inclinación.
- Del píxel a la pose en el dock (24 poses renderizadas con distorsión de lente, corregida, y montaje **conocido**): posición p95 0.35 cm y máximo 0.46 cm; ángulo p95 0.44° y máximo 0.72°.
- Con un reset real, una odometría que había derivado 9 cm vuelve a quedar a menos de 1.5 cm.
- Sin reset, una deriva de 7 cm y 4° cambia el giro planificado hacia el siguiente dock más de 2°; con reset, menos de 0.5°.

## Lo que falta
1. Medir el montaje y la posición del tag (arriba). Sin esto no hay pose en el dock.
2. El adaptador ROS 2: publicar `map → odom` desde `ResetPose.map_odom` y leer `/odom` con su marca de tiempo (sin verificar en el robot).
3. Decidir con el docente el marco del dock y si el reset debe ocurrir antes o después de la segunda medición del pit (README de referencia §15).
4. Con la cámara real, cuánto se aparta la medición de estas cifras (iluminación, foco, calibración).
