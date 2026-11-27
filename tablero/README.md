# tablero/ — prototipo de extensión del tablero

`panel.html` + `panel.js` + `panel.css`: página estática, sin dependencias, de solo lectura. `datos_simulados.py` genera los datos de prueba.

```bash
python3 tablero/datos_simulados.py            # escribe tablero/datos/ (se ignora en git)
# abrir tablero/panel.html con doble clic
```

Detalle, límites (no está conectado al tablero del curso; los botones solo funcionan con `?api=`) y cómo probarlo en vivo: [`docs/tablero_y_evidencia.md`](../docs/tablero_y_evidencia.md).
