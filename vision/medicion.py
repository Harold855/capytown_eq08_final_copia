"""Medición de la pose de un AprilTag con una cámara calibrada: calidad, agregación, filtro y evidencia.

Une lo que ya existe (herramienta del docente, calibración de cámara y corrección de distorsión) en una sola
medición que se puede USAR: una pose solo se entrega si el tag es único, tiene la calidad pedida y, si se agrega,
es estable entre cuadros. Ante cualquier duda devuelve "no válida" con el motivo y NUNCA una pose conjeturada.

Pose en el sistema de la cámara, como la herramienta del docente: x a la derecha, y hacia abajo, z hacia adelante,
en METROS; `dth` en GRADOS (giro del tag alrededor del eje vertical de la cámara; 0 = de frente). Esta pose NO
está en el marco del dock: falta el montaje de la cámara en el carrito y `dock_frames.yaml`.

Los umbrales de calidad (margen, hamming, dispersión) son PROVISIONALES: en simulación una detección sana da un
margen de 105 a 120 y con poca luz baja a 23-47, pero no se han medido con la cámara real. Cada medición guarda su
margen y su hamming para ajustarlos con datos del laboratorio.
"""
from __future__ import annotations

import csv
import datetime
import math
import statistics
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterator, List, Optional, Sequence, Tuple

from . import herramienta as hv
from .calibracion_focal import cargar_camara, focal_desde_fov

ht = hv.ht
MARGEN_MIN_DEFECTO = 30.0
HAMMING_MAX_DEFECTO = 0
MIN_FRACCION_VALIDOS = 0.7
DISPERSION_MAX_POS_M = 0.005        # rango entre cuadros de x, y, z
DISPERSION_MAX_DTH_DEG = 2.0
INVALIDOS_PARA_OLVIDAR = 5          # cuadros no válidos seguidos tras los que el filtro olvida su historial
MOTIVOS = ('sin_tag', 'otro_id', 'varios_tags', 'sin_pose', 'hamming', 'margen_bajo', 'error_pose')


class ErrorMedicion(ValueError):
    pass


@dataclass(frozen=True)
class Criterios:
    margen_min: float = MARGEN_MIN_DEFECTO
    hamming_max: int = HAMMING_MAX_DEFECTO
    error_pose_max: Optional[float] = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.margen_min) or self.margen_min < 0:
            raise ErrorMedicion('margen_min debe ser >= 0')
        if not 0 <= self.hamming_max <= 5:
            raise ErrorMedicion('hamming_max debe estar entre 0 y 5')
        if self.error_pose_max is not None and (not math.isfinite(self.error_pose_max) or self.error_pose_max <= 0):
            raise ErrorMedicion('error_pose_max debe ser positivo')


@dataclass(frozen=True)
class Medicion:
    """Un cuadro. Si `valido` es False, la pose es None: no se entrega pose de una detección dudosa."""
    ts: float
    valido: bool
    motivo: Optional[str]
    id: Optional[int] = None
    x_m: Optional[float] = None
    y_m: Optional[float] = None
    z_m: Optional[float] = None
    dth_deg: Optional[float] = None
    margen: Optional[float] = None
    hamming: Optional[int] = None
    error_pose: Optional[float] = None


