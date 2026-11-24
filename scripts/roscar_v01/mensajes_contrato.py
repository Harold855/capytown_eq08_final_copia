"""Constructores de mensajes del carrito según el contrato del docente (vendor/granprix/pc-race/contrato).

Provisional: se moverá al paquete `carrito/` cuando exista la plantilla del curso. Unidades internas
SI (m, rad); el contrato usa `dth` en GRADOS. Los campos extra de la telemetría (escalas, vuelta,
estado, pieza) los pide el HTML; Race Control los ignora hoy (`extra="ignore"`).
"""
import json
import math
import time

VERSION = 1
SUBTIPOS = ('fisica', 'web', 'teleoperacion', 'software')
TIPOS_PIT = ('pit_ok', 'reintento')


def _base(ts):
    return {'v': VERSION, 'ts': time.time() if ts is None else float(ts)}


def _equipo(n):
    if not isinstance(n, int) or not 1 <= n <= 99:
        raise ValueError('equipo debe ser un entero de 1 a 99')
    return n


def topico_equipo(equipo, canal):
    if canal not in ('telemetria', 'evento', 'vuelta'):
        raise ValueError('canal desconocido')
    return f'granprix/eq{_equipo(equipo):02d}/{canal}'


def topico_solicitud(estacion):
    if estacion not in (1, 2, 3, 4):
        raise ValueError('estación debe ser 1 a 4')
    return f'granprix/estacion/{estacion}/solicitud'


def solicitud(equipo, dock, dx_m, dy_m, dth_rad, pieza_trae=None, ts=None):
    if dock not in (1, 2, 3, 4):
        raise ValueError('dock debe ser 1 a 4')
    if not all(math.isfinite(v) for v in (dx_m, dy_m, dth_rad)):
        raise ValueError('pose no finita')
    return {**_base(ts), 'equipo': _equipo(equipo), 'dock': dock,
            'pose': {'dx': dx_m, 'dy': dy_m, 'dth': math.degrees(dth_rad)}, 'pieza_trae': pieza_trae}


def telemetria(equipo, x_m, y_m, theta_rad, v=None, w=None, bateria=None, ts=None, **extra):
    msg = {**_base(ts), 'equipo': _equipo(equipo), 'pose': {'x': x_m, 'y': y_m, 'theta': theta_rad},
           'bateria': bateria, 'velocidad': v}
    if w is not None:
        msg['omega'] = w
    msg.update(extra)
    return {k: val for k, val in msg.items() if val is not None}


def evento_intervencion(equipo, subtipo, declarada=True, ts=None):
    if subtipo not in SUBTIPOS:
        raise ValueError(f'subtipo debe ser uno de {SUBTIPOS}')
    return {**_base(ts), 'equipo': _equipo(equipo), 'tipo': 'intervencion', 'subtipo': subtipo,
            'declarada': bool(declarada)}


def evento_pit(equipo, tipo, estacion, ts=None):
    if tipo not in TIPOS_PIT:
        raise ValueError(f'tipo debe ser uno de {TIPOS_PIT}')
    return {**_base(ts), 'equipo': _equipo(equipo), 'tipo': tipo, 'estacion': estacion}


def vuelta(equipo, numero, t_inicio, t_fin, estaciones=None, ts=None):
    if t_fin <= t_inicio:
        raise ValueError('t_fin debe ser posterior a t_inicio')
    msg = {**_base(ts), 'equipo': _equipo(equipo), 'numero': numero, 't_inicio': t_inicio, 't_fin': t_fin}
    if estaciones is not None:
        msg['estaciones'] = list(estaciones)
    return msg


def a_json(msg):
    return json.dumps(msg, separators=(',', ':'))
