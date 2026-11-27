"""Acople fino: ciclo medir -> corregir -> medir con control proporcional.

Reutiliza `planificar_acople` (geometría), `comandar` (compensa con cd y ca), `EjecutorMovimiento`
(publica) y `acople_valido` (4 cm y 6°). Aquí solo se añade el ciclo, la ganancia y las salvaguardas.
La medición y el movimiento entran como funciones, así que no usa ROS. Los umbrales propios son provisionales.

El ciclo es un generador (`acoplar_pasos`): cada `yield` pide esperar un periodo. `acoplar` lo corre de forma bloqueante y la
máquina del pit lo avanza un paso por tick sin hilos. `medir` y `mover` pueden ser funciones normales o generadores.

Las correcciones del acople NO alimentan al estimador de escalas (ver calibracion_tramo.py).
"""
from __future__ import annotations

import dataclasses
import inspect
import math
import os
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable, Deque, Generator, List, Optional, Tuple
from collections import deque

from comun import yaml_estricto as ye
from geometria_dock.transformaciones import Pose2D, wrap

from .configuracion import ConfigMovimiento, DIRECTORIO_DEFECTO
from .docks import DOCKS_HTML, dock_a_mapa
from .ejecutor import Config, Estado, EjecutorMovimiento, Resultado, Salida, pasos_hasta_el_final
from .planificador import (TOL_ANG_DEG, TOL_POS_M, V_MAX, W_MAX, Comando, Escalas, Primitiva, Tramo, comandar,
                           error_acople, planificar_acople)
from .pose_dock import PoseDock

VERSION = 1
MAX_REINTENTOS = 2    # límite del reto

Medir = Callable[[], Optional[PoseDock]]
Mover = Callable[[Comando], Tuple[Comando, Resultado]]


@dataclass(frozen=True)
class ConfigAcople:
    tol_pos_m: float = 0.03       # se corrige hasta quedar dentro de esto (margen sobre los 4 cm del reto)
    tol_ang_deg: float = 4.0      # idem sobre los 6°
    ganancia_pos: float = 1.0     # fracción de la distancia que se avanza en cada corrección
    ganancia_ang: float = 1.0     # fracción del giro final que se aplica
    reintentos: int = MAX_REINTENTOS
    v: float = 0.10               # igual a movimiento.v_ref: las escalas cd/ca valen a esa velocidad
    w: float = 0.50
    error_max_m: float = 0.30     # más lejos no se intenta acoplar
    error_max_deg: float = 45.0
    giro_max_deg: float = 120.0   # no se hace ningún giro mayor de esto
    reversa_max_m: float = 0.10   # marcha atrás permitida; 0 la desactiva
    lecturas_max: int = 3         # intentos seguidos de medir antes de rendirse por tag ausente
    presupuesto_s: Optional[float] = 4.0   # no se inicia otra corrección pasado este tiempo; None = sin límite
    min_avance_m: float = 0.01
    min_giro_deg: float = 1.0

    def __post_init__(self) -> None:
        nums = (self.tol_pos_m, self.tol_ang_deg, self.ganancia_pos, self.ganancia_ang, self.v, self.w,
                self.error_max_m, self.error_max_deg, self.giro_max_deg, self.min_avance_m, self.min_giro_deg)
        if not all(math.isfinite(x) and x > 0 for x in nums) or not math.isfinite(self.reversa_max_m) \
                or self.reversa_max_m < 0:
            raise ValueError('los parámetros deben ser finitos y positivos (reversa_max_m puede ser 0)')
        if self.tol_pos_m > TOL_POS_M or self.tol_ang_deg > TOL_ANG_DEG:
            raise ValueError(f'la tolerancia no puede superar la del reto ({TOL_POS_M} m y {TOL_ANG_DEG}°)')
        if self.ganancia_pos > 1 or self.ganancia_ang > 1:
            raise ValueError('las ganancias deben estar en (0, 1]')
        if not 0 <= self.reintentos <= MAX_REINTENTOS or not isinstance(self.reintentos, int):
            raise ValueError(f'reintentos debe ser un entero entre 0 y {MAX_REINTENTOS}')
        if self.v > V_MAX or self.w > W_MAX:
            raise ValueError('velocidad por encima de los límites del reto')
        if self.lecturas_max < 1 or not isinstance(self.lecturas_max, int):
            raise ValueError('lecturas_max debe ser un entero >= 1')
        if self.presupuesto_s is not None and not (math.isfinite(self.presupuesto_s) and self.presupuesto_s > 0):
            raise ValueError('presupuesto_s debe ser positivo o None')


