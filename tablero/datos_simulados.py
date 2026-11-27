#!/usr/bin/env python3
"""Datos SIMULADOS para probar el panel sin robot: corre la misión simulada y escribe lo que el panel lee.

    python3 tablero/datos_simulados.py [--escenario normal|aprendiendo|falla] [--hasta-s 200] [--salida tablero/datos]
                                       [--evidencia bag_vacio,video_truncado] [--vivo --velocidad 20]

Escribe eventos.jsonl, pits.csv, datos.json y datos.js (este último para abrir el panel con doble clic, sin servidor). Todo lleva
`fuente: "simulado"`: el panel lo avisa en pantalla. La telemetría (batería, latencia) no se simula: queda en None.
Con --vivo avanza la simulación en tiempo real (acelerada) y reescribe datos.json cada 0.5 s, para probar la actualización a ≥ 2 Hz.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Optional, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from carrito.granprix_carrito.eventos_mision import RegistroEventos  # noqa: E402
from carrito.granprix_carrito.maquina_pit import Estado  # noqa: E402
from carrito.granprix_carrito.tablero_extension.metricas import calcular, escribir_json  # noqa: E402
from evidencia import archivos_falsos as af  # noqa: E402
from evidencia import verificar_evidencias as ve  # noqa: E402
from simulacion.mision_simulada import Mundo  # noqa: E402

ESCENARIOS = {'normal': dict(escalas_ini=(1.01, 1.09)), 'aprendiendo': dict(cd=1.0, ca=1.04, escalas_ini=(1.0, 1.0)),
              'falla': dict(escalas_ini=(1.01, 1.09))}
TERMINALES = (Estado.FIN, Estado.FALLA)


def crear_mundo(escenario: str, semilla: int, ruta_eventos: Optional[str] = None) -> Mundo:
    if escenario not in ESCENARIOS:
        raise ValueError(f'escenario debe ser uno de {sorted(ESCENARIOS)}')
    m = Mundo(semilla=semilla, **ESCENARIOS[escenario])
    if escenario == 'falla':
        m.estacion.respuesta = lambda est, ok, deja: (False, None) if est == 3 and m.mision.vuelta == 2 else (ok, deja)
    if ruta_eventos:
        m.fsm.eventos = RegistroEventos(lambda: 1.7e9 + m.t, ruta_eventos)
    return m


def paquete(m: Mundo, evidencia: Optional[dict] = None) -> dict:
    """Lo que lee el panel: métricas + los bloques que no salen de los eventos."""
    e = m.fsm.entorno
    v, w = (m.vel[-1][1], m.vel[-1][2]) if m.vel else (None, None)
    return {'fuente': 'simulado', 'generado': time.time(), 'metricas': calcular(m.fsm.eventos.eventos, m.cfg_mision, intervenciones=0),
            'telemetria': {'v': v, 'w': w, 'bateria': None, 'latencia_ms': None, 'video': None},
            'banderas': {'bandera': e.bandera, 'turno': e.autorizado, 'enlace': e.enlace, 'estaciones': dict(e.estaciones)},
            'intervenciones': {'contador': 0, 'bitacora': []}, 'evidencia': evidencia}


def informe_evidencia(defectos: Sequence[str]) -> dict:
    with tempfile.TemporaryDirectory() as d:
        af.carpeta_simulada(d, defectos=tuple(defectos))
        return ve.verificar(d, ve.cargar_spec()).a_dict()


def escribir(destino: str, datos: dict) -> None:
    escribir_json(datos, os.path.join(destino, 'datos.json'))
    tmp = os.path.join(destino, 'datos.js.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('window.DATOS = ' + json.dumps(datos, ensure_ascii=False, allow_nan=False) + ';\n')
    os.replace(tmp, os.path.join(destino, 'datos.js'))


def generar(destino: str, escenario: str = 'normal', hasta_s: Optional[float] = None, semilla: int = 0,
            defectos_evidencia: Optional[Sequence[str]] = None) -> dict:
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, 'eventos.jsonl')
    if os.path.exists(ruta):
        os.remove(ruta)
    m = crear_mundo(escenario, semilla, ruta)
    t_fin = None if hasta_s is None else m.t + hasta_s
    while m.fsm.estado not in TERMINALES and m.t < (t_fin or m.t + 1e9) and m.t < 1000.0 + 1500:
        m.paso()
    m.fsm.eventos.cerrar()
    m.mision.exportar_pits(os.path.join(destino, 'pits.csv'))
    datos = paquete(m, None if defectos_evidencia is None else informe_evidencia(defectos_evidencia))
    escribir(destino, datos)
    return datos


def vivo(destino: str, escenario: str, velocidad: float, semilla: int, cada: float = 0.5) -> None:
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, 'eventos.jsonl')
    if os.path.exists(ruta):
        os.remove(ruta)
    m = crear_mundo(escenario, semilla, ruta)
    try:
        while True:
            fin = m.t + velocidad * cada
            while m.t < fin and m.fsm.estado not in TERMINALES:
                m.paso()
            escribir(destino, paquete(m))
            if m.fsm.estado in TERMINALES:
                return
            time.sleep(cada)
    except KeyboardInterrupt:
        pass
    finally:
        m.fsm.eventos.cerrar()


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--escenario', default='normal', choices=sorted(ESCENARIOS))
    p.add_argument('--hasta-s', type=float, help='detiene la misión a estos segundos (para ver el panel "en curso")')
    p.add_argument('--salida', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datos'))
    p.add_argument('--semilla', type=int, default=0)
    p.add_argument('--evidencia', help='defectos a inyectar en una evidencia simulada, separados por comas ("" = sin defectos)')
    p.add_argument('--vivo', action='store_true')
    p.add_argument('--velocidad', type=float, default=20.0, help='segundos simulados por segundo real (con --vivo)')
    a = p.parse_args(argv)
    if a.hasta_s is not None and a.hasta_s <= 0 or a.velocidad <= 0:
        p.error('--hasta-s y --velocidad deben ser positivos')
    try:
        if a.vivo:
            vivo(a.salida, a.escenario, a.velocidad, a.semilla)
            return 0
        defectos = None if a.evidencia is None else [x for x in a.evidencia.split(',') if x]
        d = generar(a.salida, a.escenario, a.hasta_s, a.semilla, defectos)
    except (ValueError, OSError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    e = d['metricas']['estado']
    print(f'{a.salida}: estado {e["estado"]} (vuelta {e["vuelta"]}), {d["metricas"]["mision"]["pits"]} pits, '
          f'{len(d["metricas"]["eventos_recientes"])} eventos recientes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
