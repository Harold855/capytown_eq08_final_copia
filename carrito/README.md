# carrito/ — módulos del ROSCar (Python puro, sin ROS)

Primer módulo real del carrito: el **planificador matemático** (sección 1.2 de la división, y 1.4 para el acople). No usa ROS: se prueba en cualquier PC y se empaquetará como paquete ROS 2 cuando el curso publique la plantilla. El ejecutor (que publica `/cmd_vel` por `twist_mux`) tomará los `Comando` que produce.

```
carrito/granprix_carrito/
  docks.py          docks del circuito (nominales del HTML; cargables desde JSON), conversión mapa <-> dock
  planificador.py   tramos, comando compensado, estimador de escalas, vuelta, presupuesto y acople
simulacion/modelo_granprix.py   port a Python del simulate() del HTML, usando este planificador
```

## Qué hace
| Función | Fórmula / comportamiento |
|---|---|
| `planificar_tramo(pose, destino)` | `phi = wrap(atan2(dy, dx) - theta)`, `L = hypot(dx, dy)`; destino coincidente → giro 0 |
| `comandar(tramo, Escalas(cd, ca), v, w)` | `phi_cmd = phi/ca`, `L_cmd = L/cd`, `t_giro = abs(phi_cmd)/w`, `t_avance = L_cmd/v`; rechaza `v > 0.20` o `w > 0.8` |
| `pose_prevista`, `medir_tramo` | llegada ideal; distancia y giro entre dos poses medidas |
| `actualizar_escalas(...)` | `escala + alpha*(medido/comandado - escala)`, con protecciones provisionales |
| `planificar_vuelta`, `tiempo_vuelta` | los 4 comandos de una vuelta y su tiempo (116.57 s por vuelta con 6 s de pit, como el HTML) |
| `acople_valido`, `planificar_acople` | 4 cm y 6° a la vez; corrección con giros y avances (sin movimiento lateral) |

```python
from geometria_dock.transformaciones import Pose2D
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito import planificador as pl

tramo = pl.planificar_tramo(D[1].pose, (D[2].x, D[2].y))      # E1 -> E2: giro +90°, 2.0 m
cmd = pl.comandar(tramo, pl.Escalas(cd=1.01, ca=0.988))       # compensado, con duraciones
```

## Ejecutor de movimiento (`ejecutor.py`)
Toma un `Comando` y lo ejecuta en lazo abierto: **giro → pausa en ceros → avance → asentamiento en ceros**. No usa ROS: publica por una `Salida` (`publicar(v, w)`) y recibe el reloj por inyección. Se maneja con `paso()` a ~20 Hz y no bloquea.

```python
from carrito.granprix_carrito.ejecutor import EjecutorMovimiento, Config, Estado
ej = EjecutorMovimiento(salida, reloj, Config(), odom_ok=..., debe_parar=...)
ej.iniciar(cmd)                 # valida límites; lanza ValueError si no cumple
while ej.paso() not in (Estado.COMPLETO, Estado.ABORTADO, Estado.DETENIDO): ...
r = ej.resultado()              # L_ejecutada, phi_ejecutado (lo realmente enviado)
esc = pl.actualizar_escalas(esc, ej.comando_efectivo(cmd), d_medida, g_medido).escalas
```

| Condición | Resultado |
|---|---|
| `v > 0.20`, `|w| > 0.8`, valores no finitos, distancia negativa, tramo > 60 s | `iniciar` lanza `ValueError`, no publica nada |
| `debe_parar()` verdadero | `DETENIDO` (`PARADA_EXTERNA`) y ceros |
| `odom_ok()` falso | `ABORTADO` (`ODOM_PERDIDA`) y ceros |
| más de 0.25 s entre dos `paso()` (también el primero), o reloj que retrocede | `ABORTADO` (`HUECO_DE_TIEMPO` / `RELOJ_RETROCEDE`) y ceros |
| la `Salida` lanza excepción | `ABORTADO` (`ERROR_SALIDA`) |
| `abortar(motivo)` | `ABORTADO` y ceros; **no reanuda** |

