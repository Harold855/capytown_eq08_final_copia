"""Calibración de la focal de la cámara con un AprilTag y distancias medidas con regla. Matemática pura.

Problema: la herramienta del docente aproxima la cámara con `--fov-h`, y un 6 % de error de campo de visión
mete ~2 cm de error en la distancia `z` a 28 cm (docs/apriltag_sin_robot.md). Aquí se ajusta la focal real.

Método (sin damero): se pone el tag de frente a varias distancias medidas con regla y se mide su `z` con una
focal supuesta `f0`. En una cámara pin-hole la `z` estimada es proporcional a la focal supuesta:

    z_est(f0) = k * (z_regla + d0),     k = f0 / f_real

`d0` absorbe que la regla se apoya en el frente de la lente y no en el centro óptico. Una regresión lineal de
z_est contra z_regla da k (pendiente) y k*d0 (ordenada); la focal real es f0/k. Se itera con la nueva focal
hasta que k = 1, porque la proporcionalidad solo es exacta si el tag está de frente y centrado.

Lo que este ajuste NO resuelve: la distorsión del lente, un punto principal descentrado (se supone en el
centro de la imagen), ni el tamaño real del tag, que debe medirse con regla/calibre y darse aparte (el
tamaño y la focal están ligados en `z`: un tag mal medido sesga la focal).
"""
from __future__ import annotations

import datetime
import math
import os
import tempfile
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from comun import yaml_estricto as ye

VERSION = 1
MIN_DISTANCIAS = 3
MIN_RANGO_ERROR_CM = 8.0     # menos separación entre la distancia mayor y la menor: el ajuste no se puede resolver
MIN_RANGO_AVISO_CM = 15.0
RMS_AVISO_CM = 0.3
RMS_FALLO_CM = 1.0           # el ajuste no explica las mediciones: no se guarda una calibración así
OFFSET_AVISO_CM = 5.0
FOV_PLAUSIBLE_DEG = (40.0, 120.0)


class ErrorCalibracion(ValueError):
    pass


def focal_desde_fov(ancho: int, fov_h_deg: float) -> float:
    if not 0 < fov_h_deg < 180:
        raise ValueError('fov_h debe estar entre 0 y 180 grados')
    return (ancho / 2) / math.tan(math.radians(fov_h_deg) / 2)


def fov_desde_focal(ancho: int, f_px: float) -> float:
    return math.degrees(2 * math.atan((ancho / 2) / f_px))


