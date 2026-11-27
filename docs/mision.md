# Máquina de la misión (`maquina_pit`)

Coordina toda la misión del ROSCar: navegar a cada estación, medir, acoplar, solicitar el intercambio, esperar quieto, recalibrar y salir, durante cuatro vueltas, con la seguridad de **nuestra** lógica. Python puro más un nodo delgado. **Nunca se ejecutó con ROS 2 real, con el robot ni con Race Control**: solo con una planta y una estación simuladas, y con un `rclpy` sustituto.

## Archivos

Se empezó con estados, temporización y seguridad **dentro de `maquina_pit.py`** (387 líneas); se separarán si crece.

| Archivo | Función |
|---|---|
| `carrito/granprix_carrito/maquina_pit.py` | Estados y transiciones, `MaquinaPit`, plazos por estado (`_plazo`), `Seguridad`, `SalidaSegura` y `Puerto` |
| `carrito/granprix_carrito/mision.py` | `Mision` (estaciones, vueltas, piezas, registro de pits) y `cargar_mision` |
| `carrito/config/mision.yaml` | Equipo, vueltas, cadena de piezas, plazos y seguridad |
| `carrito/granprix_carrito/adaptador_ros.py` | Nodo `maquina_pit`: conecta el núcleo con ROS 2 |
| `tests/carrito/test_maquina_pit.py` | Estados, transiciones, plazos, seguridad e intercambio, fallos (49 pruebas) |
| `tests/carrito/test_mision.py` | Configuración, estaciones, piezas y vueltas (14) |
| `tests/carrito/test_adaptador_ros.py` | Cableado del nodo con `rclpy` sustituto (21) |
| `simulacion/mision_simulada.py` | Misión completa simulada (`python3 simulacion/mision_simulada.py`) |

Cambios en lo anterior: `acoplar` es ahora un generador (`acoplar_pasos`; la versión bloqueante sigue igual) para que `ACOPLANDO` avance un paso por tick sin hilos; `MedidorTag.intentar/esperar` y `mover_con_ejecutor(dormir=None)` hacen lo mismo con la medición y el movimiento.

## Estados

```
ESPERA ─(autorizado)─> [ MIDIENDO ─> ACOPLANDO ─> SOLICITANDO ─> ESPERANDO_RESULTADO ─> RECALIBRANDO ─> SALIENDO ─> NAVEGANDO ] ─> … ─> FIN
cualquier estado activo ─(fallo)─> FALLA          FIN / FALLA ─(reiniciar)─> ESPERA
```

| Estado | Qué hace | Plazo (`mision.yaml`) |
|---|---|---|
| `ESPERA` | No publica nada (se puede posicionar el robot). Arranca con turno autorizado, bandera verde y enlace vivo; el primer pit es el de E1 | — |
| `MIDIENDO` | Espera una medición válida del tag con el robot quieto | 4 s |
| `ACOPLANDO` | `acoplar_pasos` con la medición ya hecha; si queda fuera de 4 cm y 6° → `FALLA` y **no se solicita** | 20 s |
| `SOLICITANDO` | Publica la solicitud con la pose medida y la pieza que trae; espera si hay un intercambio en curso | 3 s |
| `ESPERANDO_RESULTADO` | Quieto durante la manipulación; solo acepta el `resultado` de su estación | 15 s |
| `RECALIBRANDO` | Segunda medición, reset de pose (reintenta si `/odom` no llegó), `CalibradorTramo.cerrar_parada`, cierra el pit en la misión | 6 s |
| `SALIENDO` | Espera que ninguna estación esté `CAMBIANDO`, planifica el tramo con las escalas nuevas y arranca el ejecutor | 3 s |
| `NAVEGANDO` | Ejecuta el tramo (lazo abierto); al terminar guarda el comando efectivo y pasa a `MIDIENDO` | tramo + margen 8 s |
| `FIN` | Misión completa; ceros hasta que alguien reinicie | — |
| `FALLA` | Aborta y mantiene parada segura (ceros en cada paso); terminal hasta `reiniciar()` | — |

La secuencia exacta de estados de las 16 paradas está fijada por una prueba.

## Misión