@dataclass(frozen=True)
class Intento:
    n: int
    pose_antes: PoseDock
    comandos: Tuple[Comando, ...]
    efectivos: Tuple[Comando, ...]
    pose_despues: Optional[PoseDock]


@dataclass(frozen=True)
class ResultadoAcople:
    exito: bool                    # la última pose medida cumple los 4 cm y 6° del reto
    motivo: Optional[str]          # None: dentro del margen interno; 'EN_BORDE': exito pero sin margen; otro: por qué se paró
    intentos: Tuple[Intento, ...]
    pose_inicial: Optional[PoseDock]
    pose_final: Optional[PoseDock]
    duracion_s: float

    @property
    def correcciones(self) -> int:
        return len(self.intentos)


# ------------------------------------------------------------------ plan de una corrección
def _dentro(p: PoseDock, cfg: ConfigAcople) -> bool:
    pos, ang = error_acople(p.dx, p.dy, p.dth_deg)
    return pos <= cfg.tol_pos_m and ang <= cfg.tol_ang_deg


class _Rechazo(Exception):
    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def _tramos(p: PoseDock, cfg: ConfigAcople) -> List[Tramo]:
    """Una o dos pasadas (giro+avance, giro final), con la ganancia aplicada al avance y al giro final."""
    pos, ang = error_acople(p.dx, p.dy, p.dth_deg)
    if pos <= cfg.tol_pos_m:
        return [Tramo(-p.dth * cfg.ganancia_ang, 0.0)]
    kw = dict(min_dist=cfg.min_avance_m, min_giro=math.radians(cfg.min_giro_deg))
    prims: List[Primitiva] = planificar_acople(p.dx, p.dy, p.dth_deg, permitir_reversa=cfg.reversa_max_m > 0, **kw)
    if any(q.tipo == 'avance' and q.valor < -cfg.reversa_max_m for q in prims):
        prims = planificar_acople(p.dx, p.dy, p.dth_deg, **kw)
    giros = [q.valor for q in prims if q.tipo == 'giro']
    if any(abs(math.degrees(g)) > cfg.giro_max_deg for g in giros):
        raise _Rechazo('GIRO_EXCESIVO')
    avance = next((q.valor for q in prims if q.tipo == 'avance'), 0.0) * cfg.ganancia_pos
    tramos = []
    if prims[0].tipo == 'giro' or avance:
        tramos.append(Tramo(prims[0].valor if prims[0].tipo == 'giro' else 0.0, avance))
    if prims[-1].tipo == 'giro' and len(prims) > 1:
        tramos.append(Tramo(prims[-1].valor * cfg.ganancia_ang, 0.0))
    return tramos


def comando_acople(tramo: Tramo, escalas: Escalas, cfg: ConfigAcople) -> Comando:
    """`comandar` solo admite distancia positiva: la marcha atrás se expresa con L_cmd < 0 y duración positiva."""
    c = comandar(Tramo(tramo.phi, abs(tramo.L)), escalas, cfg.v, cfg.w)
    return c if tramo.L >= 0 else dataclasses.replace(c, L_cmd=-c.L_cmd)


def planificar_correccion(p: PoseDock, escalas: Escalas, cfg: ConfigAcople) -> List[Comando]:
    return [comando_acople(t, escalas, cfg) for t in _tramos(p, cfg)]


# ------------------------------------------------------------------ ciclo
Pasos = Generator[None, None, Any]


def _llamar(f: Callable, *args: Any) -> Pasos:
    r = f(*args)
    if inspect.isgenerator(r):
        r = yield from r
    return r


