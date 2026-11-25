"""Brazo simulado para probar la estrategia sin hardware ni broker.

Registra cada llamada y avanza un reloj falso con duraciones configurables, de modo que también
sirve para estimar el presupuesto de tiempo de un cambio (con duraciones medidas en el brazo real).
Las duraciones por defecto son PLACEHOLDERS, no mediciones.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .puerto import Pose6


class RelojFalso:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def avanzar(self, s: float) -> None:
        self.t += s


class BrazoSimulado:
    def __init__(self, reloj: Optional[RelojFalso] = None, dur_mover: float = 1.0, dur_pinza: float = 0.4,
                 agarre: str = 'agarrado', fallar_en: Optional[int] = None, lanzar_en: Optional[int] = None) -> None:
        self.reloj = reloj or RelojFalso()
        self.dur_mover, self.dur_pinza, self.agarre = dur_mover, dur_pinza, agarre
        self.fallar_en, self.lanzar_en = fallar_en, lanzar_en
        self.llamadas: List[Tuple[str, tuple]] = []

    def _llamada(self, nombre: str, args: tuple, duracion: float) -> bool:
        n = len(self.llamadas)
        self.llamadas.append((nombre, args))
        if self.lanzar_en == n:
            raise RuntimeError('fallo simulado del brazo')
        self.reloj.avanzar(duracion)
        return self.fallar_en != n

    def mover_coords(self, pose: Pose6) -> bool:
        return self._llamada('mover_coords', tuple(pose), self.dur_mover)

    def abrir_pinza(self) -> bool:
        return self._llamada('abrir_pinza', (), self.dur_pinza)

    def cerrar_pinza(self) -> str:
        ok = self._llamada('cerrar_pinza', (), self.dur_pinza)
        return self.agarre if ok else 'error'

    def soltar_torque(self) -> None:
        self._llamada('soltar_torque', (), 0.0)

    def nombres(self) -> List[str]:
        return [n for n, _ in self.llamadas]