Detalles que importan:
- Cada segmento dura lo que dice el comando **medido desde su primer envío**, y el último paso se escala (`ajustar_ultimo_paso`) para que lo comandado sea exacto y no un múltiplo del periodo. Sin esto se perdía hasta `v·0.05` m por segmento (bug encontrado por las pruebas).
- `comando_efectivo` devuelve lo integrado (Σ v·dt, Σ w·dt) de lo publicado de verdad. Es lo que debe recibir el estimador, sobre todo si se usa rampa o hubo un aborto.
- Rampa opcional (`a_lin_max`, `a_ang_max`): solo limita acelerar, nunca frenar; arranca desde el reposo. Desactivada por defecto.
- Termina siempre con ceros, repetidos tras un aborto o parada.

**Límites que este módulo no puede cubrir:** si el nodo ROS muere, nadie llama a `paso()` y el firmware conserva la última orden. La protección real es el timeout de la entrada de `twist_mux` (verificar en el robot que existe y su valor). Los valores `pausa_s = 0.30` y `asentamiento_s = 0.50` son **placeholders**: hay que medirlos en el robot (retardo de `/odom` 0.5–0.65 s sugiere que 0.5 s se queda corto para leer odometría tras parar). Falta el adaptador ROS 2 (Twist + `/odom` + reloj), que aquí no se puede probar.

## Verificación
- **Equivalencia con el HTML oficial:** `simulacion/modelo_granprix.py` usa este planificador y reproduce el `simulate()` original (mismas semillas) en 18 casos y 288 llegadas, con una tolerancia de 1e-9 (`tests/carrito/test_equivalencia_html.py`). La referencia son salidas del JavaScript original ejecutado con Node.js (`tests/carrito/referencia_html.json`).
- Pruebas en `tests/carrito/` (planificador, docks, equivalencia con el HTML y ejecutor con reloj falso y planta ideal con escalas reales, incluido un lazo cerrado planificador+ejecutor+estimador). Se ejecutan con `bash scripts/ejecutar_pruebas.sh`.
- Es lógica en Python puro: **no valida el movimiento físico**. La planta de las pruebas del ejecutor es ideal (sin retardo ni deslizamiento).

## Decisiones y supuestos (provisionales)
1. **`comandado` es lo que se envió** (ya compensado), no lo nominal. Con lo nominal el estimador converge a un valor sesgado (hay una prueba que lo demuestra).
2. **Protecciones del estimador** (`proteger=True`, por defecto): escalas en [0.5, 1.5], cambio máximo de 0.05 por actualización, y se ignoran tramos con menos de 10 cm o giros fuera de 20°–150°. El HTML pide un "paso limitado" sin fijar números: son nuestros. Con `proteger=False` el resultado es idéntico al del simulador oficial.
3. **Medir antes del acople:** la distancia y el giro de `medir_tramo` deben salir de las poses medidas al salir del dock anterior y al llegar al siguiente, antes de cualquier corrección.
4. **Marco del dock** (origen en el centro, x en el rumbo de llegada, y a la izquierda) es un supuesto hasta que exista `dock_frames.yaml`. El rumbo de llegada de cada dock coincide con el sentido del tramo que lo precede.
5. **Reversa:** el acople no usa reversa por defecto (el carrito no detecta obstáculos hacia atrás). `permitir_reversa=True` elige el camino de menor tiempo.
6. **Por debajo de 1 cm** el acople no avanza, solo corrige el rumbo; los giros menores de 0.5° se omiten.
7. **No modela** aceleración, frenado, retardo de `/odom`, ni qué pasa si el tag deja de verse durante el acople.
8. `scripts/roscar_v01/matematica.py` (v0.1) queda como referencia histórica; este módulo lo sustituye.
