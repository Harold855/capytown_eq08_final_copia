"""Carga y validación de la configuración YAML del carrito (`carrito/config/`).

- `movimiento.yaml` -> `ConfigMovimiento` (velocidades del planificador y `Config` del ejecutor).
- `calibracion.yaml` -> `EstimadorEscalas` (ver `calibracion.py`).

Falla cerrado (ErrorYaml, que es un ValueError). Una configuración NO puede aflojar el reto: las
velocidades máximas no pueden superar 0.20 m/s ni 0.8 rad/s. Las claves desconocidas o duplicadas son
error. `cargar_carrito` además comprueba que el perfil de la calibración coincida con las velocidades.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

from comun import yaml_estricto as ye

from .calibracion import EstimadorEscalas
from .ejecutor import Config
from .planificador import V_MAX, W_MAX

VERSION = 1
DIRECTORIO_DEFECTO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')


@dataclass(frozen=True)
class ConfigMovimiento:
    v_ref: float
    w_ref: float
    v_max: float
    w_max: float
    ejecutor: Config


def cargar_movimiento(ruta: str) -> ConfigMovimiento:
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'movimiento', ('version', 'velocidades', 'ejecutor'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('movimiento: versión desconocida')

    vel = ye.seccion(d, 'velocidades', 'movimiento')
    ye.exigir_claves(vel, 'movimiento.velocidades', ('v_ref', 'w_ref', 'v_max', 'w_max'))
    v_max = ye.numero(vel, 'v_max', 'movimiento.velocidades', 0, V_MAX, exclusivo_min=True)
    w_max = ye.numero(vel, 'w_max', 'movimiento.velocidades', 0, W_MAX, exclusivo_min=True)
    v_ref = ye.numero(vel, 'v_ref', 'movimiento.velocidades', 0, v_max, exclusivo_min=True)
    w_ref = ye.numero(vel, 'w_ref', 'movimiento.velocidades', 0, w_max, exclusivo_min=True)

    ej = ye.seccion(d, 'ejecutor', 'movimiento')
    claves = ('periodo_s', 'pausa_s', 'asentamiento_s', 'max_hueco_s', 't_max_tramo_s', 'a_lin_max', 'a_ang_max',
              'ajustar_ultimo_paso', 'ceros_al_abortar')
    ye.exigir_claves(ej, 'movimiento.ejecutor', claves)
    donde = 'movimiento.ejecutor'
    periodo = ye.numero(ej, 'periodo_s', donde, 0, 0.2, exclusivo_min=True)
    max_hueco = ye.numero(ej, 'max_hueco_s', donde, 0, 1.0, exclusivo_min=True)
    if max_hueco < 2 * periodo:
        raise ye.ErrorYaml(f'{donde}.max_hueco_s: debe ser al menos el doble de periodo_s '
                           f'({2 * periodo:g}), o el ejecutor abortaría por un retraso normal')
    config = Config(
        periodo_s=periodo,
        pausa_s=ye.numero(ej, 'pausa_s', donde, 0, 5.0),
        asentamiento_s=ye.numero(ej, 'asentamiento_s', donde, 0, 5.0),
        max_hueco_s=max_hueco,
        t_max_tramo_s=ye.numero(ej, 't_max_tramo_s', donde, 0, 120.0, exclusivo_min=True),
        a_lin_max=ye.numero(ej, 'a_lin_max', donde, 0, exclusivo_min=True, permitir_none=True),
        a_ang_max=ye.numero(ej, 'a_ang_max', donde, 0, exclusivo_min=True, permitir_none=True),
        ajustar_ultimo_paso=ye.booleano(ej, 'ajustar_ultimo_paso', donde),
        ceros_al_abortar=ye.entero(ej, 'ceros_al_abortar', donde, 1, 50),
        v_max=v_max,
        w_max=w_max,
    )
    return ConfigMovimiento(v_ref, w_ref, v_max, w_max, config)


def cargar_carrito(directorio: str = DIRECTORIO_DEFECTO, robot_esperado: str = None  # type: ignore[assignment]
                   ) -> Tuple[ConfigMovimiento, EstimadorEscalas]:
    """Carga `movimiento.yaml` y `calibracion.yaml` de un directorio y comprueba que sean coherentes."""
    mov = cargar_movimiento(os.path.join(directorio, 'movimiento.yaml'))
    est = EstimadorEscalas.cargar(os.path.join(directorio, 'calibracion.yaml'), robot_esperado)
    v_ref, w_ref = est.perfil
    if v_ref is not None and abs(v_ref - mov.v_ref) > 1e-9:
        raise ye.ErrorYaml(f'calibracion.perfil.v_ref ({v_ref:g}) no coincide con movimiento.velocidades.v_ref '
                           f'({mov.v_ref:g}): las escalas no valdrían para la velocidad que se va a usar')
    if w_ref is not None and abs(w_ref - mov.w_ref) > 1e-9:
        raise ye.ErrorYaml(f'calibracion.perfil.w_ref ({w_ref:g}) no coincide con movimiento.velocidades.w_ref '
                           f'({mov.w_ref:g}): las escalas no valdrían para la velocidad que se va a usar')
    return mov, est
