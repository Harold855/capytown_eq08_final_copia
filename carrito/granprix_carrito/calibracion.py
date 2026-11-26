"""Estimadores de las escalas de distancia `cd` y de giro `ca` (sección 1.4.4 a 1.4.7 de la división).

Qué es cada escala: `cd` = distancia real recorrida / distancia comandada; `ca` = giro real / giro
comandado. Con ellas el planificador compensa (`L_cmd = L/cd`, `phi_cmd = phi/ca`).

La fórmula es la del HTML (filtro exponencial, alpha = 0.35 de referencia) y vive en
`planificador.actualizar_escalas`; este módulo añade lo que hace falta para usarla en la carrera:
- estado y registro de cada observación (qué se midió, qué se usó y por qué se rechazó lo demás);
- una observación = pose medida al salir del dock anterior + pose medida al llegar (ANTES de cualquier
  acople) + el comando realmente enviado (`EjecutorMovimiento.comando_efectivo`);
- las escalas de distancia y de giro dependen de la velocidad (RC-1 midió un giro de 7 a 11 % de más
  según ω): una observación hecha con otra v u otra ω que la de referencia NO se mezcla;
- congelar las escalas (3.5.4: fijar parámetros antes de la tanda) sin perder el registro;
- guardar y cargar un archivo JSON que lleva el identificador del robot y NO se aplica a otro robot
  (1.1.4); la carga falla cerrada ante cualquier valor dudoso;
- criterio de convergencia y evaluación de la reducción del error antes/después (≥ 70 % de paradas).

Python puro, sin ROS. Todo umbral que no viene del HTML o del reto es nuestro y provisional.
"""
from __future__ import annotations

import csv
import dataclasses
import json
import math
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from geometria_dock.transformaciones import Pose2D

from .planificador import LIMITES_ESCALA, Comando, Escalas, actualizar_escalas, medir_tramo

ALPHA_REF = 0.35          # referencia del HTML, no ajuste definitivo
VERSION_ARCHIVO = 1
TOL_VELOCIDAD = 1e-6      # misma v / misma ω si difieren menos que esto (m/s, rad/s)


def _finitos(*v: float) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)


def _pose_ok(p: Optional[Pose2D]) -> bool:
    """None = el tag no se vio. (Pose2D ya rechaza valores no finitos al crearse.)"""
    return p is not None and _finitos(p.x, p.y, p.th)


@dataclass(frozen=True)
class Registro:
    """Una observación del estimador. `razon_*` es medido/comandado (la escala que sugiere esa medición)."""
    k: int
    t: Optional[float]
    v: float
    w: float                   # con signo, el del comando
    L_cmd: float
    phi_cmd: float
    dist_medida: float
    giro_medido: float
    razon_cd: Optional[float]
    razon_ca: Optional[float]
    cd_antes: float
    ca_antes: float
    cd_despues: float
    ca_despues: float
    uso_cd: bool
    uso_ca: bool
    motivo_cd: Optional[str]
    motivo_ca: Optional[str]


