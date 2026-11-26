"""Carga y validación de `estacion/config/estacion.yaml`. Compatible con Python 3.8.

Falla cerrado (ErrorConfiguracion). Una configuración no puede aflojar el reto: la tolerancia de acople
no puede superar 4 cm ni 6 grados y el tope del cambio no puede pasar de 10 s (el pit completo del reto).
Las geometrías son SUPUESTOS hasta medir el montaje (ver el YAML). Necesita PyYAML en la Jetson: sin
verificar; si falta, el error lo dice (las poses siguen pudiendo leerse desde .json sin PyYAML).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from comun import yaml_estricto as ye
from geometria_dock.transformaciones import Pose2D, desde_grados

from .compensacion_pose import GeometriaEstacion
from .posiciones import ErrorConfiguracion

VERSION = 1
TOL_POS_MAX_M, TOL_ANG_MAX_DEG, TIEMPO_MAX_RETO_S = 0.04, 6.0, 10.0


@dataclass(frozen=True)
class ConfigEstacion:
    tol_pos_m: float
    tol_ang_deg: float
    tiempo_max_s: float
    geometria: GeometriaEstacion

    def argumentos_estrategia(self) -> Dict[str, Any]:
        """Argumentos con nombre para `EstrategiaCambio(rol, brazo, poses, **cfg.argumentos_estrategia())`."""
        return {'geo': self.geometria, 'tol_pos_m': self.tol_pos_m, 'tol_ang_deg': self.tol_ang_deg,
                'tiempo_max_s': self.tiempo_max_s}


def _pose2d(d: Dict[str, Any], clave: str) -> Pose2D:
    donde = f'geometria.{clave}'
    s = ye.seccion(d, clave, 'geometria')
    ye.exigir_claves(s, donde, ('x_m', 'y_m', 'th_deg'))
    return desde_grados(ye.numero(s, 'x_m', donde, -1.0, 1.0), ye.numero(s, 'y_m', donde, -1.0, 1.0),
                        ye.numero(s, 'th_deg', donde, -360.0, 360.0))


def cargar_estacion(ruta: str) -> ConfigEstacion:
    try:
        d = ye.cargar_mapeo(ruta)
        ye.exigir_claves(d, 'estacion', ('version', 'estrategia', 'geometria'))
        if d['version'] != VERSION or isinstance(d['version'], bool):
            raise ye.ErrorYaml('estacion: versión desconocida')
        est = ye.seccion(d, 'estrategia', 'estacion')
        ye.exigir_claves(est, 'estrategia', ('tol_pos_m', 'tol_ang_deg', 'tiempo_max_s'))
        tol_pos = ye.numero(est, 'tol_pos_m', 'estrategia', 0, TOL_POS_MAX_M, exclusivo_min=True)
        tol_ang = ye.numero(est, 'tol_ang_deg', 'estrategia', 0, TOL_ANG_MAX_DEG, exclusivo_min=True)
        tmax = ye.numero(est, 'tiempo_max_s', 'estrategia', 0, TIEMPO_MAX_RETO_S, exclusivo_min=True)

        geo = ye.seccion(d, 'geometria', 'estacion')
        ye.exigir_claves(geo, 'geometria', ('cuna_en_robot', 'brazo_en_dock', 'alcance_min_m', 'alcance_max_m'))
        a_min = ye.numero(geo, 'alcance_min_m', 'geometria', 0, 0.5, exclusivo_min=True)
        a_max = ye.numero(geo, 'alcance_max_m', 'geometria', 0, 0.5, exclusivo_min=True)
        if a_max <= a_min:
            raise ye.ErrorYaml('geometria: alcance_max_m debe ser mayor que alcance_min_m')
        g = GeometriaEstacion(cuna_en_robot=_pose2d(geo, 'cuna_en_robot'), brazo_en_dock=_pose2d(geo, 'brazo_en_dock'),
                              alcance_min_m=a_min, alcance_max_m=a_max)
        return ConfigEstacion(tol_pos, tol_ang, tmax, g)
    except ye.ErrorYaml as e:
        raise ErrorConfiguracion(str(e)) from e