def regresion(x: Sequence[float], y: Sequence[float]) -> Tuple[float, float, float]:
    """Mínimos cuadrados y = k*x + b. Devuelve (k, b, rms de los residuos)."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx <= 0:
        raise ErrorCalibracion('todas las distancias son iguales: hacen falta distancias distintas')
    k = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx
    b = my - k * mx
    rms = math.sqrt(sum((yy - (k * xx + b)) ** 2 for xx, yy in zip(x, y)) / n)
    return k, b, rms


@dataclass(frozen=True)
class Ajuste:
    f_px: float
    offset_cm: float             # z_real = z_regla + offset (centro óptico detrás del frente de la lente si > 0)
    rms_cm: float
    iteraciones: int
    residuos_cm: Tuple[float, ...]
    advertencias: Tuple[str, ...]


def ajustar_focal(distancias_cm: Sequence[float], z_estimada_cm: Callable[[float], Sequence[float]],
                  f_inicial_px: float, ancho_px: int, max_iter: int = 10, tol: float = 1e-3) -> Ajuste:
    """`z_estimada_cm(f)` devuelve la `z` medida (cm) a cada distancia con la focal `f` supuesta.
    `tol`: se da por convergido cuando la pendiente k difiere de 1 menos de 0.1 %, que es la focal a 0.1 %;
    más estricto que eso queda por debajo del ruido numérico de la estimación de pose del detector."""
    d = [float(v) for v in distancias_cm]
    if len(d) < MIN_DISTANCIAS:
        raise ErrorCalibracion(f'hacen falta al menos {MIN_DISTANCIAS} distancias distintas (hay {len(d)})')
    if not all(math.isfinite(v) and v > 0 for v in d):
        raise ErrorCalibracion('las distancias deben ser positivas y finitas')
    if not math.isfinite(f_inicial_px) or f_inicial_px <= 0:
        raise ErrorCalibracion('la focal inicial debe ser positiva')
    rango = max(d) - min(d)
    if rango < MIN_RANGO_ERROR_CM:
        raise ErrorCalibracion(f'las distancias cubren solo {rango:.1f} cm: se necesitan al menos '
                               f'{MIN_RANGO_ERROR_CM:g} cm de separación (mejor {MIN_RANGO_AVISO_CM:g} o más)')
    f, it = f_inicial_px, 0
    for it in range(1, max_iter + 1):
        z = [float(v) for v in z_estimada_cm(f)]
        if len(z) != len(d) or not all(math.isfinite(v) and v > 0 for v in z):
            raise ErrorCalibracion('la medición de z dio valores no válidos')
        k, b, _ = regresion(d, z)
        if k <= 0:
            raise ErrorCalibracion('la z medida no crece con la distancia de la regla: revisar las mediciones')
        f_nueva = f / k
        if abs(k - 1.0) < tol:
            break
        f = f_nueva
    else:
        raise ErrorCalibracion('el ajuste no convergió: las mediciones no son coherentes con una cámara pin-hole')
    offset = b / k                      # z, k y b son los de la focal final (k ≈ 1): no se vuelve a medir
    res = tuple(zz - (dd + offset) for dd, zz in zip(d, z))
    rms = math.sqrt(sum(r * r for r in res) / len(res))
    adv: List[str] = []
    if rms > RMS_FALLO_CM:
        raise ErrorCalibracion(f'el ajuste deja un error de {rms:.2f} cm (máximo admitido {RMS_FALLO_CM:g}): '
                               'el tag o la regla se movieron, o la cámara se desenfocó. Repetir las capturas')
    if rms > RMS_AVISO_CM:
        adv.append(f'error del ajuste {rms:.2f} cm (> {RMS_AVISO_CM:g}): revisar las mediciones con regla')
    if rango < MIN_RANGO_AVISO_CM:
        adv.append(f'rango de distancias {rango:.1f} cm (< {MIN_RANGO_AVISO_CM:g}): el offset queda poco determinado')
    if abs(offset) > OFFSET_AVISO_CM:
        adv.append(f'offset {offset:+.1f} cm: el centro óptico no suele estar a más de {OFFSET_AVISO_CM:g} cm del frente de la lente')
    fov = fov_desde_focal(ancho_px, f)
    if not FOV_PLAUSIBLE_DEG[0] <= fov <= FOV_PLAUSIBLE_DEG[1]:
        adv.append(f'campo de visión resultante {fov:.0f}° fuera de lo habitual ({FOV_PLAUSIBLE_DEG[0]:g}-{FOV_PLAUSIBLE_DEG[1]:g}°): '
                   'revisar el tamaño del tag dado')
    return Ajuste(f, offset, rms, it, res, tuple(adv))


# ------------------------------------------------------------------ resultado en YAML
@dataclass(frozen=True)
class ParametrosCamara:
    ancho: int
    alto: int
    fx: float
    fy: float
    cx: float
    cy: float
    tamano_tag_m: float
    offset_cm: float
    rms_cm: float
    n_distancias: int
    rango_cm: Tuple[float, float]
    fecha: str
    advertencias: Tuple[str, ...] = ()

    @property
    def fov_h_deg(self) -> float:
        return fov_desde_focal(self.ancho, self.fx)

    def tupla(self) -> Tuple[float, float, float, float]:
        """(fx, fy, cx, cy): lo que espera `herramienta_apriltag.detectar_en`."""
        return self.fx, self.fy, self.cx, self.cy


def parametros_desde_ajuste(a: Ajuste, ancho: int, alto: int, tamano_tag_m: float, distancias_cm: Sequence[float],
                            fecha: Optional[str] = None) -> ParametrosCamara:
    return ParametrosCamara(
        ancho, alto, a.f_px, a.f_px, ancho / 2, alto / 2, tamano_tag_m, a.offset_cm, a.rms_cm,
        len(set(round(v, 2) for v in distancias_cm)), (min(distancias_cm), max(distancias_cm)),
        fecha or datetime.datetime.now().isoformat(timespec='seconds'), a.advertencias)


def guardar_camara(ruta: str, p: ParametrosCamara) -> None:
    """Escritura atómica. Es un RESULTADO de la calibración: va a la carpeta del experimento, con fecha."""
    datos = {
        'version': VERSION,
        'imagen': {'ancho': p.ancho, 'alto': p.alto},
        'intrinsecos': {'fx': p.fx, 'fy': p.fy, 'cx': p.cx, 'cy': p.cy},
        'tag': {'tamano_m': p.tamano_tag_m},
        'ajuste': {'metodo': 'regla', 'fov_h_deg': round(p.fov_h_deg, 3), 'offset_cm': p.offset_cm,
                   'rms_cm': p.rms_cm, 'n_distancias': p.n_distancias, 'rango_cm': list(p.rango_cm),
                   'fecha': p.fecha, 'advertencias': list(p.advertencias)},
    }
    texto = ye.volcar(datos, 'Calibración de la cámara con regla y AprilTag, generada por vision/calibrar.py.\n'
                             'Supone punto principal en el centro y SIN distorsión. fx = fy.\n'
                             'No editar a mano: repetir la calibración si cambia la cámara, la resolución o el foco.')
    carpeta = os.path.dirname(os.path.abspath(ruta))
    fd, tmp = tempfile.mkstemp(dir=carpeta, prefix='.camara_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(texto)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cargar_camara(ruta: str) -> ParametrosCamara:
    """Falla (ErrorYaml, ValueError) ante cualquier valor dudoso, clave desconocida o duplicada."""
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'camara', ('version', 'imagen', 'intrinsecos', 'tag', 'ajuste'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('camara: versión desconocida')
    im = ye.seccion(d, 'imagen', 'camara')
    ye.exigir_claves(im, 'camara.imagen', ('ancho', 'alto'))
    ancho, alto = ye.entero(im, 'ancho', 'camara.imagen', 16, 16384), ye.entero(im, 'alto', 'camara.imagen', 16, 16384)
    it = ye.seccion(d, 'intrinsecos', 'camara')
    ye.exigir_claves(it, 'camara.intrinsecos', ('fx', 'fy', 'cx', 'cy'))
    fx = ye.numero(it, 'fx', 'camara.intrinsecos', 0, exclusivo_min=True)
    fy = ye.numero(it, 'fy', 'camara.intrinsecos', 0, exclusivo_min=True)
    cx = ye.numero(it, 'cx', 'camara.intrinsecos', 0, ancho)
    cy = ye.numero(it, 'cy', 'camara.intrinsecos', 0, alto)
    tag = ye.seccion(d, 'tag', 'camara')
    ye.exigir_claves(tag, 'camara.tag', ('tamano_m',))
    tamano = ye.numero(tag, 'tamano_m', 'camara.tag', 0.005, 0.5)
    aj = ye.seccion(d, 'ajuste', 'camara')
    ye.exigir_claves(aj, 'camara.ajuste', ('metodo', 'fov_h_deg', 'offset_cm', 'rms_cm', 'n_distancias', 'rango_cm',
                                           'fecha', 'advertencias'))
    if aj['metodo'] != 'regla':
        raise ye.ErrorYaml("camara.ajuste.metodo: solo se admite 'regla'")
    rango = aj['rango_cm']
    if (not isinstance(rango, list) or len(rango) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                                                              or not math.isfinite(v) for v in rango)):
        raise ye.ErrorYaml('camara.ajuste.rango_cm: debe ser [mínimo, máximo]')
    adv = aj['advertencias']
    if not isinstance(adv, list) or not all(isinstance(a, str) for a in adv):
        raise ye.ErrorYaml('camara.ajuste.advertencias: debe ser una lista de textos')
    return ParametrosCamara(
        ancho, alto, fx, fy, cx, cy, tamano, ye.numero(aj, 'offset_cm', 'camara.ajuste', -50, 50),
        ye.numero(aj, 'rms_cm', 'camara.ajuste', 0, 100), ye.entero(aj, 'n_distancias', 'camara.ajuste', 1, 1000),
        (float(rango[0]), float(rango[1])), ye.texto(aj, 'fecha', 'camara.ajuste'), tuple(adv))
