"""Archivos de evidencia SINTÉTICOS para probar el verificador y la interfaz, incluidos los fallos conocidos (bag sin mensajes
como en RC-1, video sin cerrar, CSV vacío). Un MP4 sintético tiene la estructura de cajas correcta pero no imágenes: no es
un video reproducible."""
from __future__ import annotations

import csv
import os
import sqlite3
import struct
from typing import Dict, Iterable, Optional, Sequence

from carrito.granprix_carrito.mision import CAMPOS_PITS
from comun import yaml_estricto as ye

TOPICS_DEFECTO = {'/odom': 20.0, '/imu': 25.0, '/tag/pose': 10.0, '/pit/calibracion': 0.05, '/cmd_vel': 20.0}
TIPOS = {'/odom': 'nav_msgs/msg/Odometry', '/imu': 'sensor_msgs/msg/Imu', '/tag/pose': 'geometry_msgs/msg/PoseStamped',
         '/pit/calibracion': 'std_msgs/msg/String', '/cmd_vel': 'geometry_msgs/msg/Twist'}
DEFECTOS = ('bag_vacio', 'bag_sin_metadata', 'bag_metadata_miente', 'bag_corto', 'imu_ausente', 'video_truncado', 'video_sin_moov',
            'video_pequeno', 'sin_video_vuelta3', 'csv_sin_filas', 'sin_csv_vuelta2', 'sin_bag_vuelta4')


def _caja(tipo: bytes, carga: bytes) -> bytes:
    return struct.pack('>I4s', 8 + len(carga), tipo) + carga


def mp4_minimo(ruta: str, ancho: int = 640, alto: int = 480, fps: float = 15.0, duracion_s: float = 30.0, mdat_bytes: int = 4096,
               sin_moov: bool = False, truncar_bytes: int = 0) -> None:
    escala = 90000
    muestras = int(fps * duracion_s)
    ftyp = _caja(b'ftyp', b'isom' + struct.pack('>I', 512) + b'isomiso2mp41')
    mvhd = _caja(b'mvhd', struct.pack('>I4I', 0, 0, 0, 1000, int(duracion_s * 1000)) + b'\0' * 80)
    tkhd = _caja(b'tkhd', struct.pack('>I5I', 0, 0, 0, 1, 0, int(duracion_s * 1000)) + b'\0' * 8 + struct.pack('>4h', 0, 0, 0, 0)
                 + b'\0' * 36 + struct.pack('>II', ancho << 16, alto << 16))
    mdhd = _caja(b'mdhd', struct.pack('>I4I', 0, 0, 0, escala, int(duracion_s * escala)) + b'\0' * 4)
    hdlr = _caja(b'hdlr', struct.pack('>II', 0, 0) + b'vide' + b'\0' * 13)
    stsz = _caja(b'stsz', struct.pack('>III', 0, 0, muestras))
    trak = _caja(b'trak', tkhd + _caja(b'mdia', mdhd + hdlr + _caja(b'minf', _caja(b'stbl', stsz))))
    moov = b'' if sin_moov else _caja(b'moov', mvhd + trak)
    datos = ftyp + _caja(b'mdat', b'\0' * mdat_bytes) + moov
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, 'wb') as f:
        f.write(datos[:len(datos) - truncar_bytes] if truncar_bytes else datos)