def correr(gen: Pasos, dormir: Callable[[float], None], periodo_s: float = 0.02) -> Any:
    """Corre un generador de pasos de forma bloqueante y devuelve su valor final."""
    try:
        while True:
            next(gen)
            dormir(periodo_s)
    except StopIteration as fin:
        return fin.value


def _leer(medir: Medir, intentos: int) -> Pasos:
    for _ in range(intentos):
        p = yield from _llamar(medir)
        if p is not None:
            return p
    return None


def _bloqueo(pose: PoseDock, n: int, cfg: ConfigAcople, transcurrido: float, parar: Optional[Callable[[], bool]]
             ) -> Optional[str]:
    """Motivo por el que no se debe intentar otra corrección (None = se puede)."""
    if math.hypot(pose.dx, pose.dy) > cfg.error_max_m or abs(pose.dth_deg) > cfg.error_max_deg:
        return 'FUERA_DE_ALCANCE'
    if n > cfg.reintentos:
        return 'REINTENTOS_AGOTADOS'
    if cfg.presupuesto_s is not None and transcurrido >= cfg.presupuesto_s:
        return 'SIN_TIEMPO'
    if parar is not None and parar():
        return 'PARADA_EXTERNA'
    return None


def _ejecutar(cmds: List[Comando], mover: Mover) -> Generator[None, None, Tuple[List[Comando], Optional[str]]]:
    efectivos: List[Comando] = []
    for c in cmds:
        try:
            efectivo, res = yield from _llamar(mover, c)
        except ValueError:
            return efectivos, 'COMANDO_INVALIDO'
        efectivos.append(efectivo)
        if res.estado is not Estado.COMPLETO:
            return efectivos, f'MOVIMIENTO_{res.motivo or res.estado.name}'
    return efectivos, None


def acoplar_pasos(medir: Medir, mover: Mover, cfg: ConfigAcople = ConfigAcople(), escalas: Escalas = Escalas(),
                  reloj: Callable[[], float] = time.monotonic, debe_parar: Optional[Callable[[], bool]] = None,
                  pose_inicial: Optional[PoseDock] = None) -> Generator[None, None, ResultadoAcople]:
    """Corrige hasta quedar dentro de la tolerancia interna, con `1 + reintentos` correcciones como máximo.
    `medir` devuelve la pose en el dock con el robot ya quieto (None si no hay tag); `mover` ejecuta un Comando y
    devuelve (comando efectivo, Resultado del ejecutor). `pose_inicial` evita repetir la primera medición.
    Tras un movimiento fallido no se afirma ninguna pose final."""
    t0 = reloj()
    pose = inicial = pose_inicial if pose_inicial is not None else (yield from _leer(medir, cfg.lecturas_max))
    intentos: List[Intento] = []
    motivo: Optional[str] = None
    perdido = False
    while True:
        if pose is None:
            motivo = 'SIN_TAG'
        elif _dentro(pose, cfg):
            break
        else:
            motivo = _bloqueo(pose, len(intentos), cfg, reloj() - t0, debe_parar)
        if motivo:
            break
        try:
            cmds = planificar_correccion(pose, escalas, cfg)
        except _Rechazo as e:
            motivo = e.motivo
            break
        efectivos, motivo = yield from _ejecutar(cmds, mover)
        perdido = motivo is not None
        nueva = None if perdido else (yield from _leer(medir, cfg.lecturas_max))
        intentos.append(Intento(len(intentos) + 1, pose, tuple(cmds), tuple(efectivos), nueva))
        if perdido:
            break
        pose = nueva
    final = None if perdido else (intentos[-1].pose_despues if intentos else inicial)
    exito = final is not None and final.en_tolerancia
    if exito and motivo in ('REINTENTOS_AGOTADOS', 'SIN_TIEMPO'):
        motivo = 'EN_BORDE'
    return ResultadoAcople(exito, motivo, tuple(intentos), inicial, final, reloj() - t0)


