# Entorno de desarrollo

Qué hay que tener en cada máquina y qué está **verificado**. Lo no verificado se marca.

| Dónde | Qué | Estado |
|---|---|---|
| PC / laptop (Linux, macOS, WSL2 o Windows) | Python 3.10+, `.venv`, pruebas de software, Race Control del docente | **Verificado** (Linux, Python 3.13) |
| WSL2 con Ubuntu 22.04 | ROS 2 Humble y el simulador de RC-1 | Sin verificar aquí; procedimiento de RC-1 |
| Pi5 del ROSCar (contenedor `ros2_dev`) | ROS 2 Humble, `rclpy`, nuestros scripts | Sin verificar; ver `docs/procedimiento_laboratorio_roscar.md` |
| Jetson de la estación | Python de la imagen, `pymycobot` | Sin verificar; el código está escrito para Python 3.8+ |

## 1. PC: entorno de pruebas (sin robots ni red)
```bash
bash scripts/preparar_entorno.sh            # crea .venv e instala requirements-dev.txt
source .venv/bin/activate
bash scripts/ejecutar_pruebas.sh            # 70 pruebas; "TODO OK" si pasan
```
En Windows sin WSL: `py -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements-dev.txt` y `python -m unittest discover -s tests/estacion` (y análogo para los otros directorios). El script `.sh` necesita bash.

Las pruebas heredadas de RC-0 (`scripts/historicos/rc0/test`) se corren aparte: `cd scripts/historicos/rc0 && python -m pytest -q test`. Una falla es anterior al reto (`test_elegir_topic_ambiguo_exige_indicarlo`).

## 2. PC: Race Control del docente (integración)
Pide Python 3.12+ y un broker MQTT (Mosquitto).
```bash
bash scripts/preparar_entorno.sh --pc-race      # instala vendor/granprix/pc-race en modo editable
source .venv/bin/activate
mosquitto -v                                     # en otra terminal (apt install mosquitto, o la instalación de Windows)
pc-race                                          # tablero del juez en http://127.0.0.1:8080
python vendor/granprix/pc-race/simulador_carritos.py --host localhost --carritos 3 --velocidad 20
```
Verificado: las 126 pruebas de `pc-race` pasan. **No verificado:** la ejecución contra un Mosquitto real (no había broker en el entorno donde se preparó). La instalación editable deja `pc_race.egg-info` dentro de `vendor/`; está ignorada por Git y no modifica archivos versionados.

## 3. WSL2 + ROS 2 Humble + simulador (para ensayar scripts de ROS)
Seguir `instalar_en_wsl.sh` y `SIMULACION.md` del repositorio de RC-1 (rama `claude/sleepy-knuth-kc6wex` o el zip del docente). Luego, `docs/material_docente_rc1.md` sección 3. Copiar este repositorio **dentro** de Ubuntu (`~/`), no trabajar desde `/mnt/c`.

## 4. Pi5 y Jetson
- Pi5: ROS 2 vive en el contenedor `ros2_dev` (`docker exec -it ros2_dev bash`). Llevar el repositorio con `scp` y `docker cp`.
- Jetson: no instalar nada sin coordinar con el docente. El diagnóstico necesita `pymycobot` y no se debe ejecutar si otro programa usa el puerto serie.
- Antes de usar nuestros scripts en un robot: `bash scripts/ejecutar_pruebas.sh` en la PC, y el preflight correspondiente en el robot.

## 5. Convenciones
- `.venv/` y las cachés están en `.gitignore`. No se ignoran CSV, videos ni bags (son evidencia).
- Nunca subir claves, tokens ni contraseñas (`.env`, `*.key`, `*.pem` están ignorados).
- Una prueba simulada no demuestra precisión, tiempo ni seguridad física.