class EstimadorEscalas:
    def __init__(self, escalas: Escalas = Escalas(), alpha: float = ALPHA_REF, *, proteger: bool = True,
                 robot: Optional[str] = None, v_ref: Optional[float] = None, w_ref: Optional[float] = None,
                 ventana: int = 4, tol_convergencia: float = 0.01) -> None:
        if not _finitos(alpha) or not 0 < alpha <= 1:
            raise ValueError('alpha debe estar en (0, 1]')
        if ventana < 2 or not _finitos(tol_convergencia) or tol_convergencia <= 0:
            raise ValueError('ventana >= 2 y tol_convergencia > 0')
        for nombre, val in (('v_ref', v_ref), ('w_ref', w_ref)):
            if val is not None and (not _finitos(val) or val <= 0):
                raise ValueError(f'{nombre} debe ser positiva y finita')
        self._esc, self._alpha, self._proteger = escalas, alpha, proteger
        self._robot, self._v_ref, self._w_ref = robot, v_ref, w_ref
        self._ventana, self._tol = ventana, tol_convergencia
        self._reg: List[Registro] = []
        self._congelado: Optional[str] = None

    # ------------------------------------------------------------------ consulta
    @property
    def escalas(self) -> Escalas:
        return self._esc

    @property
    def alpha(self) -> float:
        return self._alpha

    @property
    def robot(self) -> Optional[str]:
        return self._robot

    @property
    def perfil(self) -> Tuple[Optional[float], Optional[float]]:
        """(v_ref, w_ref) con las que valen las escalas. None = aún sin fijar (se fijan con la 1.ª observación usada)."""
        return self._v_ref, self._w_ref

    @property
    def registros(self) -> Tuple[Registro, ...]:
        return tuple(self._reg)

    @property
    def congelado(self) -> bool:
        return self._congelado is not None

    # ------------------------------------------------------------------ control
    def congelar(self, motivo: str = 'manual') -> None:
        """Las escalas dejan de cambiar. Las observaciones se siguen registrando (como 'congelado')."""
        self._congelado = motivo or 'manual'

    def descongelar(self) -> None:
        self._congelado = None

    # ------------------------------------------------------------------ observar
    def observar(self, inicio: Optional[Pose2D], fin: Optional[Pose2D], cmd: Comando, t: Optional[float] = None) -> Registro:
        """Incorpora el tramo ejecutado. `inicio` y `fin` son poses MEDIDAS (tag; None si no se vio), `fin` antes del acople.
        `cmd` debe ser lo realmente enviado (compensado), no el tramo nominal."""
        if not _finitos(cmd.phi_cmd, cmd.L_cmd, cmd.v, cmd.w):
            raise ValueError('comando no finito')
        antes = self._esc
        razon_cd = razon_ca = None
        uso_cd = uso_ca = False
        motivo_cd = motivo_ca = None
        d_med = g_med = float('nan')

        if not (_pose_ok(inicio) and _pose_ok(fin)):
            motivo_cd = motivo_ca = 'medicion_invalida'
        else:
            d_med, g_med = medir_tramo(inicio, fin)
            if cmd.L_cmd != 0:
                razon_cd = d_med / cmd.L_cmd
            if cmd.phi_cmd != 0:
                razon_ca = g_med / cmd.phi_cmd
            res = actualizar_escalas(antes, cmd, d_med, g_med, self._alpha, proteger=self._proteger)
            cd, ca = res.escalas.cd, res.escalas.ca
            uso_cd, uso_ca, motivo_cd, motivo_ca = res.uso_cd, res.uso_ca, res.motivo_cd, res.motivo_ca

            if uso_cd and self._v_ref is not None and abs(cmd.v - self._v_ref) > TOL_VELOCIDAD:
                cd, uso_cd, motivo_cd = antes.cd, False, 'velocidad_distinta'
            if uso_ca and self._w_ref is not None and abs(abs(cmd.w) - self._w_ref) > TOL_VELOCIDAD:
                ca, uso_ca, motivo_ca = antes.ca, False, 'velocidad_angular_distinta'
            if self._congelado is not None:
                cd, ca = antes.cd, antes.ca
                if uso_cd:
                    uso_cd, motivo_cd = False, 'congelado'
                if uso_ca:
                    uso_ca, motivo_ca = False, 'congelado'
            else:
                if uso_cd and self._v_ref is None:
                    self._v_ref = cmd.v
                if uso_ca and self._w_ref is None:
                    self._w_ref = abs(cmd.w)
                self._esc = Escalas(cd, ca)

        reg = Registro(len(self._reg), t, cmd.v, cmd.w, cmd.L_cmd, cmd.phi_cmd, d_med, g_med, razon_cd, razon_ca,
                       antes.cd, antes.ca, self._esc.cd, self._esc.ca, uso_cd, uso_ca, motivo_cd, motivo_ca)
        self._reg.append(reg)
        return reg

    # ------------------------------------------------------------------ convergencia
    def convergencia(self) -> Dict[str, bool]:
        """Una escala 'convergió' si hay al menos `ventana` actualizaciones usadas y las últimas `ventana`
        estimaciones difieren entre sí menos de `tol_convergencia`. Umbrales provisionales."""
        out = {}
        for nombre, uso, valor in (('cd', 'uso_cd', 'cd_despues'), ('ca', 'uso_ca', 'ca_despues')):
            ult = [getattr(r, valor) for r in self._reg if getattr(r, uso)][-self._ventana:]
            out[nombre] = len(ult) >= self._ventana and (max(ult) - min(ult)) < self._tol
        return out

    def convergio(self) -> bool:
        return all(self.convergencia().values())

    # ------------------------------------------------------------------ persistencia
    def a_dict(self) -> dict:
        return {'version': VERSION_ARCHIVO, 'robot': self._robot, 'cd': self._esc.cd, 'ca': self._esc.ca,
                'alpha': self._alpha, 'v_ref': self._v_ref, 'w_ref': self._w_ref,
                'observaciones': len(self._reg)}

    def guardar(self, ruta: str) -> None:
        """Escritura atómica: un corte a medias no deja un archivo corrupto."""
        datos = json.dumps(self.a_dict(), indent=2, sort_keys=True)
        carpeta = os.path.dirname(os.path.abspath(ruta))
        fd, tmp = tempfile.mkstemp(dir=carpeta, prefix='.calibracion_', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(datos + '\n')
            os.replace(tmp, ruta)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    @classmethod
    def cargar(cls, ruta: str, robot_esperado: Optional[str] = None, **kwargs) -> 'EstimadorEscalas':
        """Falla (ValueError) ante archivo ilegible, versión desconocida, valores no finitos o fuera de
        límites, o si `robot_esperado` no coincide con el robot del archivo."""
        try:
            with open(ruta, encoding='utf-8') as f:
                d = json.load(f)
        except (OSError, ValueError) as e:
            raise ValueError(f'calibración ilegible: {e}') from e
        if not isinstance(d, dict) or d.get('version') != VERSION_ARCHIVO:
            raise ValueError('versión de calibración desconocida')
        cd, ca = d.get('cd'), d.get('ca')
        if isinstance(cd, bool) or isinstance(ca, bool) or not _finitos(cd, ca):
            raise ValueError('cd y ca deben ser números finitos')
        lo, hi = LIMITES_ESCALA
        if not (lo <= cd <= hi and lo <= ca <= hi):
            raise ValueError(f'cd y ca deben estar en [{lo}, {hi}]')
        if robot_esperado is not None and d.get('robot') != robot_esperado:
            raise ValueError(f"la calibración es del robot {d.get('robot')!r}, no de {robot_esperado!r}")
        alpha = d.get('alpha', ALPHA_REF)
        for nombre in ('v_ref', 'w_ref'):
            if d.get(nombre) is not None and (isinstance(d[nombre], bool) or not _finitos(d[nombre])):
                raise ValueError(f'{nombre} inválido')
        return cls(Escalas(cd, ca), alpha, robot=d.get('robot'), v_ref=d.get('v_ref'), w_ref=d.get('w_ref'),
                   **kwargs)

    def exportar_csv(self, ruta: str) -> None:
        """Un renglón por observación, para las gráficas y la evidencia del informe."""
        campos = [f.name for f in dataclasses.fields(Registro)]
        with open(ruta, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            for r in self._reg:
                w.writerow(dataclasses.asdict(r))


# ------------------------------------------------------------------ reducción del error (1.4.7)
@dataclass(frozen=True)
class EvaluacionParadas:
    n: int
    n_mejoran: int
    fraccion: float
    cumple: bool
    n_ya_dentro: int   # paradas cuyo error previo ya estaba dentro de la tolerancia dada


def evaluar_reduccion(pre_post: Sequence[Tuple[float, float]], umbral: float = 0.70,
                      tolerancia: Optional[float] = None, excluir_dentro: bool = False) -> EvaluacionParadas:
    """Fracción de paradas con error posterior menor que el previo (la evaluación oficial pide >= 70 %).
    `pre_post` = [(error_previo, error_posterior)] medidos con el MISMO criterio. Cómo cuenta la rúbrica
    las paradas que ya estaban dentro de tolerancia está sin confirmar: con `tolerancia` se informa cuántas
    son (`n_ya_dentro`) y con `excluir_dentro=True` se calcula sin ellas."""
    if not 0 < umbral <= 1:
        raise ValueError('umbral en (0, 1]')
    datos = []
    for pre, post in pre_post:
        if not _finitos(pre, post) or pre < 0 or post < 0:
            raise ValueError('errores no finitos o negativos')
        datos.append((pre, post))
    dentro = sum(1 for pre, _ in datos if tolerancia is not None and pre <= tolerancia)
    if excluir_dentro:
        if tolerancia is None:
            raise ValueError('excluir_dentro requiere tolerancia')
        datos = [(a, b) for a, b in datos if a > tolerancia]
    mejoran = sum(1 for pre, post in datos if post < pre)
    frac = mejoran / len(datos) if datos else 0.0
    return EvaluacionParadas(len(datos), mejoran, frac, bool(datos) and frac >= umbral, dentro)
