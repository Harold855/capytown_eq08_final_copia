"""Calibración de la cámara con un damero (focal, punto principal y DISTORSIÓN del lente).

Cuándo hace falta: el método de la regla (`calibrar.py`) ajusta la focal pero no ve la distorsión, que solo
se nota fuera del eje (con barril k1 = -0.4 un tag a 10 cm del centro da 1.6 cm de error en z). Si la
validación con el tag a los lados falla, se usa este método.

La herramienta del docente supone un lente sin distorsión: los coeficientes solo sirven si cada imagen se
corrige ANTES de detectar el tag (`vision.herramienta.Corrector`). La focal y la distorsión no dependen del
tamaño exacto del cuadro del damero (solo la traslación): no hace falta medirlo al milímetro, a diferencia del
tag en el método de la regla.

Modelos: 'simple' = k1, k2 (sin tangencial ni k3; el más estable con pocas vistas y lo habitual en webcams) y
'completo' = k1, k2, p1, p2, k3. En ambos fx = fy. Necesita OpenCV.
"""
from __future__ import annotations

import dataclasses
import datetime
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from . import herramienta as hv
from .calibracion_focal import (DetalleDamero, ErrorCalibracion, ParametrosCamara, cargar_camara,
                                focal_desde_fov)

ht = hv.ht
BUSQUEDA = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
CRITERIO_SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
MODELOS = ('simple', 'completo')
MIN_IMAGENES_ERROR, MIN_IMAGENES_AVISO = 10, 15
INCLINACION_MIN_DEG, N_INCLINADAS_MIN, INCLINACION_AVISO_DEG = 15.0, 3, 25.0
RMS_AVISO_PX, RMS_FALLO_PX, VALIDACION_AVISO_PX = 0.7, 1.5, 1.0
FACTOR_ATIPICA, UMBRAL_ATIPICA_PX, MAX_DESCARTE = 3.0, 1.0, 0.25
COBERTURA_AVISO_CELDAS = 6          # de 9
PRINCIPAL_AVISO = 0.10              # fracción de la imagen que puede desviarse el punto principal del centro
DESPLAZAMIENTO_DESPRECIABLE_PX = 2.0
EXT = ('.png', '.jpg', '.jpeg', '.bmp')


@dataclass(frozen=True)
class Patron:
    """Esquinas INTERIORES del damero (un damero de 10x7 cuadros tiene 9x6 esquinas interiores)."""
    cols: int
    filas: int
    cuadro_m: float

    def __post_init__(self) -> None:
        if not (3 <= self.cols <= 50 and 3 <= self.filas <= 50):
            raise ErrorCalibracion('el patrón debe tener entre 3 y 50 esquinas interiores por lado')
        if self.cols == self.filas:
            raise ErrorCalibracion('el patrón no puede ser cuadrado (cols = filas): la orientación sería ambigua; '
                                   'usar p. ej. 9x6')
        if not math.isfinite(self.cuadro_m) or not 0.002 <= self.cuadro_m <= 0.2:
            raise ErrorCalibracion('el lado del cuadro debe estar entre 2 y 200 mm')

    @property
    def tamano(self) -> Tuple[int, int]:
        return self.cols, self.filas

    def puntos_objeto(self) -> np.ndarray:
        p = np.zeros((self.cols * self.filas, 3), np.float32)
        p[:, :2] = np.mgrid[0:self.cols, 0:self.filas].T.reshape(-1, 2) * self.cuadro_m
        return p


# ------------------------------------------------------------------ crear el damero para imprimir
def imagen_damero(patron: Patron, px_cuadro: int = 80) -> np.ndarray:
    """PNG en gris del damero con un margen blanco de un cuadro."""
    ncol, nfil = patron.cols + 1, patron.filas + 1
    celdas = (np.indices((nfil, ncol)).sum(axis=0) % 2 == 0).astype(np.uint8)    # 1 = negro; esquina sup. izq. negra
    grande = np.kron(1 - celdas, np.ones((px_cuadro, px_cuadro), np.uint8)) * 255
    return np.pad(grande, px_cuadro, constant_values=255).astype(np.uint8)


