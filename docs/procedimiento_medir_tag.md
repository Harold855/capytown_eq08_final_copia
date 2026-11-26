# Medir la pose del AprilTag con `medir_tag.py`

`scripts/camara/medir_tag.py` mide la pose del tag con una cámara **calibrada**: corrige la distorsión, descarta las detecciones dudosas y promedia varios cuadros. Solo lee la cámara: no mueve ningún robot. Núcleo en `vision/medicion.py`.

**Estado:** probado con una cámara sintética de parámetros conocidos (42 pruebas), **no con la cámara real**. Los umbrales de calidad son **provisionales**: se ajustan con los datos del primer día de laboratorio (cada medición guarda su margen y su hamming justamente para eso).

## Qué entrega y qué no
- **Pose en el sistema de la cámara:** `x` a la derecha, `y` hacia abajo, `z` hacia adelante, en **metros**; `dth` en **grados** (0 = tag de frente). Es la convención de la herramienta del docente.
- **NO está en el marco del dock.** Falta el montaje de la cámara en el carrito y `dock_frames.yaml` (el docente no lo ha publicado). Para pasarla a pose del robot en el dock y en el mapa: `scripts/roscar_v01/pose_dock.py` ([`marcos_y_reset_pose.md`](marcos_y_reset_pose.md)); necesita el montaje de la cámara medido.
- **Nunca entrega una pose conjeturada.** Una medición solo la lleva si el tag es único, tiene la calidad pedida y, al agregar, es estable entre cuadros. Si no, la pose es `null` y viene el motivo.
- La pose es en la **resolución de la calibración**: una imagen de otro tamaño es un error, no una medición.

## Uso
La cámara se da con `--camara-yaml` (de `calibrar_focal.py` o `calibrar_damero.py`; con la de damero hay que añadir `--tamano-mm`, el lado del cuadrado negro medido con regla). **Sin calibrar** (`--fov-h` + `--tamano-mm`) solo sirve para pruebas y avisa: un campo de visión con 6 % de error da ~2 cm de error en `z`.

```bash
# Una medición agregada (10 cuadros por defecto). Código 0 si se acepta, 2 si no:
python3 scripts/camara/medir_tag.py una --camara 0 --camara-yaml experimentos/dia03_camara/camara_calibrada.yaml --tag-id 3

# Un JSON por cuadro con mediana móvil de 5 cuadros válidos:
python3 scripts/camara/medir_tag.py continuo --camara 0 --camara-yaml ... --tamano-mm 59.5 --ventana 5 --segundos 30

# Comparar con la verdad medida con regla y transportador, guardando la evidencia (también lo que falle):
python3 scripts/camara/medir_tag.py comparar --camara 0 --camara-yaml ... --esperado-z-cm 28 --esperado-x-cm 0 \
    --esperado-dth 0 --offset-cm 1.8 --csv experimentos/dia03_camara_medicion/mediciones.csv --observaciones "luz de techo"

# Estadística de la evidencia:
python3 scripts/camara/medir_tag.py resumen --csv experimentos/dia03_camara_medicion/mediciones.csv
```
La fuente puede ser también `--imagen archivo.png` o `--video archivo.avi`. Si hay más de un tag a la vista, dar `--tag-id`; si no, no se mide.

### Salida de `una`
Un JSON por línea en la salida estándar (los avisos van a la salida de errores):
```json
{"modo": "una", "aceptada": true, "motivo": null, "id": 3, "n_cuadros": 10, "n_validos": 10,
 "x_m": 0.0303, "y_m": 0.0003, "z_m": 0.2796, "dth_deg": 9.71,
 "rango_x_m": 0.0, "rango_y_m": 0.0, "rango_z_m": 0.0, "rango_dth_deg": 0.0,
 "rechazos": {}, "calibrada": true, "distorsion_corregida": true, "camara": "..."}
```
`x_m`, `y_m`, `z_m` y `dth_deg` son la **mediana** de los cuadros válidos; los `rango_*` son la dispersión (máximo menos mínimo). `rechazos` cuenta por qué se descartaron cuadros.

