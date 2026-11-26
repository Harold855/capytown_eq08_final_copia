"""Acceso a la herramienta AprilTag del docente (vendor/granprix/estacion/herramientas, sin modificar).

Necesita OpenCV y pupil-apriltags (requirements-vision.txt). Un solo detector por proceso: la librería nativa
aborta con memoria corrupta al mezclar familias o detectores (visto con tag25h9 en pupil-apriltags 1.0.4).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'vendor' / 'granprix' / 'estacion' / 'herramientas'))
import herramienta_apriltag as ht  # noqa: E402  (importa cv2 y numpy)

FAMILIA = 'tag36h11'
_DETECTOR = None


def detector():
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = ht.crear_detector(FAMILIA)
    return _DETECTOR


def pose_tag(imagen, params: Tuple[float, float, float, float], tamano_m: float,
             tag_id: Optional[int] = None) -> Optional[dict]:
    """Pose del tag respecto de la cámara (x, y, z en m; dth en grados) o None si no hay exactamente un tag
    (del id pedido, si se da). Mejor no medir que medir el equivocado."""
    dets = [d for d in ht.detectar_en(detector(), imagen, params, tamano_m) if tag_id is None or d['id'] == tag_id]
    return dets[0] if len(dets) == 1 and dets[0]['pose'] else None


class Corrector:
    """Quita la distorsión del lente de las imágenes de una cámara calibrada (con damero).

    La herramienta del docente supone un lente sin distorsión: con una cámara que distorsiona hay que pasar cada
    imagen por aquí ANTES de detectar el tag, y usar `cam.tupla()` (los intrínsecos de la imagen corregida).
    Sin distorsión en la calibración devuelve la imagen tal cual. Los mapas se calculan una vez.
    """

    def __init__(self, cam) -> None:
        self._tam = (cam.ancho, cam.alto)
        self._mapas = None
        if cam.distorsion is not None:
            K = np.array([[cam.fx, 0, cam.cx], [0, cam.fy, cam.cy], [0, 0, 1.0]])
            self._mapas = cv2.initUndistortRectifyMap(K, np.array(cam.distorsion), None, K, self._tam, cv2.CV_16SC2)

    def __call__(self, imagen: np.ndarray) -> np.ndarray:
        if self._mapas is None:
            return imagen
        if (imagen.shape[1], imagen.shape[0]) != self._tam:
            raise ValueError(f'la imagen es {imagen.shape[1]}x{imagen.shape[0]} y la calibración de {self._tam[0]}x{self._tam[1]}')
        return cv2.remap(imagen, self._mapas[0], self._mapas[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=128)


def pose_tag_calibrada(imagen, cam, corrector: Optional[Corrector] = None, tamano_m: Optional[float] = None,
                       tag_id: Optional[int] = None) -> Optional[dict]:
    """Pose del tag con una cámara calibrada: corrige la distorsión (si la hay) y usa sus intrínsecos.
    `tamano_m` es obligatorio si la calibración es de damero (no guarda el tamaño del tag)."""
    tamano = tamano_m if tamano_m is not None else cam.tamano_tag_m
    if tamano is None:
        raise ValueError('falta el tamaño del tag (la calibración de damero no lo guarda)')
    corrector = corrector or Corrector(cam)
    return pose_tag(corrector(imagen), cam.tupla(), tamano, tag_id)
