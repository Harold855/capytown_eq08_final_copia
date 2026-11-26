# carrito/ — módulos del ROSCar (Python puro, sin ROS)

Primer módulo real del carrito: el **planificador matemático** (sección 1.2 de la división, y 1.4 para el acople). No usa ROS: se prueba en cualquier PC y se empaquetará como paquete ROS 2 cuando el curso publique la plantilla. El ejecutor (que publica `/cmd_vel` por `twist_mux`) tomará los `Comando` que produce.

```
carrito/granprix_carrito/
  docks.py          docks del circuito (nominales del HTML; cargables desde JSON), conversión mapa <-> dock
  planificador.py   tramos, comando compensado, estimador de escalas, vuelta, presupuesto y acople
  acople.py         ciclo medir -> corregir -> medir con control proporcional (usa planificar_acople y el ejecutor)
  maquina_pit.py    máquina de estados de la misión (estados, plazos y seguridad dentro) y mision.py (estaciones, vueltas, piezas)
  calibracion_tramo.py  coordina las mediciones de cada parada con el estimador de escalas y guarda errores antes/después
  config/mision.yaml    equipo, vueltas, piezas, plazos y seguridad de la misión
  config/acople.yaml    tolerancias, ganancias, velocidades, reintentos y alcance del acople
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

## Configuración (`config/` y `configuracion.py`)
`config/movimiento.yaml` (velocidades y parámetros del ejecutor) y `config/calibracion.yaml` (semilla de las escalas y del estimador). `cargar_carrito(directorio, robot_esperado)` los carga, valida y comprueba que sean coherentes entre sí. Una configuración no puede superar 0.20 m/s ni 0.8 rad/s. Mapa completo y reglas en [`docs/configuracion.md`](../docs/configuracion.md).

```python
from carrito.granprix_carrito.configuracion import cargar_carrito
mov, est = cargar_carrito(robot_esperado='eq08-roscar')
ej = EjecutorMovimiento(salida, reloj, mov.ejecutor)
cmd = pl.comandar(tramo, est.escalas, mov.v_ref, mov.w_ref, mov.v_max, mov.w_max)
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

## Estimadores de escala (`calibracion.py`)
`EstimadorEscalas` es el estado de `cd` y `ca` durante la carrera. La fórmula es la del HTML (`c += alpha·(medido/comandado − c)`, `alpha = 0.35`); aquí se añade lo que hace falta para usarla.

```python
from carrito.granprix_carrito.calibracion import EstimadorEscalas
est = EstimadorEscalas(robot='eq08-roscar')          # o EstimadorEscalas.cargar('calibracion.yaml', robot_esperado='eq08-roscar')
cmd = pl.comandar(tramo, est.escalas)
# ... el ejecutor mueve el carrito; antes del acople se mide la pose de llegada con el tag ...
reg = est.observar(pose_salida_medida, pose_llegada_medida, ej.comando_efectivo(cmd), t=ahora)
est.escalas, est.convergio(), reg.motivo_cd, reg.motivo_ca
```

