# Guion del día de laboratorio con el ROSCar

Escalera de pruebas, de lo más seguro a la misión completa. **Cada peldaño valida una cosa y solo se sube si pasa el anterior.** Todo el software de este guion se probó únicamente con simulación y con un `rclpy` sustituto: **nunca se ha ejecutado contra ROS 2 real ni contra el robot**. Espera encontrar errores el primer día, y anótalos: es parte del resultado.

Complementa a [`procedimiento_laboratorio_roscar.md`](procedimiento_laboratorio_roscar.md) (lo que ya funcionó en RC-0 y RC-1), que sigue vigente para el bringup y los errores conocidos.

## 0. Reglas del día

1. **Tres personas como mínimo:** *operador* (teclado), *vigilante* (mano en el interruptor y mirando el robot, no la pantalla) y *registrador* (cinta, transportador, bitácora).
2. **El robot nunca se mueve sin `--zona-segura`**, sin zona libre y plana de ≥ 3 × 3 m, ni con otro publicador en `/cmd_vel`.
3. **Corte físico siempre a mano.** Si el nodo muere, el firmware conserva la última orden: nada de este software lo evita. Verifica el *timeout* de tu entrada de `twist_mux` en el paso 1.
4. **Un cambio por vez.** Si algo falla, anótalo, vuelve al peldaño anterior y no toques dos parámetros a la vez.
5. **Se registra todo, también lo que falla.** Nada de sobrescribir CSV.
6. **El robot asignado puede no ser el ROSCar 4:** no apliques `wheel_params_g8.yaml` ni escalas de otro día.
7. **No se sube de peldaño con deuda:** sin el paso 3 (`cd`, `ca`) no se hace el 8; sin el 6 (`marcos.yaml`) no hay pose en el dock. Con escalas 1,0 la primera parada llega a ~28 cm y el acople se rinde.

## 1. Antes de salir (en la PC)

- [ ] `git pull` de `main` y `bash scripts/ejecutar_pruebas.sh` → `TODO OK`.
- [ ] Llevar: cinta métrica, transportador circular, regla, cinta de pintor (marcas de dock a ≥ 25 cm del centro de las ruedas), los **4 tags oficiales** de los docks (AprilTag 36h11 de 6 cm, ID = número de estación; los entrega el curso en `docks/` de `granprix-esan`, que **todavía no está en nuestra copia**: confirma con el docente cómo y cuándo), un cubo del curso (para la revisión de la cuna del P5), damero si hay, cargador, cable de red. Para ensayar antes de tener los oficiales puedes generar uno con la herramienta del docente (`python3 vendor/granprix/estacion/herramientas/herramienta_apriltag.py crear --help`); **mide con regla el lado real de cada tag impreso**.
- [ ] Copiar el repositorio al Pi y de ahí al contenedor (`scp -r`, `docker cp`; ver el procedimiento). Los commits se hacen desde la PC, nunca desde el Pi.
- [ ] Imprimir la tabla de valores de la sección 12.

## 2. Al llegar

```bash
sudo timedatectl set-time "AAAA-MM-DD HH:MM:SS"      # el Pi no guarda la hora
date -Is ; docker exec ros2_dev date -Is             # deben coincidir
```

- Batería ≥ 70, cargador desconectado. Bringup con la calibración **del robot asignado** (terminal 1, abierta todo el día).
- En cada terminal: `export ROS_DOMAIN_ID=8 ROS_LOCALHOST_ONLY=1`.
- Carpeta de hoy: `experimentos/diaNN_roscar/` (los scripts por defecto escriben en `dia01_roscar/`; usa `--csv` donde exista).

**Cómo anotar cada paso** (un registro por prueba, también las fallidas):

```bash
python3 -m carrito.granprix_carrito.registro_experimental agregar --tipo recta --robot <id> --operador <nombre> \
  --estado ok|fallo|parcial|abortado --parametro distancia_m=0.25 --resultado distancia_fisica_m=0.247 \
  --archivo experimentos/dia01_roscar/movimientos_odom.csv --notas "superficie cartón, batería 78"
```

---

## 3. Los pasos

### P1 · Diagnóstico sin mover
**Hacer:** `bash scripts/roscar_v01/preflight.sh` y `python3 scripts/roscar_v01/diagnostico_roscar.py`.
**Comprobar a mano:** `ros2 node list` (un solo `/odom_corrector`), `ros2 topic info /cmd_vel -v` (nadie más publicando), `ros2 topic hz /odom` (≈ 11 Hz), `ros2 topic echo /battery --once`. Averigua **qué entrada de `twist_mux` te corresponde** y su *timeout*, y qué tópico de imagen publica la cámara (`ros2 topic list -t`).
**Pasa si:** el diagnóstico no da FALLA y `/odom` llega.
**Anotar:** tópico de comandos autorizado, *timeout* del mux, tópico de imagen, qué calibración de ruedas está activa.

