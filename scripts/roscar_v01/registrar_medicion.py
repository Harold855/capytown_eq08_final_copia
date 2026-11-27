#!/usr/bin/env python3
"""Añade UNA fila validada a experimentos/dia01_roscar/mediciones_fisicas.csv.

Con --auto toma lo comandado y lo medido por odometría de la última fila de
movimientos_odom.csv (la que escribe prueba_movimiento.py); tú aportas solo lo medido con cinta
y transportador. Valida unidades (metros, no centímetros) para evitar errores de captura.
"""
import argparse
import csv
from datetime import datetime
from pathlib import Path

CABECERA = ['fecha', 'robot', 'superficie', 'corrida', 'modo', 'distancia_comandada_m', 'giro_comandado_deg',
            'velocidad_m_s', 'velocidad_rad_s', 'distancia_fisica_m', 'giro_fisico_deg', 'desvio_lateral_cm',
            'distancia_odom_m', 'giro_odom_deg', 'estado', 'observaciones']
CSV_MEDICIONES = Path('experimentos/dia01_roscar/mediciones_fisicas.csv')
CSV_ODOM = Path('experimentos/dia01_roscar/movimientos_odom.csv')


def _rango(nombre, valor, minimo, maximo, pista):
    if valor is not None and not minimo <= valor <= maximo:
        raise ValueError(f'{nombre}={valor} fuera de [{minimo}, {maximo}]. {pista}')


def construir_fila(a, ultimo_odom=None):
    """Devuelve la fila (lista) o lanza ValueError con un mensaje claro."""
    if a.modo not in ('recta', 'giro'):
        raise ValueError("modo debe ser 'recta' o 'giro'")
    _rango('distancia_fisica_m', a.distancia_fisica, 0.0, 5.0, '¿está en metros? 98 cm = 0.98')
    _rango('distancia_comandada_m', a.distancia_comandada, 0.0, 5.0, 'metros, no centímetros')
    _rango('distancia_odom_m', a.distancia_odom, 0.0, 5.0, 'metros, no centímetros')
    _rango('giro_fisico_deg', a.giro_fisico, -720.0, 720.0, '¿grados, no radianes?')
    _rango('giro_comandado_deg', a.giro_comandado, -720.0, 720.0, '¿grados, no radianes?')
    _rango('desvio_lateral_cm', a.desvio_lateral_cm, -50.0, 50.0, 'centímetros, con signo (+ izquierda)')
    if a.modo == 'recta' and a.distancia_fisica is None:
        raise ValueError('una recta necesita --distancia-fisica (cinta, en metros)')
    if a.modo == 'giro' and a.giro_fisico is None:
        raise ValueError('un giro necesita --giro-fisico (transportador, en grados, con signo: + antihorario)')
    cmd_d, cmd_g, vel_l, vel_a, odom_d, odom_g = (a.distancia_comandada, a.giro_comandado, a.velocidad_m_s,
                                                 a.velocidad_rad_s, a.distancia_odom, a.giro_odom)
    estado = a.estado
    if ultimo_odom is not None:
        if ultimo_odom['modo'] != a.modo:
            raise ValueError(f"la última fila de odometría es de modo {ultimo_odom['modo']}, no {a.modo}")
        orden, vel = float(ultimo_odom['orden_si']), float(ultimo_odom['velocidad_si'])
        if a.modo == 'recta':
            cmd_d, vel_l = orden, vel
        else:
            cmd_g, vel_a = orden * 180 / 3.141592653589793, vel
        odom_d = float(ultimo_odom['dist_odom_m']) if ultimo_odom['dist_odom_m'] != '' else odom_d
        odom_g = float(ultimo_odom['giro_odom_deg']) if ultimo_odom['giro_odom_deg'] != '' else odom_g
        estado = estado or ultimo_odom['estado']
    fila = [datetime.now().isoformat(timespec='seconds'), a.robot, a.superficie, a.corrida, a.modo,
            cmd_d, cmd_g, vel_l, vel_a, a.distancia_fisica, a.giro_fisico, a.desvio_lateral_cm,
            odom_d, odom_g, estado or '', a.observaciones]
    return ['' if v is None else v for v in fila]


def ultima_fila_odom(ruta=CSV_ODOM):
    with Path(ruta).open(newline='') as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise ValueError(f'{ruta} no tiene filas')
    return filas[-1]


def anexar(fila, ruta=CSV_MEDICIONES):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    if not nuevo:
        with ruta.open(newline='') as f:
            cab = next(csv.reader(f), [])
        if cab != CABECERA:
            raise ValueError(f'la cabecera de {ruta} no coincide; no se escribe nada')
    with ruta.open('a', newline='') as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerow(fila)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('modo', choices=['recta', 'giro'])
    p.add_argument('--robot', required=True, help='identificador del ROSCar asignado')
    p.add_argument('--superficie', required=True, help='p. ej. carton_elevado, ceramica')
    p.add_argument('--corrida', required=True)
    p.add_argument('--auto', action='store_true', help='toma lo comandado y lo odométrico de movimientos_odom.csv')
    p.add_argument('--distancia-comandada', type=float, dest='distancia_comandada')
    p.add_argument('--giro-comandado', type=float, dest='giro_comandado')
    p.add_argument('--velocidad-m-s', type=float, dest='velocidad_m_s')
    p.add_argument('--velocidad-rad-s', type=float, dest='velocidad_rad_s')
    p.add_argument('--distancia-fisica', type=float, dest='distancia_fisica', help='cinta, metros')
    p.add_argument('--giro-fisico', type=float, dest='giro_fisico', help='transportador, grados, + antihorario')
    p.add_argument('--desvio-lateral-cm', type=float, dest='desvio_lateral_cm')
    p.add_argument('--distancia-odom', type=float, dest='distancia_odom')
    p.add_argument('--giro-odom', type=float, dest='giro_odom')
    p.add_argument('--estado', default='')
    p.add_argument('--observaciones', default='')
    a = p.parse_args(argv)
    try:
        fila = construir_fila(a, ultima_fila_odom() if a.auto else None)
        anexar(fila)
    except (ValueError, OSError) as e:
        p.error(str(e))
    print('Fila añadida a', CSV_MEDICIONES)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