def acoplar(medir: Medir, mover: Mover, cfg: ConfigAcople = ConfigAcople(), escalas: Escalas = Escalas(),
            reloj: Callable[[], float] = time.monotonic, debe_parar: Optional[Callable[[], bool]] = None,
            pose_inicial: Optional[PoseDock] = None, dormir: Callable[[float], None] = time.sleep) -> ResultadoAcople:
    """Versión bloqueante de `acoplar_pasos` (scripts y pruebas). Con funciones normales nunca duerme."""
    return correr(acoplar_pasos(medir, mover, cfg, escalas, reloj, debe_parar, pose_inicial), dormir)


# ------------------------------------------------------------------ medición y movimiento reales
class MedidorTag:
    """Entrega una pose estable del tag: mediana de `lecturas` mediciones llegadas DESPUÉS de que el robot se quedó quieto.
    Las lecturas anteriores al reposo (o con la imagen aún en movimiento) no valen. `agregar` lo llama el callback del tópico."""

    def __init__(self, reloj: Callable[[], float], dormir: Callable[[float], None], lecturas: int = 3,
                 espera_s: float = 0.8, timeout_s: float = 3.0) -> None:
        if lecturas < 1 or espera_s < 0 or timeout_s <= 0:
            raise ValueError('lecturas >= 1, espera_s >= 0, timeout_s > 0')
        self._reloj, self._dormir, self._n, self._espera, self._timeout = reloj, dormir, lecturas, espera_s, timeout_s
        self._lect: Deque[Tuple[float, PoseDock]] = deque(maxlen=50)
        self._desde = float('-inf')

    def agregar(self, pose: PoseDock) -> None:
        self._lect.append((self._reloj(), pose))

    def en_reposo(self, espera_s: Optional[float] = None) -> None:
        """Solo valen las lecturas posteriores a ahora + `espera_s` (por defecto la del medidor; 0 si el robot no se movió)."""
        self._desde = self._reloj() + (self._espera if espera_s is None else espera_s)

    def intentar(self) -> Optional[PoseDock]:
        """Sin esperar: la pose estable si ya llegaron `lecturas` mediciones posteriores al reposo, o None."""
        nuevas = [p for t, p in self._lect if t >= self._desde]
        return self._mediana(nuevas[-self._n:]) if len(nuevas) >= self._n else None

    def esperar(self) -> Pasos:
        fin = self._reloj() + self._timeout + max(0.0, self._desde - self._reloj())
        while True:
            p = self.intentar()
            if p is not None or self._reloj() >= fin:
                return p
            yield

    def medir(self) -> Optional[PoseDock]:
        return correr(self.esperar(), self._dormir)

    @staticmethod
    def _mediana(poses: List[PoseDock]) -> PoseDock:
        dx, dy, dth = (statistics.median(getattr(p, c) for p in poses) for c in ('dx', 'dy', 'dth'))
        u = poses[-1]
        return dataclasses.replace(u, dx=dx, dy=dy, dth=dth,
                                   mapa=dock_a_mapa(DOCKS_HTML[u.estacion], dx, dy, math.degrees(dth)))


def mover_con_ejecutor(salida: Salida, reloj: Callable[[], float], dormir: Optional[Callable[[float], None]],
                       config: Config = Config(), cfg: ConfigAcople = ConfigAcople(),
                       odom_ok: Optional[Callable[[], bool]] = None, debe_parar: Optional[Callable[[], bool]] = None,
                       al_parar: Optional[Callable[[], None]] = None) -> Mover:
    """Un `Mover` que ejecuta cada Comando con el ejecutor existente. `al_parar` se llama al terminar (p. ej. `MedidorTag.en_reposo`).
    Con `dormir=None` devuelve un generador de pasos (para la máquina del pit); si se cancela, publica ceros."""
    config = dataclasses.replace(config, permitir_reversa=cfg.reversa_max_m > 0)

    def pasos(cmd: Comando) -> Generator[None, None, Tuple[Comando, Resultado]]:
        ej = EjecutorMovimiento(salida, reloj, config, odom_ok, debe_parar)
        try:
            ej.iniciar(cmd)
            yield from pasos_hasta_el_final(ej)
        finally:
            if ej.estado is not Estado.ESPERA:
                ej.abortar('CANCELADO')   # no hace nada si ya terminó; si se cancela a medias, frena
        if al_parar is not None:
            al_parar()
        return ej.comando_efectivo(cmd), ej.resultado()
    return pasos if dormir is None else (lambda cmd: correr(pasos(cmd), dormir, config.periodo_s))