### P2 · Movimiento mínimo
**Hacer:** primero sin mover (`prueba_movimiento.py recta --distancia 0.25`), luego con el robot en la zona y el vigilante listo:
```bash
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25 --velocidad 0.05 --ejecutar --zona-segura
python3 scripts/roscar_v01/prueba_movimiento.py giro --grados 15 --velocidad 0.25 --ejecutar --zona-segura
```
Usa `--topic-cmd` con la entrada autorizada de `twist_mux` si no es `/cmd_vel`.
**Pasa si:** se mueve, frena con ceros, el CSV se escribe y el vigilante no tuvo que cortar. Prueba también `Ctrl+C` en plena marcha: el robot debe quedar parado.
**Si falla:** no sigas hasta entender por qué (¿el mux ignora la entrada?, ¿`/odom` viejo?).

### P3 · Caracterización de `cd` y `ca`  *(el paso más importante)*
**Hacer:** rectas de 2 m a 0,10 m/s y giros de 90° a 0,5 rad/s, **5 corridas por condición**, sobre la superficie real (la base de cartón del circuito), con las mismas velocidades que usará el robot. Por cada corrida mide con cinta y transportador y registra:
```bash
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 2 --velocidad 0.10 --ejecutar --zona-segura
python3 scripts/roscar_v01/registrar_medicion.py recta --robot <id> --superficie carton --corrida 1 --auto --distancia-fisica 1.97 --desvio-lateral-cm 2
python3 scripts/roscar_v01/analizar_movimientos.py
```
**Medir bien:** líneas cruzadas y transportador circular para el giro (medir el ángulo sobre el robot dio ±10° en RC-1); cinta fuera del círculo de las ruedas.
**Pasa si:** la dispersión entre corridas es pequeña frente al efecto (p. ej. < 2 % en distancia, < 2° en giro). Si no, caracterizar otra vez la superficie antes de fiarse.
**Resultado:** copia a mano `cd` y `ca` (y el robot) a `carrito/config/calibracion.yaml`; deja `perfil` con `v_ref: 0.10` y `w_ref: 0.50`.

### P4 · Tiempos del ejecutor y retardo de `/odom`
**Hacer:** graba un bag corto (`ros2 bag record -o experimentos/diaNN_roscar/bag_tiempos /cmd_vel /odom`) durante una recta de 0,25 m y mira cuánto tarda `/odom` en dejar de cambiar tras el último comando distinto de cero, y cuánto va `/odom` atrasado respecto al movimiento.
**Resultado:** valores para `pausa_s` y `asentamiento_s` (`movimiento.yaml`, hoy 0,3 y 0,5 s, **supuestos**) y el retardo de `/odom` (0,5–0,65 s en RC-1) para el reset de pose. *(No hay script de análisis para esto todavía: pídelo si lo necesitas.)*

### P5 · Cámara
**Qué estás midiendo:** el tag de la pared es un cuadrado negro con una cuadrícula de bits (familia 36h11) cuyo ID es la estación. Al conocer su tamaño real y la calibración de la cámara, sus cuatro esquinas en la imagen dan su pose respecto a la cámara (`z` ≈ 28 cm, `x` lateral, `dth`), y de ahí, con el montaje de la cámara, la pose del carro en el dock. **Un lado mal medido o una focal mal calibrada se convierten en error de distancia en la misma proporción**: por eso se mide el tag impreso y se calibra primero. Los códigos de los cubos del JetCobot no intervienen: las piezas se distinguen por color y el brazo no usa cámara.

**Hacer:** sigue [`procedimiento_calibracion_camara.md`](procedimiento_calibracion_camara.md): `calibrar_focal.py capturar` → `calcular` → `validar` (con el tag a los lados). Si falla fuera del eje, damero ([`procedimiento_calibracion_damero.md`](procedimiento_calibracion_damero.md)). Después valida con regla y transportador:
```bash
python3 scripts/camara/medir_tag.py comparar --camara 0 --camara-yaml experimentos/diaNN_camara/camara_calibrada.yaml \
  --tag-id 2 --esperado-z-cm 28 --esperado-x-cm 0 --esperado-dth 0 --csv experimentos/diaNN_camara/mediciones.csv
python3 scripts/camara/medir_tag.py resumen --csv experimentos/diaNN_camara/mediciones.csv
```
Haz decenas de puntos en la zona de acople (±6 cm, ±8°), no uno solo.
**Pasa si:** error medio y p95 de pose compatibles con decidir 4 cm y 6° con margen.
**Anotar:** el tamaño real del tag, la resolución y si el enfoque a ~28 cm es bueno.

