#!/usr/bin/env python3
"""Cronómetro manual de un cambio de pieza, por fases. No se conecta al brazo.

Úsalo mientras el brazo trabaja (p. ej. con el código del Reto 1 o, más adelante, con la estrategia):
una persona pulsa Enter en cada marca. Sirve para la "puerta del pit" del día 3: cuánto del
presupuesto de 10 s consume el brazo. El pit total (frenado a arranque) incluye además medir,
acoplar, MQTT, reset y recalibración, así que el brazo no puede usar los 10 s completos.

    python3 scripts/jetcobot_v01/cronometro_ciclo.py --rol 2 --corrida 1
"""
import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

PRESUPUESTO_PIT_S = 10.0
MARCAS = {
    1: ['inicio', 'tomado_de_almacen', 'colocado_en_cuna', 'brazo_libre'],
    2: ['inicio', 'retirado_de_cuna', 'dejado_en_recepcion', 'tomado_de_almacen', 'colocado_en_cuna', 'brazo_libre'],
    3: ['inicio', 'retirado_de_cuna', 'dejado_en_recepcion', 'tomado_de_almacen', 'colocado_en_cuna', 'brazo_libre'],
    4: ['inicio', 'retirado_de_cuna', 'dejado_en_recepcion', 'brazo_libre'],
}
CABECERA = ['fecha', 'rol', 'corrida', 'fuente', 'marca', 't_acum_s', 't_fase_s']


def calcular_fases(tiempos):
    """tiempos: lista de (marca, t_acum_s) con la primera en 0. Devuelve (marca, t_acum, t_fase)."""
    out, previo = [], None
    for marca, t in tiempos:
        out.append((marca, t, 0.0 if previo is None else t - previo))
        previo = t
    return out


def medir(marcas, entrada=input, reloj=time.monotonic):
    """Pide Enter por cada marca y devuelve [(marca, t_acum_s)]. `entrada` y `reloj` son inyectables."""
    tiempos, t0 = [], None
    for m in marcas:
        entrada(f'Enter en la marca «{m}» ')
        t = reloj()
        t0 = t if t0 is None else t0
        tiempos.append((m, t - t0))
    return tiempos


def guardar(ruta, filas):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    with ruta.open('a', newline='') as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerows(filas)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--rol', type=int, choices=[1, 2, 3, 4], required=True)
    p.add_argument('--corrida', required=True)
    p.add_argument('--fuente', default='manual', help='qué código movía el brazo (nivel4, estrategia, ...)')
    p.add_argument('--csv', type=Path, default=Path('experimentos/dia01_jetcobot/tiempos_manipulacion.csv'))
    a = p.parse_args(argv)
    fases = calcular_fases(medir(MARCAS[a.rol]))
    fecha = datetime.now().isoformat(timespec='seconds')
    guardar(a.csv, [[fecha, a.rol, a.corrida, a.fuente, m, f'{t:.3f}', f'{d:.3f}'] for m, t, d in fases])
    total = fases[-1][1]
    for m, t, d in fases:
        print(f'  {m:22s} acumulado {t:6.2f} s   fase {d:5.2f} s')
    print(f'Total del brazo: {total:.2f} s. Quedan {PRESUPUESTO_PIT_S - total:.2f} s del pit de {PRESUPUESTO_PIT_S:g} s '
          'para medir, acoplar, MQTT, reset y recalibración.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
