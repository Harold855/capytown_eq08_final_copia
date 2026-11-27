"""Eventos que genera NUESTRA lógica de misión, con un formato único: una línea JSON por evento (JSONL).

Es la fuente de `cronometro.py` y `metricas.py`. Registrar nunca debe detener al robot: si el disco falla se sigue en memoria
y queda anotado en `error_escritura`. Un corte a mitad de escritura deja a lo sumo la última línea incompleta, que `leer_eventos`
descarta. No sustituye al `grabador` del curso (video, rosbag2): es el registro de lo que decidió nuestra máquina.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

TIPOS = ('inicio', 'estado', 'entrada', 'acople', 'solicitud', 'resultado', 'ignorado', 'reset', 'pit_cerrado', 'pit', 'vuelta',
         'aviso', 'falla', 'fin')
DURABLES = ('falla', 'fin', 'vuelta')      # estos fuerzan fsync


@dataclass(frozen=True)
class Evento:
    ts: float
    tipo: str
    estado: Optional[str] = None
    vuelta: Optional[int] = None
    estacion: Optional[int] = None
    motivo: Optional[str] = None
    datos: Dict[str, Any] = field(default_factory=dict)

    def a_dict(self) -> dict:
        return {'ts': self.ts, 'tipo': self.tipo, 'estado': self.estado, 'vuelta': self.vuelta, 'estacion': self.estacion,
                'motivo': self.motivo, 'datos': self.datos}

    @classmethod
    def desde_dict(cls, d: dict) -> 'Evento':
        if not isinstance(d, dict) or d.get('tipo') not in TIPOS or not isinstance(d.get('ts'), (int, float)) \
                or isinstance(d['ts'], bool) or not math.isfinite(d['ts']):
            raise ValueError(f'evento inválido: {d!r}')
        datos = d.get('datos') or {}
        if not isinstance(datos, dict):
            raise ValueError('datos debe ser un objeto')
        return cls(float(d['ts']), d['tipo'], d.get('estado'), d.get('vuelta'), d.get('estacion'), d.get('motivo'), datos)


def _limpio(x: Any) -> Any:
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {str(k): _limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_limpio(v) for v in x]
    return x if x is None or isinstance(x, (bool, int, str)) else str(x)


class RegistroEventos:
    def __init__(self, reloj_ts: Callable[[], float] = time.time, ruta: Optional[str] = None, maximo: int = 50000) -> None:
        self._reloj, self._ruta, self._f = reloj_ts, ruta, None
        self._mem: Deque[Evento] = deque(maxlen=maximo)
        self.error_escritura: Optional[str] = None
        if ruta:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
                self._f = open(ruta, 'a', encoding='utf-8')
            except OSError as e:
                self.error_escritura = str(e)

    @property
    def eventos(self) -> List[Evento]:
        return list(self._mem)

    def registrar(self, tipo: str, estado: Optional[str] = None, vuelta: Optional[int] = None, estacion: Optional[int] = None,
                  motivo: Optional[str] = None, datos: Optional[dict] = None) -> Evento:
        if tipo not in TIPOS:
            raise ValueError(f'tipo de evento desconocido: {tipo!r}')
        ev = Evento(self._reloj(), tipo, estado, vuelta, estacion, motivo, _limpio(datos or {}))
        self._mem.append(ev)
        if self._f is not None:
            try:
                self._f.write(json.dumps(ev.a_dict(), separators=(',', ':'), allow_nan=False) + '\n')
                self._f.flush()
                if tipo in DURABLES:
                    os.fsync(self._f.fileno())
            except (OSError, ValueError) as e:
                self.error_escritura, self._f = str(e), None
        return ev

    def cerrar(self) -> None:
        if self._f is not None:
            self._f.close()
            self._f = None


def leer_eventos(ruta: str) -> List[Evento]:
    """Lee un JSONL. La última línea incompleta (corte de energía) se descarta; una línea mala en medio es un error."""
    with open(ruta, encoding='utf-8') as f:
        lineas = f.read().split('\n')
    if lineas and lineas[-1] == '':
        lineas.pop()
    out = []
    for i, linea in enumerate(lineas):
        try:
            out.append(Evento.desde_dict(json.loads(linea)))
        except ValueError as e:
            if i == len(lineas) - 1:
                break
            raise ValueError(f'{ruta}, línea {i + 1}: {e}') from e
    return out