**Revisión con la pieza en la cuna (obligatoria, 5 minutos):** pon un cubo en la cuna del carro y mira la imagen de la cámara en vivo (o `python3 scripts/camara/medir_tag.py continuo --camara 0 --camara-yaml … --tag-id 2 --segundos 20`).
- ¿Aparece el cubo, o algún código impreso en él, en la imagen? Anótalo con una captura.
- La medición del tag de la pared **debe seguir saliendo** (código de salida 0) con el cubo puesto, en posición de llegada.
- Cómo se comporta el software: con `--tag-id` fijo, los tags de otro ID se **ignoran**; solo se rechaza la medición (`varios_tags`) si hay dos tags del mismo ID o si no se fija ninguno y aparecen dos. Si el código del cubo tuviera el mismo ID que el tag del dock, o si el nodo corre sin `tag_id`, sí habría problema. **No sé si los cubos del curso llevan código**: esta revisión lo dice.

### P6 · Montaje de la cámara y posición del tag  → `marcos.yaml`
**Hacer:** coloca el robot **exactamente sobre su marca** en un dock (centro del dock, rumbo de llegada), mide con cinta dónde está el tag respecto al centro del dock y:
```bash
python3 scripts/camara/medir_tag.py una --camara 0 --camara-yaml experimentos/diaNN_camara/camara_calibrada.yaml --tag-id 2 | \
  python3 scripts/roscar_v01/pose_dock.py montaje --tag-en-dock 0.38,0,0 --robot-en-dock 0,0,0 --inclinacion-deg <medida>
```
El `0.38,0,0` es un **supuesto** (28 cm de cámara a tag + 10 cm de cámara a centro): **mídelo**. Mide también la inclinación de la cámara.
**Resultado:** rellena `carrito/config/marcos.yaml` (sin `null`; `cargar_marcos` falla si queda alguno).
**Comprobar:** con el robot desplazado 3 cm y rotado 5° a mano, `pose_dock.py convertir --marcos carrito/config/marcos.yaml` debe devolver esos valores (a ~1 cm y 1°). Repite en otro dock.

### P7 · Nodos con ROS 2 real, robot parado
En terminales separadas (robot sobre su marca, sin moverlo):
```bash
python3 carrito/nodos/camara_apriltag_node.py --ros-args -p camara_yaml:=experimentos/diaNN_camara/camara_calibrada.yaml \
  -p tamano_mm:=<lado real medido del tag> -p tag_id:=<ID de la estación donde está el robot> -p image_topic:=<tópico de imagen del P1>
python3 carrito/nodos/nodo_reset_pose.py --ros-args -p marcos_yaml:=carrito/config/marcos.yaml -p retardo_odom_s:=<del P4>
ros2 topic echo /tag/pose --once ; ros2 service call /reset_pose/aplicar std_srvs/srv/Trigger
```
En este paso `tag_id` es el de **un solo dock** (el del P6). Más abajo, para la misión de 4 estaciones, hay que **quitarlo**. `/pit/dock` debe valer la estación donde está el robot (`ros2 topic pub --once /pit/dock std_msgs/msg/Int32 "{data: 2}"` si aún no corre la máquina).
**Pasa si:** `/tag/pose` llega a ≥ 5 Hz sin excepciones y el servicio responde con `motivo` coherente (`ODOM_INSUFICIENTE` en el primer intento es normal: reintenta).
**Si falla:** anota el error exacto (primera vez que corre con `rclpy` real) y la versión de OpenCV / `pupil-apriltags` del Pi.

