# Procedimiento: calibrar la cámara del ROSCar con regla y AprilTag

**Para qué:** la herramienta del docente calcula la pose del tag suponiendo un campo de visión y un tamaño de tag. Un 6 % de error en el campo de visión mete ~2 cm de error en la distancia `z`, la mitad de la tolerancia de acople (`docs/apriltag_sin_robot.md`). Este procedimiento ajusta la focal real y comprueba que sirva en todo el cuadro. Dura unos 20–30 minutos y **no mueve el robot**: solo lee la cámara.

**Estado:** el script y su matemática están probados con una cámara sintética de parámetros conocidos (62 pruebas), **no con la cámara real del ROSCar**. Es la primera vez que se usará con hardware: anotar cualquier cosa rara en la bitácora.

## Material
- El tag `tag36h11` impreso **al 100 %** (SVG de la herramienta del docente), pegado en una superficie **rígida y plana** (cartón pluma o tablero; un papel combado falsea la pose).
- Regla o calibre (mm), una escuadra, cinta.
- Una superficie estable donde el robot quede **quieto** apuntando al tag, y luz pareja sin reflejos en el papel.

## 0. Preparación (una vez)
```bash
bash scripts/preparar_entorno.sh --vision        # OpenCV, numpy, pupil-apriltags y PyYAML
python3 scripts/camara/calibrar_focal.py --help
```
La cámara debe estar libre. Si un nodo de ROS la tiene abierta, `capturar` dirá que no puede abrirla: en ese caso guardar imágenes por otro medio y escribir el CSV a mano (paso 4, alternativa). No se asumen nombres de dispositivos ni de tópicos: ver `ros2 topic list` en el robot.

## 1. Medir el tag impreso
Con regla o calibre, medir el lado del **cuadrado negro** (el margen blanco no cuenta) en dos direcciones y promediar. Anotar el valor en mm (p. ej. `59.5`). **Este número se usa tal cual en los comandos**: un tag 1 % más grande de lo dado hace que la focal salga 1 % más chica (hay una prueba que lo demuestra).

## 2. Dejar la cámara fija
- Robot quieto, sin enviar ningún comando de movimiento. No tocar el foco ni cambiar la resolución durante todo el procedimiento.
- Anotar la resolución con la que se capturará (la herramienta la imprime). **La focal calculada solo vale para esa resolución.**
- Si la cámara tiene autofoco, conviene fijarlo si se puede [Especulando: algunos lentes cambian ligeramente su campo de visión al enfocar].

## 3. Preparar las distancias
La distancia se mide **desde el frente de la lente hasta la cara impresa del tag**, en perpendicular. No hace falta acertar el centro óptico: el ajuste calcula ese desfase (el "offset").
- Marcar en la mesa seis distancias: **15, 20, 25, 30, 35 y 40 cm** (el acople trabaja cerca de 28 cm; si el espacio no alcanza, usar al menos 3 y que sumen **10 cm o más** de rango).
- Usar la escuadra para que el tag quede **paralelo a la cámara** (de frente) y **centrado** en el cuadro. El tag inclinado más de 15° da aviso.
- Con el tag completo dentro del cuadro y bien enfocado a todas las distancias.

## 4. Capturar
```bash
python3 scripts/camara/calibrar_focal.py capturar --camara 0 --ancho 640 --alto 480 \
    --distancias 15,20,25,30,35,40 --tamano-mm 59.5 --salida experimentos/dia03_camara/
```
El script pide ir colocando el tag a cada distancia, descarta unos cuadros (autoexposición) y guarda diez por distancia. Si en menos del 70 % se ve el tag, pide repetir. `--camara` acepta un índice, una ruta (`/dev/video0`) o un pipeline de GStreamer.

*Alternativa sin el script de captura:* guardar las imágenes con cualquier medio y escribir `capturas.csv`:
```
imagen,distancia_cm,posicion
imagenes/a.png,15,centro
imagenes/b.png,20,centro
```
(`posicion` es opcional; sin ella cuenta como `centro`. Las rutas son relativas a la carpeta del CSV.)

## 5. Calcular
```bash
python3 scripts/camara/calibrar_focal.py calcular --csv experimentos/dia03_camara/capturas.csv --tamano-mm 59.5
```
Se guarda `camara_calibrada.yaml` junto al CSV (no pisa uno existente salvo `--sobrescribir`) y se imprime el comando para usarla con la herramienta del docente. Cómo leer el resultado:

