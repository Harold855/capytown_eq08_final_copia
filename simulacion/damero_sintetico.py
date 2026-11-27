"""Imágenes sintéticas de un damero con pose, cámara y distorsión conocidas, para probar la calibración sin cámara.

Cámara pin-hole con la matriz K y la distorsión `dist` (modelo de OpenCV), desenfoque y ruido gaussiano. Es una
cota optimista: no modela iluminación real, enfoque variable ni damero combado.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Sequence, Tuple

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulacion.lente import distorsionar  # noqa: E402
from vision.calibracion_damero import Patron, imagen_damero  # noqa: E402

PX_CUADRO = 60


def renderizar(patron: Patron, rvec: Sequence[float], tvec: Sequence[float], K: np.ndarray, dist: Sequence[float],
               ancho: int, alto: int, *, desenfoque_px: float = 0.6, ruido: float = 2.0, semilla: int = 0,
               supermuestreo: int = 3, fondo: int = 120) -> np.ndarray:
    tab = imagen_damero(patron, PX_CUADRO)
    h, w = tab.shape
    # el origen del tablero físico es la primera esquina interior: (2 cuadros desde el borde de la imagen)
    fis = np.array([[(u - 2 * PX_CUADRO) / PX_CUADRO * patron.cuadro_m, (v - 2 * PX_CUADRO) / PX_CUADRO * patron.cuadro_m, 0.0]
                    for u, v in ((0, 0), (w, 0), (w, h), (0, h))])
    px, _ = cv2.projectPoints(fis, np.asarray(rvec, float), np.asarray(tvec, float), K, None)
    # Convención de píxel: projectPoints da coordenadas de CENTRO de píxel (el píxel 0 está en 0.0), y los bordes
    # del tablero están a medio píxel del centro de sus píxeles extremos; la imagen supermuestreada también.
    origen = np.array([[-0.5, -0.5], [w - 0.5, -0.5], [w - 0.5, h - 0.5], [-0.5, h - 0.5]], np.float32)
    destino = ((px.reshape(-1, 2) + 0.5) * supermuestreo - 0.5).astype(np.float32)
    H = cv2.getPerspectiveTransform(origen, destino)
    grande = cv2.warpPerspective(tab, H, (ancho * supermuestreo, alto * supermuestreo), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=fondo)
    img = cv2.resize(grande, (ancho, alto), interpolation=cv2.INTER_AREA)
    img = distorsionar(img, K, dist, fondo).astype(np.float32)
    if desenfoque_px > 0:
        img = cv2.GaussianBlur(img, (0, 0), desenfoque_px)
    if ruido > 0:
        img += np.random.default_rng(semilla).normal(0.0, ruido, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def esquinas_visibles(patron: Patron, rvec, tvec, K, ancho: int, alto: int, margen: float = 25.0) -> bool:
    """¿Quedan todas las esquinas interiores (y algo de margen del tablero) dentro de la imagen?"""
    obj = patron.puntos_objeto()
    pts, _ = cv2.projectPoints(obj, np.asarray(rvec, float), np.asarray(tvec, float), K, None)
    p = pts.reshape(-1, 2)
    return bool(p[:, 0].min() > margen and p[:, 1].min() > margen and p[:, 0].max() < ancho - margen
                and p[:, 1].max() < alto - margen)


def poses_aleatorias(n: int, patron: Patron, K: np.ndarray, ancho: int, alto: int, semilla: int = 0,
                     inclinacion_max_deg: float = 40.0) -> List[Tuple[np.ndarray, np.ndarray]]:
    """n poses (rvec, tvec) variadas: distintas distancias, desplazamientos hasta cerca de los bordes e inclinaciones."""
    rng = np.random.default_rng(semilla)
    ancho_tab = (patron.cols - 1) * patron.cuadro_m
    alto_tab = (patron.filas - 1) * patron.cuadro_m
    poses: List[Tuple[np.ndarray, np.ndarray]] = []
    while len(poses) < n:
        ang = np.radians(rng.uniform(0, inclinacion_max_deg))
        eje = rng.normal(size=3)
        eje[2] = abs(eje[2]) * 0.2                # inclinar sobre todo alrededor de ejes del plano
        eje /= np.linalg.norm(eje)
        rvec = eje * ang
        z = rng.uniform(0.30, 0.55)
        # centro del tablero (no de la primera esquina) distribuido por toda la imagen
        cx_m = rng.uniform(-0.5, 0.5) * (ancho / 2 / K[0, 0] * z)
        cy_m = rng.uniform(-0.5, 0.5) * (alto / 2 / K[0, 0] * z)
        R, _ = cv2.Rodrigues(rvec)
        centro_local = np.array([ancho_tab / 2, alto_tab / 2, 0.0])
        tvec = np.array([cx_m, cy_m, z]) - R @ centro_local
        if esquinas_visibles(patron, rvec, tvec, K, ancho, alto):
            poses.append((rvec, tvec))
    return poses
