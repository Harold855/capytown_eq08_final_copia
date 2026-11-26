# Tablero, métricas y evidencia

Esta parte puntúa (evidencia 3 puntos, tablero 2) pero **no bloquea la navegación**: se hizo sobre los eventos de la máquina de la misión y sin tocar el control. Todo se probó con datos simulados; nada con el robot, el `grabador` ni el tablero base del curso.

## Archivos

| Archivo | Función | Prioridad |
|---|---|---|
| `carrito/granprix_carrito/eventos_mision.py` | Eventos de nuestra lógica en JSONL (`eventos.jsonl`) | P0 |
| `evidencia/registro_experimental.py` | Registro de las pruebas de laboratorio, encadenado por hash | P0 |
| `carrito/granprix_carrito/cronometro.py` | Tiempos de vuelta, sectores, tramos y pits desde los eventos | P1 |
| `carrito/granprix_carrito/metricas.py` | Indicadores consolidados (el JSON del panel) | P1 |
| `evidencia/verificar_evidencias.py` (+ `evidencia.yaml`) | Comprueba que la evidencia existe y tiene contenido | P1 |
| `tablero/datos_simulados.py` | Datos de prueba para el panel, también en vivo | P1 |
| `tablero/panel.html`, `panel.js`, `panel.css` | Prototipo de extensión del tablero | P1 |
| `tests/carrito/test_metricas.py` (46), `tests/evidencia/test_registro_experimental.py` (24), `test_verificar_evidencias.py` (39) | Pruebas | — |
| `evidencia/archivos_falsos.py` | Genera evidencia sintética con fallos conocidos (para probar) | — |

Eventos y métricas son lo que ya genera `MaquinaPit` (`eventos=` opcional; por defecto en memoria). Un fallo al escribir el registro **nunca** detiene la misión (una prueba lo fuerza).

## Eventos (`eventos.jsonl`)

Una línea por evento: `ts` (reloj de pared), `tipo`, `estado`, `vuelta`, `estacion`, `motivo`, `datos`. Tipos: `inicio`, `estado` (cada transición, con `de`), `entrada` (turno, bandera, enlace y estado de estación, **solo cuando cambian**), `acople`, `solicitud`, `resultado`, `ignorado`, `reset`, `pit_cerrado`, `pit` (la fila completa de `pits.csv`), `vuelta`, `aviso`, `falla`, `fin`. `fsync` solo en `falla`, `vuelta` y `fin`; un corte deja a lo sumo la última línea incompleta, que la lectura descarta (una línea mala en medio es un error).

## Cronómetro y métricas

- **Vuelta** = desde la llegada a E1 hasta el fin del pit de E4 (la misma que se publica en `vuelta`). **Sectores:** S1 llegada E1 → llegada E2, S2 E2 → E3, S3 E3 → E4, S4 llegada E4 → fin de su pit. Suman exactamente la vuelta (una prueba lo exige). Cada sector incluye el pit de su estación de salida. Lo que falta queda en `None`.
- **Métricas:** vueltas cerradas y válidas, pits (tiempo medio, máximo, p95, lentos, con corrección, reintentos), errores antes y después (media y p95), fracción de paradas que mejoran (el criterio del 70 %, con y sin las que ya llegaron dentro), escalas (inicial, final, si convergen: el mismo criterio que el estimador), fallas y la **estimación** de puntos de tanda y de pieza. Los puntos de autonomía solo se calculan si se da el número de intervenciones (`--intervenciones`); nada se rellena con ceros.
- `python3 -m carrito.granprix_carrito.metricas CARPETA --salida datos.json [--cada 0.5]` (escritura atómica: el panel nunca lee un archivo a medias).

## Verificador de evidencia

`python3 evidencia/verificar_evidencias.py CARPETA [--json informe.json]`. Sale 0 sin fallas, 1 con alguna. No se fía de los metadatos:

| Archivo | Qué se comprueba |
|---|---|
| MP4 | Se recorre por cajas: `ftyp`, **`moov`** (falta si la grabación no se cerró), `mdat` con datos, archivo no cortado; resolución, fps y duración de la pista de video (mínimos 640×480, 15 fps) |
| rosbag2 | Se cuenta **cada mensaje en el SQLite** (no `metadata.yaml`): falla si un dato requerido tiene 0 mensajes, si `metadata.yaml` dice que hay y no hay (el caso de RC-1), si falta `metadata.yaml` (bag sin cerrar), si hay mensajes de contenido vacío, o si la frecuencia es menos de la mitad de la esperada. Bags divididos en varios `.db3` se suman. `mcap` solo se revisa por `metadata.yaml` |
| CSV de eventos del pit | Encabezado, columna de vuelta, filas por vuelta (4), y que el archivo de la vuelta N solo tenga filas de la N |
| Cobertura | Con `eventos.jsonl` en la carpeta: el video y el bag deben cubrir el tiempo de cada vuelta (con 5 s de holgura) |
| Registro experimental | Si hay `registro_experimental.jsonl`, su cadena de hashes y sus adjuntos |

