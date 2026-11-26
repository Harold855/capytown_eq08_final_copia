#!/usr/bin/env python3
"""Comprueba que la evidencia de la tanda EXISTE y TIENE CONTENIDO: video, rosbag2 y CSV de cada vuelta.

    python3 evidencia/verificar_evidencias.py carpeta [--spec evidencia/evidencia.yaml] [--json informe.json]

No se fía de los metadatos: el MP4 se recorre por cajas (moov, mdat, resolución, fps, duración) y los rosbag2 se cuentan mensaje a
mensaje en su SQLite, porque en RC-1 hubo bags con metadatos pero sin mensajes. Si hay `eventos.jsonl` en la carpeta se usan
los tiempos de cada vuelta para comprobar que video y bag la cubren. Código de salida: 0 sin fallas, 1 con alguna.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import re
import sqlite3
import struct
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from comun import yaml_estricto as ye  # noqa: E402

ESPEC_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'evidencia.yaml')
VERSION = 1
CONTENEDORES = (b'moov', b'trak', b'mdia', b'minf', b'stbl')


class ErrorArchivo(ValueError):
    pass


@dataclass(frozen=True)
class Requisito:
    nombre: str
    topics: Tuple[str, ...]
    hz_min: float


@dataclass(frozen=True)
class Spec:
    vueltas: int = 4
    ancho_min: int = 640
    alto_min: int = 480
    fps_min: float = 15.0
    duracion_min_s: float = 10.0
    cobertura_min: float = 0.9
    tolerancia_s: float = 5.0
    requeridos: Tuple[Requisito, ...] = (Requisito('odometria', ('/odom',), 5.0), Requisito('imu', ('/imu',), 5.0),
                                         Requisito('pose_apriltag', ('/tag/pose', '/pit/medicion'), 0.0),
                                         Requisito('escalas_cd_ca', ('/pit/calibracion',), 0.0))
    patron_csv: str = 'pit'
    filas_por_vuelta: int = 4
    col_vuelta: str = 'vuelta'
    columnas: Tuple[str, ...] = ()


def cargar_spec(ruta: str = ESPEC_DEFECTO) -> Spec:
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'evidencia', ('version', 'vueltas', 'video', 'bags', 'csv'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('evidencia: versión desconocida')
    v, b, c = ye.seccion(d, 'video', 'evidencia'), ye.seccion(d, 'bags', 'evidencia'), ye.seccion(d, 'csv', 'evidencia')
    ye.exigir_claves(v, 'evidencia.video', ('ancho_min', 'alto_min', 'fps_min', 'duracion_min_s', 'cobertura_min'))
    ye.exigir_claves(b, 'evidencia.bags', ('tolerancia_s', 'requeridos'))
    ye.exigir_claves(c, 'evidencia.csv', ('patron', 'filas_por_vuelta', 'columna_vuelta', 'columnas'))
    req = []
    for nombre, r in ye.seccion(b, 'requeridos', 'evidencia.bags').items():
        r = r if isinstance(r, dict) else {}
        ye.exigir_claves(r, f'evidencia.bags.requeridos.{nombre}', ('topics', 'hz_min'))
        topics = r['topics']
        if not isinstance(topics, list) or not topics or not all(isinstance(t, str) and t.startswith('/') for t in topics):
            raise ye.ErrorYaml(f'evidencia.bags.requeridos.{nombre}.topics: lista no vacía de tópicos que empiecen con /')
        req.append(Requisito(nombre, tuple(topics), ye.numero(r, 'hz_min', f'evidencia.bags.requeridos.{nombre}', 0)))
    if not req:
        raise ye.ErrorYaml('evidencia.bags.requeridos: no puede estar vacío')
    cols = c['columnas']
    if not isinstance(cols, list) or not all(isinstance(x, str) for x in cols):
        raise ye.ErrorYaml('evidencia.csv.columnas: debe ser una lista de textos')
    return Spec(ye.entero(d, 'vueltas', 'evidencia', 1, 10), ye.entero(v, 'ancho_min', 'evidencia.video', 1), ye.entero(v, 'alto_min', 'evidencia.video', 1),
                ye.numero(v, 'fps_min', 'evidencia.video', 0, exclusivo_min=True), ye.numero(v, 'duracion_min_s', 'evidencia.video', 0),
                ye.numero(v, 'cobertura_min', 'evidencia.video', 0, 1), ye.numero(b, 'tolerancia_s', 'evidencia.bags', 0), tuple(req),
                ye.texto(c, 'patron', 'evidencia.csv') or '', ye.entero(c, 'filas_por_vuelta', 'evidencia.csv', 1, 100),
                ye.texto(c, 'columna_vuelta', 'evidencia.csv') or 'vuelta', tuple(cols))


@dataclass(frozen=True)
class Hallazgo:
    nivel: str          # OK | AVISO | FALLA
    item: str
    detalle: str


class Informe:
    def __init__(self) -> None:
        self.hallazgos: List[Hallazgo] = []

    def add(self, nivel: str, item: str, detalle: str) -> None:
        self.hallazgos.append(Hallazgo(nivel, item, detalle))

    @property
    def fallas(self) -> List[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == 'FALLA']

    @property
    def avisos(self) -> List[Hallazgo]:
        return [h for h in self.hallazgos if h.nivel == 'AVISO']

    @property
    def ok(self) -> bool:
        return not self.fallas

    def a_dict(self) -> dict:
        return {'version': VERSION, 'ok': self.ok, 'fallas': len(self.fallas), 'avisos': len(self.avisos),
                'hallazgos': [h.__dict__ for h in self.hallazgos]}


def num_vuelta(nombre: str, estricto: bool = False) -> Optional[int]:
    """Número de vuelta del nombre (lap01, vuelta_2, v3). `estricto` (carpetas contenedoras) no acepta la `v` suelta."""
    m = re.search(r'(?i)(?<![a-z])(?:vuelta|lap' + ('' if estricto else '|v') + r')[_\- ]?0*(\d+)', nombre)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ MP4
def _hijos(buf: bytes, ini: int, fin: int):
    while ini + 8 <= fin:
        tam, tipo = struct.unpack_from('>I4s', buf, ini)
        cab = 8
        if tam == 1:
            tam, cab = struct.unpack_from('>Q', buf, ini + 8)[0], 16
        elif tam == 0:
            tam = fin - ini
        if tam < cab or ini + tam > fin:
            raise ErrorArchivo('caja corrupta dentro de moov')
        yield tipo, ini + cab, ini + tam
        ini += tam


def _buscar(buf: bytes, ini: int, fin: int, *ruta: bytes) -> Optional[Tuple[int, int]]:
    for tipo, a, b in _hijos(buf, ini, fin):
        if tipo == ruta[0]:
            return (a, b) if len(ruta) == 1 else _buscar(buf, a, b, *ruta[1:])
    return None


def _pista_video(buf: bytes, ini: int, fin: int) -> Optional[dict]:
    mdia = _buscar(buf, ini, fin, b'mdia')
    hdlr = mdia and _buscar(buf, *mdia, b'hdlr')
    if not hdlr or buf[hdlr[0] + 8:hdlr[0] + 12] != b'vide':
        return None
    tkhd, mdhd, stsz = _buscar(buf, ini, fin, b'tkhd'), _buscar(buf, *mdia, b'mdhd'), _buscar(buf, *mdia, b'minf', b'stbl', b'stsz')
    if not (tkhd and mdhd and stsz):
        raise ErrorArchivo('la pista de video no tiene tkhd, mdhd o stsz')
    v1 = buf[mdhd[0]] == 1
    escala, dur = struct.unpack_from('>IQ' if v1 else '>II', buf, mdhd[0] + (20 if v1 else 12))
    a, b = tkhd
    ancho, alto = struct.unpack_from('>II', buf, b - 8)
    return {'ancho': ancho >> 16, 'alto': alto >> 16, 'duracion_s': dur / escala if escala else 0.0,
            'muestras': struct.unpack_from('>I', buf, stsz[0] + 8)[0]}


def inspeccionar_mp4(ruta: str) -> dict:
    """{ancho, alto, fps, duracion_s, muestras, bytes_mdat}. Lanza ErrorArchivo si falta moov (grabación sin cerrar), mdat, o el archivo está cortado."""
    tam_archivo = os.path.getsize(ruta)
    if tam_archivo == 0:
        raise ErrorArchivo('archivo vacío')
    cajas, pos = {}, 0
    with open(ruta, 'rb') as f:
        while pos < tam_archivo:
            f.seek(pos)
            cab = f.read(16)
            if len(cab) < 8:
                raise ErrorArchivo('archivo cortado: caja incompleta al final')
            tam, tipo = struct.unpack_from('>I4s', cab)
            largo = 8
            if tam == 1:
                tam, largo = struct.unpack_from('>Q', cab, 8)[0], 16
            elif tam == 0:
                tam = tam_archivo - pos
            if tam < largo or pos + tam > tam_archivo:
                raise ErrorArchivo(f'archivo cortado: la caja {tipo.decode("latin1")!r} promete {tam} bytes y solo hay {tam_archivo - pos}')
            cajas.setdefault(tipo, (pos + largo, pos + tam))
            pos += tam
        if b'ftyp' not in cajas:
            raise ErrorArchivo('no es un MP4: falta la caja ftyp')
        if b'moov' not in cajas:
            raise ErrorArchivo('falta moov: la grabación no se cerró y el video no se puede reproducir')
        if b'mdat' not in cajas or cajas[b'mdat'][1] - cajas[b'mdat'][0] <= 0:
            raise ErrorArchivo('mdat vacío: el video no tiene imágenes')
        a, b = cajas[b'moov']
        f.seek(a)
        buf = f.read(b - a)
    info = None
    for tipo, ini, fin in _hijos(buf, 0, len(buf)):
        if tipo == b'trak':
            info = _pista_video(buf, ini, fin)
            if info:
                break
    if info is None:
        raise ErrorArchivo('no hay ninguna pista de video')
    info['fps'] = info['muestras'] / info['duracion_s'] if info['duracion_s'] > 0 else 0.0
    info['bytes_mdat'] = cajas[b'mdat'][1] - cajas[b'mdat'][0]
    return info


# ------------------------------------------------------------------ rosbag2
def inspeccionar_bag(carpeta: str) -> dict:
    """Cuenta los mensajes de verdad. {formato, metadata, topics{nombre: {real, meta, vacios}}, inicio_s, fin_s, problemas[(nivel, texto)]}."""
    info: dict = {'formato': None, 'metadata': False, 'topics': {}, 'inicio_s': None, 'fin_s': None, 'problemas': []}
    meta_ruta, archivos, cuentas = os.path.join(carpeta, 'metadata.yaml'), [], {}
    if os.path.exists(meta_ruta):
        try:
            m = ye.cargar_mapeo(meta_ruta)['rosbag2_bagfile_information']
            info['metadata'], info['formato'] = True, m.get('storage_identifier')
            archivos = [os.path.join(carpeta, os.path.basename(p)) for p in m.get('relative_file_paths') or []]
            cuentas = {t['topic_metadata']['name']: t['message_count'] for t in m.get('topics_with_message_count') or []}
        except (ye.ErrorYaml, KeyError, TypeError, OSError) as e:
            info['problemas'].append(('FALLA', f'metadata.yaml ilegible: {e}'))
    else:
        info['problemas'].append(('FALLA', 'sin metadata.yaml: el bag no se cerró y `ros2 bag info` no lo leerá'))
    if not archivos:
        archivos = sorted(glob.glob(os.path.join(carpeta, '*.db3')))
    if not info['formato']:
        info['formato'] = 'sqlite3' if archivos else ('mcap' if glob.glob(os.path.join(carpeta, '*.mcap')) else None)
    if info['formato'] == 'mcap':
        info['topics'] = {k: {'real': None, 'meta': v, 'vacios': 0} for k, v in cuentas.items()}
        info['problemas'].append(('AVISO', 'formato mcap: solo se comprobó metadata.yaml (no se cuentan los mensajes)'))
        return info
    if not archivos:
        info['problemas'].append(('FALLA', 'no hay ningún archivo .db3'))
        return info
    reales: Dict[str, List[int]] = {}
    ini = fin = None
    for ruta in archivos:
        if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
            info['problemas'].append(('FALLA', f'{os.path.basename(ruta)}: no existe o está vacío'))
            continue
        try:
            con = sqlite3.connect(f'file:{ruta}?mode=ro', uri=True)
            for nombre, n, t0, t1, vacios in con.execute(
                    'SELECT t.name, COUNT(m.id), MIN(m.timestamp), MAX(m.timestamp), COALESCE(SUM(LENGTH(m.data) = 0), 0) '
                    'FROM topics t LEFT JOIN messages m ON m.topic_id = t.id GROUP BY t.id'):
                r = reales.setdefault(nombre, [0, 0])
                r[0] += n
                r[1] += vacios
                if n:
                    ini, fin = min(x for x in (ini, t0) if x is not None), max(x for x in (fin, t1) if x is not None)
            con.close()
        except sqlite3.Error as e:
            info['problemas'].append(('FALLA', f'{os.path.basename(ruta)} no se puede leer: {e}'))
    for nombre in set(reales) | set(cuentas):
        r = reales.get(nombre)
        info['topics'][nombre] = {'real': None if r is None else r[0], 'meta': cuentas.get(nombre), 'vacios': 0 if r is None else r[1]}
    if ini is not None:
        info['inicio_s'], info['fin_s'] = ini / 1e9, fin / 1e9
    return info


# ------------------------------------------------------------------ verificación
def _recorrer(raiz: str):
    mp4, bags, csvs = [], [], []
    for d, dirs, files in os.walk(raiz):
        if os.path.exists(os.path.join(d, 'metadata.yaml')) or any(f.endswith(('.db3', '.mcap')) for f in files):
            bags.append(d)
            dirs[:] = []
            continue
        mp4 += [os.path.join(d, f) for f in files if f.lower().endswith('.mp4')]
        csvs += [os.path.join(d, f) for f in files if f.lower().endswith('.csv')]
    return sorted(mp4), sorted(bags), sorted(csvs)


def _por_vuelta(rutas: Sequence[str], vueltas: int) -> Tuple[Dict[int, List[str]], List[str]]:
    con, sin = {}, []
    for r in rutas:
        n = num_vuelta(os.path.basename(r.rstrip('/')))
        if n is None:
            n = num_vuelta(os.path.basename(os.path.dirname(r.rstrip('/'))), True)
        (con.setdefault(n, []) if n is not None else sin).append(r)
    return con, sin


def _videos(inf: Informe, mp4: Sequence[str], spec: Spec, ventanas: dict) -> None:
    por, sin = _por_vuelta(mp4, spec.vueltas)
    for r in sin:
        inf.add('AVISO', f'video {os.path.basename(r)}', 'sin número de vuelta en el nombre: no se puede asociar a ninguna vuelta')
    for n in range(1, spec.vueltas + 1):
        item = f'video vuelta {n}'
        archivos = por.get(n, [])
        if not archivos:
            inf.add('FALLA', item, 'no hay ningún MP4 con ese número de vuelta')
            continue
        if len(archivos) > 1:
            inf.add('AVISO', item, f'hay {len(archivos)} archivos para la misma vuelta: se revisa el primero')
        try:
            i = inspeccionar_mp4(archivos[0])
        except (ErrorArchivo, OSError, struct.error) as e:
            inf.add('FALLA', item, f'{os.path.basename(archivos[0])}: {e}')
            continue
        mal = []
        if i['ancho'] < spec.ancho_min or i['alto'] < spec.alto_min:
            mal.append(f'resolución {i["ancho"]}x{i["alto"]} (mínimo {spec.ancho_min}x{spec.alto_min})')
        if i['fps'] < spec.fps_min * 0.98:
            mal.append(f'{i["fps"]:.1f} fps (mínimo {spec.fps_min:g})')
        if i['duracion_s'] < spec.duracion_min_s:
            mal.append(f'dura {i["duracion_s"]:.1f} s (mínimo {spec.duracion_min_s:g})')
        if n in ventanas and i['duracion_s'] < spec.cobertura_min * (ventanas[n][1] - ventanas[n][0]):
            mal.append(f'dura {i["duracion_s"]:.1f} s y la vuelta {ventanas[n][1] - ventanas[n][0]:.1f} s')
        inf.add('FALLA' if mal else 'OK', item, '; '.join(mal) if mal else f'{i["ancho"]}x{i["alto"]}, {i["fps"]:.1f} fps, {i["duracion_s"]:.1f} s')


def _revisar_bag(inf: Informe, ruta: str, raiz: str, spec: Spec, ventana: Optional[Tuple[float, float]]) -> dict:
    nombre = f'bag {os.path.relpath(ruta, raiz)}'
    i = inspeccionar_bag(ruta)
    for nivel, texto in i['problemas']:
        inf.add(nivel, nombre, texto)
    mal = False
    for t, c in i['topics'].items():
        if c['real'] == 0 and (c['meta'] or 0) > 0:
            inf.add('FALLA', nombre, f'{t}: metadata.yaml dice {c["meta"]} mensajes y la base de datos no tiene ninguno (bag vacío)')
            mal = True
    for req in spec.requeridos:
        elegido = next((t for t in req.topics if (i['topics'].get(t) or {}).get('real')), None)
        if elegido is None:
            if i['formato'] == 'mcap' and any((i['topics'].get(t) or {}).get('meta') for t in req.topics):
                continue
            vistos = ', '.join(f'{t}={i["topics"][t]["real"] or 0}' for t in req.topics if t in i['topics']) or 'tópico ausente'
            inf.add('FALLA', nombre, f'sin mensajes de {req.nombre} ({vistos})')
            mal = True
            continue
        t = i['topics'][elegido]
        dur = (i['fin_s'] - i['inicio_s']) if i['inicio_s'] is not None else 0.0
        if t['vacios']:
            inf.add('FALLA', nombre, f'{elegido}: {t["vacios"]} mensajes con el contenido vacío')
            mal = True
        if req.hz_min > 0 and dur > 0 and t['real'] / dur < req.hz_min * 0.5:
            inf.add('FALLA', nombre, f'{elegido}: {t["real"] / dur:.2f} Hz (se esperaba al menos {req.hz_min:g}): faltan mensajes')
            mal = True
        if t['meta'] is not None and t['meta'] != t['real']:
            inf.add('AVISO', nombre, f'{elegido}: metadata.yaml dice {t["meta"]} mensajes y hay {t["real"]}')
    if ventana and i['inicio_s'] is not None:
        falta_ini, falta_fin = i['inicio_s'] - (ventana[0] + spec.tolerancia_s), (ventana[1] - spec.tolerancia_s) - i['fin_s']
        if falta_ini > 0 or falta_fin > 0:
            inf.add('FALLA', nombre, f'no cubre el tramo {ventana[1] - ventana[0]:.0f} s: empieza {max(falta_ini, 0):.1f} s tarde '
                                     f'y termina {max(falta_fin, 0):.1f} s antes')
            mal = True
    if not mal and not any(n == 'FALLA' for n, _ in i['problemas']):
        total = sum(t['real'] or 0 for t in i['topics'].values())
        inf.add('OK', nombre, f'{len(i["topics"])} tópicos, {total} mensajes' + ('' if i['inicio_s'] is None else f', {i["fin_s"] - i["inicio_s"]:.1f} s'))
    return i


def _bags(inf: Informe, bags: Sequence[str], raiz: str, spec: Spec, ventanas: dict) -> None:
    if not bags:
        inf.add('FALLA', 'rosbag2', 'no se encontró ningún bag (carpeta con metadata.yaml o .db3)')
        return
    por, tanda = _por_vuelta(bags, spec.vueltas)
    for n in range(1, spec.vueltas + 1):
        if n not in por and not tanda:
            inf.add('FALLA', f'bag vuelta {n}', 'no hay un bag para esta vuelta ni uno de toda la tanda')
    for n, rutas in por.items():
        if n > spec.vueltas:
            inf.add('AVISO', f'bag {os.path.basename(rutas[0])}', f'vuelta {n} fuera de las {spec.vueltas} esperadas')
        for r in rutas:
            _revisar_bag(inf, r, raiz, spec, ventanas.get(n))
    ventana_tanda = (min(v[0] for v in ventanas.values()), max(v[1] for v in ventanas.values())) if ventanas else None
    for r in tanda:
        _revisar_bag(inf, r, raiz, spec, ventana_tanda)


def _leer_csv(ruta: str) -> Tuple[List[str], List[dict]]:
    with open(ruta, newline='', encoding='utf-8-sig') as f:
        lector = csv.DictReader(f)
        return list(lector.fieldnames or []), [r for r in lector if any((v or '').strip() for v in r.values())]


def _csvs(inf: Informe, rutas: Sequence[str], spec: Spec) -> None:
    pit = [r for r in rutas if spec.patron_csv.lower() in os.path.basename(r).lower()]
    por, tanda = _por_vuelta(pit, spec.vueltas)
    cols = (spec.col_vuelta, *spec.columnas)
    filas_por_lap: Dict[int, int] = {}
    for r in [x for rs in por.values() for x in rs] + tanda:
        item = f'csv {os.path.basename(r)}'
        try:
            cab, filas = _leer_csv(r)
        except (OSError, UnicodeDecodeError, csv.Error) as e:
            inf.add('FALLA', item, f'no se puede leer: {e}')
            continue
        faltan = [c for c in cols if c not in cab]
        if faltan:
            inf.add('FALLA', item, f'faltan columnas: {", ".join(faltan)}')
            continue
        n_arch = num_vuelta(os.path.basename(r)) or (num_vuelta(os.path.basename(os.path.dirname(r)), True) if r not in tanda else None)
        for fila in filas:
            try:
                v = int(float(fila[spec.col_vuelta]))
            except (TypeError, ValueError):
                inf.add('FALLA', item, f'valor de {spec.col_vuelta} no numérico: {fila[spec.col_vuelta]!r}')
                break
            filas_por_lap[v] = filas_por_lap.get(v, 0) + 1
            if n_arch is not None and v != n_arch:
                inf.add('FALLA', item, f'el archivo es de la vuelta {n_arch} y una fila dice vuelta {v}')
                break
        else:
            inf.add('OK' if filas else 'FALLA', item, f'{len(filas)} filas' if filas else 'solo tiene el encabezado')
    if not pit:
        inf.add('FALLA', 'csv de eventos del pit', f'no hay ningún CSV cuyo nombre contenga {spec.patron_csv!r}')
        return
    for n in range(1, spec.vueltas + 1):
        if filas_por_lap.get(n, 0) < spec.filas_por_vuelta:
            inf.add('FALLA', f'eventos del pit vuelta {n}', f'{filas_por_lap.get(n, 0)} filas (se esperaban {spec.filas_por_vuelta}, una por parada)')


def verificar(raiz: str, spec: Spec = Spec(), ventanas: Optional[Dict[int, Tuple[float, float]]] = None) -> Informe:
    inf = Informe()
    if not os.path.isdir(raiz):
        inf.add('FALLA', 'carpeta', f'no existe {raiz}')
        return inf
    ventanas = dict(ventanas or {})
    ev_ruta = os.path.join(raiz, 'eventos.jsonl')
    if os.path.exists(ev_ruta):
        from carrito.granprix_carrito.eventos_mision import leer_eventos
        try:
            for e in leer_eventos(ev_ruta):
                if e.tipo == 'vuelta' and e.datos.get('numero') is not None:
                    ventanas[int(e.datos['numero'])] = (float(e.datos['t_inicio']), float(e.datos['t_fin']))
            inf.add('OK', 'eventos.jsonl', f'legible; tiempos de {len(ventanas)} vueltas para comprobar la cobertura')
        except (ValueError, OSError, KeyError, TypeError) as e:
            inf.add('FALLA', 'eventos.jsonl', str(e))
    elif not ventanas:
        inf.add('AVISO', 'cobertura', 'sin eventos.jsonl no se comprueba que el video y el bag cubran cada vuelta')
    mp4, bags, csvs = _recorrer(raiz)
    _videos(inf, mp4, spec, ventanas)
    _bags(inf, bags, raiz, spec, ventanas)
    _csvs(inf, csvs, spec)
    reg_ruta = os.path.join(raiz, 'registro_experimental.jsonl')
    if os.path.exists(reg_ruta):
        from evidencia.registro_experimental import verificar_ruta
        for p in verificar_ruta(reg_ruta, raiz) or ['íntegro']:
            inf.add('OK' if p == 'íntegro' else 'FALLA', 'registro_experimental.jsonl', p)
    return inf


def imprimir(inf: Informe) -> None:
    for h in inf.hallazgos:
        print(f'[{h.nivel:5s}] {h.item}: {h.detalle}')
    print(f'\n{"EVIDENCIA COMPLETA" if inf.ok else "EVIDENCIA INCOMPLETA"}: {len(inf.fallas)} fallas, {len(inf.avisos)} avisos')


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('carpeta')
    p.add_argument('--spec', default=ESPEC_DEFECTO)
    p.add_argument('--vueltas', type=int, help='sobrescribe las vueltas de la especificación')
    p.add_argument('--json', help='guarda el informe en este archivo (lo lee el panel)')
    a = p.parse_args(argv)
    try:
        spec = cargar_spec(a.spec)
        if a.vueltas:
            from dataclasses import replace
            spec = replace(spec, vueltas=a.vueltas)
        inf = verificar(a.carpeta, spec)
        if a.json:
            with open(a.json, 'w', encoding='utf-8') as f:
                json.dump(inf.a_dict(), f, ensure_ascii=False, indent=1)
    except (OSError, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    imprimir(inf)
    return 0 if inf.ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
