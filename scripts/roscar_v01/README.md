# ROSCar GranPrix — inicio v0.1 experimental

Grupo 8. Código provisional independiente de `granprix-esan`, aún pendiente. No reemplaza driver, agente microROS, odom_corrector ni firmware. Basado en algoritmos de las secciones 3 y 7 del HTML oficial. No incluye aún vigilancia MQTT, visión, acople, reset TF ni FSM; no es apto para la tanda.

## Instalación
Copiar las carpetas `scripts/roscar_v01`, `tests/roscar_v01` y la plantilla CSV al repositorio copia. Desde su raíz, en la terminal local del Pi5 y con el entorno ROS 2 autorizado cargado:

```bash
bash scripts/roscar_v01/preflight.sh
python3 scripts/roscar_v01/matematica.py
python3 -m unittest discover -s tests/roscar_v01 -v
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25
python3 scripts/roscar_v01/prueba_movimiento.py giro --grados 15
```

Los últimos dos son solo cálculo. Para pruebas físicas: únicamente con autorización, área despejada y plana alejada de los bordes, parada física disponible, supervisor junto al robot, brazo y otros robots fuera del alcance. Confirmar que el driver acepta Twist en `/cmd_vel`, `/odom` está activo y que no hay otro publicador. No usar en red de carrera ni con el vigilante/controlador de otro ensayo activo. No lanzar pruebas de movimiento simultáneas. No detener procesos existentes sin permiso.

```bash
python3 scripts/roscar_v01/prueba_movimiento.py recta --distancia 0.25 --velocidad 0.05 --ejecutar --zona-segura
python3 scripts/roscar_v01/prueba_movimiento.py giro --grados 15 --velocidad 0.25 --ejecutar --zona-segura
```

Solo después de comprobar movimiento y parada, con espacio suficiente y condiciones seguras, ensayar rectas de 2 m a 0.10 m/s y giros de 90° a 0.50 rad/s. Medir con cinta y transportador. `--grados` positivo = giro antihorario convencional ROS. `Ctrl+C` solicita parada con ceros, pero no garantiza parada si falla el Pi, driver, proceso o enlace microROS: mantener medio de corte físico autorizado. El script rechaza publicadores concurrentes detectados y ausencia de odometría; no sustituye vigilancia de bajo nivel. Si se detecta otro controlador durante el ensayo, parar físicamente si procede y coordinar.

## Evidencia
- `preflight.sh` escribe diagnóstico en experimentos/dia01_roscar/.
- `prueba_movimiento.py` guarda medidas odométricas y estado; no mide distancia física. Completar manualmente `mediciones_fisicas.csv` y conservar corridas fallidas.
- `matematica.py` tiene docks nominales del HTML, planificador, compensación y actualización de escalas. El intervalo [.5,1.5] y mínimo de comando son protecciones provisionales, no reglas oficiales. Calibración de ruedas ≠ escalas cd/ca.
- La caracterización definitiva se hará sobre la base de cartón real cuando esté montada; no usar valores de ejemplo como mediciones.
- `ROS_DOMAIN_ID=8`, `ROS_LOCALHOST_ONLY=1` son los valores de competencia. No cambiar procesos existentes sin coordinar el agente y nodos. No se presupone que la WiFi oficial esté activa.
- Verificar el conteo de mensajes de cualquier bag con `ros2 bag info` antes de guardar evidencias.

## Próximo paso
Revisar diagnóstico; adaptar al robot real (tópicos, cámara, batería, TF y watchdog) y al contrato oficial cuando llegue. Las pruebas de software aquí no validan el movimiento físico.
