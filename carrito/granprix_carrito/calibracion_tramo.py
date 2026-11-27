"""Coordina las mediciones de cada parada con el estimador de escalas `EstimadorEscalas`.

Garantiza lo que el estimador necesita para no converger sesgado:
- el tramo se observa con la pose medida al SALIR del pit anterior y la pose medida al LLEGAR, antes de
  cualquier corrección del acople (se toma de `ResultadoAcople.pose_inicial`, no se puede pasar otra);
- el comando es el realmente enviado en el tramo; los movimientos del acople no se mezclan;
- cada parada guarda el error antes y después con el mismo criterio, para evaluar la reducción (>= 70 %).

Python puro, sin ROS. El criterio de error normalizado (peor de posición/tolerancia y ángulo/tolerancia) es nuestro:
el reto no define cómo se compara el error antes y después.
"""
from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from typing import List, Optional

from geometria_dock.transformaciones import Pose2D

from .acople import ResultadoAcople
from .calibracion import EstimadorEscalas, EvaluacionParadas, Registro, evaluar_reduccion
from .planificador import TOL_ANG_DEG, TOL_POS_M, Comando, error_acople
from .pose_dock import PoseDock


def error_normalizado(pos_m: float, ang_deg: float, tol_pos_m: float = TOL_POS_M, tol_ang_deg: float = TOL_ANG_DEG) -> float:
    """1.0 = justo en el límite del reto; menor es mejor."""
    return max(pos_m / tol_pos_m, ang_deg / tol_ang_deg)


@dataclass(frozen=True)
class TramoObservado:
    inicio: Optional[Pose2D]
    fin: Optional[Pose2D]
    cmd: Comando
    t: Optional[float] = None


@dataclass(frozen=True)
class Parada:
    k: int
    vuelta: Optional[int]
    estacion: int
    err_pos_pre_m: Optional[float]
    err_ang_pre_deg: Optional[float]
    err_pos_post_m: Optional[float]
    err_ang_post_deg: Optional[float]
    correcciones: int
    exito: bool
    motivo: Optional[str]
    cd: float
    ca: float
    registro: Optional[Registro] = None

    @property
    def error_pre(self) -> Optional[float]:
        return None if self.err_pos_pre_m is None else error_normalizado(self.err_pos_pre_m, self.err_ang_pre_deg)

    @property
    def error_post(self) -> Optional[float]:
        return None if self.err_pos_post_m is None else error_normalizado(self.err_pos_post_m, self.err_ang_post_deg)


CAMPOS_PARADAS = ('k', 'vuelta', 'estacion', 'err_pos_pre_m', 'err_ang_pre_deg', 'err_pos_post_m', 'err_ang_post_deg',
                  'err_norm_pre', 'err_norm_post', 'correcciones', 'exito', 'motivo', 'cd', 'ca', 'uso_cd', 'uso_ca')
CAMPOS_TRAMOS = ('k', 't', 'v', 'w', 'L_cmd', 'phi_cmd', 'x0', 'y0', 'th0', 'x1', 'y1', 'th1')


def _error(p: Optional[PoseDock]):
    return (None, None) if p is None else error_acople(p.dx, p.dy, p.dth_deg)


