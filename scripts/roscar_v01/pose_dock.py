#!/usr/bin/env python3
"""Convierte la pose del tag (salida de medir_tag.py) en pose del robot en el dock y en el mapa, u obtiene el montaje.

    python3 scripts/camara/medir_tag.py una --camara-yaml cam.yaml --tag-id 2 | \\
        python3 scripts/roscar_v01/pose_dock.py convertir --marcos carrito/config/marcos.yaml

    python3 scripts/camara/medir_tag.py una --camara-yaml cam.yaml --tag-id 2 | \\
        python3 scripts/roscar_v01/pose_dock.py montaje --tag-en-dock 0.38,0,0 --robot-en-dock 0,0,0

Códigos de salida: 0 bien; 1 error o datos no válidos; 2 la pose está fuera del dock (convertir). Solo calcula.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from carrito.granprix_carrito import transformacion_camara_dock as mc  # noqa: E402
from comun.yaml_estricto import ErrorYaml  # noqa: E402
from geometria_dock.transformaciones import desde_grados  # noqa: E402


def _terna(texto):
    try:
        a, b, c = (float(v) for v in texto.split(','))
    except ValueError:
        raise argparse.ArgumentTypeError(f'se esperaban tres números separados por comas: {texto!r}')
    return a, b, c


def construir_parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='comando', required=True)

    def medicion(q):
        q.add_argument('--json', help='salida de medir_tag.py (si no se da y no hay --x-m, se lee de la entrada estándar)')
        for k in ('x-m', 'y-m', 'z-m', 'dth-deg'):
            q.add_argument(f'--{k}', type=float)
        q.add_argument('--estacion', type=int, help='1 a 4; por defecto el id del tag')

    c = sub.add_parser('convertir')
    medicion(c)
    c.add_argument('--marcos', default='carrito/config/marcos.yaml')
    m = sub.add_parser('montaje')
    medicion(m)
    m.add_argument('--tag-en-dock', type=_terna, required=True, help='x_m,y_m,yaw_deg del tag medido con regla')
    m.add_argument('--robot-en-dock', type=_terna, default=(0.0, 0.0, 0.0), help='dx_m,dy_m,dth_deg del robot sobre su marca')
    m.add_argument('--inclinacion-deg', type=float, default=0.0)
    return p


def _leer(a):
    if a.x_m is not None:
        d = {'aceptada': True, 'id': a.estacion, 'x_m': a.x_m, 'y_m': a.y_m, 'z_m': a.z_m, 'dth_deg': a.dth_deg}
    else:
        try:
            d = json.loads(a.json if a.json else sys.stdin.read())
        except ValueError as e:
            raise ValueError(f'la medición no es un JSON válido: {e}')
        if a.estacion is not None:
            d['id'] = a.estacion
    if not d.get('aceptada', d.get('valido', False)):
        raise ValueError(f"la medición no fue aceptada ({d.get('motivo')})")
    if any(d.get(k) is None for k in ('x_m', 'y_m', 'z_m', 'dth_deg')):
        raise ValueError('la medición no trae x_m, y_m, z_m y dth_deg')
    return d


def main(argv=None):
    a = construir_parser().parse_args(argv)
    try:
        d = _leer(a)
        if a.comando == 'convertir':
            r = mc.desde_medicion(mc.cargar_marcos(a.marcos), d, a.estacion)
            print(json.dumps({'estacion': d['id'], 'dock': {'dx_m': round(r.dock.x, 5), 'dy_m': round(r.dock.y, 5),
                                                             'dth_deg': round(math.degrees(r.dock.th), 3)},
                              'mapa': {'x_m': round(r.mapa.x, 5), 'y_m': round(r.mapa.y, 5),
                                       'th_deg': round(math.degrees(r.mapa.th), 3)}, 'cerca_del_dock': r.cerca}))
            return 0 if r.cerca else 2
        tag = desde_grados(*a.tag_en_dock)
        cam = mc.montaje_desde_referencia(desde_grados(*a.robot_en_dock), tag, d['x_m'], d['y_m'], d['z_m'], d['dth_deg'],
                                          math.radians(a.inclinacion_deg))
        print(f'camara_en_robot:\n  x_m: {cam.x:.3f}\n  y_m: {cam.y:.3f}\n  yaw_deg: {math.degrees(cam.th):.1f}\n'
              f'  inclinacion_deg: {a.inclinacion_deg:g}\ntag_en_dock:\n  x_m: {tag.x:.3f}\n  y_m: {tag.y:.3f}\n'
              f'  yaw_deg: {math.degrees(tag.th):.1f}')
        return 0
    except (ValueError, ErrorYaml, OSError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
