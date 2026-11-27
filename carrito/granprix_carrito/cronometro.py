"""Tiempos de vueltas, sectores y pits calculados desde los eventos de la misión (por si la base no los ofrece).

Vuelta = desde la llegada a E1 hasta el fin del pit de E4 (la misma que se publica en `vuelta`). Los cuatro sectores suman
exactamente la vuelta: S1 llegada E1 -> llegada E2, S2 E2 -> E3, S3 E3 -> E4 y S4 llegada E4 -> fin de su pit (cada sector
incluye el pit de su estación de salida). Un dato que falta queda en None y nunca se inventa.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .eventos_mision import Evento


@dataclass(frozen=True)
class VueltaTiempo:
    numero: int
    t_inicio: float
    t_fin: float
    duracion: float
    sectores: Tuple[Optional[float], ...]       # 4
    pits: Tuple[Optional[float], ...]           # 4, tiempo de pit por estación
    valida: bool


def _resta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    return None if a is None or b is None else a - b


def vueltas_desde_eventos(eventos: Sequence[Evento]) -> List[VueltaTiempo]:
    llegadas: Dict[Tuple[int, int], float] = {}
    pits: Dict[Tuple[int, int], dict] = {}
    cierres: List[Evento] = []
    for e in eventos:
        if e.tipo == 'estado' and e.estado == 'MIDIENDO' and e.vuelta and e.estacion:
            llegadas.setdefault((e.vuelta, e.estacion), e.ts)
        elif e.tipo == 'pit':
            pits[(e.datos.get('vuelta'), e.datos.get('estacion'))] = e.datos
        elif e.tipo == 'vuelta':
            cierres.append(e)
    out = []
    for c in cierres:
        n, t_ini, t_fin = c.datos.get('numero'), c.datos.get('t_inicio'), c.datos.get('t_fin')
        if None in (n, t_ini, t_fin):
            continue
        llegada = [llegadas.get((n, s)) for s in (1, 2, 3, 4)]
        sectores = (_resta(llegada[1], llegada[0]), _resta(llegada[2], llegada[1]), _resta(llegada[3], llegada[2]),
                    _resta(t_fin, llegada[3]))
        por_estacion = [pits.get((n, s)) for s in (1, 2, 3, 4)]
        out.append(VueltaTiempo(n, t_ini, t_fin, t_fin - t_ini, sectores,
                                tuple(p.get('t_pit_s') if p else None for p in por_estacion),
                                all(p is not None and p.get('valido') is True for p in por_estacion)))
    return out


def resumen_vueltas(vueltas: Sequence[VueltaTiempo]) -> dict:
    """Última, mejor y delta como en el tablero (delta = última − mejor)."""
    if not vueltas:
        return {'ultima': None, 'mejor': None, 'delta': None, 'media': None}
    d = [v.duracion for v in vueltas]
    return {'ultima': d[-1], 'mejor': min(d), 'delta': d[-1] - min(d), 'media': sum(d) / len(d)}


def tramos_desde_eventos(eventos: Sequence[Evento]) -> List[Tuple[int, int, float]]:
    """(vuelta, estación de destino, duración) de cada tramo: del inicio de NAVEGANDO a la llegada (MIDIENDO)."""
    salida, out = None, []
    for e in eventos:
        if e.tipo == 'estado' and e.estado == 'NAVEGANDO':
            salida = e.ts
        elif e.tipo == 'estado' and e.estado == 'MIDIENDO' and salida is not None:
            out.append((e.vuelta, e.estacion, e.ts - salida))
            salida = None
        elif e.tipo == 'estado' and e.estado == 'FALLA':
            salida = None
    return out
