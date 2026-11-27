"""Poses de trabajo de cada rol, enseñadas en el laboratorio. Falla cerrado si algo falta.

Las poses son de la forma [x, y, z, rx, ry, rz] en mm y grados (convención de pymycobot). Se
ENSEÑAN con el carrito en su pose nominal; la estrategia solo suma la compensación de la cuna.
No hay valores por defecto: sin configuración, la estrategia devuelve NO_CONFIGURADO.
Este módulo no inventa coordenadas: la plantilla `estacion/config/poses.plantilla.yaml` trae `null`.
Se lee .yaml (con PyYAML, claves duplicadas rechazadas) o .json (solo biblioteca estándar).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .roles import PIEZAS_POR_BANDEJA, ROLES

Pose6T = Tuple[float, float, float, float, float, float]
CAMPOS_UNICOS = ('cuna_aprox', 'cuna_agarre', 'cuna_dejar', 'pose_libre')
CAMPOS_BANDEJA = ('almacen_aprox', 'almacen_agarre', 'recepcion_aprox', 'recepcion_dejar')


class ErrorConfiguracion(Exception):
    pass


@dataclass(frozen=True)
class PosesRol:
    rol: int
    cuna_aprox: Optional[Pose6T] = None
    cuna_agarre: Optional[Pose6T] = None
    cuna_dejar: Optional[Pose6T] = None
    pose_libre: Optional[Pose6T] = None
    almacen_aprox: Optional[Tuple[Pose6T, ...]] = None
    almacen_agarre: Optional[Tuple[Pose6T, ...]] = None
    recepcion_aprox: Optional[Tuple[Pose6T, ...]] = None
    recepcion_dejar: Optional[Tuple[Pose6T, ...]] = None


def requeridas(rol: int) -> List[str]:
    """Campos que necesita un rol. `pose_libre` y `cuna_aprox` los usan todos."""
    r = ROLES[rol]
    campos = ['cuna_aprox', 'pose_libre']
    if r.retira:
        campos += ['cuna_agarre', 'recepcion_aprox', 'recepcion_dejar']
    if r.coloca:
        campos += ['cuna_dejar', 'almacen_aprox', 'almacen_agarre']
    return campos


def _pose(valor: object, nombre: str) -> Pose6T:
    if not isinstance(valor, (list, tuple)) or len(valor) != 6:
        raise ErrorConfiguracion(f'{nombre}: se esperaban 6 valores [x, y, z, rx, ry, rz]')
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in valor):
        raise ErrorConfiguracion(f'{nombre}: valores no numéricos o no finitos')
    x, y, z = valor[0], valor[1], valor[2]
    if max(abs(x), abs(y), abs(z)) < 2.0:
        raise ErrorConfiguracion(f'{nombre}: x, y, z parecen estar en METROS; la API usa milímetros')
    if max(abs(x), abs(y), abs(z)) > 600.0:
        raise ErrorConfiguracion(f'{nombre}: |x|, |y| o |z| > 600 mm, fuera del alcance del JetCobot')
    return tuple(float(v) for v in valor)  # type: ignore[return-value]


def desde_dict(datos: Dict[str, object]) -> PosesRol:
    rol = datos.get('rol')
    if rol not in ROLES:
        raise ErrorConfiguracion(f'rol debe ser uno de {sorted(ROLES)}')
    poses = datos.get('poses')
    if not isinstance(poses, dict):
        raise ErrorConfiguracion("falta el objeto 'poses'")
    faltan = [c for c in requeridas(rol) if poses.get(c) is None]
    if faltan:
        raise ErrorConfiguracion(f'rol {rol}: faltan poses por enseñar: {", ".join(faltan)}')
    campos: Dict[str, object] = {'rol': rol}
    for c in CAMPOS_UNICOS:
        if poses.get(c) is not None:
            campos[c] = _pose(poses[c], c)
    for c in CAMPOS_BANDEJA:
        if poses.get(c) is not None:
            lista = poses[c]
            if not isinstance(lista, (list, tuple)) or len(lista) != PIEZAS_POR_BANDEJA:
                raise ErrorConfiguracion(f'{c}: se esperaban {PIEZAS_POR_BANDEJA} poses (una por pieza)')
            campos[c] = tuple(_pose(p, f'{c}[{i}]') for i, p in enumerate(lista))
    return PosesRol(**campos)  # type: ignore[arg-type]


def cargar(ruta: str) -> PosesRol:
    """.json con la biblioteca estándar; .yaml/.yml con el cargador estricto (necesita PyYAML)."""
    if ruta.lower().endswith('.json'):
        try:
            with open(ruta, encoding='utf-8') as f:
                return desde_dict(json.load(f))
        except (OSError, ValueError) as e:
            raise ErrorConfiguracion(f'no se pudo leer {ruta}: {e}') from e
    from comun import yaml_estricto as ye
    try:
        datos = ye.cargar_mapeo(ruta)
    except ye.ErrorYaml as e:
        raise ErrorConfiguracion(str(e)) from e
    return desde_dict(datos)
