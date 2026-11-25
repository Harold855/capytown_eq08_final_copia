"""Tipos del contrato de la app del equipo y puerto del brazo.

PROVISIONAL: según docs/arquitectura/02 del repositorio del docente, la app recibe una
`PoseDock` y la pieza que trae el carrito, y devuelve un `ResultadoCambio`. Solo usa el objeto
`brazo` (puerto `BrazoJetCobot`), cuya firma real el curso aún no publica. Los métodos de abajo
son una SUPOSICIÓN razonable (mover, abrir y cerrar la pinza, soltar torque); cuando salga el
puerto oficial hay que ajustarlos en este único archivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence

Pieza = str  # 'A', 'B' o 'C'
Pose6 = Sequence[float]  # x, y, z en mm; rx, ry, rz en grados (convención de pymycobot)


@dataclass(frozen=True)
class PoseDock:
    """Pose del carrito en el dock. dx y dy en metros; dth en GRADOS (contrato del docente)."""
    dx: float
    dy: float
    dth: float


@dataclass(frozen=True)
class ResultadoCambio:
    ok: bool
    pieza_dejo: Optional[Pieza] = None  # pieza que queda en la cuna (None si no deja ninguna)
    t_cambio: Optional[float] = None    # segundos que tardó el cambio
    error: Optional[str] = None


class BrazoJetCobot(Protocol):
    """Puerto del brazo (SUPUESTO; ver el aviso del módulo)."""

    def mover_coords(self, pose: Pose6) -> bool: ...

    def abrir_pinza(self) -> bool: ...

    def cerrar_pinza(self) -> str:
        """'agarrado', 'vacia' (cerró sin pieza) o 'error'."""
        ...

    def soltar_torque(self) -> None: ...


class EstrategiaDeCambio(Protocol):
    def cambiar(self, pose: PoseDock, pieza_trae: Optional[Pieza]) -> ResultadoCambio: ...