Una vuelta son los pits E1, E2, E3 y E4; cierra al terminar el de E4 y la misión, al cerrar la última (16 pits). Piezas (`mision.yaml`): E1 trae vacío y deja A; E2 A→B; E3 B→C; E4 C→vacío; la cadena debe cerrar o el cargador falla. Por pit se guarda una fila de `pits.csv` (vuelta, estación, llegada, tiempo de pit, errores antes y después, correcciones, reintentos, `cd`, `ca`, piezas, validez), lo que pide la evidencia salvo el video y el bag.

- `resultado ok` con otra pieza de la esperada: el pit se marca inválido (`PIEZA_INESPERADA`), se avisa y **la misión sigue** (se necesitan 3 vueltas válidas de 4).
- `resultado` no ok: `FALLA` (`RESULTADO_NO_OK`) sin avanzar la misión.
- Tiempo de pit = desde que termina el tramo hasta que arranca el siguiente. Pasar de 10 s **se cuenta** (`pits_lentos`) pero no aborta: abortar sería peor que un pit lento.

## Seguridad de nuestra lógica

Lo que hace: impedir movimientos no autorizados, impedir la salida durante un intercambio y gestionar fallos. **No sustituye** al `vigilante_red` del curso, a `twist_mux` ni a la parada física, y no hay vigilante de red ni puente MQTT propios.

| Condición | Efecto |
|---|---|
| Sin turno autorizado (o nunca llegó) | No arranca; en marcha → `SIN_AUTORIZACION` |
| Bandera roja | `BANDERA_ROJA` en cualquier estado activo |
| Sin enlace o último latido de más de 2 s | `ENLACE_PERDIDO` |
| Estación `OFFLINE` | `ESTACION_OFFLINE` |
| Tanda de más de 720 s | `TANDA_AGOTADA` |
| Parada manual (`~/parar`) | `PARADA_MANUAL`, al instante |
| Plazo de un estado vencido | `TIMEOUT_<ESTADO>` |
| Movimiento abortado (odometría perdida, parada externa…) | `MOVIMIENTO_<motivo>` |
| Acople no válido | `ACOPLE_<motivo>`; no se solicita |
| Error inesperado en el código | `ERROR_INTERNO`; el robot no se queda con la última orden |

- **Una sola puerta de salida:** todo `Twist` pasa por `SalidaSegura`. Solo sale velocidad en `NAVEGANDO` y `ACOPLANDO`, con permiso y sin intercambio en curso (solicitud enviada sin resultado, o **cualquier** estación `CAMBIANDO`: hay un equipo por tanda). En cualquier otro caso sale cero.
- En los estados quietos, `FALLA` y `FIN` se publican ceros en cada paso (20 Hz). `ESPERA` no publica.
- Falla cerrada: lo que no ha llegado nunca (turno, enlace) cuenta como no autorizado.
- Mensajes inválidos del curso (JSON roto, tipo incorrecto, otro equipo) se descartan y nunca autorizan nada.
- `FALLA` no se recupera sola. `reiniciar()` (servicio `~/reiniciar`) solo funciona desde `ESPERA`, `FIN` o `FALLA`; reinicia la misión desde E1 (hay que recolocar el robot) y **conserva las escalas aprendidas**. No se reanuda a mitad de tramo: el ejecutor no sabe retomarlo.
- Un solo hilo (`rclpy.spin`): sin cerrojos.

**Lo que esto no cubre:** si el nodo muere, nadie publica ceros y el firmware conserva la última orden; lo protege el *timeout* de nuestra entrada de `twist_mux` y la parada física, y ambos están **sin verificar** en el robot.

## Interfaz ROS 2 (nombres nuestros, provisionales)

El curso no ha publicado las interfaces del `puente_mqtt`; los nombres son parámetros del nodo y los mensajes del contrato viajan como JSON en `std_msgs/String`.