## Cuándo se rechaza
| Motivo | Significa |
|---|---|
| `sin_tag` | no se detectó ningún tag |
| `otro_id` | hay tags pero ninguno del `--tag-id` pedido |
| `varios_tags` | más de un tag candidato (sin `--tag-id`, o repetido): no se adivina |
| `hamming` | la detección no coincide exactamente con el código (defecto: hamming máximo 0) |
| `margen_bajo` | margen de decisión bajo (defecto: 30; poca luz, desenfoque, tag lejos) |
| `sin_pose` / `error_pose` | el detector no calculó la pose, o su error supera `error_pose_max` si se pidió |
| `pocos_cuadros_validos` | menos del 70 % de los cuadros fueron válidos |
| `inestable_posicion` | `x`, `y` o `z` varían más de 0.5 cm entre cuadros |
| `inestable_angulo` | `dth` varía más de 2° entre cuadros |
| `ids_distintos` | los cuadros válidos vieron ids distintos |

Umbrales (todos **provisionales**): margen mínimo 30, hamming máximo 0, 70 % de cuadros válidos, dispersión de 0.5 cm y 2°. En simulación una detección sana da un margen de 105 a 120; con poco contraste baja a 23–47 y movido a ~53, y el margen no predijo el error de pose. Pueden cambiarse con `--margen-min` y `--hamming-max`; los de dispersión están en `vision/medicion.py`.

El modo `continuo` filtra con una mediana móvil y **olvida su historial tras 5 cuadros no válidos seguidos**: nunca presenta una pose vieja como actual.

## Validar la cadena de visión en el laboratorio (con regla y transportador)
Es el paso que faltaba para cerrar la visión: comparar lo que mide el código con una verdad física. **Antes**: calibrar la cámara y validarla fuera del eje (`procedimiento_calibracion_camara.md`).

1. Tag plano y rígido, medido con regla (lado del cuadrado negro). Robot quieto; no se envía ningún movimiento.
2. Para cada punto, colocar el tag y medir con **regla** la distancia del frente de la lente al plano del tag (`--esperado-z-cm`), con una **escuadra** el desplazamiento lateral respecto al eje de la cámara (`--esperado-x-cm`, positivo a la derecha) y con un **transportador** el giro del tag (`--esperado-dth`).
3. Ejecutar `comparar` con esos valores. Si la calibración es de regla, el desfase (`offset`) sale sola; con la de damero, darlo con `--offset-cm` (el que estimó `calibrar_focal.py validar`) o el error de `z` incluirá la distancia entre el frente de la lente y el centro óptico.
4. Cubrir: distancias de **20 a 36 cm** (el acople trabaja cerca de 28 cm), desplazamientos laterales hasta los bordes del cuadro, giros de **0° a ±30°** y, de preferencia, distintas condiciones de luz. **Hacen falta decenas de puntos**, no tres.
5. `resumen` calcula el error medio, el p95 y el máximo de `z`, `x` y `dth` de las mediciones **aceptadas** y compara con `--tol-cm` (1 cm) y `--tol-deg` (2°). Esas tolerancias son provisionales (una cuarta parte de los 4 cm del acople y un tercio de sus 6°). **Las no aceptadas se conservan en el CSV pero no cuentan**: si hay muchas, el problema es de luz, foco o umbrales, y es un resultado en sí.
6. Anotar en la bitácora y comparar con la simulación (`docs/apriltag_sin_robot.md`): en simulación el error de posición es de centésimas de centímetro y el de `dth` es peor con el tag **de frente** (p95 de 1.0 a 1.7°). Si la cámara real queda muy por encima, la diferencia es información sobre iluminación, foco, calibración o montaje.

## Lo que no se ha verificado
La cámara real, el Pi 5, la Jetson, y la latencia allí. En esta PC una medición completa (con corrección de distorsión) tarda unos 20–30 ms por cuadro; en el Pi 5 **no está medido** y cuenta contra el presupuesto de 10 s del pit.
