# JetCobot — diagnóstico y cronómetro (v0.1, sin movimiento)

Scripts para el día de laboratorio con el brazo. **Ninguno mueve el brazo.**

| Script | Qué hace |
|---|---|
| `diagnostico_jetcobot.py` | Lee ángulos, coordenadas, pinza y servos, y mide la latencia de lectura del puerto serie (la que el repositorio del docente deja "por confirmar"). Guarda el informe en `experimentos/dia01_jetcobot/`. Una prueba automática comprueba que el archivo no contiene órdenes de movimiento, de pinza ni de apagado |
| `cronometro_ciclo.py` | Cronómetro manual por fases: una persona pulsa Enter en cada marca mientras el brazo trabaja. Guarda `tiempos_manipulacion.csv` y dice cuánto queda del pit de 10 s |

## Uso

```bash
# Sin brazo, para comprobar que el script corre:
python3 scripts/jetcobot_v01/diagnostico_jetcobot.py --simular

# En la Jetson, con el brazo encendido y ningún otro programa usando el puerto serie:
python3 scripts/jetcobot_v01/diagnostico_jetcobot.py --puerto /dev/ttyUSB0

# Durante un ciclo de E2 hecho con cualquier código (p. ej. el Nivel 4 del Reto 1):
python3 scripts/jetcobot_v01/cronometro_ciclo.py --rol 2 --corrida 1 --fuente nivel4
```

Antes del diagnóstico:
- Confirmar el modelo del brazo y el método de acceso a la Jetson con el docente (sigue sin definir).
- No ejecutarlo si el `supervisor_estacion` del curso u otro programa ya tiene abierto el puerto serie.
- Si `pymycobot` no está instalado, el script lo dice y termina sin hacer nada.

## Limitaciones
- Los límites articulares de referencia son los del Reto 1, no los del guardián del curso (que no está publicado).
- El cronómetro mide con una persona: sirve para la puerta del día 3, no para validar el pit. El pit completo se mide con marcas propias del carrito.
- Probado solo con pruebas automáticas y con `--simular`. Nunca se ejecutó contra un brazo real desde este repositorio.
