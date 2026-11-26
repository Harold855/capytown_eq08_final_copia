"""Precisión de la pose AprilTag con imágenes sintéticas (ver simulacion/apriltag_sintetico.py).

Es SIMULACIÓN con una cámara pin-hole ideal: da una cota optimista. La cámara real del ROSCar (resolución,
campo de visión, distorsión, enfoque, iluminación) no está medida: los modelos de cámara de abajo son
ejemplos, no el hardware. Uso:  python3 simulacion/barrido_apriltag.py [muestras_por_condicion]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulacion import apriltag_sintetico as s  # noqa: E402

# (nombre, ancho, alto, fov_h)
CAMARAS = (('640x480 fov70', 640, 480, 70.0), ('1280x720 fov70', 1280, 720, 70.0),
           ('640x480 fov90', 640, 480, 90.0), ('320x240 fov70', 320, 240, 70.0))
RUIDOS = (('suave', 0.8, 3.0), ('fuerte', 1.5, 8.0))   # (nombre, desenfoque px, ruido en niveles de gris)
BINES_YAW = ((0, 6), (6, 15), (15, 30), (30, 45))


def muestrear(cam, ruido, bin_yaw, n, semilla) -> Dict[str, float]:
    _, ancho, alto, fov = cam
    _, blur, sigma = ruido
    rng = np.random.default_rng(semilla)
    ex, ez, eth, visto = [], [], [], 0
    for i in range(n):
        z, x, y = rng.uniform(0.22, 0.34), rng.uniform(-0.06, 0.06), rng.uniform(-0.03, 0.03)
        yaw = rng.uniform(*bin_yaw) * rng.choice((-1, 1))
        img = s.renderizar(int(rng.integers(0, 12)), s.rot_y(yaw), (x, y, z), ancho, alto, fov,
                           desenfoque_px=blur, ruido=sigma, semilla=int(rng.integers(1 << 30)))
        # el id se conoce (un solo tag en la escena); aquí se acepta cualquiera que lea el detector
        d = s.medir(img, fov)
        if d is None:
            continue
        visto += 1
        ex.append(abs(d['pose']['x'] - x) * 100)
        ez.append(abs(d['pose']['z'] - z) * 100)
        eth.append(abs(d['pose']['dth'] - yaw))
    p = lambda v, q: float(np.percentile(v, q)) if v else float('nan')  # noqa: E731
    return {'vistos': visto / n, 'x_p95': p(ex, 95), 'z_p95': p(ez, 95), 'th_p95': p(eth, 95),
            'th_max': max(eth) if eth else float('nan'), 'th_med': p(eth, 50)}


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    print(f'{n} muestras por celda; z 22-34 cm, x ±6 cm, y ±3 cm; tag 6 cm tag36h11; errores en cm y grados')
    for ruido in RUIDOS:
        print(f'\n== ruido {ruido[0]} (desenfoque {ruido[1]} px, ruido {ruido[2]} niveles) ==')
        print(f"{'cámara':16s} {'|yaw| °':>8s} {'visto':>6s} {'x p95':>7s} {'z p95':>7s} {'dth med':>8s} {'dth p95':>8s} {'dth max':>8s}")
        for cam in CAMARAS:
            for k, b in enumerate(BINES_YAW):
                r = muestrear(cam, ruido, b, n, semilla=1000 * k + 7)
                print(f"{cam[0]:16s} {b[0]:>3d}-{b[1]:<4d} {r['vistos']:>6.0%} {r['x_p95']:>7.2f} {r['z_p95']:>7.2f} "
                      f"{r['th_med']:>8.2f} {r['th_p95']:>8.2f} {r['th_max']:>8.2f}")


if __name__ == '__main__':
    main()
