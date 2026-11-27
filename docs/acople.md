# Acople fino y calibración por tramo

Cómo se corrige la pose del ROSCar en el dock con el tag, y cómo se alimenta con esas mediciones el estimador de `cd` y `ca` sin sesgarlo. Python puro: nada de esto se ha ejecutado contra el robot, la cámara ni ROS 2 real.

## Archivos

| Archivo | Función | Sin ROSCar |
|---|---|---|
| `carrito/granprix_carrito/acople.py` | Control proporcional y ciclo de corrección visual: `acoplar`, `ConfigAcople`, `MedidorTag`, `mover_con_ejecutor`, `cargar_acople` | Sí |
| `carrito/granprix_carrito/calibracion_tramo.py` | Coordina las mediciones con el `EstimadorEscalas` existente: `CalibradorTramo`, errores antes/después, CSV | Sí |
| `carrito/config/acople.yaml` | Tolerancias, ganancias, velocidades, reintentos y alcance | Sí |
| `tests/carrito/test_acople.py` | Corrección, convergencia, fallos, ejecutor real, medidor | Sí |
| `tests/carrito/test_calibracion_tramo.py` | Actualización integrada del estimador y circuito completo simulado | Sí |
| `scripts/roscar_v01/prueba_acople.py` | Ensayo en una estación: `simular` (sin ROS) y `ensayo` (con el robot) | Preparado |
| `scripts/roscar_v01/prueba_calibracion_adaptativa.py` | Escalas durante varios pits: `simular` y `repetir` (con tramos medidos) | Preparado |
| `scripts/roscar_v01/analizar_acople.py` | Resumen y gráficos SVG de errores y escalas | Sí |
| `simulacion/robot_simulado.py` | Robot con escalas reales ocultas y ruido, para las pruebas y los scripts | Sí |

Reutiliza `planificar_acople` (geometría), `comandar` (compensa con `cd` y `ca`), `EjecutorMovimiento`, `acople_valido` y `EstimadorEscalas.observar`. Lo nuevo es el ciclo, las salvaguardas y el orden de los datos.

## El ciclo

```
medir ─ ¿dentro de la tolerancia interna? ─ sí ─> listo
          │ no
          ├─ fuera de alcance / sin tiempo / parada / reintentos agotados ─> se detiene con un motivo
          └─ plan: giro hacia el dock + avance (ganancia) + giro final (ganancia) ─> ejecutor ─> medir ─> ...
```

- **Tolerancia interna** 3 cm y 4° (`acople.yaml`): se corrige hasta quedar dentro de esto. El éxito se juzga con los **4 cm y 6° del reto**. Una pose entre ambos es `exito=True` con `motivo='EN_BORDE'`. El cargador rechaza tolerancias mayores que las del reto.
- **Reintentos:** `1 + reintentos` correcciones como máximo (reintentos ≤ 2, límite del reto). Es una lectura del reto: «con hasta 2 reintentos» → la primera corrección más dos. **Por confirmar con el docente.**
- **Solo ángulo** si la posición ya está dentro del margen: un giro en su sitio, sin avanzar.
- **Ganancia** (1.0 por defecto) sobre el avance y el giro final; el giro de alineación hacia el dock no se escala.
- **Compensa con las escalas** `cd` y `ca` vigentes. Usa las mismas `v` y `ω` que `movimiento.yaml` (el cargador lo exige: las escalas valen a esa velocidad).
- **Marcha atrás** hasta `reversa_max_m` (0.10 m) para sobrepasos. Sin ella, pasarse 7 cm del dock obligaría a girar casi 180° dos veces. Pide un `permitir_reversa` en el ejecutor, desactivado por defecto y que solo activa el acople. `reversa_max_m: 0` la desactiva; `prueba_acople.py --sin-reversa` también.
- **No gira más de 120°** (`GIRO_EXCESIVO`), **no intenta** más allá de 30 cm o 45° (`FUERA_DE_ALCANCE`) y **no inicia otra corrección** pasados 4 s (`SIN_TIEMPO`).
- Tras un **movimiento fallido** (odometría perdida, parada externa, comando rechazado) no se vuelve a medir ni se afirma ninguna pose: `exito=False`, `pose_final=None`.
- La medición y el movimiento entran como funciones, así que el ciclo es el mismo con el simulador, con un robot real y con la futura máquina de estados.

### Motivos de `ResultadoAcople.motivo`
`None` (dentro del margen) · `EN_BORDE` (éxito sin margen) · `SIN_TAG` · `FUERA_DE_ALCANCE` · `GIRO_EXCESIVO` · `REINTENTOS_AGOTADOS` · `SIN_TIEMPO` · `PARADA_EXTERNA` · `MOVIMIENTO_<motivo del ejecutor>` · `COMANDO_INVALIDO`.

### `MedidorTag`
Devuelve la mediana de `lecturas` mediciones llegadas **después** de que el robot quedó quieto y pasó `espera_s`. Las lecturas anteriores no valen: el nodo de cámara filtra con una ventana de 5 y una imagen tomada en movimiento daría una pose falsa. Lo alimenta el callback de `/tag/pose` (`agregar`) y lo avisa `mover_con_ejecutor` al terminar cada movimiento (`en_reposo`).

## Calibración por tramo

`CalibradorTramo` impone el orden que el estimador necesita:

1. `salida(pose)`: la pose medida **al salir** del pit anterior (la medición posterior al intercambio).
2. `comando(efectivo)`: lo **realmente enviado** en el tramo (`comando_efectivo` del ejecutor).
3. `cerrar_parada(estacion, resultado_acople, post)`: al final del pit. Observa el tramo con la pose de **`resultado_acople.pose_inicial`** (la de llegada, antes de cualquier corrección; no se puede pasar otra), guarda los errores antes y después, y deja `post` como salida del tramo siguiente.

