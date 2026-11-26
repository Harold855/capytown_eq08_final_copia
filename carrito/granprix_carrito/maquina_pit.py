"""Máquina de estados de la misión del ROSCar: coordina navegación, pit, acople, solicitud, recalibración y seguridad.

Estados: ESPERA -> [MIDIENDO -> ACOPLANDO -> SOLICITANDO -> ESPERANDO_RESULTADO -> RECALIBRANDO -> SALIENDO -> NAVEGANDO] x 16 -> FIN;
cualquier estado activo puede pasar a FALLA, que es terminal hasta `reiniciar()`. Se llama a `paso()` a ~20 Hz desde un solo hilo.

La seguridad de NUESTRA lógica (no sustituye al vigilante de red, a twist_mux ni a la parada física del curso):
- todo movimiento pasa por `SalidaSegura`: solo sale velocidad en NAVEGANDO y ACOPLANDO, con turno autorizado, bandera
  verde, enlace vivo y sin intercambio en curso; en cualquier otro caso sale cero;
- en los estados quietos se publican ceros en cada paso (FALLA y FIN, hasta que alguien reinicie);
- cada estado tiene plazo; un error inesperado también termina en FALLA.
Todo lo externo entra por `recibir_*` y toda salida hacia el curso sale por el `Puerto`.
"""
from __future__ import annotations

import time
from dataclasses import asdict
from enum import Enum
from typing import Callable, Dict, Optional, Protocol, Tuple

from geometria_dock.transformaciones import Pose2D

from .acople import ConfigAcople, MedidorTag, ResultadoAcople, acoplar_pasos, mover_con_ejecutor
from .calibracion_tramo import CalibradorTramo
from .configuracion import ConfigMovimiento
from .docks import DOCKS_HTML
from .eventos_mision import RegistroEventos
from .ejecutor import Estado as EstadoMov
from .ejecutor import EjecutorMovimiento, Salida
from .mision import Mision, RegistroPit
from .planificador import comandar, planificar_tramo
from .pose_dock import PoseDock


class Estado(Enum):
    ESPERA = 'ESPERA'
    NAVEGANDO = 'NAVEGANDO'
    MIDIENDO = 'MIDIENDO'
    ACOPLANDO = 'ACOPLANDO'
    SOLICITANDO = 'SOLICITANDO'
    ESPERANDO_RESULTADO = 'ESPERANDO_RESULTADO'
    RECALIBRANDO = 'RECALIBRANDO'
    SALIENDO = 'SALIENDO'
    FIN = 'FIN'
    FALLA = 'FALLA'


E = Estado
TRANSICIONES = {E.ESPERA: {E.MIDIENDO}, E.NAVEGANDO: {E.MIDIENDO}, E.MIDIENDO: {E.ACOPLANDO}, E.ACOPLANDO: {E.SOLICITANDO},
                E.SOLICITANDO: {E.ESPERANDO_RESULTADO}, E.ESPERANDO_RESULTADO: {E.RECALIBRANDO},
                E.RECALIBRANDO: {E.SALIENDO}, E.SALIENDO: {E.NAVEGANDO, E.FIN}, E.FIN: {E.ESPERA}, E.FALLA: {E.ESPERA}}
INACTIVOS = (E.ESPERA, E.FIN, E.FALLA)
MOVIMIENTO = (E.NAVEGANDO, E.ACOPLANDO)
QUIETOS = tuple(e for e in Estado if e not in MOVIMIENTO and e is not E.ESPERA)     # aquí se publican ceros en cada paso


class Puerto(Protocol):
    """Salidas hacia el curso. El adaptador ROS las traduce al contrato MQTT; no hay puente MQTT propio."""
    def solicitud(self, estacion: int, pose: PoseDock, pieza_trae: Optional[str]) -> None: ...
    def evento(self, tipo: str, estacion: int) -> None: ...
    def vuelta(self, numero: int, t_inicio: float, t_fin: float, estaciones: Tuple[int, ...]) -> None: ...
    def pedir_reset(self) -> bool: ...
    def resultado_reset(self) -> Optional[Tuple[bool, Optional[str]]]: ...
    def aviso(self, nivel: str, texto: str) -> None: ...


