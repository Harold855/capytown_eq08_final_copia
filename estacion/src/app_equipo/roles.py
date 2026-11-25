"""Los cuatro roles de la estación. Un solo programa; el rol es un parámetro."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .puerto import Pieza


@dataclass(frozen=True)
class Rol:
    estacion: int
    retira: Optional[Pieza]   # pieza que trae el carrito y hay que retirar de la cuna
    coloca: Optional[Pieza]   # pieza que hay que dejar en la cuna


ROLES: Dict[int, Rol] = {
    1: Rol(1, None, 'A'),   # E1 carga A
    2: Rol(2, 'A', 'B'),    # E2 retira A y coloca B
    3: Rol(3, 'B', 'C'),    # E3 retira B y coloca C
    4: Rol(4, 'C', None),   # E4 descarga C
}
PIEZAS_POR_BANDEJA = 4