- **Entrada de cada observación:** pose medida al salir del dock anterior, pose medida al llegar **antes** de cualquier acople (`None` si no se vio el tag: se registra como `medicion_invalida` y no cambia nada) y el comando **realmente enviado** (`comando_efectivo`). Una prueba con rampa de aceleración muestra que con el comando nominal `cd` converge sesgado (≈ 1 %) y con el efectivo no.
- **Rechazos registrados**, escala por escala: tramo menor de 10 cm, giro fuera de 20°–150°, razón medido/comandado fuera de [0.5, 1.5], tag ausente, congelado, velocidad distinta. El paso máximo por actualización es 0.05.
- **No mezcla velocidades:** la escala vale para la `v` y la `ω` con que se calculó (se fijan con la primera observación usada, o al construir con `v_ref`/`w_ref`). RC-1 midió un giro 7–11 % mayor que el ordenado según ω, así que mezclar velocidades contaminaría `ca`. Mientras el planificador use siempre 0.10 m/s y 0.5 rad/s esto no se nota. *Es una inferencia con pocos datos ([Probable]), no una ley medida.*
- **`congelar()`** fija las escalas para la tanda oficial (3.5.4) y sigue registrando.
- **Archivo `calibracion.yaml`** con el identificador del robot; `cargar` falla si el robot no coincide, si hay valores no finitos o fuera de [0.5, 1.5], claves desconocidas o duplicadas, o versión desconocida (1.1.4: no aplicar parámetros históricos a otro robot). Escritura atómica. `carrito/config/calibracion.yaml` es la semilla editable; el estado generado va a la carpeta del experimento.
- **`exportar_csv`**: un renglón por observación (razones, escalas antes/después, motivos) para las gráficas del informe.
- **`evaluar_reduccion`**: fracción de paradas con error posterior menor que el previo (umbral 70 %). Cómo cuenta la rúbrica las paradas que ya estaban dentro de tolerancia **no está confirmado**: la función informa ambas versiones (`excluir_dentro`).

**Sobre alpha** (`python3 simulacion/barrido_alpha.py`, 200 semillas × 4 vueltas, robot simulado con giro +9 % y distancia +1 %, ruido del HTML, métricas en la última vuelta):

| alpha | error de llegada | llegadas válidas | pits para quedar a ±1.5 % en `ca` |
|---|---|---|---|
| 0.10 | 6.6 cm | 15 % | 17 |
| 0.20 | 2.8 cm | 78 % | 9 |
| **0.35** | **2.6 cm** | **83 %** | 5 |
| 0.50 | 2.8 cm | 78 % | 3 |
| 0.70 | 3.0 cm | 73 % | 2 |

Lectura: en este modelo 0.35 es un buen compromiso y no hay motivo para cambiarlo antes de medir. Alpha bajo no alcanza a corregir en las 16 paradas de una carrera de 4 vueltas; alpha alto amplifica el ruido del tag. Pero con 0.35 `ca` tarda en promedio unos 5 pits en estabilizarse, más que una vuelta: **conviene arrancar con las escalas caracterizadas el día 3 y no con 1.0**. Es simulación con el ruido del HTML; el ruido real del tag y el robot real pueden mover estos números.

**Criterio de convergencia** (provisional): al menos 4 actualizaciones usadas y diferencia máxima entre ellas < 0.01. En 300 semillas simuladas no declaró convergencia falsa y la declara entre 8 y 12 pits.

**Lo que no cubre:** la medición de poses (tag) es de `vision/`, la conversión a pose en el dock y el reset de pose están en `transformacion_camara_dock.py` y `reset_pose.py` (ver `docs/marcos_y_reset_pose.md`) y la secuencia del pit es de otro módulo; aquí se asume que las poses llegan ya medidas y coherentes entre sí. No hay adaptador ROS ni se escribe el archivo de estado automáticamente: lo decide el nodo que use este módulo.

## Acople fino y calibración por tramo (`acople.py`, `calibracion_tramo.py`)
`acoplar(medir, mover, cfg, escalas)` corrige la pose en el dock con el tag (hasta `1 + reintentos` correcciones) y `CalibradorTramo.cerrar_parada(...)` alimenta al estimador con la pose de llegada **anterior** al acople y con el comando realmente enviado del tramo, sin mezclar las correcciones. Ciclo, salvaguardas, scripts de ensayo, cifras de simulación y riesgos (sobre todo el tiempo y la marcha atrás): [`docs/acople.md`](../docs/acople.md).

```python
from carrito.granprix_carrito.acople import acoplar, cargar_acople, mover_con_ejecutor, MedidorTag
from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo
cfg = cargar_acople(None, mov)                                   # acople.yaml; exige v y w iguales a movimiento.yaml
res = acoplar(medidor.medir, mover_con_ejecutor(salida, reloj, dormir, mov.ejecutor, cfg, odom_ok, al_parar=medidor.en_reposo),
              cfg, est.escalas)
parada = calibrador.cerrar_parada(estacion, res, post=pose_tras_el_intercambio, vuelta=1)
```

