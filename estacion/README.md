# estacion/ — estrategia de cambio de pieza (plantilla provisional)

Según `vendor/granprix/docs/arquitectura/02-jetcobot-estacion.md`, en la estación el curso ejecuta el `supervisor_estacion` (MQTT, turno, validación, congelar el brazo) y el equipo escribe la estrategia `EstrategiaDeCambio.cambiar(pose, pieza_trae)`. **El supervisor y el puerto `BrazoJetCobot` aún no están publicados.** Esta carpeta es una plantilla nuestra, para probar la lógica y los tiempos con un brazo simulado. No mueve nada real.

## Qué hay

```
estacion/
  src/app_equipo/
    puerto.py              tipos del contrato (PoseDock, ResultadoCambio) y puerto del brazo (SUPUESTO)
    roles.py               E1 carga A, E2 retira A y coloca B, E3 retira B y coloca C, E4 retira C
    compensacion_pose.py   dónde queda la cuna respecto al brazo (SUPUESTOS de marcos)
    posiciones.py          carga y valida poses enseñadas; sin valores por defecto
    estrategia.py          EstrategiaCambio: valida, compensa y ejecuta los pasos
    brazo_simulado.py      brazo y reloj falsos para pruebas y estimación de tiempo
    configuracion.py       carga estacion.yaml: tolerancias, tope de tiempo y geometría (no puede aflojar el reto)
  config/estacion.yaml          parámetros de la estrategia y geometría (SUPUESTOS marcados)
  config/poses.plantilla.yaml   plantilla con null: nada se mueve hasta enseñar las poses
geometria_dock/transformaciones.py   transformaciones 2D (compartidas con el carrito)
```

Pruebas: `bash scripts/ejecutar_pruebas.sh` (sin robots, sin red).

## Comportamiento
- **Falla cerrada:** sin poses enseñadas devuelve `NO_CONFIGURADO` y no llama al brazo.
- **Valida antes de mover:** pieza esperada (`PIEZA_INESPERADA`), tolerancia 4 cm y 6° (`FUERA_DE_TOLERANCIA`), alcance de la cuna 14–22 cm (`FUERA_DE_ALCANCE`), bandeja de 4 (`BANDEJA_AGOTADA`).
- **Un fallo detiene la secuencia** y no intenta recuperarse: el estado del brazo es incierto y lo gestiona el supervisor. Un agarre en vacío no consume la ranura de la bandeja.
- **Compensación:** las poses se enseñan con el carrito en su pose nominal; la estrategia solo suma el desplazamiento de la cuna a los movimientos que ocurren sobre el carrito. El almacén y la recepción no se desplazan.
- **Termina en una pose libre** para que el carrito no salga con el brazo sobre su trayectoria.
- **Límite de tiempo propio** (`tiempo_max_s`, por defecto 8 s, placeholder): el límite real del pit (10 s) incluye medir, acoplar, MQTT, reset y recalibración.

## Hallazgo de tiempo (con duraciones de EJEMPLO)
Con 1.0 s por movimiento y 0.4 s por maniobra de pinza (**placeholders, no mediciones**), la secuencia actual tarda 8.2 s en E1 y E4 y **15.4 s en E2 y E3** (13 movimientos y 6 maniobras de pinza). Aunque se midan los tiempos reales, E2 y E3 hacen el doble de trabajo que E1: habrá que fusionar waypoints (quitar los puntos de subida intermedios) o validar con el docente cuánto del pit se reserva al brazo. Es lo primero que debe medir el día 3 (con `scripts/jetcobot_v01/cronometro_ciclo.py` y, luego, con esta estrategia).

## Supuestos que hay que confirmar (ver el aviso de cada módulo)
1. **Puerto del brazo:** `mover_coords`, `abrir_pinza`, `cerrar_pinza`, `soltar_torque` son una suposición. Si el puerto oficial es articular o difiere, solo cambia `puerto.py` y las llamadas de `estrategia.py`.
2. **Marcos:** origen del dock en su centro, x en el rumbo de llegada, y a la izquierda; `PoseDock` es la pose del carrito en ese marco; el brazo a la derecha, a 29 cm; la cuna a 11 cm a la derecha del centro del carrito. Falta `dock_frames.yaml`.
3. **`pieza_dejo`:** se entiende como la pieza que queda en la cuna (None en E4).
4. **Rol y ranura:** la firma `cambiar(pose, pieza_trae)` no trae el dock ni la ranura de la bandeja; aquí el rol se fija al crear la estrategia y la ranura se cuenta internamente (`fijar_indice` sirve para reanudar tras un reinicio).
5. **Orientación de la pinza:** no se compensa `dth` en la orientación del efector; con una cuna cónica se asume que no hace falta.
6. **Python:** pensado para 3.8 o superior; no se ha probado en la Jetson.

## Enseñar las poses (en el laboratorio)
1. Copiar `config/poses.plantilla.yaml` a `poses_rolN.yaml` (también se acepta `.json`).
2. Con el carrito en su pose nominal (cruz del dock), mover el brazo con el método autorizado y leer `get_coords()` en cada punto (mm y grados).
3. Rellenar solo lo que el rol necesita; las listas de bandeja llevan 4 poses.
4. Cargar con `app_equipo.posiciones.cargar(ruta)`: rechaza valores en metros, fuera de ±600 mm, listas de otro tamaño, claves desconocidas y duplicadas. Más en [`docs/configuracion.md`](../docs/configuracion.md).