Por cada vuelta se espera un MP4 y un CSV con el número de vuelta en el nombre (`lap01`, `vuelta_2`, `v3`); un bag por vuelta o uno de toda la tanda. En las pruebas, 22 errores introducidos a propósito en el verificador y el registro fueron detectados.

**Lo que NO verifica:** que el video tenga imágenes reproducibles (solo su estructura), que un `mcap` tenga mensajes, que el contenido de los mensajes sea el correcto, ni que el layout del `grabador` real coincida con el supuesto.

**Supuestos por confirmar con el docente y el primer bag real:**
- Los **nombres de tópicos** de `evidencia.yaml` son candidatos (`/odom`, `/imu`, `/tag/pose` o `/pit/medicion`, `/pit/calibracion`): ajústalos tras `ros2 bag info` de un bag real.
- La lista de la referencia del HTML es distinta de la de la imagen que usas (el HTML pide además `sensores.csv`, `vueltas.csv`, `intervenciones.csv` y `mensajes.csv`, y no define cuáles genera el `grabador`). El verificador sigue la lista de la imagen y es configurable; `vueltas.csv` se podría generar desde las métricas si el curso no lo hace.

## Registro experimental

`evidencia/registro_experimental.py agregar | listar | verificar | exportar`. Una línea JSON por prueba (tipo, robot, operador, estado `ok|fallo|parcial|abortado`, parámetros, resultados, notas, archivos adjuntos con SHA-256, `corrige`). **Solo se añade**: las pruebas fallidas se registran igual y una corrección es un registro nuevo. Cada línea lleva el hash de la anterior: se detecta que se edite, borre a mitad o reordene una línea, y que un adjunto cambie después. **No detecta** que se borren las últimas líneas ni que alguien reescriba todo el archivo; por eso conviene exportar el CSV y subirlo al repositorio. Un corte a mitad de línea se avisa y no deja seguir hasta revisarlo. Complementa la bitácora escrita (`docs/bitacora_laboratorio.md`); no la sustituye.

## Panel (`tablero/`)

Página estática (sin dependencias) con los bloques de la referencia: Control, Cronometraje (vuelta n/4, última, mejor, delta y cuatro sectores con colores F1), Estaciones, Carrito, Banderas e intervenciones; más pits y precisión, evidencia y eventos recientes. Se actualiza cada 0.5 s y avisa si los datos tienen más de 3 s con la misión en marcha.

```bash
python3 tablero/datos_simulados.py [--escenario normal|aprendiendo|falla] [--hasta-s 200] [--evidencia bag_vacio,video_truncado]
# abrir tablero/panel.html con doble clic (usa datos/datos.js), o:
python3 tablero/datos_simulados.py --vivo --velocidad 20 &   # reescribe datos.json cada 0.5 s
cd tablero && python3 -m http.server 8080                    # y abrir http://localhost:8080/panel.html
```

- **Es un prototipo de solo lectura.** Los botones (Iniciar, Reset carrito, Reiniciar vuelta, **E-STOP**) solo envían una orden con `?api=URL` (`POST URL/orden {"orden": "..."}`); ese contrato es **provisional** y no existe todavía en el tablero base del curso. Sin API el panel lo dice en pantalla. **El E-stop real es el físico y el del curso**, no este botón.
- Batería, latencia y video no salen de nuestros eventos: aparecen como «—» (el video lo da el tablero base). Los datos simulados llevan `fuente: "simulado"` y el panel muestra «DATOS SIMULADOS».
- Una prueba comprueba que cada clave que lee `panel.js` existe en lo que genera `datos_simulados.py`. El JavaScript se revisó con un navegador (escritorio y móvil, sin errores de consola), pero **no hay pruebas automáticas del JavaScript**.
- Para el día de la tanda hace falta decidir cómo se integra con el tablero base del curso (FastAPI en el Pi5, puerto 8080) y quién alimenta `datos.json`.