class Entorno:
    """Lo último que se supo del mundo. `None` = nunca llegó (la seguridad falla cerrada)."""

    def __init__(self) -> None:
        self.reiniciar()

    def reiniciar(self) -> None:
        self.autorizado: Optional[bool] = None
        self.bandera: Optional[str] = None
        self.enlace: Optional[bool] = None
        self.t_enlace: Optional[float] = None
        self.estaciones: Dict[int, str] = {}
        self.intercambio = False
        self.parada = False
        self.t_inicio: Optional[float] = None


class Seguridad:
    def __init__(self, mision: Mision, entorno: Entorno, reloj: Callable[[], float]) -> None:
        self._m, self.e, self._reloj = mision, entorno, reloj

    def motivo(self) -> Optional[str]:
        e, s, t = self.e, self._m.cfg.seguridad, self._reloj()
        if e.parada:
            return 'PARADA_MANUAL'
        if s.requiere_autorizacion and e.autorizado is not True:
            return 'SIN_AUTORIZACION'
        if e.bandera == 'roja':
            return 'BANDERA_ROJA'
        if s.requiere_enlace and not (e.enlace is True and e.t_enlace is not None and t - e.t_enlace <= s.enlace_max_s):
            return 'ENLACE_PERDIDO'
        if s.estacion_offline_aborta and e.estaciones.get(self._m.estacion) == 'OFFLINE':
            return 'ESTACION_OFFLINE'
        if e.t_inicio is not None and t - e.t_inicio > self._m.cfg.tiempos.tanda_max_s:
            return 'TANDA_AGOTADA'
        return None

    def intercambio(self) -> bool:
        return self.e.intercambio or 'CAMBIANDO' in self.e.estaciones.values()

    def puede_mover(self, estado: Estado) -> bool:
        return estado in MOVIMIENTO and not self.intercambio() and self.motivo() is None


class SalidaSegura:
    def __init__(self, salida: Salida, permitido: Callable[[], bool]) -> None:
        self._salida, self._permitido = salida, permitido

    def publicar(self, v: float, w: float) -> None:
        self._salida.publicar(*((v, w) if self._permitido() else (0.0, 0.0)))