class CamaraTag:
    """Una cámara lista para medir: intrínsecos, tamaño del tag y corrección de distorsión si la hay."""

    def __init__(self, ancho: int, alto: int, params: Tuple[float, float, float, float], tamano_m: float,
                 corrector: Optional[Callable[[Any], Any]] = None, calibrada: bool = False,
                 offset_cm: Optional[float] = None, origen: str = '') -> None:
        if not 0.005 <= tamano_m <= 0.5:
            raise ErrorMedicion('el tamaño del tag debe estar entre 5 y 500 mm')
        self.ancho, self.alto, self.params, self.tamano_m = ancho, alto, params, tamano_m
        self._corrector, self.calibrada, self.offset_cm, self.origen = corrector, calibrada, offset_cm, origen

    @property
    def con_distorsion_corregida(self) -> bool:
        return self._corrector is not None

    @classmethod
    def desde_yaml(cls, ruta: str, tamano_mm: Optional[float] = None) -> 'CamaraTag':
        """Con una calibración (`camara_calibrada.yaml`). El tamaño del tag viene de la calibración de regla; con la de
        damero hay que darlo. Si se da y la calibración ya lo trae, deben coincidir: la focal y el tamaño van ligados."""
        cam = cargar_camara(ruta)
        if cam.tamano_tag_m is not None:
            if tamano_mm is not None and abs(tamano_mm / 1000 - cam.tamano_tag_m) > 1e-4:
                raise ErrorMedicion(f'la calibración se hizo con un tag de {cam.tamano_tag_m * 1000:g} mm y se pidió '
                                    f'{tamano_mm:g} mm: la focal y el tamaño del tag van ligados; usar el mismo tag o recalibrar')
            tamano = cam.tamano_tag_m
        elif tamano_mm is None:
            raise ErrorMedicion('esta calibración (damero) no guarda el tamaño del tag: indicar --tamano-mm')
        else:
            tamano = tamano_mm / 1000
        corrector = hv.Corrector(cam) if cam.distorsion is not None else None
        return cls(cam.ancho, cam.alto, cam.tupla(), tamano, corrector, True, cam.offset_cm, str(ruta))

    @classmethod
    def desde_fov(cls, ancho: int, alto: int, fov_h_deg: float, tamano_mm: float) -> 'CamaraTag':
        """SIN calibrar: campo de visión aproximado y sin distorsión. Un 6 % de error en el campo de visión da ~2 cm
        de error en z (docs/apriltag_sin_robot.md): usar solo para pruebas."""
        f = focal_desde_fov(ancho, fov_h_deg)
        return cls(ancho, alto, (f, f, ancho / 2, alto / 2), tamano_mm / 1000, None, False, None, f'fov {fov_h_deg:g}')

    def medir(self, imagen: Any, tag_id: Optional[int] = None, criterios: Criterios = Criterios(),
              ts: Optional[float] = None) -> Medicion:
        ts = time.time() if ts is None else ts
        alto, ancho = imagen.shape[:2]
        if (ancho, alto) != (self.ancho, self.alto):
            raise ErrorMedicion(f'la imagen es {ancho}x{alto} y la cámara está calibrada para {self.ancho}x{self.alto}: '
                                'la focal en píxeles solo vale para su resolución')
        if self._corrector is not None:
            imagen = self._corrector(imagen)
        dets = ht.detectar_en(hv.detector(), imagen, self.params, self.tamano_m)
        if not dets:
            return Medicion(ts, False, 'sin_tag')
        elegidos = [d for d in dets if tag_id is None or d['id'] == tag_id]
        if not elegidos:
            return Medicion(ts, False, 'otro_id')
        if len(elegidos) > 1:
            return Medicion(ts, False, 'varios_tags')
        d = elegidos[0]
        base = dict(id=int(d['id']), margen=float(d['margen']), hamming=int(d['hamming']))
        if d['pose'] is None:
            return Medicion(ts, False, 'sin_pose', **base)
        pose = d['pose']
        base['error_pose'] = float(pose['error'])
        if d['hamming'] > criterios.hamming_max:
            return Medicion(ts, False, 'hamming', **base)
        if d['margen'] < criterios.margen_min:
            return Medicion(ts, False, 'margen_bajo', **base)
        if criterios.error_pose_max is not None and pose['error'] > criterios.error_pose_max:
            return Medicion(ts, False, 'error_pose', **base)
        return Medicion(ts, True, None, x_m=float(pose['x']), y_m=float(pose['y']), z_m=float(pose['z']),
                        dth_deg=float(pose['dth']), **base)


# ------------------------------------------------------------------ agregar varios cuadros
@dataclass(frozen=True)
class Agregado:
    """Mediana de los cuadros válidos y su dispersión (rango). `aceptada` es lo único que debe mirar quien la use."""
    aceptada: bool
    motivo: Optional[str]
    n_cuadros: int
    n_validos: int
    id: Optional[int] = None
    x_m: Optional[float] = None
    y_m: Optional[float] = None
    z_m: Optional[float] = None
    dth_deg: Optional[float] = None
    rango_x_m: Optional[float] = None
    rango_y_m: Optional[float] = None
    rango_z_m: Optional[float] = None
    rango_dth_deg: Optional[float] = None
    motivos_rechazo: Tuple[Tuple[str, int], ...] = ()


