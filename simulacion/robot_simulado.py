"""Robot simulado para probar el acople y la calibración sin hardware.

Pose verdadera en el mapa; escalas reales `cd` y `ca` que el controlador no conoce; ruido multiplicativo en
cada movimiento y ruido aditivo en la medición del tag. Implementa las interfaces `Mover` y `Medir` de
`carrito/granprix_carrito/acople.py`. Es un modelo ideal: sin retardos, deslizamiento ni zona muerta.
"""
from __future__ import annotations

import math
import random
from typing import Optional, Tuple

from carrito.granprix_carrito.docks import DOCKS_HTML, dock_a_mapa, mapa_a_dock
from carrito.granprix_carrito.ejecutor import Estado, Resultado
from carrito.granprix_carrito.planificador import Comando
from carrito.granprix_carrito.pose_dock import PoseDock
from geometria_dock.transformaciones import Pose2D, wrap

PAUSA_Y_ASENTAMIENTO_S = 0.8   # igual que movimiento.yaml: 0.3 + 0.5


class RobotSimulado:
    def __init__(self, pose: Pose2D, estacion: int = 1, cd: float = 1.0, ca: float = 1.0, ruido_d: float = 0.0,
                 ruido_a: float = 0.0, ruido_tag_m: float = 0.0, ruido_tag_deg: float = 0.0, p_sin_tag: float = 0.0,
                 semilla: int = 0) -> None:
        self.pose, self.estacion, self.cd, self.ca = pose, estacion, cd, ca
        self._r = (ruido_d, ruido_a, ruido_tag_m, ruido_tag_deg, p_sin_tag)
        self._rng = random.Random(semilla)
        self.t = 0.0
        self.movimientos = 0

    def reloj(self) -> float:
        return self.t

    def mover(self, cmd: Comando) -> Tuple[Comando, Resultado]:
        rd, ra = self._r[0], self._r[1]
        th = wrap(self.pose.th + cmd.phi_cmd * self.ca * (1 + self._rng.gauss(0, ra)))
        d = cmd.L_cmd * self.cd * (1 + self._rng.gauss(0, rd))
        self.pose = Pose2D(self.pose.x + d * math.cos(th), self.pose.y + d * math.sin(th), th)
        self.t += cmd.t_total + PAUSA_Y_ASENTAMIENTO_S
        self.movimientos += 1
        return cmd, Resultado(Estado.COMPLETO, None, cmd.L_cmd, cmd.phi_cmd, cmd.t_total)

    def medir(self) -> Optional[PoseDock]:
        _, _, sm, sg, p = self._r
        if p and self._rng.random() < p:
            return None
        dock = DOCKS_HTML[self.estacion]
        dx, dy, deg = mapa_a_dock(dock, self.pose)
        dx, dy, deg = dx + self._rng.gauss(0, sm), dy + self._rng.gauss(0, sm), deg + self._rng.gauss(0, sg)
        mapa = dock_a_mapa(dock, dx, dy, deg)
        cerca = math.hypot(dx, dy) <= 0.30 and abs(deg) <= 45.0
        return PoseDock(self.estacion, dx, dy, math.radians(deg), mapa, 'tag', cerca)

    def colocar_en_dock(self, dx: float, dy: float, dth_deg: float, estacion: Optional[int] = None) -> None:
        if estacion is not None:
            self.estacion = estacion
        self.pose = dock_a_mapa(DOCKS_HTML[self.estacion], dx, dy, dth_deg)


class PlantaSimulada(RobotSimulado):
    """El mismo robot, pero con la velocidad que se le publica (`publicar`) integrada en el tiempo (`avanzar`).
    El ruido multiplicativo se sortea una vez por cada arranque de avance o de giro."""

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self._v = self._w = 0.0
        self._fd = self._fa = 1.0

    def publicar(self, v: float, w: float) -> None:
        if v and not self._v:
            self._fd = 1 + self._rng.gauss(0, self._r[0])
        if w and not self._w:
            self._fa = 1 + self._rng.gauss(0, self._r[1])
        self._v, self._w = v, w

    def avanzar(self, dt: float) -> None:
        th = wrap(self.pose.th + self._w * self.ca * self._fa * dt)
        d = self._v * self.cd * self._fd * dt
        self.pose = Pose2D(self.pose.x + d * math.cos(th), self.pose.y + d * math.sin(th), th)
        self.t += dt
