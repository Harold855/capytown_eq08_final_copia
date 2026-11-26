from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from geometria_dock.transformaciones import Pose2D

from .docks import DOCKS_HTML, Dock, mapa_a_dock
from .marcos import Marcos, desde_medicion
from .planificador import acople_valido, error_acople
from .reset_pose import ResetPose, ResultadoReset


@dataclass(frozen=True)
class PoseDock:
    estacion: int
    dx: float
    dy: float
    dth: float
    mapa: Pose2D
    fuente: str
    cerca: bool
    desplazamiento_odom_m: float = 0.0

    @property
    def dth_deg(self) -> float:
        return math.degrees(self.dth)

    @property
    def error(self) -> Tuple[float, float]:
        return error_acople(self.dx, self.dy, self.dth_deg)

    @property
    def en_tolerancia(self) -> bool:
        return acople_valido(self.dx, self.dy, self.dth_deg)

    def a_contrato(self) -> Dict[str, float]:
        return {'dx': self.dx, 'dy': self.dy, 'dth': self.dth_deg}


class LocalizadorDock:
    def __init__(self, marcos: Marcos, reset: Optional[ResetPose] = None, docks: Dict[int, Dock] = DOCKS_HTML) -> None:
        self._marcos, self._docks = marcos, docks
        self.reset = reset if reset is not None else ResetPose()
        self._odom_ref: Optional[Pose2D] = None

    def pose_desde_tag(self, medicion: dict, estacion: Optional[int] = None) -> PoseDock:
        pr = desde_medicion(self._marcos, medicion, estacion, self._docks)
        est = int(estacion if estacion is not None else medicion['id'])
        return PoseDock(est, pr.dock.x, pr.dock.y, pr.dock.th, pr.mapa, 'tag', pr.cerca)

    def aplicar_reset(self, pose: PoseDock, odom_ini: Pose2D, odom_fin: Optional[Pose2D] = None) -> ResultadoReset:
        if pose.fuente != 'tag':
            raise ValueError('el reset solo puede hacerse con una pose medida con el tag')
        accion = self.reset.actualizar if self.reset.inicializado else self.reset.inicializar
        res = accion(pose.mapa, odom_ini, odom_fin, cerca=pose.cerca)
        if res.aceptado:
            self._odom_ref = odom_ini if odom_fin is None else odom_fin
        return res

    def pose_desde_odom(self, estacion: int, odom: Pose2D) -> PoseDock:
        if estacion not in self._docks:
            raise ValueError('estación debe ser 1 a 4')
        mapa = self.reset.pose_mapa(odom)
        dx, dy, deg = mapa_a_dock(self._docks[estacion], mapa)
        cerca = math.hypot(dx, dy) <= self._marcos.cerca_m and abs(deg) <= self._marcos.cerca_deg
        ref = self._odom_ref
        recorrido = math.hypot(odom.x - ref.x, odom.y - ref.y) if ref is not None else 0.0
        return PoseDock(estacion, dx, dy, math.radians(deg), mapa, 'odom', cerca, recorrido)
