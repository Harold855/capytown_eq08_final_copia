"""Compensación de la pose del carrito: dónde queda la cuna respecto al brazo.

SUPUESTOS PROVISIONALES (el curso aún no publica `dock_frames.yaml`):
- Marco del dock: origen en el centro del dock, x en el rumbo nominal de llegada, y a la izquierda.
- `PoseDock` es la pose del carrito en ese marco; `dth` positivo es antihorario.
- El brazo está a la DERECHA del carrito: su eje queda a 29 cm del centro del dock; la cuna, a
  11 cm a la derecha del centro del carrito (HTML, sección 4).
- Los ejes del marco del brazo son paralelos a los del dock; si no lo son, se refleja en el ángulo
  de `brazo_en_dock` (la transformación ya rota las posiciones y los deltas).
Toda cifra de `GeometriaEstacion` debe sustituirse por las medidas reales y por `dock_frames.yaml`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple

from geometria_dock.transformaciones import Pose2D, aplicar, desde_grados, invertir
from .puerto import PoseDock


@dataclass(frozen=True)
class GeometriaEstacion:
    cuna_en_robot: Pose2D = field(default_factory=lambda: Pose2D(0.0, -0.11, 0.0))
    brazo_en_dock: Pose2D = field(default_factory=lambda: Pose2D(0.0, -0.29, 0.0))
    alcance_min_m: float = 0.14
    alcance_max_m: float = 0.22


@dataclass(frozen=True)
class Compensacion:
    cuna_en_brazo: Tuple[float, float]   # posición medida de la cuna en el marco del brazo (m)
    delta_en_brazo: Tuple[float, float]  # medida menos nominal, en el marco del brazo (m)
    distancia_al_eje_m: float
    alcanzable: bool


def _cuna_en_brazo(pose: PoseDock, geo: GeometriaEstacion) -> Tuple[float, float]:
    t_dock_robot = desde_grados(pose.dx, pose.dy, pose.dth)
    cuna_dock = aplicar(t_dock_robot, (geo.cuna_en_robot.x, geo.cuna_en_robot.y))
    t_brazo_dock = invertir(geo.brazo_en_dock)
    return aplicar(t_brazo_dock, cuna_dock)


def compensar(pose: PoseDock, geo: GeometriaEstacion = GeometriaEstacion()) -> Compensacion:
    medida = _cuna_en_brazo(pose, geo)
    nominal = _cuna_en_brazo(PoseDock(0.0, 0.0, 0.0), geo)
    dx, dy = medida[0] - nominal[0], medida[1] - nominal[1]
    d = math.hypot(*medida)
    eps = 1e-9  # los extremos de ±4 cm caen exactamente en el borde del alcance
    return Compensacion(medida, (dx, dy), d, geo.alcance_min_m - eps <= d <= geo.alcance_max_m + eps)
