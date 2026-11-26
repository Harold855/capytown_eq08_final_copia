#!/usr/bin/env python3
"""Evalúa cómo evolucionan las escalas cd y ca durante varios pits. No mueve ningún robot.

    python3 scripts/roscar_v01/prueba_calibracion_adaptativa.py simular --cd 1.01 --ca 1.09 --vueltas 4
    python3 scripts/roscar_v01/prueba_calibracion_adaptativa.py repetir --tramos tramos.csv --alpha 0.2 0.35 0.5

simular: circuito completo con un robot simulado cuyas escalas reales el controlador no conoce (tramo, acople,
         medición del tag y estimador, como en la carrera). repetir: vuelve a calcular las escalas con los tramos
         medidos de verdad (CalibradorTramo.exportar_tramos), para probar otro alpha sin repetir la tanda.
Salida 0 siempre que corra; la evaluación se lee en pantalla. Con --csv-* guarda lo que pide la evidencia.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from carrito.granprix_carrito.acople import ConfigAcople, acoplar  # noqa: E402
from carrito.granprix_carrito.calibracion import ALPHA_REF, EstimadorEscalas  # noqa: E402
from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo, leer_tramos  # noqa: E402
from carrito.granprix_carrito.docks import DOCKS_HTML, ORDEN, siguiente  # noqa: E402
from carrito.granprix_carrito.planificador import Escalas, comandar, planificar_tramo  # noqa: E402
from simulacion.robot_simulado import RobotSimulado  # noqa: E402
from geometria_dock.transformaciones import Pose2D  # noqa: E402


def simular_circuito(cd=1.01, ca=1.09, vueltas=4, alpha=ALPHA_REF, escalas_ini=(1.0, 1.0), ruido_mov=0.01, ruido_tag_m=0.002,
                     ruido_tag_deg=0.25, semilla=0, cfg=ConfigAcople()):
    """Devuelve (CalibradorTramo, RobotSimulado). El robot sale de E1 sobre su marca; el planificador parte de la pose medida."""
    est = EstimadorEscalas(Escalas(*escalas_ini), alpha, robot='simulado', v_ref=cfg.v, w_ref=cfg.w)
    cal = CalibradorTramo(est)
    r = RobotSimulado(Pose2D(0, 0, 0), 1, cd, ca, ruido_mov, ruido_mov, ruido_tag_m, ruido_tag_deg, 0.0, semilla)
    r.colocar_en_dock(0, 0, 0)
    pose = r.medir()
    cal.salida(pose.mapa)
    actual = 1
    for vuelta in range(1, vueltas + 1):
        for _ in ORDEN:
            destino = siguiente(actual)
            tramo = planificar_tramo(pose.mapa, (DOCKS_HTML[destino].x, DOCKS_HTML[destino].y))
            efectivo, _ = r.mover(comandar(tramo, est.escalas, cfg.v, cfg.w))
            cal.comando(efectivo)
            r.estacion = destino
            res = acoplar(r.medir, r.mover, cfg, est.escalas, r.reloj)
            post = r.medir() or res.pose_final
            cal.cerrar_parada(destino, res, post, vuelta)
            pose, actual = post or r.medir() or pose, destino
    return cal, r


def resumen(cal, cd=None, ca=None):
    est = cal.estimador
    print('vuelta est  pre_cm  pre_deg  corr  post_cm  post_deg    cd     ca')
    for p in cal.paradas:
        f = lambda x, m: '   -  ' if x is None else f'{x * m:6.2f}'  # noqa: E731
        print(f'{p.vuelta or 0:5d} E{p.estacion}  {f(p.err_pos_pre_m, 100)}  {f(p.err_ang_pre_deg, 1)}   {p.correcciones:4d}  '
              f'{f(p.err_pos_post_m, 100)}  {f(p.err_ang_post_deg, 1)}   {p.cd:.3f}  {p.ca:.3f}')
    e = est.escalas
    real = '' if cd is None else f' (reales: cd={cd:.3f}, ca={ca:.3f})'
    print(f'\nEscalas finales: cd={e.cd:.3f}, ca={e.ca:.3f}{real}. Convergencia: {est.convergencia()}')
    for excluir in (False, True):
        ev = cal.evaluacion(excluir_dentro=excluir)
        print(f'Reducción del error ({"sin" if excluir else "con"} paradas que ya llegaron dentro): '
              f'{ev.n_mejoran}/{ev.n} = {ev.fraccion:.0%} -> {"CUMPLE" if ev.cumple else "no cumple"} (umbral 70 %)')


def repetir(tramos, alphas):
    for alpha in alphas:
        est = EstimadorEscalas(Escalas(), alpha)
        usados = 0
        for tr in tramos:
            r = est.observar(tr.inicio, tr.fin, tr.cmd, tr.t)
            usados += r.uso_cd or r.uso_ca
        e = est.escalas
        print(f'alpha={alpha:.2f}: cd={e.cd:.4f} ca={e.ca:.4f}; observaciones usadas {usados}/{len(tramos)}; '
              f'convergencia {est.convergencia()}')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='modo', required=True)
    s = sub.add_parser('simular')
    s.add_argument('--cd', type=float, default=1.01, help='escala real de distancia (el controlador no la conoce)')
    s.add_argument('--ca', type=float, default=1.09, help='escala real de giro')
    s.add_argument('--vueltas', type=int, default=4)
    s.add_argument('--alpha', type=float, default=ALPHA_REF)
    s.add_argument('--semilla', type=int, default=0)
    s.add_argument('--csv-paradas', type=Path)
    s.add_argument('--csv-tramos', type=Path)
    q = sub.add_parser('repetir')
    q.add_argument('--tramos', type=Path, required=True)
    q.add_argument('--alpha', type=float, nargs='+', default=[ALPHA_REF])
    a = p.parse_args(argv)
    try:
        if a.modo == 'repetir':
            repetir(leer_tramos(a.tramos), a.alpha)
            return 0
        if not 1 <= a.vueltas <= 50 or not 0 < a.cd < 3 or not 0 < a.ca < 3 or not 0 < a.alpha <= 1:
            p.error('vueltas en 1..50, cd y ca en (0, 3), alpha en (0, 1]')
        cal, _ = simular_circuito(a.cd, a.ca, a.vueltas, a.alpha, semilla=a.semilla)
        resumen(cal, a.cd, a.ca)
        for ruta, guardar in ((a.csv_paradas, cal.exportar_paradas), (a.csv_tramos, cal.exportar_tramos)):
            if ruta:
                ruta.parent.mkdir(parents=True, exist_ok=True)
                guardar(str(ruta))
                print(f'Guardado: {ruta}')
        return 0
    except (OSError, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