### P8 · Acople en una estación
```bash
python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --marcos carrito/config/marcos.yaml          # solo mide y calcula
python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --marcos carrito/config/marcos.yaml \
  --ejecutar --zona-segura --csv experimentos/diaNN_roscar/paradas.csv
python3 scripts/roscar_v01/analizar_acople.py experimentos/diaNN_roscar/paradas.csv --salida experimentos/diaNN_roscar/graficos
```
Coloca el robot **a propósito** desplazado 4–8 cm y girado 5–10° del dock, y **mide con cinta antes y después**: eso valida la cadena visual. Primero sin marcha atrás (`--sin-reversa`); ensáyala después, con el vigilante, si el dock lo permite.
**Pasa si:** la pose que dice el ensayo coincide con lo medido a mano (≈ 1 cm y 1°) y el acople termina en ≤ 4 cm y 6° medidos con cinta, en al menos 8 de 10 intentos.
**Mide también cuánto tarda una corrección** (el pit simulado se pasa de 10 s con ella).

### P9 · Evidencia real
Graba un bag corto con los tópicos de evidencia y comprueba que **tiene mensajes** (en RC-1, 2 de 3 bags salieron vacíos):
```bash
ros2 bag record -o experimentos/diaNN_roscar/bag_prueba /odom /imu /tag/pose /cmd_vel     # 20 s, y Ctrl+C
ros2 bag info experimentos/diaNN_roscar/bag_prueba
python3 -c "from evidencia.verificar_evidencias import inspeccionar_bag as i; import pprint; pprint.pprint(i('experimentos/diaNN_roscar/bag_prueba'))"
```
**Pasa si:** `ros2 bag info` y el verificador coinciden en el conteo de mensajes de cada tópico. **Anota** la lista real de tópicos y el formato (¿`sqlite3` o `mcap`?): el verificador (`evidencia/evidencia.yaml`) solo cuenta mensajes en `sqlite3`.

### P10 · Misión con la estación falsa (sin JetCobot)
Es la prueba de la máquina completa: navegación, visión, acople, solicitud, espera, recalibración y seguridad. **No valida el intercambio real ni su tiempo** (`t_cambio_s` es un supuesto), y la estación falsa **solo ve la pose que el carro reporta**: mide con cinta si llegó bien.

Preparación: copia `carrito/config/mision.yaml` a `experimentos/diaNN_roscar/mision_1vuelta.yaml` y pon `vueltas: 1`. Terminales (el robot en la marca de E1):
```bash
python3 carrito/nodos/estacion_falsa.py --ros-args -p t_cambio_s:=5.8 -p registro_dir:=experimentos/diaNN_roscar/falsa
python3 carrito/nodos/camara_apriltag_node.py --ros-args ...               # como en P7 pero SIN tag_id (0 = cualquiera): con un ID fijo solo mediría 1 de las 4 estaciones
python3 carrito/nodos/nodo_reset_pose.py --ros-args ...                    # como en P7
python3 carrito/granprix_carrito/adaptador_ros.py --ros-args -p marcos_yaml:=carrito/config/marcos.yaml \
  -p mision_yaml:=experimentos/diaNN_roscar/mision_1vuelta.yaml -p cmd_topic:=<entrada autorizada del P1> \
  -p resultados_dir:=experimentos/diaNN_roscar/resultados
```
Con `tag_id` sin fijar, el nodo acepta cualquier tag **único** a la vista y la estación se toma de `/pit/dock`: el nodo **no comprueba** que el ID detectado coincida con la estación actual (si dos docks quedaran en el campo de visión, mediría el equivocado). Vigila que cada medición cuadre con el dock donde está el robot. La máquina queda en `ESPERA`: **no da el turno por sí sola**. El curso falso lo da con `ros2 service call /estacion_falsa/iniciar std_srvs/srv/Trigger`.

Haz las pruebas en este orden, cada una con el vigilante listo:

| # | Prueba | Cómo | Debe pasar |
|---|---|---|---|
| a | **Seguridad en el aire** | Robot sobre soportes con las ruedas libres. Arranca la misión | Las ruedas giran solo en `NAVEGANDO` y `ACOPLANDO`; quietas en `ESPERANDO_RESULTADO` (`ros2 topic echo /pit/estado`) |
| b | **Sin turno no arranca** | No llames a `iniciar`; espera 30 s | Se queda en `ESPERA` y no publica velocidad |
| c | **Parada por orden del curso** | Robot en el suelo, en marcha: `ros2 service call /estacion_falsa/roja std_srvs/srv/Trigger`; en otras corridas `/estacion_falsa/retirar_turno`, `/estacion_falsa/cortar_enlace`, `/estacion_falsa/silenciar_enlace` | Termina en `FALLA` con el motivo esperado (`BANDERA_ROJA`, `SIN_AUTORIZACION`, `ENLACE_PERDIDO`) y el robot **para** |
| d | **Parada manual** | `ros2 service call /maquina_pit/parar std_srvs/srv/Trigger` en marcha | `FALLA` (`PARADA_MANUAL`) al instante |
| e | **Fallas de la estación** | Relanza la falsa con `-p modo:=rechazar`, `no_responder` o `offline` | `RESULTADO_NO_OK`, `TIMEOUT_ESPERANDO_RESULTADO` (a los 15 s) y `ESTACION_OFFLINE`; el robot queda quieto |
| f | **Una vuelta** | `modo:=ok`, 1 vuelta: E1 → E2 → E3 → E4 | 4 pits válidos; mide con cinta la pose de llegada en cada parada |
| g | **Cuatro vueltas** | `mision.yaml` original (solo si f salió limpia y hay batería) | `FIN`; mira `pits.csv`, `paradas.csv` y la evidencia |

