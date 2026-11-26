"""Acceso a la herramienta AprilTag del docente (vendor/granprix/estacion/herramientas, sin modificar).

Necesita OpenCV y pupil-apriltags (requirements-vision.txt). Un solo detector por proceso: la librería nativa
aborta con memoria corrupta al mezclar familias o detectores (visto con tag25h9 en pupil-apriltags 1.0.4).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

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
