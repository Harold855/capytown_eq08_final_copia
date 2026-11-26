"""Calibración de la focal de la cámara con un AprilTag y distancias medidas con regla (orquestación).

Capturar (con la cámara) -> calcular (ajuste de focal y offset) -> validar (con capturas nuevas). La matemática
está en `calibracion_focal.py`; aquí está la lectura de imágenes y CSV, la detección con la herramienta del
docente y la captura interactiva. Solo LEE la cámara: no mueve ningún robot.
"""
from __future__ import annotations

import csv
import dataclasses
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import herramienta as hv
from .calibracion_focal import (Ajuste, ErrorCalibracion, ParametrosCamara, ajustar_focal, cargar_camara,
                                focal_desde_fov, parametros_desde_ajuste)

ht = hv.ht
FOV_INICIAL_DEG = 70.0
DTH_AVISO_DEG = 15.0
DISTANCIA_CM = (5.0, 100.0)
TAMANO_MM = (5.0, 500.0)
ENCABEZADO_CSV = ['imagen', 'distancia_cm', 'posicion']
ENCABEZADO_CSV_ANTIGUO = ENCABEZADO_CSV[:2]      # se sigue leyendo; todas las filas cuentan como 'centro'
POSICION_CENTRO = 'centro'


# ------------------------------------------------------------------ lectura
def leer_csv(ruta: Path) -> List[Tuple[Path, float, str]]:
    """`imagen,distancia_cm[,posicion]`; las rutas son relativas a la carpeta del CSV. `posicion` es un nombre
    libre (centro, izq, der, arriba, abajo...): la calibración usa solo 'centro'; la validación las separa.
    Falla cerrado ante filas dudosas."""
    ruta = Path(ruta)
    try:
        with open(ruta, newline='', encoding='utf-8') as f:
            lector = csv.reader(f)
            filas = [r for r in lector if any(c.strip() for c in r)]
    except OSError as e:
        raise ErrorCalibracion(f'no se pudo leer {ruta.name}: {e.strerror or e}') from e
    encabezado = [c.strip() for c in filas[0]] if filas else []
    if encabezado not in (ENCABEZADO_CSV, ENCABEZADO_CSV_ANTIGUO):
        raise ErrorCalibracion(f'{ruta.name}: el encabezado debe ser {",".join(ENCABEZADO_CSV)} (la última es opcional)')
    out = []
    for n, r in enumerate(filas[1:], start=2):
        if len(r) != len(encabezado):
            raise ErrorCalibracion(f'{ruta.name} fila {n}: se esperaban {len(encabezado)} columnas')
        try:
            d = float(r[1])
        except ValueError:
            raise ErrorCalibracion(f'{ruta.name} fila {n}: distancia {r[1]!r} no es un número') from None
        if not math.isfinite(d) or not DISTANCIA_CM[0] <= d <= DISTANCIA_CM[1]:
            raise ErrorCalibracion(f'{ruta.name} fila {n}: distancia {d} cm fuera de {DISTANCIA_CM[0]:g}-{DISTANCIA_CM[1]:g} cm '
                                   '(¿metros en vez de centímetros?)')
        img = ruta.parent / r[0].strip()
        if not img.is_file():
            raise ErrorCalibracion(f'{ruta.name} fila {n}: no existe la imagen {r[0]}')
        pos = r[2].strip().lower() if len(r) == 3 else ''
        out.append((img, d, pos or POSICION_CENTRO))
    if not out:
        raise ErrorCalibracion(f'{ruta.name}: no tiene capturas')
    return out


@dataclass(frozen=True)
class Captura:
    nombre: str
    distancia_cm: float
    imagen: Any
    posicion: str = POSICION_CENTRO


def cargar_capturas(filas: Sequence[Tuple[Path, float, str]]) -> List[Captura]:
    caps = [Captura(p.name, d, ht.leer_imagen(p), pos) for p, d, pos in filas]
    formas = {c.imagen.shape[:2] for c in caps}
    if len(formas) != 1:
        raise ErrorCalibracion(f'las imágenes tienen tamaños distintos {sorted(formas)}: usar siempre la misma resolución')
    return caps


def _params(f: float, ancho: int, alto: int) -> Tuple[float, float, float, float]:
    return f, f, ancho / 2, alto / 2


