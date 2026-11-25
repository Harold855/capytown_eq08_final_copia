#!/usr/bin/env python3
"""Diagnóstico de SOLO LECTURA del JetCobot. No envía ningún movimiento ni cambia la pinza.

Lee ángulos, coordenadas, valor de la pinza y estado de los servos, y mide la latencia de lectura
del puerto serie. Sirve para llenar `2.1` y para estimar la latencia que el repositorio del
docente deja "por confirmar". Basado en el Nivel 1 del Reto 1 (el único código que ya corrió en
el brazo). No asume que el brazo esté en HOME.

Uso (en la Jetson, con el brazo encendido y SIN otro programa usando el puerto serie):
    python3 scripts/jetcobot_v01/diagnostico_jetcobot.py
    python3 scripts/jetcobot_v01/diagnostico_jetcobot.py --lecturas 30 --puerto /dev/ttyUSB0
    python3 scripts/jetcobot_v01/diagnostico_jetcobot.py --simular        # sin brazo, prueba el script
"""
import argparse
import json
import math
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Límites articulares usados en el Reto 1 (grados). Son referencia, no los del guardián del curso.
LIMITES_ARTICULARES = {1: (-168, 168), 2: (-135, 90), 3: (-150, 150), 4: (-145, 145), 5: (-165, 165), 6: (-180, 180)}


def _finitos(valores):
    return isinstance(valores, (list, tuple)) and len(valores) > 0 and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in valores)


def evaluar(angulos, coords, pinza, encendido, en_movimiento=None, fallos_lectura=0):
    """Devuelve una lista de (nivel, mensaje) con nivel OK, AVISO o FALLA. Función pura."""
    r = []
    if not _finitos(angulos) or len(angulos) != 6:
        r.append(('FALLA', f'get_angles no devolvió 6 valores válidos: {angulos!r}'))
    else:
        fuera = [f'J{i}={v}' for i, v in enumerate(angulos, 1)
                 if not LIMITES_ARTICULARES[i][0] <= v <= LIMITES_ARTICULARES[i][1]]
        r.append(('AVISO', 'articulaciones fuera de los límites de referencia: ' + ', '.join(fuera)) if fuera
                 else ('OK', 'articulaciones dentro de los límites de referencia del Reto 1'))
    if not _finitos(coords) or len(coords) != 6:
        r.append(('FALLA', f'get_coords no devolvió 6 valores válidos: {coords!r}'))
    else:
        r.append(('OK', 'coordenadas leídas (x, y, z en mm; rx, ry, rz en grados)'))
    if not isinstance(pinza, (int, float)) or isinstance(pinza, bool) or not 0 <= pinza <= 100:
        r.append(('FALLA', f'valor de pinza inválido: {pinza!r}'))
    else:
        r.append(('OK', f'pinza leída: {pinza}'))
    if encendido == 1:
        r.append(('OK', 'servos encendidos'))
    else:
        r.append(('FALLA', f'servos no encendidos o sin respuesta (is_power_on={encendido!r})'))
    if en_movimiento == 1:
        r.append(('AVISO', 'el brazo reporta movimiento: esperar a que se detenga antes de cualquier prueba'))
    if fallos_lectura:
        r.append(('AVISO', f'{fallos_lectura} lecturas fallaron o devolvieron datos inválidos'))
    return r


def resumen_latencias(segundos):
    """Estadísticas simples de las latencias de lectura (s). Devuelve None si no hay datos."""
    v = sorted(segundos)
    if not v:
        return None
    p95 = v[min(len(v) - 1, int(math.ceil(0.95 * len(v))) - 1)]
    return {'n': len(v), 'media_ms': 1000 * statistics.fmean(v), 'p95_ms': 1000 * p95, 'max_ms': 1000 * v[-1]}


class BrazoFalso:
    """Para --simular: devuelve lecturas plausibles sin hardware."""
    def get_angles(self): return [0.0, -20.0, 30.0, 0.0, 10.0, -45.0]
    def get_coords(self): return [140.0, -10.0, 260.0, -170.0, 0.0, -40.0]
    def get_gripper_value(self): return 100
    def is_power_on(self): return 1
    def is_moving(self): return 0


def leer(brazo, lecturas):
    """Lee el estado una vez y mide la latencia de `lecturas` lecturas de get_coords."""
    estado = {
        'angulos': brazo.get_angles(), 'coords': brazo.get_coords(), 'pinza': brazo.get_gripper_value(),
        'encendido': brazo.is_power_on(), 'en_movimiento': brazo.is_moving(),
    }
    lat, fallos = [], 0
    for _ in range(lecturas):
        t = time.monotonic()
        c = brazo.get_coords()
        dt = time.monotonic() - t
        if _finitos(c) and len(c) == 6:
            lat.append(dt)
        else:
            fallos += 1
        time.sleep(0.05)
    return estado, lat, fallos


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--puerto', default='/dev/ttyUSB0')
    p.add_argument('--baudios', type=int, default=1000000)
    p.add_argument('--lecturas', type=int, default=20, help='lecturas para medir la latencia (1 a 200)')
    p.add_argument('--simular', action='store_true', help='usa un brazo falso, sin hardware')
    p.add_argument('--salida', type=Path, default=None)
    a = p.parse_args(argv)
    if not 1 <= a.lecturas <= 200:
        p.error('--lecturas debe estar entre 1 y 200')
    version = 'simulado'
    if a.simular:
        brazo = BrazoFalso()
    else:
        try:
            import pymycobot
            from pymycobot.mycobot import MyCobot
        except ImportError:
            print('ERROR: falta pymycobot (pip install pymycobot).', file=sys.stderr)
            return 2
        version = getattr(pymycobot, '__version__', 'desconocida')
        brazo = MyCobot(a.puerto, a.baudios)
    estado, lat, fallos = leer(brazo, a.lecturas)
    checks = evaluar(estado['angulos'], estado['coords'], estado['pinza'], estado['encendido'],
                     estado['en_movimiento'], fallos)
    stats = resumen_latencias(lat)
    ahora = datetime.now()
    lineas = [f'=== Diagnóstico JetCobot (solo lectura) {ahora.isoformat(timespec="seconds")} ===',
              f'host={platform.node()} python={platform.python_version()} pymycobot={version} puerto={a.puerto}',
              f"ángulos [°]: {estado['angulos']}", f"coordenadas [mm, °]: {estado['coords']}",
              f"pinza: {estado['pinza']}  servos: {estado['encendido']}  en movimiento: {estado['en_movimiento']}"]
    lineas.append('latencia de lectura (get_coords): ' + (
        f"n={stats['n']} media={stats['media_ms']:.1f} ms p95={stats['p95_ms']:.1f} ms max={stats['max_ms']:.1f} ms"
        if stats else 'sin lecturas válidas'))
    lineas += [f'{n:6s} {m}' for n, m in checks]
    texto = '\n'.join(lineas)
    print(texto)
    salida = a.salida or Path('experimentos/dia01_jetcobot') / f'diagnostico_{ahora:%Y%m%d_%H%M%S}.txt'
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto + '\n' + json.dumps({'estado': estado, 'latencia': stats, 'checks': checks}, default=str) + '\n')
    print(f'Guardado en {salida}')
    return 1 if any(n == 'FALLA' for n, _ in checks) else 0


if __name__ == '__main__':
    raise SystemExit(main())