| Dirección | Tópico / servicio | Contenido |
|---|---|---|
| entra | `/odom`, `/tag/pose` | frescura de la odometría; tag → pose en el dock de la estación actual |
| entra | `/granprix/turno`, `/granprix/bandera` | `{"autorizado": bool}`, `{"bandera": "verde"\|"roja"}` |
| entra | `/granprix/enlace` | `std_msgs/Bool` (2 Hz, según la doc. 03) |
| entra | `/granprix/estacion_estado` | `{"estacion": n, "estado": "CAMBIANDO"…}` (el puente añade `estacion`) |
| entra | `/granprix/resultado` | `ResultadoMsg` más `"estacion": n`; solo el de nuestro equipo |
| sale | `/cmd_vel` | `Twist`; apuntar a la entrada autorizada de `twist_mux` |
| sale | `/granprix/solicitud`, `evento`, `vuelta`, `telemetria` | JSON del contrato (constructores de `mensajes_contrato.py`) |
| sale | `/pit/estado`, `/pit/dock` | estado (JSON) y estación actual (`Int32`; lo usa `nodo_reset_pose`) |
| cliente | `/reset_pose/aplicar` | `Trigger` de `nodo_reset_pose`; si no está disponible se sigue sin reset |
| servicios | `~/reiniciar`, `~/parar` | `Trigger` |

Con `resultados_dir`, al terminar (`FIN` o `FALLA`) guarda `pits.csv`, `paradas.csv` y `tramos.csv`.

## Qué mostró la simulación

Planta continua con `cd = 1.01` y `ca = 1.09` ocultos, ruido del 1 % en cada movimiento, tag con 2 mm y 0.25°, intercambio de 5.8 s, y una estación que valida con la pose **verdadera**. 30 semillas. Es un modelo ideal (sin retardos de cámara ni de `/odom`, sin deslizamiento).

| Caso | Resultado |
|---|---|
| Escalas caracterizadas | 30 de 30 misiones completas, todos los pits válidos; 537 s de media (máx. 571), menos de los 720 s; vuelta de 116.6 s |
| Tiempo de pit | **Sin corrección: 7.6 s** (5.8 s de intercambio + medir). **Con corrección: 14.8 s de media (11 a 19 s)**. El 54 % de los pits necesita corrección con la tolerancia interna de 3 cm y 4° |
| Escalas 1.0 con el robot de arriba | Solo 10 de 30 completan (fallan `ACOPLE_SIN_TIEMPO` o `TIMEOUT_MIDIENDO`: la primera llegada es de ~28 cm) |
| Desajuste de 4 % en el giro, escalas 1.0 | 30 de 30 completan; las escalas se aprenden en unas vueltas; 63 % de los pits lentos mientras aprende |
| Tolerancia interna 3.5 cm y 5° / 4 cm y 6° | Pits lentos 44 % / 37 %, pero con 4 cm y 6° fallan 10 de 60 misiones: la estación rechaza una pose que midió justo en el borde y no lo estaba. **Se dejó 3 cm y 4°** |
| Ganancia del acople 0.7 | Aborta por el presupuesto de tiempo del acople (`ACOPLE_SIN_TIEMPO`); sin presupuesto completa con hasta 2 reintentos por pit |

## Lo que debe saber

1. **El pit de 10 s solo cabe sin corrección** [Probable]: con un intercambio de 5.8 s quedan ~2 s para medir, y una corrección cuesta 4–5 s. Más de la mitad de los pits simulados se pasan. Lo que lo arregla es llegar mejor (escalas del día 3, reset de pose), no el acople.
2. **Arrancar con las escalas caracterizadas** es obligatorio en la práctica: con 1.0 y un giro 9 % mal la primera parada llega fuera de alcance.
3. **Todos los plazos y umbrales propios son provisionales**; los de medición (`espera_s`, `lecturas`) dependen del retardo real de la cámara y de `/odom`.
4. **Interfaces con el curso sin confirmar:** nombres de tópicos y forma del estado de la estación (si publica `ESPERANDO` antes de la solicitud no se exige; solo se bloquea si hay un intercambio en curso).
5. **Preguntas abiertas:** qué significa exactamente `autorizado` (¿calentamiento incluido?), si tras una bandera roja la carrera se reanuda (aquí es `FALLA` y hay que reiniciar), y qué cuenta la rúbrica como pit de más de 10 s.
6. **Sin telemetría de pose en mapa:** se envía la odometría (`/odom`); el contrato no fija el contenido de `pose`.
