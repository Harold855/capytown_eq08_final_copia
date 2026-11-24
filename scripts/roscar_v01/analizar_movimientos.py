#!/usr/bin/env python3
"""Resume mediciones_fisicas.csv: escalas físico/comandado, físico/odometría y dispersión.

Sirve para el día de caracterización y para fijar parámetros de la predicción firmada. NO aplica
nada al robot: solo imprime una estimación inicial de cd y ca (válida si las corridas se hicieron
con cd = ca = 1 y sin otro corrector que cambie lo comandado). Solo usa filas con estado COMPLETO.
"""
import argparse
import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def resumen(valores):
    if not valores:
        return None
    media = statistics.fmean(valores)
    desv = statistics.stdev(valores) if len(valores) > 1 else None
    return {'n': len(valores), 'media': media, 'desv': desv, 'min': min(valores), 'max': max(valores)}


def analizar(filas, incluir_todo=False):
    """Agrupa por (modo, superficie, velocidad) y calcula las razones. Devuelve un dict."""
    grupos = defaultdict(lambda: defaultdict(list))
    for r in filas:
        if not incluir_todo and r.get('estado', '').strip() != 'COMPLETO':
            continue
        modo, sup = r['modo'], r.get('superficie', '')
        if modo == 'recta':
            cmd, fis, odom, vel = _f(r['distancia_comandada_m']), _f(r['distancia_fisica_m']), _f(r['distancia_odom_m']), r['velocidad_m_s']
            des = _f(r['desvio_lateral_cm'])
            clave = (modo, sup, vel)
            if cmd and fis is not None:
                grupos[clave]['fisico/comandado'].append(fis / cmd)
            if odom and fis is not None:
                grupos[clave]['fisico/odom'].append(fis / odom)
            if des is not None and fis:
                grupos[clave]['desvio_cm_por_m'].append(des / fis)
        elif modo == 'giro':
            cmd, fis, odom, vel = _f(r['giro_comandado_deg']), _f(r['giro_fisico_deg']), _f(r['giro_odom_deg']), r['velocidad_rad_s']
            clave = (modo, sup, vel)
            if cmd and fis is not None:
                grupos[clave]['fisico/comandado'].append(fis / cmd)
            if odom and fis is not None:
                grupos[clave]['fisico/odom'].append(fis / odom)
    return {k: {m: resumen(v) for m, v in d.items()} for k, d in grupos.items()}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, default=Path('experimentos/dia01_roscar/mediciones_fisicas.csv'))
    p.add_argument('--incluir-todo', action='store_true', help='incluye corridas no COMPLETO')
    a = p.parse_args(argv)
    with a.csv.open(newline='') as f:
        filas = list(csv.DictReader(f))
    res = analizar(filas, a.incluir_todo)
    if not res:
        print('Sin filas COMPLETO con datos físicos. Completar mediciones_fisicas.csv (registrar_medicion.py).')
        return 0
    for (modo, sup, vel), metricas in sorted(res.items()):
        print(f'\n== {modo} | superficie={sup} | velocidad={vel}')
        for nombre, m in metricas.items():
            d = f"{m['desv']:.4f}" if m['desv'] is not None else 'n/a (n=1)'
            print(f"  {nombre:18s} n={m['n']:2d}  media={m['media']:.4f}  desv={d}  min={m['min']:.4f}  max={m['max']:.4f}")
        if 'fisico/comandado' in metricas:
            e = 'cd' if modo == 'recta' else 'ca'
            print(f"  -> estimación inicial de {e} = {metricas['fisico/comandado']['media']:.4f} (NO aplicar sin revisar; ver README)")
    print('\nUna dispersión alta con n pequeño no permite fijar una escala: repetir la corrida antes de confiar en la media.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