def agregar(meds: Sequence[Medicion], min_fraccion: float = MIN_FRACCION_VALIDOS,
            disp_pos_m: float = DISPERSION_MAX_POS_M, disp_dth_deg: float = DISPERSION_MAX_DTH_DEG) -> Agregado:
    n = len(meds)
    if n == 0:
        raise ErrorMedicion('no hay cuadros que agregar')
    cuenta: Dict[str, int] = {}
    for m in meds:
        if not m.valido and m.motivo:
            cuenta[m.motivo] = cuenta.get(m.motivo, 0) + 1
    rechazos = tuple(sorted(cuenta.items(), key=lambda kv: -kv[1]))
    validos = [m for m in meds if m.valido]
    if not validos:
        return Agregado(False, 'sin_cuadros_validos', n, 0, motivos_rechazo=rechazos)
    ids = {m.id for m in validos}
    if len(ids) > 1:
        return Agregado(False, 'ids_distintos', n, len(validos), motivos_rechazo=rechazos)
    med = lambda campo: statistics.median(getattr(m, campo) for m in validos)  # noqa: E731
    rng = lambda campo: max(getattr(m, campo) for m in validos) - min(getattr(m, campo) for m in validos)  # noqa: E731
    datos = dict(id=ids.pop(), x_m=med('x_m'), y_m=med('y_m'), z_m=med('z_m'), dth_deg=med('dth_deg'),
                 rango_x_m=rng('x_m'), rango_y_m=rng('y_m'), rango_z_m=rng('z_m'), rango_dth_deg=rng('dth_deg'),
                 motivos_rechazo=rechazos)
    if len(validos) < math.ceil(min_fraccion * n):
        return Agregado(False, 'pocos_cuadros_validos', n, len(validos), **datos)
    if max(datos['rango_x_m'], datos['rango_y_m'], datos['rango_z_m']) > disp_pos_m:
        return Agregado(False, 'inestable_posicion', n, len(validos), **datos)
    if datos['rango_dth_deg'] > disp_dth_deg:
        return Agregado(False, 'inestable_angulo', n, len(validos), **datos)
    return Agregado(True, None, n, len(validos), **datos)


class FiltroMediana:
    """Mediana móvil de los últimos cuadros válidos, para el modo continuo. Olvida todo tras varios cuadros no
    válidos seguidos: nunca reporta una pose vieja como si fuera actual."""

    def __init__(self, ventana: int = 5, invalidos_para_olvidar: int = INVALIDOS_PARA_OLVIDAR) -> None:
        if not 1 <= ventana <= 100:
            raise ErrorMedicion('la ventana debe estar entre 1 y 100')
        self._ventana, self._max_inv = ventana, invalidos_para_olvidar
        self._poses: Deque[Medicion] = deque(maxlen=ventana)
        self._inv = 0

    def agregar(self, m: Medicion) -> Optional[Dict[str, float]]:
        if m.valido:
            self._inv = 0
            self._poses.append(m)
        else:
            self._inv += 1
            if self._inv >= self._max_inv:
                self._poses.clear()
        if len(self._poses) < min(3, self._ventana):
            return None
        med = lambda c: statistics.median(getattr(p, c) for p in self._poses)  # noqa: E731
        return {'x_m': med('x_m'), 'y_m': med('y_m'), 'z_m': med('z_m'), 'dth_deg': med('dth_deg'),
                'n': float(len(self._poses))}


# ------------------------------------------------------------------ fuentes de fotogramas
def fotogramas_camara(abrir_camara: Callable[[], Any], descartar: int = 3) -> Iterator[Any]:
    """Cuadros de una cámara. Descarta los primeros (autoexposición). Si la cámara se cae, lanza ErrorMedicion."""
    cam = abrir_camara()
    if not cam.isOpened():
        raise ErrorMedicion('no se pudo abrir la cámara. ¿Otro programa la usa (nodo de ROS, otra terminal)? '
                            '¿El índice o la ruta son los correctos?')
    try:
        for _ in range(descartar):
            cam.read()
        while True:
            ok, cuadro = cam.read()
            if not ok:
                raise ErrorMedicion('la cámara dejó de entregar imágenes')
            yield cuadro
    finally:
        cam.release()


def fotogramas_imagen(ruta: str) -> Iterator[Any]:
    yield ht.leer_imagen(Path(ruta))


