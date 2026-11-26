# GranPrix Delivery Semiautónomo – Grupo 8

**Proyecto final de Robótica – CapyTown**

> **Estado (26-nov-2026):** hay lógica en Python y 590 pruebas automáticas sin robot. **Nada se ha ejecutado todavía contra el ROSCar, un JetCobot, una cámara real, ROS 2 ni un broker real.** Detalle en [`docs/desarrollo_realizado.md`](docs/desarrollo_realizado.md).
> **Precedencia de fuentes:** (1) lo que el docente indique por escrito; (2) su repositorio [`codeplai/GranPrix`](https://github.com/codeplai/GranPrix); (3) el HTML oficial.

## Equipo

| Número | Integrante | Parte realizada | Rol asignado |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |

## Datos

Configuración prevista del Grupo 8 (por confirmar con el curso):

| | |
|---|---|
| Equipo | `eq08` |
| ROSCar | Yahboom MicroROS-Pi5, `192.168.50.108` |
| Estaciones E1 / E2 / E3 / E4 | `192.168.50.21` / `.22` / `.23` / `.24` |
| Broker MQTT (Race Control) | `192.168.50.10:1883` |
| Red | `GranPrix-ESAN` (5 GHz, `192.168.50.0/24`) |
| Tablero web | `http://192.168.50.108:8080` |
| `ROS_DOMAIN_ID` / `ROS_LOCALHOST_ONLY` | `8` / `1` |

ROS 2 solo dentro de cada máquina; entre máquinas, únicamente MQTT. El carrito nunca depende de la red para moverse: si pierde el broker durante 1.5 s, se detiene.

## El reto en breve

Un ROSCar recorre un cuadrado de 2 m por lado y se detiene en cuatro estaciones con brazos Yahboom JetCobot (del curso) para cargar, intercambiar y descargar piezas. Usa ROS 2 dentro de cada máquina, MQTT entre máquinas y AprilTags para estimar su pose. Compiten 10 equipos (uno por tanda): **gana el que tiene menos intervenciones humanas** entre los que completan al menos 3 vueltas válidas.

- Cuatro vueltas consecutivas en 12 minutos como máximo.
- Pit de 10 s como máximo, desde que el carrito frena hasta que arranca.
- Acople dentro de 4 cm **y** 6°, con hasta 2 reintentos automáticos por parada.
- Velocidad máxima de 0.20 m/s y 0.8 rad/s (referencia de RC-1: 0.10 m/s y 0.5 rad/s).
- Una vuelta es **válida** con las cuatro paradas completas; es **limpia** si además no hubo intervención humana.

Hardware: ROSCar (Raspberry Pi 5, ROS 2 Humble, cámara), cuatro JetCobot con Jetson. Tecnologías: Python, MQTT/Mosquitto, OpenCV, AprilTag 36h11, TF2.

## Circuito

Sentido antihorario: E1 → E2 → E3 → E4 → E1. Metros, x al este, y al norte.

| Estación | Operación | Dock (x, y) | Rumbo al llegar | Carga al salir |
|---|---|---|---|---|
| E1 – Largada | Carga de pieza A | (0.40, 0.40) | −90° | A |
| E2 – Pit 1 | Intercambio A → B | (2.40, 0.40) | 0° | B |
| E3 – Pit 2 | Intercambio B → C | (2.40, 2.40) | +90° | C |
| E4 – Meta | Descarga de pieza C | (0.40, 2.40) | 180° | vacío |

## El pit

En cada parada, dentro de los 10 s y en este orden:

1. **Medir:** la cámara lee el tag del dock y calcula la pose real del carrito.
2. **Acoplar:** si está fuera de 4 cm o 6°, corrige con el tag (máximo 2 reintentos).
3. **Solicitar:** publica la pose `(dx, dy, dθ)` a la estación, que valida el turno y cambia la pieza.
4. **Reset de pose:** corrige `map → odom` con la pose medida.
5. **Recalibrar:** actualiza las escalas de distancia (`cd`) y de giro (`ca`) con lo medido en el tramo anterior.

## Quién programa qué

| Equipo | Curso |
|---|---|
| `control_odometria`, `camara_apriltag`, `maquina_pit`, y la estrategia de cambio de la estación | Race Control, `puente_mqtt`, `vigilante_red`, `tablero_web` (base), `grabador`, `supervisor_estacion`, `BrazoJetCobot` y el despliegue |

## Rúbrica (20 puntos)

| Componente | Criterio | Pts |
|---|---|---:|
| Tanda | 4 vueltas válidas → 4; 3 → 3; 2 → 1; menos de 2 → 0 | 4 |
| Pit | Medición, acople, reset y recalibración; error posterior menor que el anterior en ≥ 70 % de las paradas y escalas convergentes | 3 |
| Estación | `deploy.sh` y pieza entregada y recibida en ≥ 90 % → 3; ≥ 75 % → 2; ≥ 50 % → 1 | 3 |
| Autonomía | 0 intervenciones → 3; 1–2 → 2; 3–5 → 1; ≥ 6 → 0 | 3 |
| Evidencia | Un video por vuelta, bag completo y cinco CSV | 3 |
| Tablero web | Todos los bloques operativos | 2 |
| Informe | Dos páginas | 1 |
| Defensa | Explicar un video de vuelta sorteado | 1 |

Bono: +1 por odometría visual documentada (sin pasar de 20). Rige la rúbrica del HTML hasta que el docente confirme cambios.

## Estado del desarrollo

| Bloque | Estado |
|---|---|
| Planificador, ejecutor de movimiento y estimadores `cd`/`ca` del carrito | Hechos en Python puro; simulados |
| Estrategia de cambio de la estación | Hecha con brazo simulado |
| Configuración YAML y contrato MQTT | Hechos; verificados contra el contrato del docente |
| Visión: medición del AprilTag y calibración de la cámara | Hechas con una cámara sintética |
| Conversión cámara → dock y reset de pose | Hechos en Python puro; simulados (falta medir el montaje de la cámara) |
| Nodo ROS 2 del reset de pose (TF `map → odom`) | Escrito; **probado solo contra un sustituto de `rclpy`** |
| Nodo de cámara (`camara_apriltag_node.py`) y emulador del tag para el simulador RC-1 (`tag_emulado.py`) | Escritos; **probados solo contra un sustituto de `rclpy`** |
| Acople fino (`acople.py`) y calibración por tramo (`calibracion_tramo.py`) | Hechos en Python puro; simulados (el ensayo con el robot está preparado, sin ejecutar) |
| Máquina de estados del pit y tablero web | **Pendientes** |
| Pruebas con los robots reales | **Ninguna todavía** |

## Cómo empezar

```bash
bash scripts/preparar_entorno.sh --vision   # entorno virtual y dependencias
bash scripts/ejecutar_pruebas.sh            # 590 pruebas; "TODO OK" si pasan
```

Detalle del entorno en [`docs/entorno_desarrollo.md`](docs/entorno_desarrollo.md).

## Organización del repositorio

- `carrito/`: lógica del ROSCar (docks, planificador, ejecutor, estimadores, acople, configuración) y `nodos/` con el nodo ROS 2 del reset de pose; el resto aún no son nodos.
- `estacion/`: estrategia de cambio de pieza (`app_equipo`) con brazo simulado. El supervisor es del curso.
- `vision/`: medición del AprilTag y calibración de la cámara. `integracion/`: configuración MQTT. `comun/`, `geometria_dock/`: utilidades compartidas.
- `simulacion/`: modelo del simulador del HTML, barridos de parámetros e imágenes sintéticas.
- `scripts/`: entorno, pruebas, diagnósticos (ROSCar, JetCobot), calibración de cámara y copias históricas de RC-0 y RC-1.
- `tests/`: 590 pruebas propias. `experimentos/`: pruebas de laboratorio, separadas de la evidencia oficial.
- `vendor/granprix/`: copia fija del repositorio del docente, **sin modificar**.
- `docs/`: documentación; el índice está en [`docs/README.md`](docs/README.md).

Este repositorio es provisional: no es un fork de `granprix-esan`, y las carpetas se ajustarán a la plantilla del curso cuando se publique; por ahora se guían por `docs/arquitectura/02` y `03` del repositorio del docente.

## Documentación

- [`docs/referencia_del_reto.md`](docs/referencia_del_reto.md): reglas, pit, tópicos MQTT, evidencia, intervenciones, riesgos y preguntas abiertas al docente.
- [`docs/desarrollo_realizado.md`](docs/desarrollo_realizado.md): qué se construyó, con qué evidencia y qué falta.
- [`docs/arquitectura.md`](docs/arquitectura.md) y [`docs/requerimientos.md`](docs/requerimientos.md).
- [`docs/contexto_analisis.md`](docs/contexto_analisis.md) y [`contexto_division_reto_final.md`](contexto_division_reto_final.md): análisis previo y reparto del trabajo.

## Antecedentes (retos pasados)

Se reutilizan componentes, pero **no** se copian proyectos completos; todo valor histórico debe volver a comprobarse en el robot del GranPrix.

- [RC-0 · Calibración del ROSCar](https://github.com/Harold855/RC-0_MicroRos_Pi5/tree/main)
- [RC-1 · Control PID](https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/main) (`main` está desactualizada; lo final está en la rama [`claude/sleepy-knuth-kc6wex`](https://github.com/Harold855/microrospi5-sim_capytown_G8/tree/claude/sleepy-knuth-kc6wex)) y el [simulador base del curso](https://github.com/codeplai/microrospi5-sim/tree/main)
- [Reto 2 · El Turno del Brazo](https://github.com/Harold855/Reto_2-El_Turno_del_Brazo/tree/main)
- [Gran Reto del JetCobot](https://github.com/Harold855/El-Gran-Reto-de-JetCobot---Grupo-8/tree/main)
- Reto 1 · API del JetCobot: sin repositorio (se entregó como `.zip`).

## Por declarar en el README final

Integrantes y rol de cada uno (tabla de arriba) · sensores utilizados · si se usó odometría visual · altura real de la cuna (9–12 cm) · ROSCar asignado y calibración vigente · estructura de carpetas de la plantilla del curso (aún no publicada).

## Referencias

- [Yahboom JetCobot](https://www.yahboom.net/study/JetCobot) · [Yahboom MicroROS Pi5](https://www.yahboom.net/study/MicroROS-Pi5)
- [REP-105](https://www.ros.org/reps/rep-0105.html) · [AprilTag](https://github.com/AprilRobotics/apriltag) · [Eclipse Mosquitto](https://mosquitto.org/documentation/)