def svg_damero(patron: Patron) -> str:
    """SVG a tamaño real: cada cuadro mide `cuadro_m`. Imprimirlo al 100 % (sin 'ajustar a la página')."""
    ncol, nfil = patron.cols + 1, patron.filas + 1
    mm = patron.cuadro_m * 1000
    ancho, alto = (ncol + 2) * mm, (nfil + 2) * mm
    rects = [f'<rect x="{c + 1}" y="{f + 1}" width="1" height="1"/>' for f in range(nfil) for c in range(ncol)
             if (f + c) % 2 == 0]
    cuerpo = '\n  '.join(rects)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho:.3f}mm" height="{alto:.3f}mm" '
            f'viewBox="0 0 {ncol + 2} {nfil + 2}" shape-rendering="crispEdges">\n'
            f'  <rect width="{ncol + 2}" height="{nfil + 2}" fill="#fff"/>\n  <g fill="#000">\n  {cuerpo}\n  </g>\n</svg>\n')


# ------------------------------------------------------------------ detección
def encontrar_esquinas(imagen: np.ndarray, patron: Patron) -> Optional[np.ndarray]:
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY) if imagen.ndim == 3 else imagen
    ok, esq = cv2.findChessboardCorners(gris, patron.tamano, flags=BUSQUEDA)
    if not ok:
        return None
    return cv2.cornerSubPix(gris, esq, (11, 11), (-1, -1), CRITERIO_SUBPIX)


def descriptor(esq: np.ndarray, ancho: int, alto: int, patron: Patron) -> Tuple[float, ...]:
    """Resumen de la pose del damero en la imagen: centro, área y asimetrías (inclinación)."""
    p = esq.reshape(-1, 2)
    tl, tr, bl, br = p[0], p[patron.cols - 1], p[-patron.cols], p[-1]
    lado = lambda a, b: float(np.linalg.norm(a - b))  # noqa: E731
    arriba, abajo, izq, der = lado(tl, tr), lado(bl, br), lado(tl, bl), lado(tr, br)
    area = cv2.contourArea(cv2.convexHull(p)) / (ancho * alto)
    return (float(p[:, 0].mean() / ancho), float(p[:, 1].mean() / alto), math.log(max(area, 1e-9)),
            (arriba - abajo) / ((arriba + abajo) / 2), (izq - der) / ((izq + der) / 2))