def fotogramas_video(ruta: str) -> Iterator[Any]:
    import cv2
    if not Path(ruta).is_file():
        raise ErrorMedicion(f'no existe el video: {ruta}')
    cap = cv2.VideoCapture(ruta)
    if not cap.isOpened():
        raise ErrorMedicion(f'no se pudo abrir el video: {ruta}')
    try:
        while True:
            ok, cuadro = cap.read()
            if not ok:
                return
            yield cuadro
    finally:
        cap.release()


# ------------------------------------------------------------------ evidencia: comparar con regla y transportador
COLUMNAS = ['fecha', 'tag_id', 'aceptada', 'motivo', 'n_cuadros', 'n_validos', 'z_cm', 'x_cm', 'y_cm', 'dth_deg',
            'rango_z_cm', 'rango_dth_deg', 'esp_z_cm', 'esp_x_cm', 'esp_dth_deg', 'offset_cm', 'err_z_cm', 'err_x_cm',
            'err_dth_deg', 'camara', 'calibrada', 'observaciones']


@dataclass(frozen=True)
class Esperado:
    """Verdad de terreno medida con regla y transportador. z desde el frente de la lente al plano del tag."""
    z_cm: float
    x_cm: Optional[float] = None       # + a la derecha del eje de la cámara
    dth_deg: Optional[float] = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.z_cm) or not 5 <= self.z_cm <= 100:
            raise ErrorMedicion(f'z esperada {self.z_cm} cm fuera de 5-100 cm (¿metros en vez de centímetros?)')
        if self.x_cm is not None and (not math.isfinite(self.x_cm) or abs(self.x_cm) > 60):
            raise ErrorMedicion(f'x esperada {self.x_cm} cm fuera de ±60 cm')
        if self.dth_deg is not None and (not math.isfinite(self.dth_deg) or abs(self.dth_deg) > 90):
            raise ErrorMedicion(f'ángulo esperado {self.dth_deg}° fuera de ±90°')


def _fmt(v: Optional[float], n: int = 3) -> str:
    return '' if v is None else f'{v:.{n}f}'