| Dato | Bueno | Qué hacer si no |
|---|---|---|
| error del ajuste (rms) | ≤ 0.3 cm | > 0.3 cm avisa; **> 1 cm no guarda nada**: la regla o el tag se movieron, o la cámara se desenfocó. Repetir |
| offset de la regla | de 0 a unos 4 cm (el centro óptico suele quedar detrás del frente de la lente) | > 5 cm avisa: revisar cómo se midió |
| campo de visión resultante | 40–120° | fuera de rango avisa: revisar `--tamano-mm` y las unidades |
| rango de distancias | ≥ 15 cm | < 15 cm avisa que el offset queda poco determinado; < 8 cm no se calcula |

## 6. Validar (no omitir)
Con capturas **nuevas**: otras distancias **y el tag a los lados del cuadro a la misma distancia**.
```bash
python3 scripts/camara/calibrar_focal.py capturar --camara 0 --ancho 640 --alto 480 --distancias 18,23,28,33,38 \
    --tamano-mm 59.5 --salida experimentos/dia03_camara_validacion/
python3 scripts/camara/calibrar_focal.py capturar --camara 0 --ancho 640 --alto 480 --distancias 28 --posicion izq \
    --tamano-mm 59.5 --salida experimentos/dia03_camara_validacion/
python3 scripts/camara/calibrar_focal.py capturar --camara 0 --ancho 640 --alto 480 --distancias 28 --posicion der \
    --tamano-mm 59.5 --salida experimentos/dia03_camara_validacion/
python3 scripts/camara/calibrar_focal.py validar --camara-yaml experimentos/dia03_camara/camara_calibrada.yaml \
    --csv experimentos/dia03_camara_validacion/capturas.csv
```
Para `izq` y `der`: desplazar el tag lateralmente (hasta que quede cerca del borde del cuadro, entero a la vista) **sin cambiar la distancia al plano de la cámara**. La `z` debe salir igual que en el centro.

**Por qué los lados:** en simulación, un lente con distorsión de barril no cambia la focal ajustada ni el error del ajuste, pero el error de `z` fuera del eje crece: con `k1 = −0.25` un tag a 10 cm del centro da 1.0 cm de error y con `k1 = −0.4`, 1.6 cm. Solo se ve validando fuera del centro. Criterio: **error ≤ 1 cm en todas las posiciones** (la tolerancia del acople es 4 cm: este paso se queda con la cuarta parte del presupuesto). El comando devuelve código 0 si cumple y 2 si no.

**Si falla fuera del eje:** el lente distorsiona y este método no lo corrige. Hay que calibrar con un damero (`cv2.calibrateCamera`) para obtener también los coeficientes de distorsión. Ese script **no está hecho**; avisar y se prepara.

## 7. Registrar y usar
- Guardar en la bitácora (`docs/bitacora_laboratorio.md`): fecha, quién, lado del tag medido, resolución, resultado (focal, campo de visión, offset, rms), resultado de la validación y rutas de los archivos.
- Usar los valores con la herramienta del docente: el comando de `calcular` ya trae `--fx --fy --cx --cy --tamano-mm`. En código: `vision.calibracion_focal.cargar_camara(ruta).tupla()` da `(fx, fy, cx, cy)` para `herramienta_apriltag.detectar_en`.
- **Repetir la calibración** si cambia la cámara, la resolución o el foco, o si el robot se golpea.

## Errores comunes
| Error | Efecto |
|---|---|
| Dar el lado nominal (60 mm) en vez del medido | la focal sale sesgada en la misma proporción; el `z` posterior se compensa solo si se usa siempre ese mismo valor, pero con otro tag se descuadra |
| Tag combado o inclinado | la proporcionalidad del ajuste deja de ser exacta; avisa a partir de 15° |
| Medir la distancia desde la carcasa o desde el centro del robot | se absorbe en el offset, pero un valor > 5 cm avisa |
| Capturar con una resolución y usar otra | la focal en píxeles no sirve: `validar` lo rechaza |
| Mezclar imágenes laterales en el ajuste | el script las ignora (solo usa `centro`) y lo avisa |

## Lo que este procedimiento no resuelve
Distorsión del lente (solo la detecta), punto principal descentrado (se supone en el centro), enfoque, iluminación del laboratorio ni el montaje de la cámara respecto del centro del carrito. Esto último y el marco del dock siguen pendientes (`docs/apriltag_sin_robot.md`).