def bag_falso(carpeta: str, topics: Dict[str, float], inicio_s: float, duracion_s: float, metadata: bool = True,
              vacios: Iterable[str] = (), metadata_cuentas: Optional[Dict[str, int]] = None) -> Dict[str, int]:
    """Crea un rosbag2 sqlite3 (`topics` nombre -> Hz). `vacios`: temas declarados sin ningún mensaje. `metadata_cuentas`: lo que
    `metadata.yaml` dice (por defecto lo real). Devuelve los mensajes reales por tema."""
    os.makedirs(carpeta, exist_ok=True)
    ruta_db = os.path.join(carpeta, 'bag_0.db3')
    if os.path.exists(ruta_db):
        os.remove(ruta_db)
    con = sqlite3.connect(ruta_db)
    con.execute('CREATE TABLE topics(id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL, serialization_format TEXT NOT NULL, '
                'offered_qos_profiles TEXT NOT NULL)')
    con.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL, timestamp INTEGER NOT NULL, data BLOB NOT NULL)')
    reales, ini_ns = {}, int(inicio_s * 1e9)
    for i, (nombre, hz) in enumerate(topics.items(), 1):
        con.execute('INSERT INTO topics VALUES (?,?,?,?,?)', (i, nombre, TIPOS.get(nombre, 'std_msgs/msg/String'), 'cdr', ''))
        n = 0 if nombre in vacios else max(1, int(round(hz * duracion_s)))
        paso = int(duracion_s * 1e9 / max(n, 1))
        con.executemany('INSERT INTO messages(topic_id, timestamp, data) VALUES (?,?,?)',
                        ((i, ini_ns + k * paso, b'\x00\x01\x00\x00cdr') for k in range(n)))
        reales[nombre] = n
    con.commit()
    con.close()
    if metadata:
        cuentas = {**reales, **(metadata_cuentas or {})}
        info = {'rosbag2_bagfile_information': {
            'version': 5, 'storage_identifier': 'sqlite3', 'relative_file_paths': ['bag_0.db3'],
            'duration': {'nanoseconds': int(duracion_s * 1e9)}, 'starting_time': {'nanoseconds_since_epoch': ini_ns},
            'message_count': sum(cuentas.values()),
            'topics_with_message_count': [{'topic_metadata': {'name': k, 'type': TIPOS.get(k, 'std_msgs/msg/String'),
                                                              'serialization_format': 'cdr', 'offered_qos_profiles': ''},
                                          'message_count': v} for k, v in cuentas.items()],
            'compression_format': '', 'compression_mode': ''}}
        with open(os.path.join(carpeta, 'metadata.yaml'), 'w', encoding='utf-8') as f:
            f.write(ye.volcar(info))
    return reales


def csv_pits(ruta: str, vuelta: int, filas: int = 4, t0: float = 1.7e9) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_PITS)
        w.writeheader()
        for e in range(1, filas + 1):
            w.writerow({**{k: '' for k in CAMPOS_PITS}, 'vuelta': vuelta, 'estacion': e, 't_llegada': t0 + 30 * e, 't_pit_s': 7.6,
                        'err_pos_pre_m': 0.02, 'err_pos_post_m': 0.01, 'valido': True})


def carpeta_simulada(raiz: str, vueltas: int = 4, inicio_s: float = 1.7e9, duracion_vuelta_s: float = 100.0,
                     defectos: Sequence[str] = (), topics: Optional[Dict[str, float]] = None, bag_unico: bool = False) -> Dict[int, float]:
    """Layout: videos/lapNN.mp4, bags/lapNN/ (o bags/tanda/), csv/lapNN_pits.csv. Devuelve el inicio (s) de cada vuelta."""
    malos = set(defectos)
    if malos - set(DEFECTOS):
        raise ValueError(f'defectos desconocidos: {sorted(malos - set(DEFECTOS))}')
    inicios = {n: inicio_s + (n - 1) * duracion_vuelta_s for n in range(1, vueltas + 1)}
    base = dict(topics or TOPICS_DEFECTO)
    for n, t0 in inicios.items():
        if not (n == 3 and 'sin_video_vuelta3' in malos):
            kw = dict(duracion_s=duracion_vuelta_s)
            if n == 1 and 'video_truncado' in malos:
                kw['truncar_bytes'] = 200
            if n == 1 and 'video_sin_moov' in malos:
                kw['sin_moov'] = True
            if n == 2 and 'video_pequeno' in malos:
                kw.update(ancho=160, alto=120, fps=5.0)
            mp4_minimo(os.path.join(raiz, 'videos', f'lap{n:02d}.mp4'), **kw)
        if not (n == 2 and 'sin_csv_vuelta2' in malos):
            csv_pits(os.path.join(raiz, 'csv', f'lap{n:02d}_pits.csv'), n, 0 if n == 4 and 'csv_sin_filas' in malos else 4, t0)
        if bag_unico or (n == 4 and 'sin_bag_vuelta4' in malos):
            continue
        t = dict(base)
        if 'imu_ausente' in malos:
            t.pop('/imu')
        dur = duracion_vuelta_s * (0.4 if n == 1 and 'bag_corto' in malos else 1.0)
        carpeta = os.path.join(raiz, 'bags', f'lap{n:02d}')
        if n == 2 and 'bag_vacio' in malos:
            reales = bag_falso(carpeta, t, t0, dur, vacios=('/odom', '/imu', '/tag/pose'), metadata_cuentas={'/odom': 2000, '/imu': 2500})
        else:
            bag_falso(carpeta, t, t0, dur, metadata=not (n == 3 and 'bag_sin_metadata' in malos),
                      metadata_cuentas={'/odom': 5} if n == 1 and 'bag_metadata_miente' in malos else None)
    if bag_unico:
        bag_falso(os.path.join(raiz, 'bags', 'tanda'), dict(base), inicio_s, duracion_vuelta_s * vueltas)
    return inicios
