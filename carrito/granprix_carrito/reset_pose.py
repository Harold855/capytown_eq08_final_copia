from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from geometria_dock.transformaciones import Pose2D, componer, invertir


@dataclass(frozen=True)
class ResultadoReset:
    aceptado: bool
    motivo: Optional[str]
    salto_m: Optional[float] = None
    salto_deg: Optional[float] = None


class ResetPose:
    def __init__(self, salto_max_m: float = 0.15, salto_max_deg: float = 20.0, quieto_max_m: float = 0.005,
                 quieto_max_deg: float = 0.5) -> None:
        for v in (salto_max_m, salto_max_deg, quieto_max_m, quieto_max_deg):
            if not math.isfinite(v) or v <= 0:
                raise ValueError('los umbrales deben ser positivos y finitos')
        self._salto = (salto_max_m, salto_max_deg)
        self._quieto = (quieto_max_m, quieto_max_deg)
        self._map_odom: Optional[Pose2D] = None
        self.n_resets = 0

    @property
    def inicializado(self) -> bool:
        return self._map_odom is not None

    @property
    def map_odom(self) -> Pose2D:
        if self._map_odom is None:
            raise RuntimeError('sin referencia: falta inicializar con una pose medida')
        return self._map_odom

    def pose_mapa(self, odom: Pose2D) -> Pose2D:
        return componer(self.map_odom, odom)

    def inicializar(self, medida: Pose2D, odom_ini: Pose2D, odom_fin: Optional[Pose2D] = None, *,
                    cerca: bool) -> ResultadoReset:
        return self._reset(medida, odom_ini, odom_fin, cerca, False)

    def actualizar(self, medida: Pose2D, odom_ini: Pose2D, odom_fin: Optional[Pose2D] = None, *,
                   cerca: bool) -> ResultadoReset:
        if self._map_odom is None:
            return ResultadoReset(False, 'SIN_REFERENCIA')
        return self._reset(medida, odom_ini, odom_fin, cerca, True)

    def _reset(self, medida: Pose2D, odom_ini: Pose2D, odom_fin: Optional[Pose2D], cerca: bool,
               comprobar_salto: bool) -> ResultadoReset:
        if not cerca:
            return ResultadoReset(False, 'FUERA_DE_DOCK')
        odom = odom_ini if odom_fin is None else odom_fin
        if odom_fin is not None:
            mov = componer(invertir(odom_ini), odom_fin)
            if math.hypot(mov.x, mov.y) > self._quieto[0] or abs(math.degrees(mov.th)) > self._quieto[1]:
                return ResultadoReset(False, 'ROBOT_NO_QUIETO')
        salto_m = salto_deg = None
        if comprobar_salto:
            dif = componer(invertir(self.pose_mapa(odom)), medida)
            salto_m, salto_deg = math.hypot(dif.x, dif.y), abs(math.degrees(dif.th))
            if salto_m > self._salto[0] or salto_deg > self._salto[1]:
                return ResultadoReset(False, 'SALTO_EXCESIVO', salto_m, salto_deg)
        self._map_odom = componer(medida, invertir(odom))
        self.n_resets += 1
        return ResultadoReset(True, None, salto_m, salto_deg)