def distancia_descriptor(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


NOMBRES_CELDA = ((('arriba-izquierda', 'arriba', 'arriba-derecha'), ('izquierda', 'centro', 'derecha'),
                  ('abajo-izquierda', 'abajo', 'abajo-derecha')))


def cobertura(lista_esquinas: Sequence[np.ndarray], ancho: int, alto: int) -> Tuple[int, List[str]]:
    """(celdas cubiertas de 9, nombres de las vacías) con una rejilla de 3x3 sobre la imagen."""
    cubiertas = set()
    for esq in lista_esquinas:
        for x, y in esq.reshape(-1, 2):
            cubiertas.add((min(2, max(0, int(y / alto * 3))), min(2, max(0, int(x / ancho * 3)))))
    vacias = [NOMBRES_CELDA[i][j] for i in range(3) for j in range(3) if (i, j) not in cubiertas]
    return len(cubiertas), vacias


def inclinacion_deg(rvec: np.ndarray) -> float:
    """Ángulo entre la normal del damero y el eje óptico: 0 = de frente."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, np.float64))
    return math.degrees(math.acos(min(1.0, abs(float(R[2, 2])))))


# ------------------------------------------------------------------ calibrar
@dataclass(frozen=True)
class ResultadoDamero:
    parametros: ParametrosCamara
    errores_px: Tuple[float, ...]            # error de reproyección por imagen
    inclinaciones_deg: Tuple[float, ...]
    celdas_cubiertas: int
    celdas_vacias: Tuple[str, ...]
    desplazamiento_esquina_px: float         # cuánto mueve la distorsión un punto de la esquina de la imagen
    nombres: Tuple[str, ...]                 # imágenes usadas
    sin_damero: Tuple[str, ...]              # imágenes donde no se halló el damero
    descartadas: Tuple[str, ...] = ()        # imágenes con esquinas mal localizadas, quitadas del ajuste


def _flags(modelo: str) -> int:
    base = cv2.CALIB_USE_INTRINSIC_GUESS | cv2.CALIB_FIX_ASPECT_RATIO
    return base | (cv2.CALIB_ZERO_TANGENT_DIST | cv2.CALIB_FIX_K3 if modelo == 'simple' else 0)


def _calibrar_cv(esquinas: Sequence[np.ndarray], patron: Patron, ancho: int, alto: int, modelo: str):
    f0 = focal_desde_fov(ancho, 70.0)
    K0 = np.array([[f0, 0, ancho / 2], [0, f0, alto / 2], [0, 0, 1.0]])
    obj = [patron.puntos_objeto()] * len(esquinas)
    try:
        rms, K, D, rvecs, tvecs = cv2.calibrateCamera(obj, list(esquinas), (ancho, alto), K0, np.zeros(5),
                                                      flags=_flags(modelo))
    except cv2.error as e:
        raise ErrorCalibracion(f'OpenCV no pudo calibrar: {str(e).splitlines()[-1]}') from e
    return rms, K, D.ravel(), rvecs, tvecs


def error_reproyeccion(esq: np.ndarray, patron: Patron, K: np.ndarray, D: np.ndarray) -> float:
    """rms (px) de las esquinas medidas contra las que predice K, D con la pose óptima de ese damero."""
    obj = patron.puntos_objeto()
    ok, rvec, tvec = cv2.solvePnP(obj, esq, K, D)
    if not ok:
        raise ErrorCalibracion('solvePnP no resolvió la pose del damero')
    proy, _ = cv2.projectPoints(obj, rvec, tvec, K, D)
    return float(np.sqrt(np.mean(np.sum((proy.reshape(-1, 2) - esq.reshape(-1, 2)) ** 2, axis=1))))


def desplazamiento_en_esquina(fx: float, cx: float, cy: float, ancho: int, alto: int, d: Sequence[float]) -> float:
    """Píxeles que la distorsión radial/tangencial desplaza un punto de la esquina de la imagen."""
    k1, k2, p1, p2, k3 = (list(d) + [0.0] * 5)[:5]
    x, y = (0 - cx) / fx, (0 - cy) / fx
    r2 = x * x + y * y
    radial = 1 + k1 * r2 + k2 * r2 ** 2 + k3 * r2 ** 3
    xd = x * radial + 2 * p1 * x * y + p2 * (r2 + 2 * x * x)
    yd = y * radial + p1 * (r2 + 2 * y * y) + 2 * p2 * x * y
    return math.hypot((xd - x) * fx, (yd - y) * fx)


def _sin_atipicas(esquinas: Sequence[np.ndarray], patron: Patron, ancho: int, alto: int, modelo: str):
    """Calibra y va quitando, de una en una, la imagen peor (la que más contamina el ajuste) mientras su error de
    reproyección supere max(3 veces la mediana, 1 px). Tope: el 25 % de las imágenes y nunca bajar de 10.
    Devuelve (índices usados, índices descartados, rms, K, D, rvecs, tvecs) de la última calibración."""
    n = len(esquinas)
    activos = list(range(n))
    descartadas: List[int] = []
    while True:
        rms, K, D, rvecs, tvecs = _calibrar_cv([esquinas[i] for i in activos], patron, ancho, alto, modelo)
        errs = {i: error_reproyeccion(esquinas[i], patron, K, D) for i in activos}
        umbral = max(FACTOR_ATIPICA * statistics.median(errs.values()), UMBRAL_ATIPICA_PX)
        peor = max(activos, key=errs.get)
        if (errs[peor] <= umbral or len(descartadas) + 1 > MAX_DESCARTE * n
                or len(activos) - 1 < MIN_IMAGENES_ERROR):
            return activos, descartadas, rms, K, D, rvecs, tvecs
        activos.remove(peor)
        descartadas.append(peor)


def calibrar(esquinas: Sequence[np.ndarray], nombres: Sequence[str], patron: Patron, ancho: int, alto: int,
             modelo: str = 'simple', sin_damero: Sequence[str] = (), fecha: Optional[str] = None) -> ResultadoDamero:
    if modelo not in MODELOS:
        raise ErrorCalibracion(f"modelo debe ser uno de {', '.join(MODELOS)}")
    if len(esquinas) < MIN_IMAGENES_ERROR:
        raise ErrorCalibracion(f'hay {len(esquinas)} imágenes con damero y se necesitan al menos {MIN_IMAGENES_ERROR} '
                               f'(mejor {MIN_IMAGENES_AVISO} o más)')
    activos, descartadas, rms, K, D, rvecs, tvecs = _sin_atipicas(esquinas, patron, ancho, alto, modelo)
    esq = [esquinas[i] for i in activos]
    nom = [nombres[i] for i in activos]
    n = len(esq)
    incl = tuple(inclinacion_deg(r) for r in rvecs)
    n_incl = sum(1 for a in incl if a >= INCLINACION_MIN_DEG)
    if n_incl < N_INCLINADAS_MIN:
        raise ErrorCalibracion(f'hacen falta al menos {N_INCLINADAS_MIN} imágenes con el damero inclinado '
                               f'{INCLINACION_MIN_DEG:g}° o más (hay {n_incl}): con el damero siempre de frente la focal '
                               'no queda determinada')
    if rms > RMS_FALLO_PX:
        raise ErrorCalibracion(f'el error de reproyección es {rms:.2f} px (máximo admitido {RMS_FALLO_PX:g}): '
                               'imágenes movidas o desenfocadas, damero combado o patrón mal indicado. Repetir')
    errores = tuple(error_reproyeccion(e, patron, K, D) for e in esq)
    adv: List[str] = []
    if descartadas:
        adv.append(f'{len(descartadas)} imagen(es) descartada(s) por localización de esquinas dudosa (error de reproyección '
                   f'muy superior al resto): {", ".join(nombres[i] for i in descartadas)}')
    umbral = max(FACTOR_ATIPICA * statistics.median(errores), UMBRAL_ATIPICA_PX)
    restantes = [nom[i] for i, e in enumerate(errores) if e > umbral]
    if restantes:
        adv.append(f'imagen(es) con error de reproyección muy alto que no se pudieron descartar (quedan pocas imágenes): '
                   f'{", ".join(restantes)}. Tomar más imágenes (20 o más) para que el ajuste pueda quitarlas')
    if rms > RMS_AVISO_PX:
        adv.append(f'error de reproyección {rms:.2f} px (> {RMS_AVISO_PX:g}; lo bueno es < 0.5)')
    if n < MIN_IMAGENES_AVISO:
        adv.append(f'solo {n} imágenes (< {MIN_IMAGENES_AVISO}): el resultado es menos fiable')
    if max(incl) < INCLINACION_AVISO_DEG:
        adv.append(f'la mayor inclinación fue {max(incl):.0f}° (< {INCLINACION_AVISO_DEG:g}°): inclinar más el damero')
    cubiertas, vacias = cobertura(esq, ancho, alto)
    if cubiertas < COBERTURA_AVISO_CELDAS:
        adv.append(f'el damero solo cubrió {cubiertas} de 9 zonas de la imagen; faltan: {", ".join(vacias)}. '
                   'La distorsión se estima en los bordes: llevar el damero hasta ellos')

    rms_val: Optional[float] = None
    if n >= MIN_IMAGENES_AVISO:                      # validación cruzada: cada 5.ª imagen no se usa para ajustar
        prueba = [i for i in range(n) if i % 5 == 4]
        ajuste = [i for i in range(n) if i % 5 != 4]
        _, Kv, Dv, _, _ = _calibrar_cv([esq[i] for i in ajuste], patron, ancho, alto, modelo)
        rms_val = float(np.sqrt(np.mean([error_reproyeccion(esq[i], patron, Kv, Dv) ** 2 for i in prueba])))
        if rms_val > VALIDACION_AVISO_PX:
            adv.append(f'error en imágenes no usadas para ajustar {rms_val:.2f} px (> {VALIDACION_AVISO_PX:g}): '
                       'el modelo no generaliza; más imágenes o modelo simple')
    fx, fy, cx, cy = float(K[0, 0]), float(K[1, 1]), float(K[0, 2]), float(K[1, 2])
    if abs(cx - ancho / 2) > PRINCIPAL_AVISO * ancho or abs(cy - alto / 2) > PRINCIPAL_AVISO * alto:
        adv.append(f'el punto principal ({cx:.0f}, {cy:.0f}) está lejos del centro ({ancho / 2:.0f}, {alto / 2:.0f}): '
                   'revisar la cobertura y la inclinación')
    despl = desplazamiento_en_esquina(fx, cx, cy, ancho, alto, D)
    coef = tuple(float(v) for v in D)
    p = ParametrosCamara(
        ancho, alto, fx, fy, cx, cy, None, None, None, None, None,
        fecha or datetime.datetime.now().isoformat(timespec='seconds'), tuple(adv), coef,
        DetalleDamero(patron.cols, patron.filas, patron.cuadro_m, modelo, float(rms), rms_val, n))
    return ResultadoDamero(p, errores, incl, cubiertas, tuple(vacias), despl, tuple(nom), tuple(sin_damero),
                           tuple(nombres[i] for i in descartadas))


def cargar_carpeta(carpeta: Path) -> List[Tuple[str, Any]]:
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ErrorCalibracion(f'no existe la carpeta {carpeta}')
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() in EXT)
    if not archivos:
        raise ErrorCalibracion(f'{carpeta} no tiene imágenes ({", ".join(EXT)})')
    return [(p.name, ht.leer_imagen(p)) for p in archivos]


def _detectar_todas(imagenes: Sequence[Tuple[str, Any]], patron: Patron):
    formas = {img.shape[:2] for _, img in imagenes}
    if len(formas) != 1:
        raise ErrorCalibracion(f'las imágenes tienen tamaños distintos {sorted(formas)}: usar siempre la misma resolución')
    alto, ancho = next(iter(formas))
    esq, nombres, sin = [], [], []
    for nombre, img in imagenes:
        e = encontrar_esquinas(img, patron)
        if e is None:
            sin.append(nombre)
        else:
            esq.append(e)
            nombres.append(nombre)
    return esq, nombres, sin, ancho, alto


def calcular(carpeta: Path, patron: Patron, modelo: str = 'simple', fecha: Optional[str] = None) -> ResultadoDamero:
    esq, nombres, sin, ancho, alto = _detectar_todas(cargar_carpeta(carpeta), patron)
    if not esq:
        raise ErrorCalibracion('no se encontró el damero en ninguna imagen: revisar --cols/--filas (esquinas INTERIORES; '
                               '¿invertidos?), la luz y que el damero esté completo y plano')
    r = calibrar(esq, nombres, patron, ancho, alto, modelo, sin, fecha)
    if sin:
        extra = (f'{len(sin)} imagen(es) sin damero detectado, ignoradas: {", ".join(sin[:5])}' + (' ...' if len(sin) > 5 else ''))
        r = dataclasses.replace(r, parametros=dataclasses.replace(r.parametros, advertencias=r.parametros.advertencias + (extra,)))
    return r


def informe(r: ResultadoDamero) -> str:
    p, d = r.parametros, r.parametros.damero
    k = dict(zip(('k1', 'k2', 'p1', 'p2', 'k3'), p.distorsion))
    lineas = [
        f'imágenes usadas: {d.n_imagenes} ({len(r.sin_damero)} sin damero, {len(r.descartadas)} descartadas), resolución {p.ancho}x{p.alto}, '
        f'patrón {d.cols}x{d.filas} esquinas interiores, modelo {d.modelo}',
        f'focal: fx = fy = {p.fx:.1f} px (campo de visión horizontal {p.fov_h_deg:.1f}°); punto principal ({p.cx:.1f}, {p.cy:.1f})',
        'distorsión: ' + ', '.join(f'{n} = {v:+.4f}' for n, v in k.items()),
        f'error de reproyección: {d.rms_px:.2f} px' + (f' (en imágenes no usadas: {d.rms_validacion_px:.2f} px)'
                                                       if d.rms_validacion_px is not None else ''),
        f'la distorsión desplaza un punto de la esquina de la imagen {r.desplazamiento_esquina_px:.1f} px',
        f'inclinación del damero: {min(r.inclinaciones_deg):.0f}°-{max(r.inclinaciones_deg):.0f}°; cobertura {r.celdas_cubiertas}/9 zonas',
    ]
    if r.desplazamiento_esquina_px < DESPLAZAMIENTO_DESPRECIABLE_PX:
        lineas.append(f'La distorsión es pequeña (< {DESPLAZAMIENTO_DESPRECIABLE_PX:g} px en la esquina): probablemente el método de la '
                      'regla ya bastaba.')
    lineas += [f'AVISO: {a}' for a in p.advertencias]
    lineas.append('Usar: corregir cada imagen con vision.herramienta.Corrector(camara) antes de detectar el tag, y validar con '
                  '`calibrar_focal.py validar` (tag a los lados del cuadro).')
    return '\n'.join(lineas)


# ------------------------------------------------------------------ validar
@dataclass(frozen=True)
class ResultadoValidacionDamero:
    rms_px: float
    max_px: float
    n: int
    tolerancia_px: float
    sin_damero: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.rms_px <= self.tolerancia_px


def validar(ruta_camara: str, carpeta: Path, tolerancia_px: float = RMS_AVISO_PX) -> ResultadoValidacionDamero:
    """Mide el error de reproyección en imágenes NUEVAS (no usadas para calibrar). Tolerancia por defecto 0.7 px: con
    1 px, ignorar por completo una distorsión de k1 = -0.3 todavía "cumplía" (0.89 px)."""
    if not math.isfinite(tolerancia_px) or tolerancia_px <= 0:
        raise ErrorCalibracion('la tolerancia debe ser positiva')
    cam = cargar_camara(ruta_camara)
    if cam.damero is None:
        raise ErrorCalibracion("esta calibración es del método 'regla': no tiene patrón de damero para validar")
    patron = Patron(cam.damero.cols, cam.damero.filas, cam.damero.cuadro_m)
    esq, nombres, sin, ancho, alto = _detectar_todas(cargar_carpeta(carpeta), patron)
    if (ancho, alto) != (cam.ancho, cam.alto):
        raise ErrorCalibracion(f'las imágenes son {ancho}x{alto} y la calibración es de {cam.ancho}x{cam.alto}')
    if not esq:
        raise ErrorCalibracion('no se encontró el damero en ninguna imagen')
    K = np.array([[cam.fx, 0, cam.cx], [0, cam.fy, cam.cy], [0, 0, 1.0]])
    errores = [error_reproyeccion(e, patron, K, np.array(cam.distorsion)) for e in esq]
    return ResultadoValidacionDamero(float(np.sqrt(np.mean(np.square(errores)))), float(max(errores)), len(errores),
                                     tolerancia_px, tuple(sin))


def informe_validacion(r: ResultadoValidacionDamero) -> str:
    texto = (f'{r.n} imágenes: error de reproyección rms {r.rms_px:.2f} px, máximo {r.max_px:.2f} px '
             f'(tolerancia {r.tolerancia_px:g} px): ' + ('CUMPLE' if r.ok else 'NO CUMPLE: repetir la calibración'))
    texto += (f'\nAVISO: {len(r.sin_damero)} imagen(es) sin damero' if r.sin_damero else '')
    return texto + ('\nLIMITE: este error valida la distorsión y la consistencia del modelo, NO la escala: con el damero casi de '
                    'frente, un error de focal se compensa moviendo la distancia estimada y casi no cambia la reproyección. '
                    'La escala (focal) solo se valida con distancias medidas: `calibrar_focal.py validar` con el tag y la regla.')


# ------------------------------------------------------------------ capturar (necesita la cámara)
def _movimiento_px(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.linalg.norm(a.reshape(-1, 2) - b.reshape(-1, 2), axis=1)))


def capturar(abrir_camara: Callable[[], Any], patron: Patron, salida: Path, *, objetivo: int = 20,
             max_s: float = 300.0, intervalo_s: float = 0.2, estable_px: float = 1.5, distancia_min: float = 0.08,
             escribir: Callable[[str], None] = print, dormir: Callable[[float], None] = None,
             reloj: Callable[[], float] = None) -> List[Path]:
    """Toma automática: guarda un cuadro cuando el damero se ve completo, está QUIETO y su pose difiere lo
    suficiente de las ya guardadas. La persona solo mueve e inclina el damero. Devuelve las rutas guardadas."""
    import time
    dormir = dormir or time.sleep
    reloj = reloj or time.monotonic
    if not 10 <= objetivo <= 100:
        raise ErrorCalibracion('--objetivo debe estar entre 10 y 100 imágenes')
    carpeta = Path(salida)
    carpeta.mkdir(parents=True, exist_ok=True)
    cam = abrir_camara()
    if not cam.isOpened():
        raise ErrorCalibracion('no se pudo abrir la cámara. ¿Otro programa la usa (nodo de ROS, otra terminal)? '
                               '¿El índice o la ruta son los correctos?')
    guardadas: List[Path] = []
    descs: List[Tuple[float, ...]] = []
    esquinas: List[np.ndarray] = []
    anterior: Optional[np.ndarray] = None
    resolucion = None
    inicio = reloj()
    existentes = len(list(carpeta.glob('damero_*.png')))
    try:
        while len(guardadas) < objetivo and reloj() - inicio < max_s:
            ok, cuadro = cam.read()
            if not ok:
                raise ErrorCalibracion('la cámara dejó de entregar imágenes')
            alto, ancho = cuadro.shape[:2]
            if resolucion is None:
                resolucion = (ancho, alto)
                escribir(f'resolución de captura: {ancho}x{alto} (no la cambie después)')
            esq = encontrar_esquinas(cuadro, patron)
            dormir(intervalo_s)
            quieto = esq is not None and anterior is not None and _movimiento_px(esq, anterior) <= estable_px
            anterior = esq
            if not quieto:
                continue
            d = descriptor(esq, ancho, alto, patron)
            if any(distancia_descriptor(d, o) < distancia_min for o in descs):
                continue
            ruta = carpeta / f'damero_{existentes + len(guardadas):02d}.png'
            ht.guardar_png(ruta, cuadro)
            guardadas.append(ruta); descs.append(d); esquinas.append(esq)
            _, vacias = cobertura(esquinas, ancho, alto)
            escribir(f'  [{len(guardadas)}/{objetivo}] guardada {ruta.name}' +
                     (f'; falta cubrir: {", ".join(vacias)}' if vacias and len(guardadas) >= 3 else ''))
    finally:
        cam.release()
    if len(guardadas) < objetivo:
        escribir(f'tiempo agotado con {len(guardadas)} de {objetivo} imágenes' +
                 ('' if len(guardadas) >= MIN_IMAGENES_ERROR else f' (se necesitan al menos {MIN_IMAGENES_ERROR})'))
    return guardadas
