"""Ejecutor de movimiento en lazo abierto (secciones 1.2.4 a 1.2.7 de la división).

Toma un `Comando` del planificador y lo ejecuta: primero el giro, luego el avance, por TIEMPO (lazo
abierto, como pide el HTML). No usa ROS ni sabe de `/cmd_vel`: publica a través de una `Salida`
(el adaptador ROS 2 publicará un Twist en la entrada autorizada de `twist_mux`) y recibe el reloj por
inyección, así que se prueba con un reloj falso.

Se maneja con `paso()`, que un temporizador llama a ~20 Hz; no bloquea. Seguridad:
- Rechaza comandos que superen 0.20 m/s o 0.8 rad/s, no finitos o más largos que `t_max_tramo_s`.
- Aborta y manda ceros ante: parada externa, odometría perdida, hueco de tiempo entre llamadas,
  reloj que retrocede, error de la salida o tiempo máximo. Tras abortar NO reanuda por sí solo.
- Entre el giro y el avance y al terminar publica ceros (pausa y asentamiento).
- Registra lo que realmente envió: `comando_efectivo` devuelve la distancia y el giro comandados de
  verdad, que son los que debe usar el estimador de escalas.

Un nodo ROS muerto deja al robot con la última orden (el firmware no frena solo). Este módulo no puede
actuar si no se le llama: la protección contra eso es el timeout de la entrada de `twist_mux`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Protocol

from .planificador import V_MAX, W_MAX, Comando


class Estado(Enum):
    ESPERA = 'espera'
    GIRANDO = 'girando'
    PAUSA = 'pausa'
    AVANZANDO = 'avanzando'
    ASENTANDO = 'asentando'
    COMPLETO = 'completo'
    ABORTADO = 'abortado'
    DETENIDO = 'detenido'


FINALES = (Estado.COMPLETO, Estado.ABORTADO, Estado.DETENIDO)


class Salida(Protocol):
    def publicar(self, v: float, w: float) -> None: ...


@dataclass(frozen=True)
class Config:
    periodo_s: float = 0.05            # llamada de paso() esperada: 20 Hz
    pausa_s: float = 0.30              # PLACEHOLDER: ceros entre el giro y el avance; medir en el robot
    asentamiento_s: float = 0.50       # PLACEHOLDER: ceros tras avanzar, antes de dar el tramo por completo
    max_hueco_s: float = 0.25          # más de esto entre dos llamadas = el temporizador falló
    t_max_tramo_s: float = 60.0
    a_lin_max: Optional[float] = None  # m/s²; None = sin rampa. Solo limita acelerar, no frenar
    a_ang_max: Optional[float] = None  # rad/s²
    ajustar_ultimo_paso: bool = True   # el último paso de cada segmento se escala para igualar la duración
    ceros_al_abortar: int = 5
    v_max: float = V_MAX
    w_max: float = W_MAX


@dataclass(frozen=True)
class Resultado:
    estado: Estado
    motivo: Optional[str]
    L_ejecutada: float      # m comandados de verdad (suma de v·dt)
    phi_ejecutado: float    # rad comandados de verdad, con signo (suma de w·dt)
    duracion_s: float


class EjecutorMovimiento:
    def __init__(self, salida: Salida, reloj: Callable[[], float], config: Config = Config(),
                 odom_ok: Optional[Callable[[], bool]] = None, debe_parar: Optional[Callable[[], bool]] = None) -> None:
        if not 0 < config.periodo_s <= 0.2:
            raise ValueError('periodo_s debe estar en (0, 0.2]')
        self._salida, self._reloj, self._cfg = salida, reloj, config
        self._odom_ok, self._debe_parar = odom_ok, debe_parar
        self._estado, self._motivo = Estado.ESPERA, None
        self._cmd: Optional[Comando] = None
        self._segmentos: List[tuple] = []
        self._reiniciar_contadores()

    def _reiniciar_contadores(self) -> None:
        self._t0 = self._t_ult_paso = self._t_ult_pub = None
        self._v_ult = self._w_ult = 0.0
        self._L = self._phi = 0.0
        self._ceros_pendientes = 0
        self._t_fin = None
        self._i = 0            # segmento actual
        self._t_seg = None     # instante del primer paso() dentro del segmento actual

    # ------------------------------------------------------------------ interfaz
    @property
    def estado(self) -> Estado:
        return self._estado

    @property
    def motivo(self) -> Optional[str]:
        return self._motivo

    @property
    def terminado(self) -> bool:
        return self._estado in FINALES

    def iniciar(self, cmd: Comando) -> None:
        if self._estado not in (Estado.ESPERA,) + FINALES:
            raise RuntimeError('ya hay un tramo en ejecución')
        vals = (cmd.phi_cmd, cmd.L_cmd, cmd.v, cmd.w, cmd.t_giro, cmd.t_avance)
        if not all(math.isfinite(x) for x in vals):
            raise ValueError('comando no finito')
        if cmd.L_cmd < 0 or not 0 < cmd.v <= self._cfg.v_max or abs(cmd.w) > self._cfg.w_max:
            raise ValueError('comando fuera de los límites de velocidad o con distancia negativa')
        if cmd.t_giro + cmd.t_avance > self._cfg.t_max_tramo_s:
            raise ValueError(f'el tramo duraría más de {self._cfg.t_max_tramo_s:g} s')
        self._reiniciar_contadores()
        self._cmd, self._estado, self._motivo = cmd, Estado.ESPERA, None
        c = self._cfg
        # (estado, duración, v, w). Cada duración se mide desde el primer paso() del segmento, no desde un
        # reloj absoluto: así la cuantización del temporizador no le quita tiempo al segmento.
        seg = []
        if cmd.t_giro > 0:
            seg.append((Estado.GIRANDO, cmd.t_giro, 0.0, cmd.w))
        if cmd.t_giro > 0 and cmd.t_avance > 0 and c.pausa_s > 0:
            seg.append((Estado.PAUSA, c.pausa_s, 0.0, 0.0))
        if cmd.t_avance > 0:
            seg.append((Estado.AVANZANDO, cmd.t_avance, cmd.v, 0.0))
        seg.append((Estado.ASENTANDO, c.asentamiento_s, 0.0, 0.0))
        self._segmentos = seg
        self._t0 = self._reloj()
        self._estado = seg[0][0]

    def abortar(self, motivo: str) -> None:
        """Parada inmediata con ceros. No reanuda."""
        self._finalizar(Estado.ABORTADO, motivo)

    def paso(self) -> Estado:
        ahora = self._reloj()
        if self._estado in FINALES:
            if self._ceros_pendientes > 0:
                self._publicar(ahora, 0.0, 0.0, forzar=True)
                self._ceros_pendientes -= 1
            return self._estado
        if self._estado is Estado.ESPERA:
            return self._estado
        referencia = self._t_ult_paso if self._t_ult_paso is not None else self._t0
        if ahora < referencia:
            return self._parar_por(Estado.ABORTADO, 'RELOJ_RETROCEDE', ahora)
        if ahora - referencia > self._cfg.max_hueco_s:  # también cubre un primer paso() demasiado tardío
            return self._parar_por(Estado.ABORTADO, 'HUECO_DE_TIEMPO', ahora)
        self._t_ult_paso = ahora
        if self._debe_parar is not None and self._debe_parar():
            return self._parar_por(Estado.DETENIDO, 'PARADA_EXTERNA', ahora)
        if self._odom_ok is not None and not self._odom_ok():
            return self._parar_por(Estado.ABORTADO, 'ODOM_PERDIDA', ahora)
        t = ahora - self._t0
        if t > self._cfg.t_max_tramo_s + self._cfg.pausa_s + self._cfg.asentamiento_s + 1.0:
            return self._parar_por(Estado.ABORTADO, 'TIEMPO_MAXIMO', ahora)
        while True:
            est, dur, v, w = self._segmentos[self._i]
            if self._t_seg is None:
                self._t_seg = ahora
            restante = dur - (ahora - self._t_seg)
            if restante > 1e-9:
                break
            self._i += 1
            self._t_seg = ahora
            if self._i >= len(self._segmentos):
                return self._parar_por(Estado.COMPLETO, None, ahora)   # siempre cierra con ceros
        self._estado = est
        escala = min(1.0, restante / self._cfg.periodo_s) if self._cfg.ajustar_ultimo_paso else 1.0
        self._publicar(ahora, v * escala, w * escala)
        return self._estado

    def resultado(self) -> Resultado:
        fin = self._t_fin if self._t_fin is not None else (self._t_ult_pub or 0.0)
        return Resultado(self._estado, self._motivo, self._L, self._phi, max(0.0, fin - (self._t0 or fin)))

    def comando_efectivo(self, base: Comando) -> Comando:
        """El comando que de verdad se envió (distancia y giro integrados), para el estimador de escalas."""
        r = self.resultado()
        return Comando(r.phi_ejecutado, r.L_ejecutada, base.v, base.w, base.t_giro, base.t_avance)

    # ------------------------------------------------------------------ internos
    def _integrar(self, hasta: float) -> None:
        if self._t_ult_pub is not None:
            dt = max(0.0, hasta - self._t_ult_pub)
            self._L += self._v_ult * dt
            self._phi += self._w_ult * dt

    def _publicar(self, ahora: float, v: float, w: float, forzar: bool = False) -> bool:
        c = self._cfg
        if not forzar:
            dt = ahora - self._t_ult_pub if self._t_ult_pub is not None else c.periodo_s
            if c.a_lin_max and v > self._v_ult:
                v = min(v, self._v_ult + c.a_lin_max * dt)
            if c.a_ang_max and abs(w) > abs(self._w_ult) and w * self._w_ult >= 0:
                w = math.copysign(min(abs(w), abs(self._w_ult) + c.a_ang_max * dt), w)
        v = max(-c.v_max, min(c.v_max, v))
        w = max(-c.w_max, min(c.w_max, w))
        try:
            self._salida.publicar(v, w)
        except Exception:
            self._parar_por(Estado.ABORTADO, 'ERROR_SALIDA', ahora, publicar=False)
            return False
        self._integrar(ahora)
        self._t_ult_pub, self._v_ult, self._w_ult = ahora, v, w
        return True

    def _parar_por(self, estado: Estado, motivo: Optional[str], ahora: float, publicar: bool = True) -> Estado:
        self._estado, self._motivo = estado, motivo
        self._ceros_pendientes = max(0, self._cfg.ceros_al_abortar - 1)
        self._t_fin = ahora
        if publicar:
            try:
                self._salida.publicar(0.0, 0.0)
                self._integrar(ahora)
                self._t_ult_pub, self._v_ult, self._w_ult = ahora, 0.0, 0.0
            except Exception:
                pass
        return self._estado

    def _finalizar(self, estado: Estado, motivo: str) -> None:
        if self._estado in FINALES:
            return
        self._parar_por(estado, motivo, self._reloj())


def ejecutar_hasta_el_final(ej: EjecutorMovimiento, dormir: Callable[[float], None], periodo_s: float = 0.05,
                            max_pasos: int = 100000) -> Resultado:
    """Ayudante bloqueante para scripts y pruebas: llama a paso() cada `periodo_s` hasta terminar."""
    for _ in range(max_pasos):
        if ej.paso() in FINALES:
            break
        dormir(periodo_s)
    else:
        ej.abortar('MAX_PASOS')
    while ej._ceros_pendientes > 0:  # asegura los ceros finales tras abortar
        ej.paso()
        dormir(periodo_s)
    return ej.resultado()