Para volver a empezar tras un `FALLA`: recoloca el robot en E1 y `ros2 service call /maquina_pit/reiniciar std_srvs/srv/Trigger`. Las escalas aprendidas se conservan.
**Después:** `python3 evidencia/verificar_evidencias.py experimentos/diaNN_roscar/resultados` y `python3 -m carrito.granprix_carrito.tablero_extension.metricas experimentos/diaNN_roscar/resultados`. Lo que importa: tiempo real de pit, cuántos pits necesitan corrección y si el error tras el pit baja (≥ 70 %).

## 4. Criterios para parar el día

Paras, anotas y recoges si: el robot no frena con ceros en P2; `twist_mux` ignora tu entrada o no tiene *timeout*; la dispersión del P3 impide fijar `cd` y `ca`; hay dos publicadores en `/cmd_vel`; la batería baja de 40; o algún miembro del equipo no tiene el robot a la vista.

## 5. Al terminar

- [ ] Robot en estado seguro (ceros, nodos cerrados, bringup cerrado, apagado).
- [ ] Respaldar `experimentos/` fuera del Pi (`scp` a la PC) **antes** de apagar. Verifica que los CSV y los bags no estén vacíos.
- [ ] `python3 -m carrito.granprix_carrito.registro_experimental verificar` → íntegro.
- [ ] Completar `docs/bitacora_laboratorio.md` (incluye lo que falló).
- [ ] Commit desde la PC: valores medidos (`calibracion.yaml`, `movimiento.yaml`, `marcos.yaml`, `acople.yaml`) y las preguntas nuevas para el docente.

## 6. Tabla de valores que debes traer de vuelta

| Valor | Dónde va | Paso | Medido |
|---|---|---|---|
| Robot / calibración de ruedas activa | `calibracion.yaml: robot` | P1 | |
| `cd`, `ca` (con v = 0,10 m/s y ω = 0,5 rad/s) | `calibracion.yaml` | P3 | |
| Dispersión de rectas y giros | bitácora | P3 | |
| Entrada de `twist_mux` y su *timeout* | `cmd_topic` del adaptador | P1 | |
| Tópico de imagen, resolución, **lado real de cada tag impreso** | parámetros del nodo de cámara (`tamano_mm`) | P1/P5 | |
| ¿Aparece el cubo (o un código) en la imagen con la pieza en la cuna? ¿Sigue midiéndose el tag? | bitácora | P5 | |
| De dónde salen los tags oficiales y su ID por estación | pregunta al docente | antes | |
| `pausa_s`, `asentamiento_s`, retardo de `/odom` | `movimiento.yaml`, `retardo_odom_s` | P4 | |
| Focal y distorsión de la cámara | `camara_calibrada.yaml` | P5 | |
| Montaje de la cámara (x, y, yaw, inclinación) y tag en el dock | `marcos.yaml` | P6 | |
| Altura real de la cuna (9–12 cm) | README final | P6 | |
| Tiempo de una corrección de acople; % de acoples válidos | `acople.yaml` (ganancia, presupuesto) | P8 | |
| Formato y tópicos reales del bag | `evidencia/evidencia.yaml` | P9 | |
| Tiempo real de pit sin y con corrección | informe | P10 | |

## 7. Lo que este guion NO cubre

Los tags oficiales (`docks/`, `dock_frames.yaml`) no están en nuestra copia del repositorio del curso, así que la posición del tag en el dock sale solo de tu medición.

El intercambio real con el brazo y su tiempo, el `puente_mqtt`, el `vigilante_red` y Race Control reales (los nombres de tópicos del adaptador son provisionales), el video por vuelta, el grabador del curso y el tablero base. Sin el JetCobot tampoco se valida el pit de 10 s completo: solo la parte del carro.
