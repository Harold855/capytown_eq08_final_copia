# Índice de documentación

Qué hay y cuándo leerlo. Los documentos están agrupados por lo que se necesita hacer.

## Para entender el proyecto y su estado
| Documento | Qué contiene |
|---|---|
| [`../README.md`](../README.md) | Descripción del proyecto, reglas, pit, tópicos MQTT, rúbrica, riesgos y preguntas abiertas |
| [`desarrollo_realizado.md`](desarrollo_realizado.md) | **Registro de todo lo construido**: estado de cada pieza, evidencia, hallazgos con cifras, errores corregidos, qué falta |
| [`arquitectura.md`](arquitectura.md) | Cómo encaja el código del equipo con la arquitectura del curso, dependencias entre paquetes, flujos y adaptadores pendientes |
| [`requerimientos.md`](requerimientos.md) | Cada requisito del reto, qué lo cubre, qué prueba lo comprueba y en qué estado está |
| [`contexto_analisis.md`](contexto_analisis.md) | Análisis de los repositorios previos, del HTML oficial y del repositorio del docente |
| [`../contexto_division_reto_final.md`](../contexto_division_reto_final.md) | División del trabajo del equipo (v1.3): bloques, dependencias, plan por ventanas |

## Para preparar el entorno y correr las pruebas
| Documento | Qué contiene |
|---|---|
| [`entorno_desarrollo.md`](entorno_desarrollo.md) | PC, Race Control, WSL2/ROS 2, Pi5 y Jetson: qué está verificado |
| [`configuracion.md`](configuracion.md) | Los cinco archivos YAML, qué valores son reales, supuestos o placeholders, y qué no se creó y por qué |

## Para el día de laboratorio con el ROSCar
| Documento | Qué contiene |
|---|---|
| [`procedimiento_laboratorio_roscar.md`](procedimiento_laboratorio_roscar.md) | Cómo se trabajó en RC-0 y RC-1 (VNC, contenedor, scripts) |
| [`material_docente_rc1.md`](material_docente_rc1.md) | Material del docente de RC-1 y ensayo de los scripts en su simulador |
| [`../scripts/roscar_v01/README.md`](../scripts/roscar_v01/README.md) | Preflight, diagnóstico, prueba de movimiento, registro y análisis de mediciones |
| [`../carrito/README.md`](../carrito/README.md) | Planificador, ejecutor y estimadores: API, supuestos y verificación |
| [`bitacora_laboratorio.md`](bitacora_laboratorio.md) | Plantilla de la bitácora por sesión |

## Para la cámara y el AprilTag
| Documento | Qué contiene |
|---|---|
| [`apriltag_sin_robot.md`](apriltag_sin_robot.md) | Qué se puede probar sin robot, cifras de precisión, el efecto de la calibración y de la distorsión |
| [`procedimiento_calibracion_camara.md`](procedimiento_calibracion_camara.md) | Calibrar la focal con regla y tag (primero) y validarla fuera del eje |
| [`procedimiento_calibracion_damero.md`](procedimiento_calibracion_damero.md) | Calibrar con damero, incluida la distorsión (solo si lo anterior falla fuera del eje) |

## Para el día de laboratorio con el JetCobot
| Documento | Qué contiene |
|---|---|
| [`../scripts/jetcobot_v01/README.md`](../scripts/jetcobot_v01/README.md) | Diagnóstico de solo lectura y cronómetro del ciclo |
| [`../estacion/README.md`](../estacion/README.md) | Estrategia de cambio, supuestos, hallazgo de tiempo y cómo enseñar las poses |

## Referencias externas
- [`../vendor/README.md`](../vendor/README.md): copia fija del repositorio del docente; su documentación está en `vendor/granprix/docs/arquitectura/00`–`04`.

## Convención
Todo documento marca lo que es **verificado** (con pruebas), **simulado**, **sin verificar** o **supuesto**. Una prueba simulada no demuestra precisión, tiempo ni seguridad física.