class CalibradorTramo:
    def __init__(self, estimador: EstimadorEscalas) -> None:
        self.estimador = estimador
        self._salida: Optional[Pose2D] = None
        self._cmd: Optional[Comando] = None
        self._paradas: List[Parada] = []
        self._tramos: List[TramoObservado] = []

    @property
    def paradas(self) -> tuple:
        return tuple(self._paradas)

    @property
    def tramos(self) -> tuple:
        return tuple(self._tramos)

    def salida(self, pose_mapa: Optional[Pose2D]) -> None:
        """Pose medida con el tag al salir del pit (la medición posterior al intercambio). None = no se vio."""
        self._salida = pose_mapa

    def comando(self, efectivo: Comando) -> None:
        """Lo realmente enviado en el tramo (`EjecutorMovimiento.comando_efectivo`), no el nominal."""
        self._cmd = efectivo

    def cerrar_parada(self, estacion: int, acople: ResultadoAcople, post: Optional[PoseDock] = None,
                      vuelta: Optional[int] = None, t: Optional[float] = None) -> Parada:
        """Al final del pit: observa el tramo recién recorrido, guarda los errores y deja la salida para el tramo siguiente.
        `post` es la medición tras el intercambio; si falta se usa la última del acople (el robot no se movió)."""
        fin = None if acople.pose_inicial is None else acople.pose_inicial.mapa
        registro = None
        if self._cmd is not None:
            registro = self.estimador.observar(self._salida, fin, self._cmd, t)
            self._tramos.append(TramoObservado(self._salida, fin, self._cmd, t))
        final = post if post is not None else acople.pose_final
        pre, pos = _error(acople.pose_inicial), _error(final)
        esc = self.estimador.escalas
        parada = Parada(len(self._paradas), vuelta, estacion, pre[0], pre[1], pos[0], pos[1], acople.correcciones,
                        acople.exito if post is None else post.en_tolerancia, acople.motivo, esc.cd, esc.ca, registro)
        self._paradas.append(parada)
        self._salida = None if final is None else final.mapa
        self._cmd = None
        return parada

    # ------------------------------------------------------------------ evaluación
    def evaluacion(self, excluir_dentro: bool = False) -> EvaluacionParadas:
        """Fracción de paradas con error posterior menor que el previo. `excluir_dentro` omite las que ya
        llegaron dentro del reto (la rúbrica no aclara cómo cuentan)."""
        pares = [(p.error_pre, p.error_post) for p in self._paradas if p.error_pre is not None and p.error_post is not None]
        return evaluar_reduccion(pares, tolerancia=1.0, excluir_dentro=excluir_dentro)

    # ------------------------------------------------------------------ CSV
    def exportar_paradas(self, ruta: str, anexar: bool = False) -> None:
        """`anexar` añade renglones a un archivo existente (varios ensayos seguidos) sin repetir el encabezado."""
        nuevo = not (anexar and os.path.exists(ruta) and os.path.getsize(ruta) > 0)
        with open(ruta, 'a' if anexar else 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_PARADAS)
            if nuevo:
                w.writeheader()
            for p in self._paradas:
                r = p.registro
                w.writerow({'k': p.k, 'vuelta': p.vuelta, 'estacion': p.estacion, 'err_pos_pre_m': p.err_pos_pre_m,
                            'err_ang_pre_deg': p.err_ang_pre_deg, 'err_pos_post_m': p.err_pos_post_m,
                            'err_ang_post_deg': p.err_ang_post_deg, 'err_norm_pre': p.error_pre,
                            'err_norm_post': p.error_post, 'correcciones': p.correcciones, 'exito': p.exito,
                            'motivo': p.motivo, 'cd': p.cd, 'ca': p.ca, 'uso_cd': None if r is None else r.uso_cd,
                            'uso_ca': None if r is None else r.uso_ca})

    def exportar_tramos(self, ruta: str) -> None:
        """Lo necesario para repetir la estimación fuera de línea (`leer_tramos`)."""
        with open(ruta, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_TRAMOS)
            w.writeheader()
            for k, tr in enumerate(self._tramos):
                fila = {'k': k, 't': tr.t, 'v': tr.cmd.v, 'w': tr.cmd.w, 'L_cmd': tr.cmd.L_cmd, 'phi_cmd': tr.cmd.phi_cmd}
                for nombre, p in (('0', tr.inicio), ('1', tr.fin)):
                    fila.update({f'x{nombre}': None if p is None else p.x, f'y{nombre}': None if p is None else p.y,
                                 f'th{nombre}': None if p is None else p.th})
                w.writerow(fila)


def leer_tramos(ruta: str) -> List[TramoObservado]:
    """Inverso de `exportar_tramos`. Una pose con algún campo vacío se lee como None (tag no visto)."""
    def num(x: str) -> Optional[float]:
        return float(x) if x not in ('', None) else None

    def pose(f: dict, n: str) -> Optional[Pose2D]:
        v = [num(f[f'{c}{n}']) for c in ('x', 'y', 'th')]
        return None if any(x is None for x in v) else Pose2D(*v)

    out = []
    with open(ruta, newline='', encoding='utf-8') as f:
        for fila in csv.DictReader(f):
            phi, L, v, w = (float(fila[c]) for c in ('phi_cmd', 'L_cmd', 'v', 'w'))
            if not all(map(math.isfinite, (phi, L, v, w))) or v <= 0:
                raise ValueError(f'fila {fila["k"]}: comando inválido')
            cmd = Comando(phi, L, v, w, abs(phi) / abs(w) if w else 0.0, L / v)
            out.append(TramoObservado(pose(fila, '0'), pose(fila, '1'), cmd, num(fila['t'])))
    return out