def medir_grupos(caps: Sequence[Captura], params: Tuple[float, float, float, float], tamano_m: float,
                 tag_id: Optional[int]) -> Tuple[Dict[Tuple[float, str], List[Tuple[float, float]]], List[str]]:
    """{(distancia, posición): [(z_cm, dth)]} y los nombres de las imágenes sin tag válido."""
    grupos: Dict[Tuple[float, str], List[Tuple[float, float]]] = {}
    sin_tag: List[str] = []
    for c in caps:
        d = hv.pose_tag(c.imagen, params, tamano_m, tag_id)
        if d is None:
            sin_tag.append(c.nombre)
            continue
        grupos.setdefault((round(c.distancia_cm, 2), c.posicion), []).append((d['pose']['z'] * 100, d['pose']['dth']))
    return grupos, sin_tag


# ------------------------------------------------------------------ calcular
@dataclass(frozen=True)
class ResultadoCalculo:
    parametros: ParametrosCamara
    ajuste: Ajuste
    z_por_distancia_cm: Dict[float, float]   # mediana de z medida con la focal ajustada
    n_imagenes: int
    sin_tag: Tuple[str, ...]
    dth_max_deg: float


def calcular(ruta_csv: Path, tamano_mm: float, tag_id: Optional[int] = None, fov_inicial_deg: float = FOV_INICIAL_DEG,
             fecha: Optional[str] = None) -> ResultadoCalculo:
    if not math.isfinite(tamano_mm) or not TAMANO_MM[0] <= tamano_mm <= TAMANO_MM[1]:
        raise ErrorCalibracion(f'--tamano-mm debe estar entre {TAMANO_MM[0]:g} y {TAMANO_MM[1]:g} (lado del cuadrado negro)')
    tamano_m = tamano_mm / 1000
    todas = cargar_capturas(leer_csv(Path(ruta_csv)))
    caps = [c for c in todas if c.posicion == POSICION_CENTRO]      # el ajuste usa solo el tag centrado
    laterales = len(todas) - len(caps)
    if not caps:
        raise ErrorCalibracion(f"ninguna captura tiene posición '{POSICION_CENTRO}': la calibración se hace con el tag centrado")
    alto, ancho = caps[0].imagen.shape[:2]
    f0 = focal_desde_fov(ancho, fov_inicial_deg)
    grupos0, sin_tag = medir_grupos(caps, _params(f0, ancho, alto), tamano_m, tag_id)
    distancias = sorted({round(c.distancia_cm, 2) for c in caps})
    for d in distancias:
        if (d, POSICION_CENTRO) not in grupos0:
            raise ErrorCalibracion(f'a {d:g} cm no se detectó el tag en ninguna imagen: repetir esa distancia '
                                   '(luz, foco, tag completo en el cuadro y de frente)')
    ultimo: Dict[Tuple[float, str], List[Tuple[float, float]]] = {}

    def z_estimada(f: float) -> List[float]:
        nonlocal ultimo
        grupos, _ = medir_grupos(caps, _params(f, ancho, alto), tamano_m, tag_id)
        ultimo = grupos
        return [statistics.median(z for z, _ in grupos[(d, POSICION_CENTRO)]) for d in distancias]

    ajuste = ajustar_focal(distancias, z_estimada, f0, ancho)
    dth_max = max(abs(th) for g in ultimo.values() for _, th in g)
    extra: List[str] = []
    if sin_tag:
        extra.append(f'{len(sin_tag)} imagen(es) sin tag válido, ignoradas: {", ".join(sin_tag[:5])}' +
                     (' ...' if len(sin_tag) > 5 else ''))
    if laterales:
        extra.append(f'{laterales} captura(s) con posición distinta de centro no se usaron en el ajuste (sirven para validar)')
    if dth_max > DTH_AVISO_DEG:
        extra.append(f'el tag estuvo girado hasta {dth_max:.0f}° (> {DTH_AVISO_DEG:g}°): la proporcionalidad del ajuste '
                     'es menos exacta; ponerlo de frente')
    ajuste = dataclasses.replace(ajuste, advertencias=ajuste.advertencias + tuple(extra))
    p = parametros_desde_ajuste(ajuste, ancho, alto, tamano_m, [c.distancia_cm for c in caps], fecha)
    z_med = {d: statistics.median(z for z, _ in ultimo[(d, POSICION_CENTRO)]) for d in distancias}
    return ResultadoCalculo(p, ajuste, z_med, len(caps), tuple(sin_tag), dth_max)