def registrar_comparacion(ruta_csv: str, ag: Agregado, esperado: Esperado, cam: CamaraTag,
                          offset_cm: Optional[float] = None, observaciones: str = '',
                          fecha: Optional[str] = None) -> Dict[str, Any]:
    """Añade una fila a la evidencia (también las mediciones NO aceptadas: conservar lo que falla). Si se conoce el
    desfase de la regla (centro óptico detrás del frente de la lente) se resta de z antes de comparar."""
    if '\n' in observaciones or ',' in observaciones:
        raise ErrorMedicion('las observaciones no pueden llevar comas ni saltos de línea')
    desfase = offset_cm if offset_cm is not None else cam.offset_cm
    cm = lambda v: None if v is None else v * 100  # noqa: E731
    z, x = cm(ag.z_m), cm(ag.x_m)
    err_z = None if z is None else z - (desfase or 0.0) - esperado.z_cm
    err_x = None if x is None or esperado.x_cm is None else x - esperado.x_cm
    err_th = None if ag.dth_deg is None or esperado.dth_deg is None else ag.dth_deg - esperado.dth_deg
    fila = {'fecha': fecha or datetime.datetime.now().isoformat(timespec='seconds'), 'tag_id': ag.id if ag.id is not None else '',
            'aceptada': int(ag.aceptada), 'motivo': ag.motivo or '', 'n_cuadros': ag.n_cuadros, 'n_validos': ag.n_validos,
            'z_cm': _fmt(z), 'x_cm': _fmt(x), 'y_cm': _fmt(cm(ag.y_m)), 'dth_deg': _fmt(ag.dth_deg, 2),
            'rango_z_cm': _fmt(cm(ag.rango_z_m)), 'rango_dth_deg': _fmt(ag.rango_dth_deg, 2), 'esp_z_cm': _fmt(esperado.z_cm, 2),
            'esp_x_cm': _fmt(esperado.x_cm, 2), 'esp_dth_deg': _fmt(esperado.dth_deg, 2), 'offset_cm': _fmt(desfase, 2),
            'err_z_cm': _fmt(err_z), 'err_x_cm': _fmt(err_x), 'err_dth_deg': _fmt(err_th, 2), 'camara': cam.origen,
            'calibrada': int(cam.calibrada), 'observaciones': observaciones}
    nuevo = not Path(ruta_csv).exists()
    if not nuevo:
        with open(ruta_csv, newline='', encoding='utf-8') as f:
            if next(csv.reader(f), []) != COLUMNAS:
                raise ErrorMedicion(f'{Path(ruta_csv).name} existente tiene otras columnas: usar otro archivo')
    with open(ruta_csv, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        if nuevo:
            w.writeheader()
        w.writerow(fila)
    return fila


@dataclass(frozen=True)
class Resumen:
    n_filas: int
    n_aceptadas: int
    errores: Dict[str, Dict[str, float]]      # variable -> {n, medio_abs, p95_abs, max_abs}
    cumple: bool
    tol_cm: float
    tol_deg: float
    sin_comparar: int                          # aceptadas sin error calculable


def resumen(ruta_csv: str, tol_cm: float = 1.0, tol_deg: float = 2.0) -> Resumen:
    """Estadística de los errores de las mediciones ACEPTADAS. Cumple si el máximo de cada error está dentro de la
    tolerancia (1 cm y 2° son provisionales: una cuarta parte y un tercio de la tolerancia del acople)."""
    if not (math.isfinite(tol_cm) and tol_cm > 0 and math.isfinite(tol_deg) and tol_deg > 0):
        raise ErrorMedicion('las tolerancias deben ser positivas')
    try:
        with open(ruta_csv, newline='', encoding='utf-8') as f:
            filas = list(csv.DictReader(f))
    except OSError as e:
        raise ErrorMedicion(f'no se pudo leer {Path(ruta_csv).name}: {e.strerror or e}') from e
    if not filas or set(filas[0]) != set(COLUMNAS):
        raise ErrorMedicion(f'{Path(ruta_csv).name} no tiene las columnas esperadas ({", ".join(COLUMNAS[:4])}...)')
    aceptadas = [r for r in filas if r['aceptada'] == '1']
    errores: Dict[str, Dict[str, float]] = {}
    sin = 0
    for var in ('err_z_cm', 'err_x_cm', 'err_dth_deg'):
        vals = []
        for r in aceptadas:
            if r[var] != '':
                try:
                    vals.append(abs(float(r[var])))
                except ValueError:
                    raise ErrorMedicion(f'valor no numérico en {var}: {r[var]!r}') from None
        if vals:
            vs = sorted(vals)
            p95 = vs[min(len(vs) - 1, math.ceil(0.95 * len(vs)) - 1)]
            errores[var] = {'n': float(len(vals)), 'medio_abs': statistics.mean(vals), 'p95_abs': p95, 'max_abs': max(vals)}
    sin = sum(1 for r in aceptadas if r['err_z_cm'] == '')
    limites = {'err_z_cm': tol_cm, 'err_x_cm': tol_cm, 'err_dth_deg': tol_deg}
    cumple = bool(errores) and all(e['max_abs'] <= limites[v] for v, e in errores.items())
    return Resumen(len(filas), len(aceptadas), errores, cumple, tol_cm, tol_deg, sin)


def informe_resumen(r: Resumen) -> str:
    lineas = [f'{r.n_filas} mediciones, {r.n_aceptadas} aceptadas ({r.n_filas - r.n_aceptadas} no aceptadas, no cuentan)']
    nombres = {'err_z_cm': ('z', 'cm', r.tol_cm), 'err_x_cm': ('x', 'cm', r.tol_cm), 'err_dth_deg': ('dth', '°', r.tol_deg)}
    for var, e in r.errores.items():
        n, u, tol = nombres[var]
        lineas.append(f'  error {n:3s}: n={int(e["n"])} medio {e["medio_abs"]:.2f} {u}  p95 {e["p95_abs"]:.2f} {u}  '
                      f'máximo {e["max_abs"]:.2f} {u}  (tolerancia {tol:g} {u}) ' + ('OK' if e['max_abs'] <= tol else 'FUERA'))
    if not r.errores:
        lineas.append('  no hay mediciones aceptadas con valor esperado')
    lineas.append('CUMPLE' if r.cumple else 'NO CUMPLE')
    if r.n_aceptadas < 10:
        lineas.append(f'AVISO: solo {r.n_aceptadas} mediciones aceptadas; para decidir hacen falta decenas en distintas distancias, '
                      'posiciones y ángulos')
    return '\n'.join(lineas)
