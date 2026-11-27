"""Estrategia de cambio de pieza: un solo programa, el rol es un parámetro.

PLANTILLA PROVISIONAL. Cumple `EstrategiaDeCambio.cambiar(pose, pieza_trae)` de
docs/arquitectura/02 del repositorio del docente. Sirve para probar la lógica y los tiempos con un
brazo simulado; no mueve nada real hasta que exista el puerto oficial y se enseñen las poses.

Principios:
- Falla cerrada: sin poses configuradas devuelve NO_CONFIGURADO y no llama al brazo.
- Valida antes de mover: pieza esperada, tolerancia de la pose, alcance de la cuna y bandeja.
- Si un paso falla no intenta maniobras de recuperación: el estado del brazo es incierto y lo
  gestiona el supervisor del curso (congela el brazo). Nunca devuelve ok sin haber terminado.
- Un límite de tiempo propio (`tiempo_max_s`); el límite real del pit (10 s) incluye al carrito.
- Solo usa el objeto `brazo`; no habla con el broker ni con el hardware.

Supuesto: `pieza_dejo` es la pieza que queda en la cuna (None en E4).
"""
from __future__ import annotations

import math
import time
from typing import Callable, List, Optional, Tuple

from .compensacion_pose import GeometriaEstacion, compensar
from .posiciones import PosesRol
from .puerto import BrazoJetCobot, Pieza, Pose6, PoseDock, ResultadoCambio
from .roles import PIEZAS_POR_BANDEJA, ROLES

Paso = Tuple[str, Callable[[], Optional[str]]]


class EstrategiaCambio:
    def __init__(self, rol: int, brazo: BrazoJetCobot, poses: Optional[PosesRol],
                 geo: GeometriaEstacion = GeometriaEstacion(), *, tol_pos_m: float = 0.04,
                 tol_ang_deg: float = 6.0, tiempo_max_s: float = 8.0,
                 reloj: Callable[[], float] = time.monotonic) -> None:
        if rol not in ROLES:
            raise ValueError(f'rol debe ser uno de {sorted(ROLES)}')
        self._rol, self._brazo, self._poses, self._geo = ROLES[rol], brazo, poses, geo
        self._tol_pos, self._tol_ang, self._tmax, self._reloj = tol_pos_m, tol_ang_deg, tiempo_max_s, reloj
        self._indice = 0  # siguiente ranura de bandeja (0 a 3)

    @property
    def indice(self) -> int:
        return self._indice

    def fijar_indice(self, indice: int) -> None:
        """Para reanudar tras un reinicio: el contrato no informa qué ranura toca."""
        if not 0 <= indice <= PIEZAS_POR_BANDEJA:
            raise ValueError('índice fuera de la bandeja')
        self._indice = indice

    # ------------------------------------------------------------------ validación
    def _validar(self, pose: PoseDock, pieza_trae: Optional[Pieza]) -> Optional[str]:
        if self._poses is None or self._poses.rol != self._rol.estacion:
            return 'NO_CONFIGURADO'
        if not all(math.isfinite(v) for v in (pose.dx, pose.dy, pose.dth)):
            return 'POSE_NO_FINITA'
        if math.hypot(pose.dx, pose.dy) > self._tol_pos or abs(pose.dth) > self._tol_ang:
            return 'FUERA_DE_TOLERANCIA'
        if pieza_trae != self._rol.retira:
            return 'PIEZA_INESPERADA'
        if self._indice >= PIEZAS_POR_BANDEJA:
            return 'BANDEJA_AGOTADA'
        if not compensar(pose, self._geo).alcanzable:
            return 'FUERA_DE_ALCANCE'
        return None

    # ------------------------------------------------------------------ pasos
    def _mover(self, pose: Pose6) -> Optional[str]:
        return None if self._brazo.mover_coords(pose) else 'MOVIMIENTO_FALLIDO'

    def _abrir(self) -> Optional[str]:
        return None if self._brazo.abrir_pinza() else 'PINZA_NO_ABRIO'

    def _cerrar(self) -> Optional[str]:
        r = self._brazo.cerrar_pinza()
        return None if r == 'agarrado' else ('AGARRE_EN_VACIO' if r == 'vacia' else 'PINZA_ERROR')

    def _plan(self, pose: PoseDock) -> List[Paso]:
        p, i = self._poses, self._indice
        assert p is not None
        dx_mm, dy_mm = (v * 1000.0 for v in compensar(pose, self._geo).delta_en_brazo)

        def cuna(base: Pose6) -> Pose6:  # la compensación solo afecta a lo que está sobre el carrito
            return (base[0] + dx_mm, base[1] + dy_mm, base[2], base[3], base[4], base[5])

        pasos: List[Paso] = []
        if self._rol.retira:
            pasos += [
                ('abrir_pinza', self._abrir),
                ('cuna_aprox', lambda: self._mover(cuna(p.cuna_aprox))),
                ('cuna_agarre', lambda: self._mover(cuna(p.cuna_agarre))),
                ('cerrar_pinza_cuna', self._cerrar),
                ('cuna_subir', lambda: self._mover(cuna(p.cuna_aprox))),
                ('recepcion_aprox', lambda: self._mover(p.recepcion_aprox[i])),
                ('recepcion_dejar', lambda: self._mover(p.recepcion_dejar[i])),
                ('abrir_pinza_recepcion', self._abrir),
                ('recepcion_subir', lambda: self._mover(p.recepcion_aprox[i])),
            ]
        if self._rol.coloca:
            pasos += [
                ('abrir_pinza_almacen', self._abrir),
                ('almacen_aprox', lambda: self._mover(p.almacen_aprox[i])),
                ('almacen_agarre', lambda: self._mover(p.almacen_agarre[i])),
                ('cerrar_pinza_almacen', self._cerrar),
                ('almacen_subir', lambda: self._mover(p.almacen_aprox[i])),
                ('cuna_aprox_colocar', lambda: self._mover(cuna(p.cuna_aprox))),
                ('cuna_dejar', lambda: self._mover(cuna(p.cuna_dejar))),
                ('abrir_pinza_cuna', self._abrir),
                ('cuna_subir_colocar', lambda: self._mover(cuna(p.cuna_aprox))),
            ]
        # El carrito no debe salir con el brazo sobre su trayectoria: pose libre al final.
        pasos.append(('pose_libre', lambda: self._mover(p.pose_libre)))
        return pasos

    # ------------------------------------------------------------------ interfaz
    def cambiar(self, pose: PoseDock, pieza_trae: Optional[Pieza]) -> ResultadoCambio:
        t0 = self._reloj()

        def fin(ok: bool, error: Optional[str] = None) -> ResultadoCambio:
            return ResultadoCambio(ok, self._rol.coloca if ok else None, self._reloj() - t0, error)

        try:
            error = self._validar(pose, pieza_trae)
            if error:
                return fin(False, error)
            for nombre, accion in self._plan(pose):
                if self._reloj() - t0 > self._tmax:
                    return fin(False, f'TIEMPO_EXCEDIDO antes de {nombre}')
                fallo = accion()
                if fallo:
                    return fin(False, f'{fallo} en {nombre}')
        except Exception as e:  # el supervisor congela el brazo; aquí solo se informa
            return fin(False, f'EXCEPCION {type(e).__name__}: {e}')
        self._indice += 1
        return fin(True)
