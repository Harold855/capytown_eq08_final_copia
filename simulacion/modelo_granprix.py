"""Port a Python del modelo `simulate()` de la pestaña Simulador del HTML oficial, usando NUESTRO planificador.

Sirve para la predicción firmada: permite barrer parámetros medidos en el robot y ver cómo se
comportaría el planificador y el estimador del equipo, no solo el código del HTML. Se verifica contra
salidas del `simulate()` original (tests/carrito/referencia_html.json): mismas semillas, mismos
resultados.

Reproduce el generador del HTML: mulberry32 y Box-Muller, con el mismo orden de sorteos. Las
protecciones provisionales del estimador se desactivan (`proteger=False`) para igualar al oficial.
Limitaciones del modelo (ver el HTML): el reacople es idealizado y la llegada válida se decide con la
pose verdadera, que el robot real no conoce.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List

from carrito.granprix_carrito.docks import DOCKS_HTML
from carrito.granprix_carrito.planificador import (Escalas, actualizar_escalas, comandar, medir_tramo,
                                                   planificar_tramo)
from geometria_dock.transformaciones import Pose2D, wrap

DEG = math.pi / 180.0
V, W, HTOL, RETRY_T = 0.10, 0.5, 6.0, 4.0
SIDE = DOCKS_HTML[2].x - DOCKS_HTML[1].x
_M = 0xFFFFFFFF
PARAMS_DEFECTO = dict(sd=1.0, sa=-1.2, sdd=0.5, sth=0.4, tag=0.5, alpha=0.35, tol=4.0, tswap=6.0)


def _imul(a: int, b: int) -> int:
    return (a * b) & _M


def mulberry32(semilla: int) -> Callable[[], float]:
    a = semilla & _M

    def siguiente() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & _M
        t = _imul(a ^ (a >> 15), 1 | a)
        t = ((t + _imul(t ^ (t >> 7), 61 | t)) & _M) ^ t
        return ((t ^ (t >> 14)) & _M) / 4294967296.0

    return siguiente


class Rng:
    def __init__(self, semilla: int) -> None:
        self.u = mulberry32(semilla)

    def n(self) -> float:
        x = 0.0
        while not x:
            x = self.u()
        return math.sqrt(-2.0 * math.log(x)) * math.cos(2.0 * math.pi * self.u())


def simular(p: Dict[str, float], modo: str, vueltas: int, semilla: int) -> List[dict]:
    """modo: 'open' (sin pit), 'reset' (reset de pose) o 'recal' (reset y recalibración)."""
    if modo not in ('open', 'reset', 'recal'):
        raise ValueError('modo debe ser open, reset o recal')
    R = Rng(semilla)
    sd, sa = 1 + p['sd'] / 100, 1 + p['sa'] / 100
    tag, tag_a = p['tag'] / 100, 0.4 * DEG
    docks = [DOCKS_HTML[i] for i in (1, 2, 3, 4)]

    def medir(t: Pose2D) -> Pose2D:  # orden de sorteos: x, y, th
        x = t.x + R.n() * tag
        y = t.y + R.n() * tag
        return Pose2D(x, y, t.th + R.n() * tag_a)

    T = docks[0].pose
    esc, t = Escalas(), 0.0
    B = T if modo == 'open' else medir(T)
    retry, regs = False, []
    for k in range(4 * vueltas):
        s, s2 = k % 4, (k + 1) % 4
        retry_ini = retry
        pit = p['tswap'] + (RETRY_T if retry else 0.0)
        t += pit
        if modo == 'open':
            B = docks[s].pose
            phi, L = math.pi / 2, SIDE
            cmd = comandar(_tramo(phi, L), esc, V, W)
        else:
            tr = planificar_tramo(B, (docks[s2].x, docks[s2].y))
            cmd = comandar(tr, esc, V, W)
        phi_act = cmd.phi_cmd * sa + R.n() * p['sth'] * DEG
        L_act = cmd.L_cmd * sd * (1 + R.n() * p['sdd'] / 100)
        th = T.th + phi_act + R.n() * 0.3 * DEG
        fin = Pose2D(T.x + L_act * math.cos(th), T.y + L_act * math.sin(th), th)
        t += cmd.t_giro + cmd.t_avance
        err = math.hypot(fin.x - docks[s2].x, fin.y - docks[s2].y) * 100
        herr = abs(wrap(fin.th - docks[s2].rumbo)) / DEG
        ok = err <= p['tol'] and herr <= HTOL
        T, retry = fin, False
        if modo != 'open':
            Ma = medir(fin)
            if modo == 'recal':
                d_med, a_med = medir_tramo(B, Ma)
                esc = actualizar_escalas(esc, cmd, d_med, a_med, p['alpha'], proteger=False).escalas
            if ok:
                B = Ma
            else:
                retry = True
                x = docks[s2].x + R.n() * 0.006
                y = docks[s2].y + R.n() * 0.006
                T = Pose2D(x, y, docks[s2].rumbo + R.n() * 0.5 * DEG)
                B = medir(T)
        regs.append(dict(k=k, err=err, herr=herr, ok=ok, retry=retry_ini, pitTime=pit, t1=t, cd=esc.cd, ca=esc.ca))
    return regs


def _tramo(phi: float, L: float):
    from carrito.granprix_carrito.planificador import Tramo
    return Tramo(phi, L)
