# AprilTag sin robot: qué se puede probar y qué no

Verificado en este repositorio con `pupil-apriltags 1.0.4`, OpenCV 5.1 y la herramienta del docente (`vendor/granprix/estacion/herramientas/herramienta_apriltag.py`, sin modificar). Instalación: `bash scripts/preparar_entorno.sh --vision`.

## Qué se puede probar ya (sin robot ni cámara)
| Qué | Cómo | Resultado |
|---|---|---|
| Crear el tag e imprimirlo | `herramienta_apriltag.py crear --id 3 --tamano-mm 60` | genera PNG y SVG a tamaño real |
| La herramienta lee lo que crea | `herramienta_apriltag.py autoprueba` | OK con `tag36h11` (ids 0, 1, 7, 12) |
| Pruebas del docente | `pytest -k "not tag25h9 and not tag16h5"` en la carpeta de la herramienta | 24 pasan |
| Pose contra una verdad conocida | `simulacion/apriltag_sintetico.py` (renderiza un tag con pose conocida), `tests/vision/` | 14 pasan |
| Precisión según cámara, ruido y ángulo | `python3 simulacion/barrido_apriltag.py` | tabla abajo |
| Fallos: sin tag, otro id, dos tags, tag lejos | `tests/vision/` | `medir` devuelve `None`: no se adivina |

## Lo que mostró la simulación (cámara ideal pin-hole; cota optimista)
Con `tag36h11` de 6 cm a 22–34 cm, 40 muestras por celda, 640×480 y campo de visión de 70°:

- **Posición (x, z):** p95 del error < 0.2 cm en todas las condiciones (< 0.1 cm con 640×480 o más). Mejor de lo que supone el HTML (0.5 cm).
- **Ángulo `dth`:** es **peor cuando el tag está de frente** (|yaw| ≤ 6° con 640×480: p95 de 1.0 a 1.7°, máximo de 1.4 a 2.4°) y mejora al inclinarse (30–45°: p95 < 0.6°). Es la ambigüedad conocida de la pose plana, y justo ese es el régimen del acople (tolerancia 6°). Con 320×240 el máximo llega a 3.7°; con 1280×720 baja a ~1.2°.
- **Detección:** 100 % en todas las condiciones probadas, salvo 98 % con 1280×720, desenfoque de 1.5 px y ruido fuerte a 30–45°.

## Lo más importante: la distancia `z` depende de la calibración
La herramienta del docente aproxima la cámara con `--fov-h` (sin distorsión) y el tamaño `--tamano-mm`. Si esos datos están mal, `z` se corre aunque todo lo demás sea perfecto (tag a 24–32 cm, 640×480, error medio):

| Caso | Error en `z` | Error en `dth` |
|---|---|---|
| todo correcto | 0.02 cm | 0.34° |
| fov real 66°, se asume 70° (6 %) | **2.0 cm** | 0.60° |
| fov real 74°, se asume 70° | **2.1 cm** | 0.62° |
| fov real 60°, se asume 70° | **4.9 cm** (excede la tolerancia de 4 cm) | 0.98° |
| tag impreso 58 mm, se asume 60 | 0.9 cm | 0.62° |
| tag impreso 57 mm (impresora al 95 %) | 1.4 cm | 0.55° |
| tag impreso 63 mm, se asume 60 | 1.3 cm | 0.45° |

`x` y `dth` casi no se ven afectados. **Consecuencia práctica [Probable]:** `z` es la componente a lo largo del eje de acercamiento y entra en el error de posición del acople (≤ 4 cm), así que un fov aproximado puede consumir la mitad o todo el margen. Antes de confiar en la pose: medir el lado real del tag impreso con regla y calibrar la cámara (damero) o, como mínimo, ajustar la focal poniendo el tag a una distancia medida con regla.

## Lo que NO se puede probar sin la cámara real
- **Calibración intrínseca y distorsión** de la cámara del ROSCar. Resolución y campo de visión no están medidos: los de la tabla son ejemplos, **no son el hardware**.
- **Iluminación, enfoque, exposición, rolling shutter y retardo** reales. Mi ruido es gaussiano y simple.
- **Dónde está montada la cámara** respecto del centro del carrito y **dónde está el tag** respecto del dock: sin eso la pose de cámara no pasa a `PoseDock`. Falta `dock_frames.yaml` del docente.
- **Signo de `dth` respecto del carrito:** la prueba fija la convención de la herramienta (`dth > 0` con el tag girado como `rot_y(+)`), pero hay que comprobar físicamente qué giro real es ese antes de compensar.
- **Falsas aceptaciones** con el entorno real (otras marcas, reflejos). La herramienta informa `hamming` y `margen` pero no hay umbral decidido.
- **Rendimiento** en la Raspberry Pi 5 y en la Jetson (la frecuencia de detección).

## La distorsión del lente solo se ve fuera del eje
Probado en simulación con distorsión de barril (`k1`) y el método de calibración con regla: la focal ajustada y el error del ajuste **no cambian** (rms ≈ 0.03 cm), y con el tag centrado la validación es perfecta. El error de `z` aparece al desplazar el tag hacia los lados:

| `k1` | tag centrado | a 6 cm del centro | a 10 cm del centro |
|---|---|---|---|
| 0 (sin distorsión) | 0.04 cm | 0.08 cm | 0.02 cm |
| −0.1 | 0.04 cm | 0.18 cm | 0.42 cm |
| −0.25 | 0.05 cm | 0.44 cm | 1.00 cm |
| −0.4 | 0.02 cm | 0.75 cm | 1.66 cm |

(error máximo de `z` validando con distancias nuevas de 18 a 36 cm). Por eso el procedimiento exige validar con el tag a los lados a la misma distancia: el rms del ajuste no avisa.

## Aviso: la librería nativa aborta con otras familias
Con `pupil-apriltags 1.0.4` la prueba parametrizada del docente con `tag25h9` aborta el proceso (`malloc(): mismatching next->prev_size`, corrupción de memoria). Con `tag25h9` sola en un proceso limpio funciona, así que parece ocurrir al mezclar familias o detectores en el mismo proceso [Probable; sin investigar la causa]. **No afecta al reto** (usa `tag36h11`), pero: no crear varios `Detector` ni mezclar familias en un nodo. `simulacion/apriltag_sintetico.py` usa un solo detector por proceso. Esto explica el aborto que vi antes al probar la herramienta.

## Qué falta para cerrar la visión (necesita el laboratorio)
1. Imprimir el tag al 100 % y medir su lado con regla.
2. Calibrar la cámara del ROSCar: `scripts/camara/calibrar_focal.py` ya está hecho y probado con una cámara sintética (ajusta focal y offset de la regla con el tag a varias distancias y lo valida también fuera del eje); falta usarlo con la cámara real. Procedimiento: [`procedimiento_calibracion_camara.md`](procedimiento_calibracion_camara.md). Si el lente distorsiona (la validación fuera del eje falla), se usa el damero: `scripts/camara/calibrar_damero.py`, procedimiento en [`procedimiento_calibracion_damero.md`](procedimiento_calibracion_damero.md).
3. Medir la pose del tag a distancias y ángulos conocidos con regla y transportador, y comparar con la simulación: `scripts/camara/medir_tag.py comparar` y `resumen` ya lo hacen ([`procedimiento_medir_tag.md`](procedimiento_medir_tag.md)); falta usarlo con la cámara real.
4. Medir el montaje de la cámara y recibir/definir el marco del dock.
5. Decidir umbrales de `margen` y `hamming` con datos reales.