def comando_herramienta(p: ParametrosCamara, camara: str = '0') -> str:
    return (f'python3 vendor/granprix/estacion/herramientas/herramienta_apriltag.py detectar --camara {camara} '
            f'--ancho {p.ancho} --alto {p.alto} --tamano-mm {p.tamano_tag_m * 1000:g} '
            f'--fx {p.fx:.2f} --fy {p.fy:.2f} --cx {p.cx:g} --cy {p.cy:g}')


def informe_calculo(r: ResultadoCalculo) -> str:
    p, a = r.parametros, r.ajuste
    lineas = [
        f'imágenes: {r.n_imagenes} ({len(r.z_por_distancia_cm)} distancias, {p.rango_cm[0]:g}-{p.rango_cm[1]:g} cm), '
        f'resolución {p.ancho}x{p.alto}, tag de {p.tamano_tag_m * 1000:g} mm',
        f'focal ajustada: fx = fy = {p.fx:.1f} px  (campo de visión horizontal {p.fov_h_deg:.1f}°) en {a.iteraciones} iteración(es)',
        f'offset de la regla: {a.offset_cm:+.2f} cm (z real = z regla + offset)',
        f'error del ajuste (rms): {a.rms_cm:.2f} cm',
        'distancia regla -> z medida con la focal ajustada (menos el offset) -> residuo:',
    ]
    for (d, z), res in zip(sorted(r.z_por_distancia_cm.items()), a.residuos_cm):
        lineas.append(f'  {d:6.1f} cm -> {z - a.offset_cm:6.2f} cm   residuo {res:+.2f} cm')
    lineas += [f'AVISO: {adv}' for adv in a.advertencias]
    lineas.append('Supone punto principal en el centro y SIN distorsión: validar con capturas nuevas (subcomando validar).')
    return '\n'.join(lineas)


# ------------------------------------------------------------------ validar
@dataclass(frozen=True)
class ResultadoValidacion:
    filas: Tuple[Tuple[float, str, float, float], ...]   # (distancia regla, posición, z medida - offset, error), cm
    max_error_cm: float
    tolerancia_cm: float
    sin_tag: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.max_error_cm <= self.tolerancia_cm


def validar(ruta_camara: str, ruta_csv: Path, tag_id: Optional[int] = None, tolerancia_cm: float = 1.0
            ) -> ResultadoValidacion:
    """Mide con la calibración guardada capturas NUEVAS (otras distancias) y compara con la regla."""
    if not math.isfinite(tolerancia_cm) or tolerancia_cm <= 0:
        raise ErrorCalibracion('la tolerancia debe ser positiva')
    cam = cargar_camara(ruta_camara)
    caps = cargar_capturas(leer_csv(Path(ruta_csv)))
    alto, ancho = caps[0].imagen.shape[:2]
    if (ancho, alto) != (cam.ancho, cam.alto):
        raise ErrorCalibracion(f'las imágenes son {ancho}x{alto} y la calibración es de {cam.ancho}x{cam.alto}: '
                               'la focal en píxeles solo vale para su resolución')
    grupos, sin_tag = medir_grupos(caps, cam.tupla(), cam.tamano_tag_m, tag_id)
    if not grupos:
        raise ErrorCalibracion('no se detectó el tag en ninguna imagen')
    filas = []
    for d, pos in sorted(grupos):
        z = statistics.median(v for v, _ in grupos[(d, pos)]) - cam.offset_cm
        filas.append((d, pos, z, z - d))
    return ResultadoValidacion(tuple(filas), max(abs(e) for _, _, _, e in filas), tolerancia_cm, tuple(sin_tag))


def informe_validacion(r: ResultadoValidacion) -> str:
    lineas = ['distancia regla / posición -> z medida (menos offset) -> error']
    lineas += [f'  {d:6.1f} cm {pos:>8s} -> {z:6.2f} cm   error {e:+.2f} cm' for d, pos, z, e in r.filas]
    if {pos for _, pos, _, _ in r.filas} == {POSICION_CENTRO}:
        lineas.append('AVISO: solo hay capturas centradas. La distorsión del lente se ve fuera del eje: validar también con el '
                      "tag a los lados del cuadro a la misma distancia (posicion izq, der...).")
    lineas.append(f'error máximo {r.max_error_cm:.2f} cm (tolerancia {r.tolerancia_cm:g} cm): '
                  + ('CUMPLE' if r.ok else 'NO CUMPLE: repetir la calibración'))
    if r.sin_tag:
        lineas.append(f'AVISO: {len(r.sin_tag)} imagen(es) sin tag válido')
    return '\n'.join(lineas)


