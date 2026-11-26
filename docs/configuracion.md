# Configuraciones YAML

Siete archivos de configuración, todos con el mismo cargador estricto (`comun/yaml_estricto.py`). Cada clave que aparece en un YAML está leída y validada por código: **una clave que ninguna función lee no existe**, para que nadie edite algo creyendo que cambia el comportamiento.

| Archivo | Lo lee | Qué fija | Estado de los valores |
|---|---|---|---|
| `carrito/config/movimiento.yaml` | `carrito.granprix_carrito.configuracion.cargar_movimiento` | velocidades de referencia y límites, parámetros del ejecutor | límites = reto; referencias = HTML/RC-1; `pausa_s` y `asentamiento_s` = **placeholders a medir** |
| `carrito/config/acople.yaml` | `carrito.granprix_carrito.acople.cargar_acople` | tolerancias internas, ganancias, velocidades del acople, reintentos, alcance, marcha atrás, presupuesto de tiempo | límites = reto (el cargador rechaza más); `v` y `w` deben coincidir con `movimiento.yaml`; el resto es **propio y provisional** |
| `carrito/config/marcos.yaml` | `carrito.granprix_carrito.transformacion_camara_dock.cargar_marcos` | montaje de la cámara en el robot, posición del tag en el dock, umbrales de "cerca del dock" | **`null`: se miden en el laboratorio**; la carga falla hasta entonces |
| `carrito/config/calibracion.yaml` | `EstimadorEscalas.cargar` / `cargar_carrito` | robot, escalas `cd`/`ca` iniciales, perfil `v`/`ω`, parámetros del estimador | escalas **1.0 = sin caracterizar**; `alpha` 0.35 = referencia del HTML |
| `estacion/config/estacion.yaml` | `app_equipo.configuracion.cargar_estacion` | tolerancias, tope de tiempo, geometría del montaje | tolerancias = reto; geometría = **supuestos** hasta medir |
| `estacion/config/poses.plantilla.yaml` | `app_equipo.posiciones.cargar` (copia `poses_rolN.yaml`) | las 8 poses de trabajo de un rol | todo `null`: **se enseñan en el laboratorio** |
| `integracion/configuracion/mqtt.yaml` | `integracion.mqtt_config.cargar_mqtt` | broker, equipo, tópicos, QoS, retenidos, latido | contrato del docente; las pruebas lo comparan con su módulo y su tabla |

Quién necesita qué: el carrito usa `movimiento` y `calibracion`; la estación usa `estacion` y sus `poses_rolN`; ambos y la integración pueden usar `mqtt`.

## Reglas que el cargador hace cumplir
- **Una configuración no puede aflojar el reto:** velocidades máximas ≤ 0.20 m/s y 0.8 rad/s; tolerancia de acople ≤ 4 cm y 6°; tope de cambio ≤ 10 s; telemetría ≤ 5 Hz. Se puede ser más estricto, no más laxo.
- **Claves desconocidas, faltantes o duplicadas = error.** PyYAML por sí solo acepta duplicados y gana la última; aquí se rechazan. Un error de dedo en un nombre no se ignora en silencio.
- **Tipos exactos:** un número entre comillas, un booleano donde va un número, `.nan` o `.inf` se rechazan. `1e3` se lee como texto en YAML (hay que escribir `1000.0` o `1.0e+3`) y el error lo avisa. Claves sin comillas como `yes`, `no`, `on`, `off` se leen como booleanos y se rechazan.
- **Sin secretos:** cualquier clave que contenga `clave`, `password`, `contrasena`, `token` o `secret` con un valor se rechaza, salvo las que terminan en `_env` (el **nombre** de una variable de entorno). La contraseña MQTT va en `GRANPRIX_MQTT_CLAVE`, como en el repositorio del docente.
- **Coherencia entre archivos:** `cargar_carrito` verifica que el perfil de `calibracion.yaml` (`v_ref`, `w_ref`) coincida con las velocidades de `movimiento.yaml`.
- **Robot:** `calibracion.yaml` lleva el id del robot (`eq08-roscar`) y la carga falla si no coincide con el esperado (1.1.4: no aplicar parámetros de otro robot).

## Cómo se edita en el laboratorio
1. Los archivos de `config/` son **semillas editadas a mano y versionadas**. Los programas no escriben en ellos.
2. El estado que produce el estimador (`EstimadorEscalas.guardar`) va a la carpeta del experimento, p. ej. `experimentos/dia03_roscar/calibracion_final.yaml`. No usar como destino la ruta de la semilla: se perderían los comentarios.
3. Un valor medido se escribe con su fuente en la bitácora (`docs/bitacora_laboratorio.md`): fecha, quién, cómo se midió. No se copian escalas ni poses de RC-0/RC-1 ni de otro día.
4. Antes de usar, validar sin tocar ningún robot:
   ```bash
   python3 - <<'PY'
   from carrito.granprix_carrito.configuracion import cargar_carrito
   print(cargar_carrito(robot_esperado='eq08-roscar'))
   PY
   ```
   (con `PYTHONPATH=.` desde la raíz del repositorio). `bash scripts/ejecutar_pruebas.sh` comprueba además que los YAML del repositorio coinciden con los valores por defecto del código.

## Dependencia: PyYAML
`requirements-dev.txt` lo incluye. En el carrito viene con ROS 2 (`python3-yaml`) [Probable]. **En la Jetson no está verificado**: `diagnostico_jetcobot.py` y `preflight.sh` ahora muestran su versión o avisan de que falta. Las poses de la estación también se leen desde `.json` con solo la biblioteca estándar, por si PyYAML no estuviera.

## Lo que NO se creó y por qué
| Archivo previsto en la división | Motivo |
|---|---|
| `dock_frames.yaml` | no existe el del docente y la división dice no fijar un esquema ficticio. Los supuestos de marcos quedan marcados en `estacion.yaml`; lo que sí se puede medir (montaje de la cámara y posición del tag en el dock) va en `marcos.yaml` |
| `camara.yaml` (semilla editable) | no hay valores que inventar. Existe `camara_calibrada.yaml`, un **resultado** que generan `scripts/camara/calibrar_focal.py` (regla y tag) o `scripts/camara/calibrar_damero.py` (damero, con distorsión) y lee `vision.calibracion_focal.cargar_camara` (procedimientos en `docs/procedimiento_calibracion_camara.md` y `docs/procedimiento_calibracion_damero.md`); queda en la carpeta del experimento, no en `config/` |
| `almacenes.yaml`, `manipulacion.yaml`, `estacion.yaml` del JetCobot (inventario) | dependen de medir el montaje real y de la tabla de alcance; sus datos serían inventados |
| `caracterizacion.yaml`, `metadata.yaml` | son **resultados** de los experimentos, no configuración: los genera cada experimento |
| `roles.yaml` | los cuatro roles ya son una tabla fija del reto en `roles.py`; moverla a YAML permitiría editarla por error |

Cuando exista cada dato (o el docente publique el esquema), se agrega el archivo con su lector y sus pruebas, no antes.
