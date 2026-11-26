#!/usr/bin/env python3
"""Resume y grafica el CSV de paradas (CalibradorTramo.exportar_paradas / prueba_acople.py / prueba_calibracion_adaptativa.py).

    python3 scripts/roscar_v01/analizar_acople.py paradas.csv --salida experimentos/dia03_roscar/graficos

Imprime: errores antes y después, reducción del error (umbral 70 %, con y sin las paradas que ya llegaron dentro),
correcciones, motivos y escalas. Con --salida escribe dos SVG (se abren en cualquier navegador, sin dependencias):
acople_errores.svg (error normalizado antes y después; 1.0 = límite del reto de 4 cm y 6°) y escalas.svg.
Solo lee: no mueve nada. Salida 0 si pudo analizar, 1 si el archivo falta o no tiene el formato esperado.
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from carrito.granprix_carrito.calibracion import evaluar_reduccion  # noqa: E402
from carrito.granprix_carrito.calibracion_tramo import CAMPOS_PARADAS  # noqa: E402
from carrito.granprix_carrito.metricas import percentil  # noqa: E402


def _num(x):
    try:
        return float(x) if x not in ('', None) else None
    except ValueError:
        raise ValueError(f'valor no numérico: {x!r}')


def leer(ruta):
    with open(ruta, newline='', encoding='utf-8') as f:
        lector = csv.DictReader(f)
        faltan = [c for c in CAMPOS_PARADAS if c not in (lector.fieldnames or [])]
        if faltan:
            raise ValueError(f'faltan columnas en el CSV: {", ".join(faltan)}')
        return list(lector)


def estadisticas(filas):
    pre = [(_num(f['err_norm_pre']), _num(f['err_norm_post'])) for f in filas]
    pares = [(a, b) for a, b in pre if a is not None and b is not None]
    out = {'paradas': len(filas), 'completas': len(pares), 'validas': sum(f['exito'] == 'True' for f in filas),
           'correcciones': sum(int(f['correcciones']) for f in filas), 'motivos': Counter(f['motivo'] or '-' for f in filas),
           'ya_dentro': sum(a <= 1.0 for a, _ in pares)}
    for cual, col, m in (('pos_pre_cm', 'err_pos_pre_m', 100), ('ang_pre_deg', 'err_ang_pre_deg', 1),
                         ('pos_post_cm', 'err_pos_post_m', 100), ('ang_post_deg', 'err_ang_post_deg', 1)):
        v = [_num(f[col]) * m for f in filas if _num(f[col]) is not None]
        out[cual] = (sum(v) / len(v), percentil(v)) if v else None
    out['reduccion'] = evaluar_reduccion(pares, tolerancia=1.0) if pares else None
    out['reduccion_sin_dentro'] = evaluar_reduccion(pares, tolerancia=1.0, excluir_dentro=True) if pares else None
    out['pares'] = pares
    return out


def _marco(titulo, ancho, alto):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}" '
            'font-family="sans-serif" font-size="12">', f'<rect width="{ancho}" height="{alto}" fill="white"/>',
            f'<text x="{ancho / 2}" y="20" text-anchor="middle" font-size="14">{escape(titulo)}</text>']


def _ejes(partes, x0, y0, x1, y1, lo, hi, formato='{:.2f}'):
    for i in range(6):
        y = y1 - (y1 - y0) * i / 5
        partes.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#ddd"/>'
                      f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end">{formato.format(lo + (hi - lo) * i / 5)}</text>')
    partes.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#333"/><line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#333"/>')


def svg_barras(titulo, pares, limite=1.0):
    ancho, alto, x0, y0, x1, y1 = 900, 380, 60, 40, 880, 320
    top = max([limite * 1.2] + [max(a, b) for a, b in pares])
    py = lambda v: y1 - (y1 - y0) * v / top  # noqa: E731
    p = _marco(titulo, ancho, alto)
    _ejes(p, x0, y0, x1, y1, 0, top)
    paso = (x1 - x0) / max(1, len(pares))
    for i, (a, b) in enumerate(pares):
        x = x0 + paso * i + paso * 0.1
        w = paso * 0.4
        p.append(f'<rect x="{x:.1f}" y="{py(a):.1f}" width="{w:.1f}" height="{y1 - py(a):.1f}" fill="#999"/>'
                 f'<rect x="{x + w:.1f}" y="{py(b):.1f}" width="{w:.1f}" height="{y1 - py(b):.1f}" fill="#1f77b4"/>')
        if len(pares) <= 40:
            p.append(f'<text x="{x + w:.1f}" y="{y1 + 14}" text-anchor="middle" font-size="10">{i + 1}</text>')
    p.append(f'<line x1="{x0}" y1="{py(limite):.1f}" x2="{x1}" y2="{py(limite):.1f}" stroke="#d62728" stroke-dasharray="6 4"/>'
             f'<text x="{x1}" y="{py(limite) - 4:.1f}" text-anchor="end" fill="#d62728">límite del reto (4 cm y 6°)</text>'
             f'<rect x="{x0}" y="{alto - 28}" width="12" height="12" fill="#999"/><text x="{x0 + 18}" y="{alto - 18}">antes del acople</text>'
             f'<rect x="{x0 + 150}" y="{alto - 28}" width="12" height="12" fill="#1f77b4"/>'
             f'<text x="{x0 + 168}" y="{alto - 18}">después</text>'
             f'<text x="{(x0 + x1) / 2}" y="{alto - 4}" text-anchor="middle">parada (error normalizado = max(pos/4 cm, ang/6°))</text></svg>')
    return '\n'.join(p)


def svg_lineas(titulo, series):
    ancho, alto, x0, y0, x1, y1 = 900, 340, 60, 40, 880, 290
    todos = [v for s in series.values() for v in s]
    lo, hi = min(todos) - 0.01, max(todos) + 0.01
    p = _marco(titulo, ancho, alto)
    _ejes(p, x0, y0, x1, y1, lo, hi, '{:.3f}')
    n = max(len(s) for s in series.values())
    colores = ('#1f77b4', '#ff7f0e')
    for (nombre, s), c in zip(series.items(), colores):
        pts = ' '.join(f'{x0 + (x1 - x0) * (i / max(1, n - 1)):.1f},{y1 - (y1 - y0) * (v - lo) / (hi - lo):.1f}' for i, v in enumerate(s))
        p.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"/>'
                 f'<text x="{x1 - 40}" y="{y1 - (y1 - y0) * (s[-1] - lo) / (hi - lo) - 6:.1f}" fill="{c}">{escape(nombre)}</text>')
    p.append(f'<text x="{(x0 + x1) / 2}" y="{alto - 10}" text-anchor="middle">parada</text></svg>')
    return '\n'.join(p)


def imprimir(e):
    print(f'Paradas: {e["paradas"]} (con error antes y después: {e["completas"]}); válidas al final: {e["validas"]}; '
          f'correcciones en total: {e["correcciones"]}; motivos: {dict(e["motivos"])}')
    for k, nombre in (('pos_pre_cm', 'Posición antes (cm)'), ('pos_post_cm', 'Posición después (cm)'),
                      ('ang_pre_deg', 'Ángulo antes (°)'), ('ang_post_deg', 'Ángulo después (°)')):
        v = e[k]
        print(f'  {nombre:24s}: ' + ('sin datos' if v is None else f'media {v[0]:.2f}, p95 {v[1]:.2f}'))
    print(f'Paradas que ya llegaron dentro del reto: {e["ya_dentro"]} de {e["completas"]}')
    for k, nombre in (('reduccion', 'con'), ('reduccion_sin_dentro', 'sin')):
        r = e[k]
        print(f'Reducción del error {nombre} las que ya estaban dentro: ' + ('sin datos' if r is None else
              f'{r.n_mejoran}/{r.n} = {r.fraccion:.0%} -> {"CUMPLE" if r.cumple else "no cumple"} (umbral 70 %)'))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('csv', type=Path)
    p.add_argument('--salida', type=Path, help='carpeta donde escribir los SVG')
    a = p.parse_args(argv)
    try:
        filas = leer(a.csv)
        if not filas:
            raise ValueError('el CSV no tiene paradas')
        e = estadisticas(filas)
        imprimir(e)
        if a.salida:
            a.salida.mkdir(parents=True, exist_ok=True)
            if e['pares']:
                (a.salida / 'acople_errores.svg').write_text(svg_barras('Error de acople antes y después, por parada', e['pares']), encoding='utf-8')
            series = {'cd': [_num(f['cd']) for f in filas], 'ca': [_num(f['ca']) for f in filas]}
            (a.salida / 'escalas.svg').write_text(svg_lineas('Escalas estimadas por parada', series), encoding='utf-8')
            print(f'Gráficos en {a.salida}')
        return 0
    except (OSError, ValueError, KeyError) as ex:
        print(f'ERROR: {ex}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