Los movimientos del acople nunca llegan al estimador. Si el tag no se vio al llegar, el tramo se registra como `medicion_invalida` y las escalas no cambian. Si falta `post`, se usa la última medición del acople (el robot no se movió durante el intercambio).

**Error antes y después, con el mismo criterio:** `max(error_pos / 4 cm, error_ang / 6°)`; 1.0 es el límite del reto. Es **nuestro criterio**: el reto no define cómo se comparan. `evaluacion()` aplica el umbral del 70 % con y sin las paradas que ya llegaron dentro.

CSV: `exportar_paradas` (una fila por parada; `anexar=True` para varios ensayos) y `exportar_tramos` (lo necesario para repetir la estimación con otro `alpha`, `leer_tramos`). Las columnas del primero cubren parte de lo que pide la evidencia (`pits.csv`): vuelta, estación, errores antes y después, reintentos y escalas; faltan el tiempo de pit y la pieza, que son de la máquina de estados.

## Uso

```bash
# Sin robot
python3 scripts/roscar_v01/prueba_acople.py simular --dx -0.06 --dy 0.02 --dth 8 --cd 1.01 --ca 1.09
python3 scripts/roscar_v01/prueba_calibracion_adaptativa.py simular --vueltas 6 --csv-paradas p.csv --csv-tramos t.csv
python3 scripts/roscar_v01/prueba_calibracion_adaptativa.py repetir --tramos t.csv --alpha 0.2 0.35 0.5
python3 scripts/roscar_v01/analizar_acople.py p.csv --salida experimentos/graficos

# Con el robot (necesita ROS 2, el nodo de cámara y marcos.yaml medido)
python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --marcos carrito/config/marcos.yaml          # solo mide y calcula
python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --ejecutar --zona-segura --csv paradas.csv   # mueve el robot
```

`ensayo --ejecutar` exige `--zona-segura`, se niega si hay otro publicador en el tópico de velocidades o si `/odom` está viejo, pierde la odometría → ceros, y solo publica ceros si llegó a mover. Con `twist_mux`, indicar la entrada autorizada con `--topic-cmd`. Misma advertencia de seguridad que `prueba_movimiento.py`: zona despejada, parada física a mano, nada más publicando velocidades.

## Qué mostró la simulación

Robot con `cd = 1.01`, `ca = 1.09` que el controlador desconoce, ruido del 1 % en cada movimiento y de 2 mm y 0.25° en el tag. **Es un modelo ideal** (sin retardos, zona muerta ni deslizamiento): sirve para elegir diseño, no para predecir el robot.

| Hallazgo | Cifra |
|---|---|
| Ganancia 1.0 frente a 0.9 (2000 acoples, error inicial hasta 10 cm y 12°) | 100 % frente a 82 % de acoples válidos: con 0.9 hacen falta más correcciones y se agota el presupuesto de tiempo |
| Sin marcha atrás | El 13 % de los casos (sobrepaso) exigiría girar casi 180° |
| Tiempo por corrección | ≈ 3.9 s de movimiento y esperas del ejecutor, **sin** contar la espera de la medición |
| Escalas aprendidas en 8 vueltas (30 semillas) | `cd` y `ca` a menos del 1.4 % de los valores reales; la convergencia se declara en 26 de 30 |
| Error de llegada | Baja de ≈ 16 cm (primera vuelta, con escalas 1.0) a ≈ 3.5 cm (últimas dos vueltas) en las 30 semillas |
| Arrancar con escalas 1.0 | La primera parada llega a ≈ 28 cm (9 % de giro a 2 m) y el acople se niega por alcance; con las escalas caracterizadas, 30 de 30 circuitos tienen todas las paradas válidas (frente a 7 de 30) |
| Pose posterior al acople como entrada del estimador | No descubre las escalas (control negativo en `test_calibracion_tramo.py`) |

## Lo que debe saber antes de usarlo

1. **El tiempo es el problema real** [Probable]. Una corrección cuesta ≈ 4–5 s con la medición. Con un intercambio de 6 s en E2/E3 sobran unos 4 s dentro del pit de 10 s: **una sola corrección ya consume casi todo**. El acople es la red de seguridad; lo que ahorra tiempo es llegar bien (escalas caracterizadas el día 3 y reset de pose).
2. **Marcha atrás a ciegas** [Seguro, es una decisión]. El carrito no ve hacia atrás. Está limitada a 10 cm y dentro de la zona del dock, pero la primera vez hay que ensayarla con `--zona-segura` y alguien a mano. Si no se autoriza: `reversa_max_m: 0`.
3. **Todos los umbrales propios** (tolerancia interna, ganancia, alcance, presupuesto, mínimos) son provisionales. Los mínimos (1 cm y 1°) son una suposición: el robot real probablemente no responde a órdenes de 100 ms.
4. **`espera_s = 0.8` y `lecturas = 3`** del medidor son estimaciones: dependen del retardo real de la cámara y de `/odom` (0.5–0.65 s en RC-1). Medirlos.
5. **El modo `ensayo` se probó solo contra un `rclpy` sustituto** con un mundo simulado: demuestra el cableado, no que la API de ROS 2 esté bien usada ni que el robot responda como el modelo.
6. **Dependen de `marcos.yaml`**: sin el montaje de la cámara y la posición del tag medidos no hay pose en el dock y `ensayo` se niega a arrancar.
7. **Pendiente de decidir con el docente:** si «2 reintentos» incluye la primera corrección, cuál es el «error después del pit» de la rúbrica (la segunda medición tras el intercambio, que es lo que se usa aquí) y cómo cuentan las paradas que ya llegan dentro.
