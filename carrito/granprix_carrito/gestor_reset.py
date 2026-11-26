from __future__ import annotations

import bisect
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Tuple

from geometria_dock.transformaciones import Pose2D, wrap

from .pose_dock import LocalizadorDock, PoseDock
from .reset_pose import ResultadoReset


def _unitario(x: float, y: float, z: float, w: float) -> None:
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if not math.isfinite(n) or abs(n - 1.0) > 0.01:
        raise ValueError('cuaternión no unitario')


def yaw_de_cuaternion(x: float, y: float, z: float, w: float) -> float:
    _unitario(x, y, z, w)
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def dth_de_cuaternion(x: float, y: float, z: float, w: float) -> float:
    _unitario(x, y, z, w)
    return math.degrees(math.atan2(2 * (x * z + w * y), 1 - 2 * (x * x + y * y)))


def cuaternion_de_yaw(th: float) -> Tuple[float, float, float, float]:
    return 0.0, 0.0, math.sin(th / 2), math.cos(th / 2)


@dataclass(frozen=True)
class ResultadoAplicar:
    aceptado: bool
    motivo: Optional[str]
    reset: Optional[ResultadoReset] = None
    pose: Optional[PoseDock] = None


class GestorReset:
    def __init__(self, localizador: LocalizadorDock, retardo_odom_s: float = 0.0, ventana_quieto_s: float = 0.3,
                 edad_max_tag_s: float = 1.0, buffer_s: float = 10.0) -> None:
        for v in (ventana_quieto_s, edad_max_tag_s, buffer_s):
            if not math.isfinite(v) or v <= 0:
                raise ValueError('ventanas y edades deben ser positivas')
        if not math.isfinite(retardo_odom_s) or not 0 <= retardo_odom_s <= 3.0:
            raise ValueError('retardo_odom_s debe estar entre 0 y 3 s')
        self.localizador = localizador
        self._retardo, self._ventana, self._edad_max, self._buffer_s = retardo_odom_s, ventana_quieto_s, edad_max_tag_s, buffer_s
        self._odom: Deque[Tuple[float, Pose2D]] = deque()
        self._tag: Optional[Tuple[float, Dict[str, Any]]] = None
        self.odom_descartadas = 0
        self.ultimo: Optional[ResultadoAplicar] = None

    @property
    def map_odom(self) -> Optional[Pose2D]:
        r = self.localizador.reset
        return r.map_odom if r.inicializado else None

    def agregar_odom(self, t: float, pose: Pose2D) -> bool:
        if not math.isfinite(t) or (self._odom and t <= self._odom[-1][0]):
            self.odom_descartadas += 1
            return False
        self._odom.append((t, pose))
        while self._odom and self._odom[0][0] < t - self._buffer_s:
            self._odom.popleft()
        return True

    def agregar_tag(self, t: float, x_m: float, y_m: float, z_m: float, dth_deg: float) -> bool:
        if not all(math.isfinite(v) for v in (t, x_m, y_m, z_m, dth_deg)):
            return False
        self._tag = (t, {'aceptada': True, 'x_m': x_m, 'y_m': y_m, 'z_m': z_m, 'dth_deg': dth_deg})
        return True

    def odom_en(self, t: float) -> Optional[Pose2D]:
        if not self._odom or t < self._odom[0][0] or t > self._odom[-1][0]:
            return None
        tiempos = [p[0] for p in self._odom]
        i = bisect.bisect_left(tiempos, t)
        t1, p1 = self._odom[i]
        if t1 == t or i == 0:
            return p1
        t0, p0 = self._odom[i - 1]
        f = (t - t0) / (t1 - t0)
        return Pose2D(p0.x + f * (p1.x - p0.x), p0.y + f * (p1.y - p0.y), wrap(p0.th + f * wrap(p1.th - p0.th)))

    def aplicar(self, t_ahora: float, estacion: int) -> ResultadoAplicar:
        r = self._aplicar(t_ahora, estacion)
        self.ultimo = r
        return r

    def _aplicar(self, t_ahora: float, estacion: int) -> ResultadoAplicar:
        if estacion not in (1, 2, 3, 4):
            return ResultadoAplicar(False, 'ESTACION_INVALIDA')
        if self._tag is None:
            return ResultadoAplicar(False, 'SIN_TAG')
        t_tag, med = self._tag
        if t_tag > t_ahora + 0.1:
            return ResultadoAplicar(False, 'TAG_FUTURO')
        if t_ahora - t_tag > self._edad_max:
            return ResultadoAplicar(False, 'TAG_VIEJO')
        t_odom = t_tag + self._retardo
        if not self._odom or self._odom[-1][0] < t_odom:
            return ResultadoAplicar(False, 'ODOM_INSUFICIENTE')
        ini, fin = self.odom_en(t_odom - self._ventana), self.odom_en(t_odom)
        if ini is None or fin is None:
            return ResultadoAplicar(False, 'ODOM_NO_CUBRE')
        pose = self.localizador.pose_desde_tag({**med, 'id': estacion}, estacion)
        res = self.localizador.aplicar_reset(pose, ini, fin)
        return ResultadoAplicar(res.aceptado, res.motivo, res, pose)

    def estado(self, t_ahora: Optional[float] = None) -> Dict[str, Any]:
        r = self.localizador.reset
        mo = self.map_odom
        return {'inicializado': r.inicializado, 'n_resets': r.n_resets, 'odom_muestras': len(self._odom),
                'odom_descartadas': self.odom_descartadas,
                'edad_tag_s': None if self._tag is None or t_ahora is None else round(t_ahora - self._tag[0], 3),
                'ultimo_motivo': None if self.ultimo is None else self.ultimo.motivo,
                'map_odom': None if mo is None else {'x': mo.x, 'y': mo.y, 'yaw': mo.th}}
