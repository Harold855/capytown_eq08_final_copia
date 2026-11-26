from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional

from comun import yaml_estricto as ye
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir

from .docks import DOCKS_HTML, Dock

VERSION = 1


@dataclass(frozen=True)
class Montaje:
    pose: Pose2D
    inclinacion: float = 0.0


@dataclass(frozen=True)
class Marcos:
    montaje: Montaje
    tag_en_dock: Pose2D
    por_dock: Dict[int, Pose2D] = field(default_factory=dict)
    cerca_m: float = 0.30
    cerca_deg: float = 45.0

    def tag(self, estacion: int) -> Pose2D:
        return self.por_dock.get(estacion, self.tag_en_dock)


@dataclass(frozen=True)
class PoseRobot:
    dock: Pose2D
    mapa: Pose2D
    cerca: bool


def tag_en_camara(x_m: float, y_m: float, z_m: float, dth_deg: float, inclinacion: float = 0.0) -> Pose2D:
    adelante = z_m * math.cos(inclinacion) - y_m * math.sin(inclinacion)
    return Pose2D(adelante, -x_m, -math.radians(dth_deg))


def pose_en_dock(marcos: Marcos, estacion: int, x_m: float, y_m: float, z_m: float, dth_deg: float) -> Pose2D:
    tag_robot = componer(marcos.montaje.pose, tag_en_camara(x_m, y_m, z_m, dth_deg, marcos.montaje.inclinacion))
    return componer(marcos.tag(estacion), invertir(tag_robot))


def pose_robot(marcos: Marcos, estacion: int, x_m: float, y_m: float, z_m: float, dth_deg: float,
               docks: Dict[int, Dock] = DOCKS_HTML) -> PoseRobot:
    if estacion not in docks:
        raise ValueError('estación debe ser 1 a 4')
    en_dock = pose_en_dock(marcos, estacion, x_m, y_m, z_m, dth_deg)
    cerca = math.hypot(en_dock.x, en_dock.y) <= marcos.cerca_m and abs(math.degrees(en_dock.th)) <= marcos.cerca_deg
    return PoseRobot(en_dock, componer(docks[estacion].pose, en_dock), cerca)


def desde_medicion(marcos: Marcos, medicion: dict, estacion: Optional[int] = None,
                   docks: Dict[int, Dock] = DOCKS_HTML) -> PoseRobot:
    if not medicion.get('aceptada', medicion.get('valido', False)):
        raise ValueError('la medición no fue aceptada')
    campos = [medicion.get(k) for k in ('x_m', 'y_m', 'z_m', 'dth_deg')]
    if any(c is None for c in campos):
        raise ValueError('la medición no trae la pose')
    est = estacion if estacion is not None else medicion.get('id')
    if est is None:
        raise ValueError('falta la estación (o el id del tag)')
    return pose_robot(marcos, int(est), *campos, docks=docks)


def montaje_desde_referencia(robot_en_dock: Pose2D, tag_en_dock: Pose2D, x_m: float, y_m: float, z_m: float,
                             dth_deg: float, inclinacion: float = 0.0) -> Pose2D:
    tag_robot = componer(invertir(robot_en_dock), tag_en_dock)
    return componer(tag_robot, invertir(tag_en_camara(x_m, y_m, z_m, dth_deg, inclinacion)))


def _pose(d: dict, donde: str, rx: float, ry: float, ryaw: float) -> Pose2D:
    ye.exigir_claves(d, donde, ('x_m', 'y_m', 'yaw_deg'))
    faltan = [k for k in ('x_m', 'y_m', 'yaw_deg') if d[k] is None]
    if faltan:
        raise ye.ErrorYaml(f'{donde}: falta medir {", ".join(faltan)}')
    return desde_grados(ye.numero(d, 'x_m', donde, -rx, rx), ye.numero(d, 'y_m', donde, -ry, ry),
                        ye.numero(d, 'yaw_deg', donde, -ryaw, ryaw))


def cargar_marcos(ruta: str) -> Marcos:
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'marcos', ('version', 'camara_en_robot', 'tag_en_dock', 'por_dock', 'cerca_del_dock'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('marcos: versión desconocida')
    cam = ye.seccion(d, 'camara_en_robot', 'marcos')
    ye.exigir_claves(cam, 'marcos.camara_en_robot', ('x_m', 'y_m', 'yaw_deg', 'inclinacion_deg'))
    incl = ye.numero(cam, 'inclinacion_deg', 'marcos.camara_en_robot', -30, 60)
    pose_cam = _pose({k: cam[k] for k in ('x_m', 'y_m', 'yaw_deg')}, 'marcos.camara_en_robot', 0.25, 0.25, 45)
    tag = _pose(ye.seccion(d, 'tag_en_dock', 'marcos'), 'marcos.tag_en_dock', 1.0, 0.5, 45)
    por_dock = {}
    for k, v in (d['por_dock'] or {}).items():
        if k not in ('E1', 'E2', 'E3', 'E4'):
            raise ye.ErrorYaml(f'marcos.por_dock: la clave {k!r} debe ser E1, E2, E3 o E4')
        por_dock[int(k[1])] = _pose(v if isinstance(v, dict) else {}, f'marcos.por_dock.{k}', 1.0, 0.5, 45)
    cerca = ye.seccion(d, 'cerca_del_dock', 'marcos')
    ye.exigir_claves(cerca, 'marcos.cerca_del_dock', ('max_m', 'max_deg'))
    return Marcos(Montaje(pose_cam, math.radians(incl)), tag, por_dock,
                  ye.numero(cerca, 'max_m', 'marcos.cerca_del_dock', 0, 1.0, exclusivo_min=True),
                  ye.numero(cerca, 'max_deg', 'marcos.cerca_del_dock', 0, 90, exclusivo_min=True))