# ------------------------------------------------------------------ capturar (necesita la cámara)
def capturar(abrir_camara: Callable[[], Any], distancias_cm: Sequence[float], salida: Path, *, cuadros: int = 10,
             posicion: str = POSICION_CENTRO,
             descartar: int = 3, tag_id: Optional[int] = None, tamano_mm: float = 60.0,
             fov_inicial_deg: float = FOV_INICIAL_DEG, leer_entrada: Callable[[str], str] = input,
             escribir: Callable[[str], None] = print, dormir: Callable[[float], None] = time.sleep,
             intervalo_s: float = 0.1, intentos: int = 3) -> Path:
    """Guía la toma: para cada distancia pide colocar el tag, descarta unos cuadros (autoexposición), guarda los
    cuadros donde se ve el tag y los anota en `capturas.csv`. Devuelve la ruta del CSV."""
    if not 1 <= cuadros <= 100:
        raise ErrorCalibracion('--cuadros debe estar entre 1 y 100')
    posicion = posicion.strip().lower()
    if not posicion.isalnum():
        raise ErrorCalibracion('--posicion debe ser una palabra sin espacios ni comas (centro, izq, der, arriba, abajo)')
    for d in distancias_cm:
        if not math.isfinite(d) or not DISTANCIA_CM[0] <= d <= DISTANCIA_CM[1]:
            raise ErrorCalibracion(f'distancia {d} cm fuera de {DISTANCIA_CM[0]:g}-{DISTANCIA_CM[1]:g} cm')
    salida = Path(salida)
    carpeta_img = salida / 'imagenes'
    carpeta_img.mkdir(parents=True, exist_ok=True)
    ruta_csv = salida / 'capturas.csv'
    nuevo = not ruta_csv.exists()
    if not nuevo:
        with open(ruta_csv, newline='', encoding='utf-8') as f:
            if next(csv.reader(f), []) != ENCABEZADO_CSV:
                raise ErrorCalibracion(f'{ruta_csv.name} existente tiene otro encabezado: usar otra carpeta de salida')
    cam = abrir_camara()
    if not cam.isOpened():
        raise ErrorCalibracion('no se pudo abrir la cámara. ¿Otro programa la usa (nodo de ROS, otra terminal)? '
                               '¿El índice o la ruta son los correctos?')
    tamano_m = tamano_mm / 1000
    try:
        with open(ruta_csv, 'a', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(ENCABEZADO_CSV)
            resolucion = None
            for d in distancias_cm:
                for intento in range(1, intentos + 1):
                    resp = leer_entrada(f'\nPonga el tag de frente a {d:g} cm, posición {posicion} (regla desde el frente de la lente '
                                        f'hasta el plano del tag, perpendicular) y pulse Enter [q para terminar]: ').strip().lower()
                    if resp == 'q':
                        escribir('terminado por el usuario')
                        return ruta_csv
                    for _ in range(descartar):
                        cam.read()
                    cuadros_ok: List[Any] = []
                    for _ in range(cuadros):
                        ok, cuadro = cam.read()
                        if not ok:
                            raise ErrorCalibracion('la cámara dejó de entregar imágenes')
                        if resolucion is None:
                            resolucion = cuadro.shape[:2]
                            escribir(f'resolución de captura: {resolucion[1]}x{resolucion[0]} (no la cambie al calibrar ni al usar la pose)')
                        alto, ancho = cuadro.shape[:2]
                        pose = hv.pose_tag(cuadro, _params(focal_desde_fov(ancho, fov_inicial_deg), ancho, alto), tamano_m, tag_id)
                        if pose is not None:
                            cuadros_ok.append(cuadro)
                        dormir(intervalo_s)
                    minimo = math.ceil(0.7 * cuadros)
                    escribir(f'  tag visto en {len(cuadros_ok)} de {cuadros} cuadros')
                    if len(cuadros_ok) >= minimo:
                        for k, cuadro in enumerate(cuadros_ok):
                            nombre = f'd{d:g}cm_{posicion}_{k:02d}.png'
                            ht.guardar_png(carpeta_img / nombre, cuadro)
                            w.writerow([f'imagenes/{nombre}', f'{d:g}', posicion])
                        f.flush()
                        break
                    escribir(f'  se necesitan al menos {minimo}: revisar luz, foco, que el tag esté completo y de frente'
                             + (f' (intento {intento} de {intentos})' if intento < intentos else ''))
                else:
                    raise ErrorCalibracion(f'a {d:g} cm no se vio el tag en suficientes cuadros tras {intentos} intentos')
    finally:
        cam.release()
    return ruta_csv