class MaquinaPit:
    def __init__(self, mision: Mision, mov: ConfigMovimiento, cfg_acople: ConfigAcople, calibrador: CalibradorTramo,
                 medidor: MedidorTag, salida: Salida, puerto: Puerto, reloj: Callable[[], float] = time.monotonic,
                 reloj_ts: Callable[[], float] = time.time, odom_ok: Optional[Callable[[], bool]] = None,
                 eventos: Optional[RegistroEventos] = None) -> None:
        self.mision, self.mov, self.cfg_acople, self.calibrador, self.medidor = mision, mov, cfg_acople, calibrador, medidor
        self.puerto, self.reloj, self.reloj_ts, self.odom_ok = puerto, reloj, reloj_ts, odom_ok
        self.eventos = eventos if eventos is not None else RegistroEventos(reloj_ts)
        self.entorno = Entorno()
        self.seg = Seguridad(mision, self.entorno, reloj)
        self.raw = salida
        self.salida = SalidaSegura(salida, lambda: self.seg.puede_mover(self.estado))
        self._mover = mover_con_ejecutor(self.salida, reloj, None, mov.ejecutor, cfg_acople, odom_ok, self._debe_parar,
                                         medidor.en_reposo)
        self._t = reloj()
        self.estado, self.motivo, self.t_estado, self.pits_lentos, self.ignorados = Estado.ESPERA, None, self._t, 0, 0
        self._limpiar()
        self._manejadores = {E.ESPERA: self._espera, E.NAVEGANDO: self._navegando, E.MIDIENDO: self._midiendo,
                             E.ACOPLANDO: self._acoplando, E.SOLICITANDO: self._solicitando,
                             E.ESPERANDO_RESULTADO: self._esperando, E.RECALIBRANDO: self._recalibrando,
                             E.SALIENDO: self._saliendo}

    # ------------------------------------------------------------------ entradas
    def _entrada(self, campo: str, antes: object, ahora: object) -> None:
        if antes != ahora:
            self._ev('entrada', campo=campo, antes=antes, ahora=ahora)

    def recibir_turno(self, autorizado: bool) -> None:
        self._entrada('turno', self.entorno.autorizado, bool(autorizado))
        self.entorno.autorizado = bool(autorizado)

    def recibir_bandera(self, bandera: str) -> None:
        self._entrada('bandera', self.entorno.bandera, bandera)
        self.entorno.bandera = bandera

    def recibir_enlace(self, ok: bool) -> None:
        self._entrada('enlace', self.entorno.enlace, bool(ok))
        self.entorno.enlace, self.entorno.t_enlace = bool(ok), self.reloj()

    def recibir_estacion(self, estacion: int, estado: str) -> None:
        self._entrada(f'estacion{estacion}', self.entorno.estaciones.get(estacion), estado)
        self.entorno.estaciones[estacion] = estado

    def recibir_tag(self, pose: PoseDock) -> None:
        self.medidor.agregar(pose)

    def recibir_resultado(self, estacion: int, ok: bool, pieza_dejo: Optional[str]) -> bool:
        if self.estado is not E.ESPERANDO_RESULTADO or estacion != self.mision.estacion or self._res is not None:
            self.ignorados += 1
            self._ev('ignorado', estacion_resultado=estacion, ok=ok)
            return False
        self._res = (bool(ok), pieza_dejo)
        self._ev('resultado', ok=bool(ok), pieza_dejo=pieza_dejo)
        return True

    def parar(self, motivo: str = 'PARADA_MANUAL') -> None:
        if self.estado not in INACTIVOS:
            self._fallar(motivo)

    def reiniciar(self) -> bool:
        """Vuelve a ESPERA con la misión desde cero (las escalas aprendidas se conservan). Solo desde ESPERA, FIN o FALLA."""
        if self.estado not in INACTIVOS:
            return False
        self.mision.reiniciar()
        self.entorno.reiniciar()
        self._limpiar()
        self.motivo, self.estado, self.t_estado = None, E.ESPERA, self.reloj()
        return True

    # ------------------------------------------------------------------ ciclo
    def paso(self) -> Estado:
        self._t = t = self.reloj()
        try:
            if self.estado not in INACTIVOS:
                motivo = self.seg.motivo() or self._plazo(t)
                if motivo:
                    self._fallar(motivo)
            if self.estado in self._manejadores:
                self._manejadores[self.estado](t)
            if self.estado in QUIETOS:
                self.raw.publicar(0.0, 0.0)
        except Exception as ex:      # un error nuestro nunca deja al robot con la última orden
            self._fallar(f'ERROR_INTERNO: {type(ex).__name__}: {ex}')
        return self.estado

    def instantanea(self) -> dict:
        esc = self.calibrador.estimador.escalas
        return {'estado': self.estado.value, 'motivo': self.motivo, 'vuelta': min(self.mision.vuelta, self.mision.cfg.vueltas),
                'estacion': self.mision.estacion, 'pieza': self.pieza, 'pits': len(self.mision.pits),
                'pits_lentos': self.pits_lentos, 'pits_invalidos': self.mision.pits_invalidos,
                'cd': esc.cd, 'ca': esc.ca, 'ignorados': self.ignorados}

    # ------------------------------------------------------------------ internos
    def _limpiar(self) -> None:
        self.ej: Optional[EjecutorMovimiento] = None
        self._gen = None
        self._cmd = None
        self._reg: Optional[RegistroPit] = None
        self._acople: Optional[ResultadoAcople] = None
        self._res: Optional[Tuple[bool, Optional[str]]] = None
        self._post: Optional[PoseDock] = None
        self._pose_salida: Optional[Pose2D] = None
        self._lim_nav = 0.0
        self._t_freno = self._t
        self.pieza: Optional[str] = None
        self._sub()

    def _sub(self) -> None:
        self._post_omitida, self._reset_pedido, self._reset_listo, self._reset_n, self._reset_desde = False, False, False, 0, 0.0

    def _debe_parar(self) -> bool:
        return not self.seg.puede_mover(self.estado)

    def _ev(self, tipo: str, motivo: Optional[str] = None, estacion: Optional[int] = None, vuelta: Optional[int] = None,
            fila: Optional[dict] = None, **datos: object) -> None:
        try:
            self.eventos.registrar(tipo, self.estado.value, vuelta or min(self.mision.vuelta, self.mision.cfg.vueltas),
                                   estacion or self.mision.estacion, motivo, {**(fila or {}), **datos})
        except Exception:          # registrar nunca debe detener al robot
            pass

    def _aviso(self, nivel: str, texto: str) -> None:
        self._ev('aviso', nivel=nivel, texto=texto)
        self.puerto.aviso(nivel, texto)

    def _ir(self, nuevo: Estado) -> None:
        if nuevo is not E.FALLA and nuevo not in TRANSICIONES[self.estado]:
            raise RuntimeError(f'transición no permitida: {self.estado.value} -> {nuevo.value}')
        antes = self.estado
        self.estado, self.t_estado = nuevo, self._t
        self._ev('estado', de=antes.value)

    def _plazo(self, t: float) -> Optional[str]:
        ti = self.mision.cfg.tiempos
        limite = {E.NAVEGANDO: self._lim_nav, E.MIDIENDO: ti.midiendo_s, E.ACOPLANDO: ti.acoplando_s,
                  E.SOLICITANDO: ti.solicitando_s, E.ESPERANDO_RESULTADO: ti.esperando_resultado_s,
                  E.RECALIBRANDO: ti.recalibrando_s, E.SALIENDO: ti.saliendo_s}.get(self.estado)
        return f'TIMEOUT_{self.estado.value}' if limite and t - self.t_estado > limite else None

    def _fallar(self, motivo: str) -> None:
        if self.estado is E.FALLA:
            return
        if self.ej is not None and not self.ej.terminado:
            self.ej.abortar('FALLA')
        if self._gen is not None:
            self._gen.close()
            self._gen = None
        try:
            self.raw.publicar(0.0, 0.0)
        except Exception as ex:
            self._aviso('error', f'no se pudo publicar el cero: {ex}')
        if self._reg is not None and self._reg.valido is None:
            self._reg.valido, self._reg.motivo = False, motivo
        self.motivo = motivo
        self._ir(E.FALLA)
        self._ev('falla', motivo)
        self._aviso('error', f'FALLA: {motivo}')

    # ------------------------------------------------------------------ estados
    def _espera(self, t: float) -> None:
        if self.seg.motivo() is None:
            self.entorno.t_inicio = t
            self._ev('inicio')
            self._entrar_pit(t)

    def _entrar_pit(self, t: float) -> None:
        self._t_freno = t
        self._reg = self.mision.abrir_pit(self.reloj_ts())
        self._acople, self._res, self._post = None, None, None
        self.medidor.en_reposo()
        self._ir(E.MIDIENDO)

    def _midiendo(self, t: float) -> None:
        pose = self.medidor.intentar()
        if pose is not None:
            c = self.cfg_acople
            self._gen = acoplar_pasos(self.medidor.esperar, self._mover, c, self.calibrador.estimador.escalas, self.reloj,
                                      self._debe_parar, pose)
            self._ir(E.ACOPLANDO)

    def _acoplando(self, t: float) -> None:
        try:
            next(self._gen)
            return
        except StopIteration as fin:
            res = fin.value
        self._gen, self._acople, reg = None, res, self._reg
        reg.correcciones, reg.reintentos = res.correcciones, max(0, res.correcciones - 1)
        for _ in range(reg.reintentos):
            self.puerto.evento('reintento', self.mision.estacion)
        for pose, lado in ((res.pose_inicial, 'pre'), (res.pose_final, 'post')):
            if pose is not None:
                pos, ang = pose.error
                setattr(reg, f'err_pos_{lado}_m', pos)
                setattr(reg, f'err_ang_{lado}_deg', ang)
        self._ev('acople', res.motivo, correcciones=res.correcciones, exito=res.exito, err_pos_pre_m=reg.err_pos_pre_m,
                 err_pos_post_m=reg.err_pos_post_m, duracion_s=res.duracion_s)
        if not res.exito:
            self._fallar(f'ACOPLE_{res.motivo}')
        else:
            self._ir(E.SOLICITANDO)

    def _solicitando(self, t: float) -> None:
        if self.seg.intercambio():
            return
        self.puerto.solicitud(self.mision.estacion, self._acople.pose_final, self.mision.pieza_trae)
        self._ev('solicitud', pieza_trae=self.mision.pieza_trae, **self._acople.pose_final.a_contrato())
        self.entorno.intercambio = True
        self._ir(E.ESPERANDO_RESULTADO)

    def _esperando(self, t: float) -> None:
        if self._res is None:
            return
        ok, pieza = self._res
        if not ok:
            self._fallar('RESULTADO_NO_OK')
            return
        self.entorno.intercambio = False
        self.medidor.en_reposo(0.0)      # el robot no se movió: bastan lecturas posteriores al resultado
        self._sub()
        self._ir(E.RECALIBRANDO)

    def _recalibrando(self, t: float) -> None:
        ti = self.mision.cfg.tiempos
        if self._post is None and not self._post_omitida:
            self._post = self.medidor.intentar()
            if self._post is None and t - self.t_estado < ti.medicion_post_s:
                return
            self._post_omitida = self._post is None
            if self._post_omitida:
                self._aviso('aviso', 'sin segunda medición del tag: se usa la última del acople')
        if not self._reset_listo and t >= self._reset_desde:
            if not self._reset_pedido:
                if self.puerto.pedir_reset():
                    self._reset_pedido = True
                else:
                    self._aviso('aviso', 'reset de pose no disponible: se sigue sin él')
                    self._reset_listo = True
                return
            r = self.puerto.resultado_reset()
            if r is None:
                return
            self._reset_pedido = False
            if not r[0] and r[1] == 'ODOM_INSUFICIENTE' and self._reset_n < ti.reset_reintentos:
                self._reset_n += 1
                self._reset_desde = t + ti.reset_espera_s
                return
            self._ev('reset', r[1], aceptado=r[0], intentos=self._reset_n + 1)
            if not r[0]:
                self._aviso('aviso', f'reset de pose rechazado: {r[1]}')
            self._reset_listo = True
        if self._reset_listo:
            self._cerrar_pit()

    def _cerrar_pit(self) -> None:
        m, ts, reg = self.mision, self.reloj_ts(), self._reg
        est = m.estacion
        parada = self.calibrador.cerrar_parada(est, self._acople, self._post, m.vuelta, ts)
        reg.err_pos_post_m, reg.err_ang_post_deg, reg.cd, reg.ca = parada.err_pos_post_m, parada.err_ang_post_deg, parada.cd, parada.ca
        final = self._post if self._post is not None else self._acople.pose_final
        self._pose_salida = final.mapa
        ok, pieza = self._res
        pit, vuelta = m.cerrar_pit(ok, pieza, ts)
        self._ev('pit_cerrado', pit.motivo, estacion=est, vuelta=pit.vuelta, valido=pit.valido, pieza_recibida=pieza)
        if pit.valido:
            self.pieza = pieza
            self.puerto.evento('pit_ok', est)
        else:
            self._aviso('aviso', f'pit E{est} con {pit.motivo}: esperada {pit.pieza_esperada!r}, recibida {pieza!r}')
        if vuelta is not None:
            self._ev('vuelta', vuelta=vuelta.numero, numero=vuelta.numero, t_inicio=vuelta.t_inicio, t_fin=vuelta.t_fin,
                     estaciones=list(vuelta.estaciones))
            self.puerto.vuelta(vuelta.numero, vuelta.t_inicio, vuelta.t_fin, vuelta.estaciones)
        self._ir(E.SALIENDO)

    def _medir_pit(self, t: float) -> None:
        self._reg.t_pit_s = t - self._t_freno
        fila = asdict(self._reg)
        self._ev('pit', estacion=fila['estacion'], vuelta=fila['vuelta'], fila=fila)
        self.pits_lentos += self._reg.t_pit_s > self.mision.cfg.tiempos.pit_max_s

    def _saliendo(self, t: float) -> None:
        if self.mision.completa:
            self._medir_pit(t)
            self._ir(E.FIN)
            self._ev('fin')
            self._aviso('info', 'misión completa')
            return
        if self.seg.intercambio():
            return
        destino = DOCKS_HTML[self.mision.estacion]
        mov = self.mov
        cmd = comandar(planificar_tramo(self._pose_salida, (destino.x, destino.y)), self.calibrador.estimador.escalas,
                       mov.v_ref, mov.w_ref, mov.v_max, mov.w_max)
        ej = EjecutorMovimiento(self.salida, self.reloj, mov.ejecutor, self.odom_ok, self._debe_parar)
        ej.iniciar(cmd)
        self.ej, self._cmd = ej, cmd
        c = mov.ejecutor
        self._lim_nav = cmd.t_total + c.pausa_s + c.asentamiento_s + self.mision.cfg.tiempos.navegando_margen_s
        self._medir_pit(t)
        self._ir(E.NAVEGANDO)

    def _navegando(self, t: float) -> None:
        estado = self.ej.paso()
        if estado is EstadoMov.COMPLETO:
            self.calibrador.comando(self.ej.comando_efectivo(self._cmd))
            self.ej = None
            self._entrar_pit(t)
        elif self.ej.terminado:
            self._fallar(f'MOVIMIENTO_{self.ej.motivo or estado.name}')