# ------------------------------------------------------------------ configuración
def cargar_acople(ruta: Optional[str] = None, mov: Optional[ConfigMovimiento] = None) -> ConfigAcople:
    """Carga `acople.yaml`. Con `mov`, exige que v y w coincidan con movimiento.yaml (si no, cd y ca no valdrían)."""
    ruta = ruta or os.path.join(DIRECTORIO_DEFECTO, 'acople.yaml')
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'acople', ('version', 'tolerancia', 'ganancias', 'velocidades', 'reintentos', 'alcance',
                                   'medicion', 'tiempo', 'minimos'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('acople: versión desconocida')

    def sec(nombre: str, claves: tuple):
        s = ye.seccion(d, nombre, 'acople')
        ye.exigir_claves(s, f'acople.{nombre}', claves)
        return s, f'acople.{nombre}'

    tol, dt = sec('tolerancia', ('pos_m', 'ang_deg'))
    gan, dg = sec('ganancias', ('pos', 'ang'))
    vel, dv = sec('velocidades', ('v', 'w'))
    alc, da = sec('alcance', ('error_max_m', 'error_max_deg', 'giro_max_deg', 'reversa_max_m'))
    med, dm = sec('medicion', ('lecturas_max',))
    tie, dti = sec('tiempo', ('presupuesto_s',))
    mini, dmi = sec('minimos', ('avance_m', 'giro_deg'))
    v = ye.numero(vel, 'v', dv, 0, V_MAX, exclusivo_min=True)
    w = ye.numero(vel, 'w', dv, 0, W_MAX, exclusivo_min=True)
    if mov is not None and (abs(v - mov.v_ref) > 1e-9 or abs(w - mov.w_ref) > 1e-9):
        raise ye.ErrorYaml(f'acople.velocidades ({v:g} m/s, {w:g} rad/s) no coincide con movimiento.velocidades '
                           f'({mov.v_ref:g}, {mov.w_ref:g}): las escalas cd y ca no valdrían en el acople')
    try:
        return ConfigAcople(
            tol_pos_m=ye.numero(tol, 'pos_m', dt, 0, TOL_POS_M, exclusivo_min=True),
            tol_ang_deg=ye.numero(tol, 'ang_deg', dt, 0, TOL_ANG_DEG, exclusivo_min=True),
            ganancia_pos=ye.numero(gan, 'pos', dg, 0, 1, exclusivo_min=True),
            ganancia_ang=ye.numero(gan, 'ang', dg, 0, 1, exclusivo_min=True),
            reintentos=ye.entero(d, 'reintentos', 'acople', 0, MAX_REINTENTOS), v=v, w=w,
            error_max_m=ye.numero(alc, 'error_max_m', da, 0, 1.0, exclusivo_min=True),
            error_max_deg=ye.numero(alc, 'error_max_deg', da, 0, 90, exclusivo_min=True),
            giro_max_deg=ye.numero(alc, 'giro_max_deg', da, 0, 180, exclusivo_min=True),
            reversa_max_m=ye.numero(alc, 'reversa_max_m', da, 0, 0.30),
            lecturas_max=ye.entero(med, 'lecturas_max', dm, 1, 20),
            presupuesto_s=ye.numero(tie, 'presupuesto_s', dti, 0, 60, exclusivo_min=True, permitir_none=True),
            min_avance_m=ye.numero(mini, 'avance_m', dmi, 0, 0.05, exclusivo_min=True),
            min_giro_deg=ye.numero(mini, 'giro_deg', dmi, 0, 10, exclusivo_min=True))
    except ValueError as e:
        raise ye.ErrorYaml(f'acople: {e}') from e
