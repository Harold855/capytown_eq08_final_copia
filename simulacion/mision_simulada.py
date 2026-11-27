"""Misión completa simulada: máquina del pit + planta continua + estación simulada, con reloj falso a 20 Hz.

    python3 simulacion/mision_simulada.py --cd 1.01 --ca 1.09 --t-cambio 5.8 [--csv pits.csv]

La estación valida la pose con la posición VERDADERA del robot (la que el robot real no conoce), así que un acople que
solo parece bueno no pasa. Es un modelo ideal: sin retardos de cámara ni de /odom, sin deslizamiento ni zona muerta.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from carrito.granprix_carrito.acople import ConfigAcople, MedidorTag, cargar_acople  # noqa: E402
from carrito.granprix_carrito.calibracion import EstimadorEscalas  # noqa: E402
from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo  # noqa: E402
from carrito.granprix_carrito.configuracion import cargar_carrito  # noqa: E402
from carrito.granprix_carrito.docks import DOCKS_HTML, mapa_a_dock  # noqa: E402
from carrito.granprix_carrito.maquina_pit import Estado, MaquinaPit  # noqa: E402
from carrito.granprix_carrito.mision import ConfigMision, Mision, cargar_mision  # noqa: E402
from carrito.granprix_carrito.planificador import Escalas, acople_valido  # noqa: E402
from simulacion.robot_simulado import PlantaSimulada  # noqa: E402

DT = 0.05


class EstacionSimulada:
    """Recibe la solicitud, 'cambia' la pieza durante `t_cambio` s y responde. Valida con la pose verdadera."""

    def __init__(self, mundo: 'Mundo', t_cambio: float = 5.8) -> None:
        self.mundo, self.t_cambio, self.pendiente, self.respuesta = mundo, t_cambio, None, None   # respuesta(est, ok, deja) -> (ok, deja)
        self.solicitudes: List[Tuple[int, dict]] = []

    def solicitud(self, estacion: int, pose, pieza_trae) -> None:
        verdadera = mapa_a_dock(DOCKS_HTML[estacion], self.mundo.planta.pose)
        self.solicitudes.append((estacion, {'medida': pose.a_contrato(), 'verdadera': verdadera, 'pieza_trae': pieza_trae}))
        ok = acople_valido(*verdadera)
        deja = next(d for e, _, d in self.mundo.cfg_mision.piezas if e == estacion)
        ok, deja = self.respuesta(estacion, ok, deja) if self.respuesta else (ok, deja)
        self.pendiente = (self.mundo.t + self.t_cambio, estacion, ok, deja)
        self.mundo.fsm.recibir_estacion(estacion, 'CAMBIANDO')

    def avanzar(self) -> None:
        if self.pendiente and self.mundo.t >= self.pendiente[0]:
            _, estacion, ok, deja = self.pendiente
            self.pendiente = None
            self.mundo.fsm.recibir_estacion(estacion, 'LISTA')
            self.mundo.fsm.recibir_resultado(estacion, ok, deja if ok else None)


class PuertoSimulado:
    def __init__(self, mundo: 'Mundo', reset_tras_intentos: int = 0) -> None:
        self.mundo, self.eventos, self.vueltas, self.avisos, self.resets = mundo, [], [], [], 0
        self._falta = reset_tras_intentos
        self._pedido = False

    def solicitud(self, estacion, pose, pieza_trae):
        self.mundo.estacion.solicitud(estacion, pose, pieza_trae)

    def evento(self, tipo, estacion):
        self.eventos.append((self.mundo.t, tipo, estacion))

    def vuelta(self, numero, t_inicio, t_fin, estaciones):
        self.vueltas.append((numero, t_inicio, t_fin, tuple(estaciones)))

    def pedir_reset(self):
        self._pedido = True
        return True

    def resultado_reset(self):
        if not self._pedido:
            return None
        self._pedido = False
        if self._falta > 0:
            self._falta -= 1
            return False, 'ODOM_INSUFICIENTE'
        self.resets += 1
        return True, None

    def aviso(self, nivel, texto):
        self.avisos.append((self.mundo.t, nivel, texto))


class Mundo:
    def __init__(self, cfg_mision: Optional[ConfigMision] = None, cd: float = 1.01, ca: float = 1.09, t_cambio: float = 5.8,
                 escalas_ini: Tuple[float, float] = (1.0, 1.0), ruido_mov: float = 0.01, ruido_tag_m: float = 0.002,
                 ruido_tag_deg: float = 0.25, semilla: int = 0, cfg_acople: Optional[ConfigAcople] = None,
                 reset_tras_intentos: int = 0, odom_ok: Optional[Callable[[], bool]] = None, eventos=None) -> None:
        mov, est = cargar_carrito()
        self.cfg_mision = cfg_mision or cargar_mision()
        self.cfg_acople = cfg_acople or cargar_acople(None, mov)
        self.t = 1000.0
        self.planta = PlantaSimulada(DOCKS_HTML[1].pose, 1, cd, ca, ruido_mov, ruido_mov, ruido_tag_m, ruido_tag_deg, 0.0, semilla)
        self.planta.colocar_en_dock(0.0, 0.0, 0.0, 1)
        estimador = EstimadorEscalas(Escalas(*escalas_ini), robot='simulado', v_ref=mov.v_ref, w_ref=mov.w_ref)
        self.estacion = EstacionSimulada(self, t_cambio)
        self.puerto = PuertoSimulado(self, reset_tras_intentos)
        self.mision = Mision(self.cfg_mision)
        medidor = MedidorTag(lambda: self.t, lambda s: None)
        self.fsm = MaquinaPit(self.mision, mov, self.cfg_acople, CalibradorTramo(estimador), medidor, self.planta, self.puerto,
                              lambda: self.t, lambda: 1.7e9 + self.t, odom_ok, eventos)
        self.tag_visto, self.tag_activo, self.vel = 0, True, []
        publicar = self.planta.publicar

        def registrar(v, w):
            self.vel.append((self.t, v, w))
            publicar(v, w)
        self.planta.publicar = registrar
        self._ult_tag = self._ult_ext = -1.0
        self.estados: List[Tuple[float, str]] = []

    def externos(self, autorizado=True, bandera='verde', enlace=True) -> None:
        f = self.fsm
        f.recibir_turno(autorizado)
        f.recibir_bandera(bandera)
        f.recibir_enlace(enlace)

    def paso(self, externos: Optional[Callable[['Mundo'], None]] = None) -> Estado:
        if self.t - self._ult_ext >= 0.5:
            self._ult_ext = self.t
            (externos or Mundo.externos)(self)
        self.planta.estacion = self.mision.estacion
        if self.t - self._ult_tag >= 0.1:
            self._ult_tag = self.t
            pose = self.planta.medir()
            if self.tag_activo and pose is not None and pose.cerca:
                self.tag_visto += 1
                self.fsm.recibir_tag(pose)
        self.estacion.avanzar()
        antes = self.fsm.estado
        estado = self.fsm.paso()
        if estado is not antes:
            self.estados.append((self.t, estado.value))
        self.planta.avanzar(DT)
        self.t += DT
        return estado

    def correr(self, max_s: float = 900.0, externos=None) -> Estado:
        fin = self.t + max_s
        while self.t < fin and self.fsm.estado not in (Estado.FIN, Estado.FALLA):
            self.paso(externos)
        return self.fsm.estado


def resumen(m: Mundo) -> None:
    f, ms = m.fsm, m.mision
    print(f'Estado final: {f.estado.value} {f.motivo or ""} a los {m.t - 1000.0:.1f} s; vueltas cerradas: {len(ms.vueltas)}')
    print('vuelta est  t_pit  pre_cm  corr  post_cm   cd     ca   válido   motivo')
    for p in ms.pits:
        n = lambda x, k: '  -  ' if x is None else f'{x * k:5.2f}'  # noqa: E731
        print(f'{p.vuelta:5d} E{p.estacion}  {n(p.t_pit_s, 1)}  {n(p.err_pos_pre_m, 100)}  {p.correcciones:4d}  '
              f'{n(p.err_pos_post_m, 100)}  {p.cd or 0:.3f}  {p.ca or 0:.3f}  {str(p.valido):5s}  {p.motivo or ""}')
    ev = f.calibrador.evaluacion()
    print(f'Pits lentos (> {ms.cfg.tiempos.pit_max_s:g} s): {f.pits_lentos}; reducción del error: {ev.n_mejoran}/{ev.n}')


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--cd', type=float, default=1.01)
    p.add_argument('--ca', type=float, default=1.09)
    p.add_argument('--cd-ini', type=float, default=1.0, help='escala de distancia con la que arranca el estimador')
    p.add_argument('--ca-ini', type=float, default=1.0)
    p.add_argument('--t-cambio', type=float, default=5.8)
    p.add_argument('--semilla', type=int, default=0)
    p.add_argument('--csv', type=Path)
    a = p.parse_args(argv)
    m = Mundo(cd=a.cd, ca=a.ca, t_cambio=a.t_cambio, escalas_ini=(a.cd_ini, a.ca_ini), semilla=a.semilla)
    m.correr()
    resumen(m)
    if a.csv:
        m.mision.exportar_pits(str(a.csv))
    return 0 if m.fsm.estado is Estado.FIN else 1


if __name__ == '__main__':
    raise SystemExit(main())
