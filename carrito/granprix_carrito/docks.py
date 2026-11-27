"""Docks del circuito. Valores nominales del HTML; sustituibles por `dock_frames.yaml` cuando el curso lo publique.

Marco del mapa: x al este, y al norte, ángulos antihorarios (radianes). `rumbo` es el rumbo nominal con
que el carrito llega al dock, que coincide con el sentido del tramo que lo precede. Marco del dock
(SUPUESTO, ver estacion/src/app_equipo/compensacion_pose.py): origen en el centro del dock, x en el
rumbo nominal de llegada, y a la izquierda; la pose del carrito en ese marco es (dx, dy, dth).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, Tuple

from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir

ZONA_M = 2.8
ORDEN = (1, 2, 3, 4)  # sentido antihorario: E1 -> E2 -> E3 -> E4 -> E1


@dataclass(frozen=True)
class Dock:
    estacion: int
    x: float
    y: float
    rumbo: float  # rad

    @property
    def pose(self) -> Pose2D:
        return Pose2D(self.x, self.y, self.rumbo)


DOCKS_HTML: Dict[int, Dock] = {
    1: Dock(1, 0.40, 0.40, -math.pi / 2),
    2: Dock(2, 2.40, 0.40, 0.0),
    3: Dock(3, 2.40, 2.40, math.pi / 2),
    4: Dock(4, 0.40, 2.40, math.pi),
}


def siguiente(estacion: int) -> int:
    if estacion not in ORDEN:
        raise ValueError('estación debe ser 1 a 4')
    return ORDEN[estacion % 4]


def dock_a_mapa(dock: Dock, dx: float, dy: float, dth_deg: float) -> Pose2D:
    """Pose del carrito en el mapa a partir de su pose en el dock (dth en grados, como el contrato)."""
    return componer(dock.pose, desde_grados(dx, dy, dth_deg))


def mapa_a_dock(dock: Dock, pose: Pose2D) -> Tuple[float, float, float]:
    """Pose del carrito en el dock (dx, dy en m; dth en grados) a partir de su pose en el mapa."""
    p = componer(invertir(dock.pose), pose)
    return p.x, p.y, math.degrees(p.th)


def validar(docks: Dict[int, Dock]) -> Dict[int, Dock]:
    if sorted(docks) != [1, 2, 3, 4]:
        raise ValueError('se esperaban exactamente los docks 1, 2, 3 y 4')
    for d in docks.values():
        if not all(math.isfinite(v) for v in (d.x, d.y, d.rumbo)):
            raise ValueError(f'dock {d.estacion}: valores no finitos')
        if not (0.0 <= d.x <= ZONA_M and 0.0 <= d.y <= ZONA_M):
            raise ValueError(f'dock {d.estacion}: fuera de la zona de {ZONA_M} m; ¿metros o centímetros?')
    return docks


def cargar_json(ruta: str) -> Dict[int, Dock]:
    """Formato: {"docks": [{"estacion": 1, "x": 0.4, "y": 0.4, "rumbo_deg": -90}, ...]} (x, y en metros)."""
    with open(ruta, encoding='utf-8') as f:
        datos = json.load(f)
    docks = {int(d['estacion']): Dock(int(d['estacion']), float(d['x']), float(d['y']), math.radians(float(d['rumbo_deg'])))
             for d in datos['docks']}
    return validar(docks)
