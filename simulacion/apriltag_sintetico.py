"""Imágenes sintéticas de un AprilTag con una pose conocida, para probar la visión sin robot ni cámara.

Renderiza el tag (el mismo que genera `vendor/granprix/estacion/herramientas/herramienta_apriltag.py`)
visto por una cámara pin-hole en una pose conocida, y lo pasa por el detector del docente. Permite medir
el error de la pose contra la verdad.

Qué valida: unidades, ejes y signo de `dth` de la herramienta, y la precisión del detector con un modelo
de cámara ideal (pin-hole, sin distorsión) más desenfoque y ruido gaussiano.
Qué NO valida: la cámara real (distorsión, enfoque, exposición, rolling shutter, retardo), la
calibración intrínseca, el tamaño real impreso del tag, la iluminación del laboratorio, ni dónde está
montada la cámara en el carrito. Los números son una COTA OPTIMISTA de lo que se logrará con la cámara real.

Convención de la herramienta del docente (sistema de la cámara): x a la derecha, y hacia abajo, z hacia
adelante; el tag de frente tiene R = I; `dth` = atan2(R[0,2], R[2,2]) en grados, el giro del tag alrededor
del eje vertical de la cámara.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from vision import herramienta as hv  # noqa: E402
ht = hv.ht

FAMILIA = 'tag36h11'
TAMANO_M = 0.06            # lado del cuadrado negro del tag del reto
CELDAS_TAG = 8             # celdas por lado de tag36h11 incluido el borde negro


def parametros_camara(ancho: int, alto: int, fov_h_deg: float) -> Tuple[float, float, float, float]:
    f = (ancho / 2) / math.tan(math.radians(fov_h_deg) / 2)
    return f, f, ancho / 2, alto / 2


def rot_y(grados: float) -> np.ndarray:
    c, s = math.cos(math.radians(grados)), math.sin(math.radians(grados))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def renderizar(tag_id: int, R: np.ndarray, t: Tuple[float, float, float], ancho: int, alto: int, fov_h_deg: float,
               *, desenfoque_px: float = 0.0, ruido: float = 0.0, fondo: int = 200, supermuestreo: int = 4,
               semilla: int = 0, tamano_m: float = TAMANO_M, k1: float = 0.0) -> np.ndarray:
    """Imagen en gris de 8 bits. `R`, `t`: pose del tag (centro) en el sistema de la cámara. `tamano_m`: lado
    REAL del cuadrado negro impreso (puede diferir del nominal de 6 cm). `k1`: distorsión radial del lente
    (modelo de OpenCV, xd = xu·(1 + k1·r²) en coordenadas normalizadas; negativo = barril, típico de gran angular)."""
    fx, fy, cx, cy = parametros_camara(ancho, alto, fov_h_deg)
    tag = ht.imagen_png(FAMILIA, tag_id, 40)
    h, w = tag.shape
    mitad = tamano_m * (CELDAS_TAG + 2 * ht.MARGEN_CELDAS) / CELDAS_TAG / 2   # con el margen blanco
    esquinas_tag = np.array([[-mitad, -mitad, 0], [mitad, -mitad, 0], [mitad, mitad, 0], [-mitad, mitad, 0]])
    cam = esquinas_tag @ np.asarray(R).T + np.asarray(t)
    if np.any(cam[:, 2] <= 0.01):
        raise ValueError('el tag queda detrás de la cámara')
    px = np.stack([fx * cam[:, 0] / cam[:, 2] + cx, fy * cam[:, 1] / cam[:, 2] + cy], axis=1) * supermuestreo
    origen = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
    H = cv2.getPerspectiveTransform(origen, px.astype(np.float32))
    grande = cv2.warpPerspective(tag, H, (ancho * supermuestreo, alto * supermuestreo), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=fondo)
    img = cv2.resize(grande, (ancho, alto), interpolation=cv2.INTER_AREA)
    if k1 != 0.0:
        K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]])
        uu, vv = np.meshgrid(np.arange(ancho, dtype=np.float32), np.arange(alto, dtype=np.float32))
        pts = np.stack([uu.ravel(), vv.ravel()], 1).reshape(-1, 1, 2)
        sin = cv2.undistortPoints(pts, K, np.array([k1, 0, 0, 0, 0]), P=K).reshape(alto, ancho, 2)
        img = cv2.remap(img, sin[..., 0].astype(np.float32), sin[..., 1].astype(np.float32), cv2.INTER_LINEAR,
                        borderValue=fondo)
    img = img.astype(np.float32)
    if desenfoque_px > 0:
        img = cv2.GaussianBlur(img, (0, 0), desenfoque_px)
    if ruido > 0:
        img += np.random.default_rng(semilla).normal(0.0, ruido, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


detector = hv.detector   # un solo detector por proceso (compartido con vision.herramienta)


def medir(imagen: np.ndarray, fov_h_deg: float, tag_id: Optional[int] = None) -> Optional[dict]:
    """Pose que da la herramienta del docente, o None si no ve el tag (o ve otro id)."""
    alto, ancho = imagen.shape[:2]
    params = parametros_camara(ancho, alto, fov_h_deg)
    dets = ht.detectar_en(detector(), imagen, params, TAMANO_M)
    dets = [d for d in dets if tag_id is None or d['id'] == tag_id]
    return dets[0] if len(dets) == 1 and dets[0]['pose'] else None
