"""Transformaciones rígidas 2D. Unidades SI: metros y radianes.

Convención: `T_A_B` lleva coordenadas expresadas en B a coordenadas en A. Por eso
`componer(T_A_B, T_B_C)` devuelve `T_A_C`. Una única convención para 1.3 (carrito) y 2.4 (estación).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


def wrap(a: float) -> float:
    """Normaliza un ángulo a [-pi, pi]."""
    if not math.isfinite(a):
        raise ValueError('ángulo no finito')
    return math.atan2(math.sin(a), math.cos(a))


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    th: float

    def __post_init__(self) -> None:
        if not all(math.isfinite(v) for v in (self.x, self.y, self.th)):
            raise ValueError('pose no finita')


def componer(a: Pose2D, b: Pose2D) -> Pose2D:
    """T_A_C = T_A_B ∘ T_B_C, con a = T_A_B y b = T_B_C."""
    c, s = math.cos(a.th), math.sin(a.th)
    return Pose2D(a.x + c * b.x - s * b.y, a.y + s * b.x + c * b.y, wrap(a.th + b.th))


def invertir(a: Pose2D) -> Pose2D:
    """T_B_A a partir de T_A_B."""
    c, s = math.cos(a.th), math.sin(a.th)
    return Pose2D(-c * a.x - s * a.y, s * a.x - c * a.y, wrap(-a.th))


def aplicar(a: Pose2D, punto: Tuple[float, float]) -> Tuple[float, float]:
    """Expresa en A un punto dado en B (a = T_A_B)."""
    c, s = math.cos(a.th), math.sin(a.th)
    return (a.x + c * punto[0] - s * punto[1], a.y + s * punto[0] + c * punto[1])


def desde_grados(x: float, y: float, th_deg: float) -> Pose2D:
    """Construye una pose con el ángulo en grados (como lo entrega el contrato MQTT)."""
    return Pose2D(x, y, math.radians(th_deg))
