"""Indicadores del ROSCar consolidados desde los eventos de la misión (`eventos.jsonl`).

    python3 -m carrito.granprix_carrito.tablero_extension.metricas carpeta [--salida datos.json] [--cada 0.5] [--intervenciones N]

Devuelve un dict serializable (lo que lee el panel). Todo dato que no existe es None: nunca se rellena con ceros. Los puntos
de la rúbrica son una ESTIMACIÓN del equipo con la rúbrica del HTML (sin `deploy.sh`, sin video ni informe): no son la nota.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Dict, List, Optional, Sequence

from .. import cronometro as cr
from ..calibracion import evaluar_reduccion
from ..calibracion_tramo import error_normalizado
from ..eventos_mision import Evento, leer_eventos
from ..mision import ConfigMision

VERSION = 1


def percentil(valores: Sequence[float], q: float = 0.95) -> Optional[float]:
    v = sorted(valores)
    return v[min(len(v) - 1, max(0, math.ceil(round(len(v) * q, 9)) - 1))] if v else None   # rango más cercano


def _media(v: Sequence[float]) -> Optional[float]:
    return sum(v) / len(v) if v else None


def _stats(v: Sequence[float], k: float = 1.0) -> dict:
    return {'media': None if not v else _media(v) * k, 'p95': None if not v else percentil(v) * k, 'n': len(v)}


def _num(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def convergio(valores: Sequence[float], ventana: int = 4, tol: float = 0.01) -> bool:
    """Mismo criterio que `EstimadorEscalas.convergencia`: las últimas `ventana` estimaciones difieren menos de `tol`."""
    u = list(valores)[-ventana:]
    return len(u) >= ventana and max(u) - min(u) < tol


def _pts_tanda(validas: int) -> int:
    return 4 if validas >= 4 else 3 if validas == 3 else 1 if validas == 2 else 0


def _pts_pieza(fraccion: float) -> int:
    return 3 if fraccion >= 0.9 else 2 if fraccion >= 0.75 else 1 if fraccion >= 0.5 else 0


def _pts_autonomia(n: Optional[int]) -> Optional[int]:
    return None if n is None else 3 if n == 0 else 2 if n <= 2 else 1 if n <= 5 else 0


def calcular(eventos: Sequence[Evento], cfg: ConfigMision = ConfigMision(), intervenciones: Optional[int] = None,
             ahora: Optional[float] = None) -> dict:
    ev = list(eventos)
    estados = [e for e in ev if e.tipo == 'estado']
    pits = [e.datos for e in ev if e.tipo == 'pit']
    ultimo = estados[-1] if estados else None
    t0 = next((e.ts for e in ev if e.tipo == 'inicio'), None)
    t_fin = ev[-1].ts if ev else None
    vueltas = cr.vueltas_desde_eventos(ev)
    validas = sum(v.valida for v in vueltas)
    fallas = [{'ts': e.ts, 'motivo': e.motivo, 'estacion': e.estacion} for e in ev if e.tipo == 'falla']

    t_pit = [p['t_pit_s'] for p in pits if _num(p.get('t_pit_s'))]
    pares = [(error_normalizado(p['err_pos_pre_m'], p['err_ang_pre_deg']), error_normalizado(p['err_pos_post_m'], p['err_ang_post_deg']))
             for p in pits if all(_num(p.get(k)) for k in ('err_pos_pre_m', 'err_ang_pre_deg', 'err_pos_post_m', 'err_ang_post_deg'))]
    red = evaluar_reduccion(pares, tolerancia=1.0) if pares else None
    red_sin = evaluar_reduccion(pares, tolerancia=1.0, excluir_dentro=True) if pares else None
    cd = [p['cd'] for p in pits if _num(p.get('cd'))]
    ca = [p['ca'] for p in pits if _num(p.get('ca'))]
    validos = sum(1 for p in pits if p.get('valido') is True)
    esperados = cfg.vueltas * len(cfg.piezas)
    ultima_valida = next((p for p in reversed(pits) if p.get('valido') is True), None)

    estaciones: Dict[int, dict] = {}
    for p in pits:
        estaciones[p['estacion']] = {'estacion': p['estacion'], 'vuelta': p.get('vuelta'), 't_pit_s': p.get('t_pit_s'),
                                     'err_pos_pre_cm': None if not _num(p.get('err_pos_pre_m')) else p['err_pos_pre_m'] * 100,
                                     'err_pos_post_cm': None if not _num(p.get('err_pos_post_m')) else p['err_pos_post_m'] * 100,
                                     'valido': p.get('valido'), 'correcciones': p.get('correcciones')}
    return {
        'version': VERSION,
        'generado': ahora if ahora is not None else time.time(),
        'estado': {'estado': ultimo.estado if ultimo else 'SIN_DATOS', 'vuelta': ultimo.vuelta if ultimo else None,
                   'estacion': ultimo.estacion if ultimo else None, 'motivo': fallas[-1]['motivo'] if fallas else None,
                   'pieza': ultima_valida.get('pieza_recibida') if ultima_valida else None,
                   'cd': cd[-1] if cd else None, 'ca': ca[-1] if ca else None},
        'mision': {'duracion_s': None if t0 is None or t_fin is None else t_fin - t0, 'vueltas_total': cfg.vueltas,
                   'vueltas_cerradas': len(vueltas), 'vueltas_validas': validas, 'pits': len(pits), 'pits_esperados': esperados,
                   'pits_validos': validos, 'terminada': any(e.tipo == 'fin' for e in ev), 'fallas': fallas},
        'cronometraje': {**cr.resumen_vueltas(vueltas),
                         'vueltas': [{'numero': v.numero, 'duracion': v.duracion, 'sectores': list(v.sectores), 'pits': list(v.pits),
                                      'valida': v.valida} for v in vueltas],
                         'tramos_s': [{'vuelta': a, 'estacion': b, 'duracion': c} for a, b, c in cr.tramos_desde_eventos(ev)]},
        'pits': {'t_medio_s': _media(t_pit), 't_max_s': max(t_pit) if t_pit else None, 't_p95_s': percentil(t_pit),
                 'lentos': sum(1 for t in t_pit if t > cfg.tiempos.pit_max_s), 'limite_s': cfg.tiempos.pit_max_s,
                 'con_correccion': sum(1 for p in pits if (p.get('correcciones') or 0) > 0),
                 'reintentos': sum(p.get('reintentos') or 0 for p in pits),
                 'err_pos_pre_cm': _stats([p['err_pos_pre_m'] for p in pits if _num(p.get('err_pos_pre_m'))], 100),
                 'err_pos_post_cm': _stats([p['err_pos_post_m'] for p in pits if _num(p.get('err_pos_post_m'))], 100),
                 'err_ang_pre_deg': _stats([p['err_ang_pre_deg'] for p in pits if _num(p.get('err_ang_pre_deg'))]),
                 'err_ang_post_deg': _stats([p['err_ang_post_deg'] for p in pits if _num(p.get('err_ang_post_deg'))]),
                 'reduccion': None if red is None else {'n': red.n, 'mejoran': red.n_mejoran, 'fraccion': red.fraccion, 'cumple': red.cumple,
                                                       'ya_dentro': red.n_ya_dentro,
                                                       'sin_ya_dentro': {'n': red_sin.n, 'fraccion': red_sin.fraccion, 'cumple': red_sin.cumple}}},
        'escalas': {'cd_inicial': cd[0] if cd else None, 'cd_final': cd[-1] if cd else None, 'ca_inicial': ca[0] if ca else None,
                    'ca_final': ca[-1] if ca else None, 'convergio': bool(cd and ca and convergio(cd) and convergio(ca)),
                    'serie': [{'cd': a, 'ca': b} for a, b in zip(cd, ca)]},
        'estaciones': [estaciones[k] for k in sorted(estaciones)],
        'rubrica_estimada': {'tanda_pts': _pts_tanda(validas), 'pieza_pts': _pts_pieza(validos / esperados if esperados else 0.0),
                             'pit_cumple': bool(red and red.cumple and cd and ca and convergio(cd) and convergio(ca)),
                             'autonomia_pts': _pts_autonomia(intervenciones), 'intervenciones': intervenciones,
                             'nota': 'estimación del equipo con la rúbrica del HTML; no incluye deploy.sh, video ni informe'},
        'eventos_recientes': [e.a_dict() for e in ev[-30:]],
    }


def cargar_carpeta(carpeta: str) -> List[Evento]:
    return leer_eventos(os.path.join(carpeta, 'eventos.jsonl'))


def escribir_json(datos: dict, ruta: str) -> None:
    tmp = f'{ruta}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, allow_nan=False)
    os.replace(tmp, ruta)                 # el panel nunca lee un archivo a medias


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('carpeta')
    p.add_argument('--salida', help='escribe el JSON aquí (por defecto lo imprime)')
    p.add_argument('--cada', type=float, help='repite cada N segundos (para el panel en vivo); Ctrl+C para terminar')
    p.add_argument('--intervenciones', type=int, help='número de intervenciones declaradas, para estimar la rúbrica')
    a = p.parse_args(argv)
    if a.cada is not None and a.cada <= 0:
        p.error('--cada debe ser positivo')
    try:
        while True:
            datos = calcular(cargar_carpeta(a.carpeta), intervenciones=a.intervenciones)
            if a.salida:
                escribir_json(datos, a.salida)
            else:
                print(json.dumps(datos, ensure_ascii=False, indent=2))
            if a.cada is None:
                return 0
            time.sleep(a.cada)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
