"""Distorsión de lente sintética (modelo de OpenCV) para probar la visión sin cámara real."""
from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np


def distorsionar(img: np.ndarray, K: np.ndarray, dist: Sequence[float], fondo: int = 200) -> np.ndarray:
    """Aplica la distorsión `dist` = (k1, k2, p1, p2[, k3]) a una imagen SIN distorsión tomada con la matriz K.
    Para cada píxel de la imagen distorsionada busca de dónde viene en la imagen ideal."""
    d = np.zeros(5)
    d[:len(dist)] = dist
    if not np.any(d):
        return img
    alto, ancho = img.shape[:2]
    uu, vv = np.meshgrid(np.arange(ancho, dtype=np.float32), np.arange(alto, dtype=np.float32))
    pts = np.stack([uu.ravel(), vv.ravel()], 1).reshape(-1, 1, 2)
    sin = cv2.undistortPoints(pts, K, d, P=K).reshape(alto, ancho, 2)
    return cv2.remap(img, sin[..., 0].astype(np.float32), sin[..., 1].astype(np.float32), cv2.INTER_LINEAR,
                     borderValue=fondo)
