"""La misión: estaciones, vueltas y piezas, y su configuración (`config/mision.yaml`). Python puro.

Una vuelta son los cuatro pits E1..E4; cierra al terminar el de E4. La misión termina al cerrar la última vuelta.
Un resultado `ok` con otra pieza de la esperada no detiene la misión: el pit se marca inválido y se avisa.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from comun import yaml_estricto as ye

from .configuracion import DIRECTORIO_DEFECTO
from .docks import ORDEN, siguiente

VERSION = 1
LIMITES_ESTADO = ('navegando_margen_s', 'midiendo_s', 'acoplando_s', 'solicitando_s', 'esperando_resultado_s',
                  'recalibrando_s', 'saliendo_s')


@dataclass(frozen=True)
class Tiempos:
    tanda_max_s: float = 720.0
    pit_max_s: float = 10.0
    navegando_margen_s: float = 8.0
    midiendo_s: float = 4.0
    acoplando_s: float = 20.0
    solicitando_s: float = 3.0
    esperando_resultado_s: float = 15.0
    recalibrando_s: float = 6.0
    saliendo_s: float = 3.0
    medicion_post_s: float = 2.0
    reset_reintentos: int = 3
    reset_espera_s: float = 0.3
    reintentos_por_parada: int = 2        # reto: máximo 2; lo gastan los reintentos del acople y los rechazos de la estación


@dataclass(frozen=True)
class Seguridad:
    requiere_autorizacion: bool = True
    requiere_enlace: bool = True
    enlace_max_s: float = 2.0
    estacion_offline_aborta: bool = True
    solicitar_solo_si_esperando: bool = True      # el supervisor solo acepta con la estación en ESPERANDO (doc. 02)


@dataclass(frozen=True)
class ConfigMision:
    equipo: int = 8
    vueltas: int = 4
    piezas: Tuple[Tuple[int, Optional[str], Optional[str]], ...] = (
        (1, None, 'A'), (2, 'A', 'B'), (3, 'B', 'C'), (4, 'C', None))     # (estación, trae, deja)
    tiempos: Tiempos = Tiempos()
    seguridad: Seguridad = Seguridad()

    def __post_init__(self) -> None:
        if not 1 <= self.equipo <= 99 or not 1 <= self.vueltas <= 10:
            raise ValueError('equipo de 1 a 99 y vueltas de 1 a 10')
        if tuple(e for e, _, _ in self.piezas) != ORDEN:
            raise ValueError('las estaciones deben ser E1, E2, E3 y E4 en ese orden')
        n = len(self.piezas)
        for i, (_, _, deja) in enumerate(self.piezas):
            if self.piezas[(i + 1) % n][1] != deja:
                raise ValueError(f'la cadena de piezas no cierra: E{i + 1} deja {deja!r} y E{(i + 1) % n + 1} '
                                 f'trae {self.piezas[(i + 1) % n][1]!r}')
        t = self.tiempos
        valores = (t.tanda_max_s, t.pit_max_s, t.medicion_post_s, t.reset_espera_s, self.seguridad.enlace_max_s,
                   *(getattr(t, k) for k in LIMITES_ESTADO))
        if not all(v > 0 for v in valores) or t.reset_reintentos < 0:
            raise ValueError('los plazos deben ser positivos')
        if not 0 <= t.reintentos_por_parada <= 2:
            raise ValueError('reintentos_por_parada debe estar entre 0 y 2 (reto: máximo dos)')
        if t.tanda_max_s > 720.0 or t.pit_max_s > 10.0:
            raise ValueError('la tanda no puede pasar de 720 s ni el pit de 10 s (reglas del reto)')


@dataclass(frozen=True)
class PitCerrado:
    estacion: int
    vuelta: int
    valido: bool
    motivo: Optional[str]
    pieza_esperada: Optional[str]
    pieza_recibida: Optional[str]
    cierra_vuelta: bool
    mision_completa: bool


@dataclass(frozen=True)
class VueltaCerrada:
    numero: int
    t_inicio: float
    t_fin: float
    estaciones: Tuple[int, ...]


@dataclass
class RegistroPit:
    """Una fila de `pits.csv` (evidencia): lo que sabe la misión; los errores y escalas los añade la máquina."""
    vuelta: int
    estacion: int
    t_llegada: float
    t_pit_s: Optional[float] = None
    err_pos_pre_m: Optional[float] = None
    err_ang_pre_deg: Optional[float] = None
    err_pos_post_m: Optional[float] = None
    err_ang_post_deg: Optional[float] = None
    correcciones: int = 0
    reintentos: int = 0
    rechazos: int = 0
    cd: Optional[float] = None
    ca: Optional[float] = None
    pieza_esperada: Optional[str] = None
    pieza_recibida: Optional[str] = None
    valido: Optional[bool] = None
    motivo: Optional[str] = None


CAMPOS_PITS = tuple(RegistroPit.__dataclass_fields__)


class Mision:
    def __init__(self, cfg: ConfigMision = ConfigMision()) -> None:
        self.cfg = cfg
        self.reiniciar()

    def reiniciar(self) -> None:
        self._i = 0
        self.vuelta = 1
        self.completa = False
        self.t_inicio_vuelta: Optional[float] = None
        self._validos: List[int] = []
        self.pits: List[RegistroPit] = []
        self.vueltas: List[VueltaCerrada] = []

    @property
    def estacion(self) -> int:
        return self.cfg.piezas[self._i][0]

    @property
    def pieza_trae(self) -> Optional[str]:
        return self.cfg.piezas[self._i][1]

    @property
    def pieza_deja(self) -> Optional[str]:
        return self.cfg.piezas[self._i][2]

    @property
    def siguiente_estacion(self) -> int:
        return siguiente(self.estacion)

    @property
    def pits_invalidos(self) -> int:
        return sum(1 for p in self.pits if p.valido is False)

    def abrir_pit(self, t: float) -> RegistroPit:
        if self.t_inicio_vuelta is None:
            self.t_inicio_vuelta = t
        reg = RegistroPit(self.vuelta, self.estacion, t, pieza_esperada=self.pieza_deja)
        self.pits.append(reg)
        return reg

    def cerrar_pit(self, ok: bool, pieza_dejo: Optional[str], t: float) -> Tuple[PitCerrado, Optional[VueltaCerrada]]:
        """Registra el resultado del pit y avanza a la siguiente estación (y vuelta si era E4)."""
        motivo = None if ok and pieza_dejo == self.pieza_deja else ('RESULTADO_NO_OK' if not ok else 'PIEZA_INESPERADA')
        valido = motivo is None
        if self.pits and self.pits[-1].estacion == self.estacion and self.pits[-1].valido is None:
            self.pits[-1].valido, self.pits[-1].motivo, self.pits[-1].pieza_recibida = valido, motivo, pieza_dejo
        if valido:
            self._validos.append(self.estacion)
        cierra = self._i == len(self.cfg.piezas) - 1
        vuelta_cerrada = None
        pit = PitCerrado(self.estacion, self.vuelta, valido, motivo, self.pieza_deja, pieza_dejo, cierra,
                         cierra and self.vuelta == self.cfg.vueltas)
        if cierra:
            vuelta_cerrada = VueltaCerrada(self.vuelta, self.t_inicio_vuelta if self.t_inicio_vuelta is not None else t,
                                           t, tuple(self._validos))
            self.vueltas.append(vuelta_cerrada)
            self.completa = self.vuelta == self.cfg.vueltas
            self.vuelta += 1
            self._validos, self.t_inicio_vuelta = [], None
        self._i = (self._i + 1) % len(self.cfg.piezas)
        return pit, vuelta_cerrada

    def exportar_pits(self, ruta: str) -> None:
        with open(ruta, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_PITS)
            w.writeheader()
            for p in self.pits:
                w.writerow({k: getattr(p, k) for k in CAMPOS_PITS})


def cargar_mision(ruta: Optional[str] = None) -> ConfigMision:
    ruta = ruta or os.path.join(DIRECTORIO_DEFECTO, 'mision.yaml')
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'mision', ('version', 'equipo', 'vueltas', 'estaciones', 'tiempos', 'seguridad'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('mision: versión desconocida')
    est = ye.seccion(d, 'estaciones', 'mision')
    ye.exigir_claves(est, 'mision.estaciones', ('E1', 'E2', 'E3', 'E4'))
    piezas = []
    for n in ORDEN:
        e = ye.seccion(est, f'E{n}', 'mision.estaciones')
        ye.exigir_claves(e, f'mision.estaciones.E{n}', ('trae', 'deja'))
        piezas.append((n, ye.texto(e, 'trae', f'mision.estaciones.E{n}', True), ye.texto(e, 'deja', f'mision.estaciones.E{n}', True)))
    t = ye.seccion(d, 'tiempos', 'mision')
    ye.exigir_claves(t, 'mision.tiempos', ('tanda_max_s', 'pit_max_s', 'medicion_post_s', 'reset_reintentos', 'reset_espera_s',
                                           'reintentos_por_parada', *LIMITES_ESTADO))
    enteros = ('reset_reintentos', 'reintentos_por_parada')
    tiempos = Tiempos(**{k: ye.numero(t, k, 'mision.tiempos', 0, exclusivo_min=True) for k in t if k not in enteros},
                      reset_reintentos=ye.entero(t, 'reset_reintentos', 'mision.tiempos', 0, 10),
                      reintentos_por_parada=ye.entero(t, 'reintentos_por_parada', 'mision.tiempos', 0, 2))
    s = ye.seccion(d, 'seguridad', 'mision')
    ye.exigir_claves(s, 'mision.seguridad', ('requiere_autorizacion', 'requiere_enlace', 'enlace_max_s', 'estacion_offline_aborta',
                                             'solicitar_solo_si_esperando'))
    seg = Seguridad(ye.booleano(s, 'requiere_autorizacion', 'mision.seguridad'), ye.booleano(s, 'requiere_enlace', 'mision.seguridad'),
                    ye.numero(s, 'enlace_max_s', 'mision.seguridad', 0, 30, exclusivo_min=True),
                    ye.booleano(s, 'estacion_offline_aborta', 'mision.seguridad'),
                    ye.booleano(s, 'solicitar_solo_si_esperando', 'mision.seguridad'))
    try:
        return ConfigMision(ye.entero(d, 'equipo', 'mision', 1, 99), ye.entero(d, 'vueltas', 'mision', 1, 10), tuple(piezas), tiempos, seg)
    except ValueError as e:
        raise ye.ErrorYaml(f'mision: {e}') from e
