# Procedimiento: calibrar la cámara del ROSCar con un damero (incluye la distorsión del lente)

**Cuándo usarlo:** solo si la validación del método de la regla falla **fuera del eje** (`docs/procedimiento_calibracion_camara.md`, paso 6). Ese método ajusta la focal pero no ve la distorsión. En simulación, con barril `k1 = −0.4`, un tag a 10 cm del centro da 1.7 cm de error en `z` sin que el ajuste lo note. Si el paso 6 cumple (≤ 1 cm a los lados), **no hace falta este procedimiento**.

**Estado:** matemática y script probados con una cámara sintética de parámetros y distorsión conocidos (148 pruebas de visión), **no con la cámara real del ROSCar**. Primera vez en hardware: anotar todo lo raro en la bitácora. Dura unos 30 minutos y no mueve el robot.

## Qué entrega
`camara_calibrada.yaml` con `fx = fy`, punto principal `cx, cy` y los coeficientes `k1, k2` (y `p1, p2, k3` con el modelo `completo`). Con distorsión, **cada imagen debe corregirse antes de detectar el tag**: la herramienta del docente supone un lente sin distorsión y su comando `detectar` **no la corrige**. Por eso con una calibración de damero no se usa el comando de la herramienta tal cual, sino el código del repositorio:
```python
from vision.calibracion_focal import cargar_camara
from vision.herramienta import Corrector, pose_tag_calibrada
cam = cargar_camara('experimentos/dia03_damero/camara_calibrada.yaml')
corrector = Corrector(cam)                                   # los mapas se calculan una vez
pose = pose_tag_calibrada(imagen, cam, corrector, tamano_m=0.0595)   # corrige y mide; None si no hay un tag
```
Para medir con filtro de calidad, agregación de cuadros y evidencia, usar `scripts/camara/medir_tag.py` ([`procedimiento_medir_tag.md`](procedimiento_medir_tag.md)).
(El tamaño del tag no se guarda en la calibración de damero: se da al medir.)

## Material
- Un damero impreso al 100 % en una superficie **rígida y plana**, sin arrugas ni reflejos (papel mate, cartón pluma o tablero). Un damero combado falsea la distorsión.
- Luz pareja. Un lugar donde mover y sostener el damero frente a la cámara con el robot quieto.

## 0. Preparación
```bash
bash scripts/preparar_entorno.sh --vision
python3 scripts/camara/calibrar_damero.py crear --cols 9 --filas 6 --cuadro-mm 20 --salida experimentos/damero/
```
`--cols` y `--filas` son las esquinas **interiores** (9×6 = un damero de 10×7 cuadros). Con 20 mm por cuadro mide 240×180 mm y cabe en una hoja A4. Imprimir el SVG **al 100 %** (sin "ajustar a la página"), pegarlo en la superficie rígida y **medir con regla el lado de un cuadro impreso**. Ese valor se pasa en `--cuadro-mm`; a diferencia del tag en el método de la regla, **no es crítico**: la focal y la distorsión no dependen del tamaño del cuadro (solo la traslación).

## 1. Capturar
Con el robot quieto y la resolución que se usará en la carrera (la focal en píxeles solo vale para esa resolución):
```bash
python3 scripts/camara/calibrar_damero.py capturar --camara 0 --ancho 640 --alto 480 --objetivo 20 --salida experimentos/dia03_damero/
```
No hay que pulsar nada: el script guarda un cuadro cuando el damero se ve **completo**, está **quieto** y su pose **difiere** de las ya guardadas. Mover despacio y detenerse un instante en cada pose. Mientras captura dice qué zonas de la imagen faltan por cubrir. Lo que importa:
- **Inclinar** el damero en varias direcciones, al menos 3 imágenes con 15° o más (con el damero siempre de frente la focal no queda determinada: el cálculo lo rechaza) y de preferencia hasta 40°.
- **Llevarlo hasta los bordes y las esquinas** del cuadro: la distorsión se estima ahí. El cálculo avisa si cubrió menos de 6 de 9 zonas.
- **Variar la distancia** (cerca y lejos, con el damero ocupando entre un tercio y dos tercios del cuadro).
- **Tomar 20 o más imágenes.** Con exactamente 10 no se puede descartar ninguna atípica (ver abajo).
- La cámara debe estar libre; si un nodo de ROS la tiene abierta, el script lo dice. En ese caso guardar imágenes por otro medio en una carpeta y seguir con el paso 2.

## 2. Calcular
```bash
python3 scripts/camara/calibrar_damero.py calcular --imagenes experimentos/dia03_damero/ --cuadro-mm 20
```
Guarda `camara_calibrada.yaml` en esa carpeta (no pisa uno existente sin `--sobrescribir`). Cómo leerlo:

| Dato | Bueno | Qué hacer si no |
|---|---|---|
| error de reproyección | < 0.5 px | 0.7–1.5 px avisa; **> 1.5 px no guarda nada**: imágenes movidas o desenfocadas, damero combado o `--cols/--filas` mal |
| error en imágenes no usadas | ≤ 1 px | si es mucho mayor que el anterior, el modelo no generaliza: más imágenes o modelo `simple` |
| imágenes descartadas | 0–2 | el cálculo quita solas las imágenes con esquinas mal localizadas (de una en una, hasta el 25 % y nunca bajando de 10) y las nombra; una sola de ellas, sin descartar, desvió la focal más de un 1 % (hasta ~3 % en las pruebas) |
| cobertura | 9/9 zonas | si faltan zonas, el aviso las nombra: llevar el damero ahí |
| punto principal | cerca del centro | a más de un 10 % de la imagen avisa: revisar cobertura e inclinación |
| "la distorsión desplaza la esquina X px" | — | **< 2 px: la distorsión es despreciable y el método de la regla bastaba** |

`--modelo simple` (defecto: `k1, k2`, sin tangencial ni `k3`) es el más estable con pocas vistas y lo habitual en cámaras web; `completo` añade `p1, p2, k3` y pide más imágenes (25 o más).

## 3. Validar (hay dos comprobaciones y miden cosas distintas)

**3a. Con imágenes nuevas del damero** (no usadas para calibrar):
```bash
python3 scripts/camara/calibrar_damero.py capturar --camara 0 --ancho 640 --alto 480 --objetivo 10 --salida experimentos/dia03_damero_validacion/
python3 scripts/camara/calibrar_damero.py validar --camara-yaml experimentos/dia03_damero/camara_calibrada.yaml --imagenes experimentos/dia03_damero_validacion/
```
Cumple con un error de reproyección ≤ 0.7 px (código 0; 2 si no). **Qué valida:** la distorsión y la consistencia del modelo. En las pruebas, ignorar una distorsión `k1 = −0.3` da 0.89 px, es decir NO cumple (con una tolerancia de 1 px sí habría cumplido: por eso es 0.7). **Qué NO valida:** la escala. Un error de 10 % en la focal casi no cambia la reproyección, porque con el damero casi de frente se compensa moviendo la distancia estimada. Hay una prueba que lo demuestra y el informe lo dice.

**3b. Con el tag, la regla y el tag a los lados (esta es la que decide):**
```bash
python3 scripts/camara/calibrar_focal.py validar --camara-yaml experimentos/dia03_damero/camara_calibrada.yaml \
    --csv experimentos/dia03_camara_validacion/capturas.csv --tamano-mm 59.5
```
Es el mismo `validar` del procedimiento de la regla (mismas capturas, con `posicion` centro, izq y der). Con una calibración de damero corrige la distorsión antes de medir y estima el offset de la regla con las propias capturas centradas (el damero no lo conoce). **Criterio: error ≤ 1 cm en todas las posiciones.** En simulación pasa de 1.7 cm a menos de 0.7 cm con `k1 = −0.4`. Mide la **coherencia** entre distancias y posiciones, no la exactitud absoluta: como el offset se estima, un error de escala constante quedaría escondido solo en parte (se vería como pendiente entre distancias).

## 4. Registrar y usar
Bitácora: fecha, quién, patrón y lado del cuadro medido, resolución, número de imágenes, error de reproyección, desplazamiento en la esquina, resultado de 3a y 3b y las rutas de los archivos. Repetir la calibración si cambia la cámara, la resolución o el foco, o si el robot se golpea.

## Errores comunes
| Error | Efecto |
|---|---|
| `--cols` y `--filas` invertidos o contando cuadros en vez de esquinas interiores | no se halla el damero; el mensaje pide revisar "esquinas INTERIORES" |
| Damero siempre de frente | la focal no queda determinada: el cálculo lo rechaza |
| Damero solo en el centro | la distorsión no se estima bien: avisa y nombra las zonas vacías |
| Damero combado o impreso en papel fino | error de reproyección alto; > 1.5 px no se guarda |
| Menos de 20 imágenes | si hay una atípica no se puede descartar; avisa |
| Usar el comando `detectar` de la herramienta del docente con esta calibración | **mide mal**: no corrige la distorsión; usar `pose_tag_calibrada` |
| Cambiar la resolución después de calibrar | `validar` lo rechaza; la focal en píxeles no sirve |

## Lo que no se ha probado
Con la cámara real (hardware, enfoque, iluminación), con el OpenCV de la Jetson o del Pi 5 (el código usa funciones disponibles desde OpenCV 3.x/4.x [Probable]; no verificado ahí) ni con un damero impreso de verdad. El detector de esquinas es el clásico de OpenCV (`findChessboardCorners` con refinado subpíxel): `findChessboardCornersSB` devolvió las esquinas en otro orden y no se adoptó. Tampoco corrige el montaje de la cámara respecto del carrito ni resuelve el marco del dock.