## Máquina de la misión (`maquina_pit.py`, `mision.py`)
`MaquinaPit.paso()` (20 Hz, un hilo) recorre ESPERA → [MIDIENDO → ACOPLANDO → SOLICITANDO → ESPERANDO_RESULTADO → RECALIBRANDO → SALIENDO → NAVEGANDO] × 16 → FIN, o FALLA. Toda velocidad pasa por `SalidaSegura`; lo externo entra por `recibir_*` y las salidas hacia el curso por un `Puerto`. `nodos/adaptador_ros.py` la conecta con ROS 2. Estados, seguridad, interfaz y cifras de simulación: [`docs/mision.md`](../docs/mision.md). `python3 simulacion/mision_simulada.py` corre una misión completa simulada.

## Eventos, cronómetro y métricas
`MaquinaPit` registra sus eventos (`eventos_mision.py`, JSONL); `cronometro.py` y `metricas.py` calculan vueltas, sectores, pits y precisión desde ellos. Detalle, verificador de evidencia y panel: [`docs/tablero_y_evidencia.md`](../docs/tablero_y_evidencia.md).

## Verificación
- **Equivalencia con el HTML oficial:** `simulacion/modelo_granprix.py` usa este planificador y reproduce el `simulate()` original (mismas semillas) en 18 casos y 288 llegadas, con una tolerancia de 1e-9 (`tests/carrito/test_equivalencia_html.py`). La referencia son salidas del JavaScript original ejecutado con Node.js (`tests/carrito/referencia_html.json`).
- Pruebas en `tests/carrito/` (planificador, docks, equivalencia con el HTML y ejecutor con reloj falso y planta ideal con escalas reales, incluido un lazo cerrado planificador+ejecutor+estimador). Se ejecutan con `bash scripts/ejecutar_pruebas.sh`.
- Es lógica en Python puro: **no valida el movimiento físico**. La planta de las pruebas del ejecutor es ideal (sin retardo ni deslizamiento).

## Decisiones y supuestos (provisionales)
1. **`comandado` es lo que se envió** (ya compensado), no lo nominal. Con lo nominal el estimador converge a un valor sesgado (hay una prueba que lo demuestra).
2. **Protecciones del estimador** (`proteger=True`, por defecto): escalas en [0.5, 1.5], cambio máximo de 0.05 por actualización, y se ignoran tramos con menos de 10 cm o giros fuera de 20°–150°. El HTML pide un "paso limitado" sin fijar números: son nuestros. Con `proteger=False` el resultado es idéntico al del simulador oficial.
3. **Medir antes del acople:** la distancia y el giro de `medir_tramo` deben salir de las poses medidas al salir del dock anterior y al llegar al siguiente, antes de cualquier corrección.
4. **Marco del dock** (origen en el centro, x en el rumbo de llegada, y a la izquierda) es un supuesto hasta que exista `dock_frames.yaml`. El rumbo de llegada de cada dock coincide con el sentido del tramo que lo precede.
5. **Reversa:** `planificar_acople` no la usa por defecto (el carrito no detecta obstáculos hacia atrás). `acople.acoplar` la permite hasta 10 cm (`reversa_max_m` en `acople.yaml`; 0 la desactiva) y el ejecutor solo la admite con `Config(permitir_reversa=True)`.
6. **Por debajo de 1 cm** `planificar_acople` no avanza, solo corrige el rumbo; los giros menores de 0.5° se omiten (`acople.yaml` usa 1 cm y 1°).
7. **No modela** aceleración, frenado, retardo de `/odom`, ni qué pasa si el tag deja de verse durante el acople.
8. `scripts/roscar_v01/matematica.py` (v0.1) queda como referencia histórica; este módulo lo sustituye.
