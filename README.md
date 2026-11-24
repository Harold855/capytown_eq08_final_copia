# GranPrix Delivery Semiautónomo – Grupo 8

**Proyecto final de Robótica – CapyTown**

## 1. Descripción del proyecto

El proyecto GranPrix Delivery Semiautónomo tiene como finalidad desarrollar un sistema robótico colaborativo entre un robot móvil Yahboom MicroROS Pi5 (ROSCar) y cuatro estaciones de manipulación equipadas con brazos robóticos Yahboom JetCobot.

El ROSCar deberá recorrer una trayectoria cuadrada de 2 metros por lado, dentro de una zona de 2.8 × 2.8 metros, realizando operaciones de carga, intercambio y descarga de piezas en cada estación.

El sistema utilizará ROS 2 para la comunicación interna de cada robot y MQTT para la comunicación entre dispositivos. Asimismo, incorporará visión artificial mediante AprilTags, estimación de pose, calibración adaptativa y un tablero web de supervisión.

La finalidad principal es completar cuatro vueltas válidas con la menor cantidad posible de intervenciones humanas.

## 2. Objetivos

- Desarrollar la navegación semiautónoma del ROSCar.
- Implementar la estimación de pose mediante AprilTags y solvePnP.
- Implementar el reset de pose y la calibración adaptativa de distancia y giro.
- Desarrollar un programa único de control para las cuatro estaciones JetCobot.
- Integrar los robots mediante comunicación MQTT.
- Implementar un tablero web de supervisión y control.
- Registrar evidencias experimentales mediante CSV, ROS Bags y videos.
- Minimizar las intervenciones humanas durante la carrera.

## 3. Hardware

- Yahboom MicroROS Pi5 – ROSCar.
- Cuatro brazos robóticos Yahboom JetCobot.
- Raspberry Pi 5.
- NVIDIA Jetson de las estaciones.
- Cámara del ROSCar.
- Encoders, IMU y LiDAR, sujetos a la configuración final del robot.

## 4. Tecnologías

- ROS 2 Humble.
- Python.
- MQTT y Mosquitto.
- OpenCV.
- AprilTag 36h11.
- TF2.
- MoveIt2.
- HTML, CSS y JavaScript.
- Git y GitHub.

## 5. Configuración prevista del Grupo 8

| Parámetro | Valor |
|---|---|
| Equipo | `eq08` |
| ROS_DOMAIN_ID | `8` |
| ROS_LOCALHOST_ONLY | `1` |
| IP del ROSCar | `192.168.50.108` |
| Broker MQTT | `192.168.50.10` |
| Puerto MQTT | `1883` |
| Tablero web | `http://192.168.50.108:8080` |
| Red | `GranPrix-ESAN` |

## 6. Estaciones

| Estación | Operación |
|---|---|
| E1 – Largada | Carga de pieza A |
| E2 – Pit 1 | Intercambio A → B |
| E3 – Pit 2 | Intercambio B → C |
| E4 – Meta | Descarga de pieza C |

## 7. Restricciones principales

- Cuatro vueltas consecutivas.
- Tiempo máximo de tanda: 12 minutos.
- Tiempo máximo por pit: 10 segundos.
- Tolerancia de posición: 4 cm.
- Tolerancia angular: 6°.
- Máximo de dos reintentos automáticos por parada.
- Velocidad lineal máxima: 0.20 m/s.
- Velocidad angular máxima: 0.8 rad/s.
- Mínimo de tres vueltas válidas para clasificar.

## 8. Organización del repositorio

- `carrito/`: programa de autonomía del ROSCar.
- `estacion/`: programa de control de los JetCobot.
- `vendor/`: dependencia oficial del curso.
- `simulacion/`: simulaciones y predicciones.
- `scripts/`: automatización y diagnóstico.
- `tests/`: pruebas unitarias y de integración.
- `experimentos/`: pruebas experimentales.
- `docs/`: documentación técnica.
- `videos/`: videos de la tanda oficial.
- `bags/`: registros ROS Bag.

## 9. Referencias

- [Documentación oficial Yahboom JetCobot](https://www.yahboom.net/study/JetCobot)
- [Documentación oficial Yahboom MicroROS Pi5](https://www.yahboom.net/study/MicroROS-Pi5)
- [Repositorio CapyTown RC-0](https://github.com/Harold855/RC-0_MicroRos_Pi5)
- Documento oficial GranPrix Delivery Semiautónomo.
