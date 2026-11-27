#!/usr/bin/env python3
"""Mide la pose de un AprilTag con una cámara calibrada: corrige la distorsión, filtra por calidad y agrega cuadros.

    # Una medición agregada de 10 cuadros (la pose solo se entrega si el tag es único, de calidad y estable):
    python3 scripts/camara/medir_tag.py una --camara 0 --camara-yaml experimentos/dia03_camara/camara_calibrada.yaml --tag-id 3

    # Flujo continuo, un JSON por cuadro, con mediana móvil de 5:
    python3 scripts/camara/medir_tag.py continuo --camara 0 --camara-yaml ... --ventana 5 --segundos 30

    # Comparar con la verdad medida con regla y transportador y guardar la evidencia (también lo que falle):
    python3 scripts/camara/medir_tag.py comparar --camara 0 --camara-yaml ... --esperado-z-cm 28 --esperado-x-cm 0 \\
        --esperado-dth 0 --csv experimentos/dia03_camara_medicion/mediciones.csv

    # Resumen de la evidencia (errores medio, p95 y máximo contra una tolerancia):
    python3 scripts/camara/medir_tag.py resumen --csv experimentos/dia03_camara_medicion/mediciones.csv

La fuente es `--camara` (índice, ruta o pipeline), `--imagen` o `--video`. La cámara se da con `--camara-yaml` (una
calibración de `calibrar_focal.py` o `calibrar_damero.py`; con la de damero hay que añadir `--tamano-mm`) o, SIN
calibrar y solo para pruebas, con `--fov-h` y `--tamano-mm`.

Pose en el sistema de la CÁMARA (x a la derecha, y hacia abajo, z hacia adelante), x, y, z en METROS y dth en GRADOS.
NO está en el marco del dock: faltan el montaje de la cámara en el carrito y `dock_frames.yaml`.

Códigos de salida: 0 medición aceptada; 1 error o datos no válidos; 2 no aceptada (sin tag, inestable, poca calidad)
o la evidencia no cumple; 3 faltan dependencias. Solo lee la cámara: no mueve ningún robot.
"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def construir_parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='comando', required=True)

    def fuente(q):
        g = q.add_mutually_exclusive_group()
        g.add_argument('--camara', help='índice, ruta (/dev/video0) o pipeline GStreamer (defecto 0)')
        g.add_argument('--imagen', help='archivo de imagen')
        g.add_argument('--video', help='archivo de video')
        q.add_argument('--ancho', type=int, help='ancho pedido a la cámara')
        q.add_argument('--alto', type=int, help='alto pedido a la cámara')
        q.add_argument('--camara-yaml', help='camara_calibrada.yaml')
        q.add_argument('--tamano-mm', type=float, help='lado del cuadrado negro del tag, medido con regla o calibre')
        q.add_argument('--fov-h', type=float, help='SIN calibrar: campo de visión horizontal aproximado (solo pruebas)')
        q.add_argument('--tag-id', type=int, help='id del tag; si hay más de uno a la vista y no se da, no se mide')
        q.add_argument('--margen-min', type=float, default=30.0, help='margen de decisión mínimo (provisional, defecto 30)')
        q.add_argument('--hamming-max', type=int, default=0, help='hamming máximo (defecto 0)')

    u = sub.add_parser('una', help='una medición agregada de varios cuadros')
    fuente(u)
    u.add_argument('--cuadros', type=int, default=10, help='cuadros a promediar (con --imagen se usa 1)')

    c = sub.add_parser('continuo', help='un JSON por cuadro, con mediana móvil opcional')
    fuente(c)
    c.add_argument('--ventana', type=int, default=0, help='mediana móvil de los últimos N cuadros válidos (0 = sin filtro)')
    c.add_argument('--max-cuadros', type=int)
    c.add_argument('--segundos', type=float)

    k = sub.add_parser('comparar', help='mide y compara con regla y transportador; guarda la evidencia en un CSV')
    fuente(k)
    k.add_argument('--cuadros', type=int, default=10)
    k.add_argument('--esperado-z-cm', type=float, required=True, help='distancia por la regla: del frente de la lente al plano del tag')
    k.add_argument('--esperado-x-cm', type=float, help='desplazamiento lateral por la regla (+ a la derecha del eje)')
    k.add_argument('--esperado-dth', type=float, help='giro del tag por el transportador, en grados')
    k.add_argument('--offset-cm', type=float, help='desfase de la regla (centro óptico detrás del frente de la lente); '
                   'si la calibración lo trae se usa solo')
    k.add_argument('--csv', required=True, help='evidencia: se añade una fila por medición')
    k.add_argument('--observaciones', default='', help='sin comas ni saltos de línea')

    r = sub.add_parser('resumen', help='estadística de la evidencia')
    r.add_argument('--csv', required=True)
    r.add_argument('--tol-cm', type=float, default=1.0, help='error máximo de x y z (provisional, defecto 1 cm)')
    r.add_argument('--tol-deg', type=float, default=2.0, help='error máximo de dth (provisional, defecto 2°)')
    return p


def _redondeo(d):
    return {k: (round(v, 5) if isinstance(v, float) else _redondeo(v) if isinstance(v, dict) else v) for k, v in d.items()}


def main(argv=None, abrir_camara=None):
    args = construir_parser().parse_args(argv)
    try:
        from vision import medicion as md
        from vision.calibracion_focal import ErrorCalibracion
        from comun.yaml_estricto import ErrorYaml
    except ImportError as e:
        print(f'faltan dependencias de visión: {e}\n  instalar con: bash scripts/preparar_entorno.sh --vision '
              '(o pip install -r requirements-vision.txt)', file=sys.stderr)
        return 3
    try:
        if args.comando == 'resumen':
            r = md.resumen(args.csv, args.tol_cm, args.tol_deg)
            print(md.informe_resumen(r))
            return 0 if r.cumple else 2

        criterios = md.Criterios(args.margen_min, args.hamming_max)
        fotogramas = _fuente(args, md, abrir_camara)
        try:
            primero = next(fotogramas, None)
            if primero is None:
                raise md.ErrorMedicion('la fuente no entregó ninguna imagen')
            cam = _camara(args, md, primero)
            if not cam.calibrada:
                print('AVISO: cámara SIN calibrar (campo de visión aproximado): un 6 % de error en el campo de visión da ~2 cm '
                      'de error en z. Usar --camara-yaml.', file=sys.stderr)
            if args.comando == 'continuo':
                return _continuo(args, md, cam, criterios, primero, fotogramas)
            n = 1 if args.imagen else args.cuadros
            if not 1 <= n <= 1000:
                raise md.ErrorMedicion('--cuadros debe estar entre 1 y 1000')
            meds = [cam.medir(primero, args.tag_id, criterios)]
            for cuadro in fotogramas:
                if len(meds) >= n:
                    break
                meds.append(cam.medir(cuadro, args.tag_id, criterios))
        finally:
            fotogramas.close()
        ag = md.agregar(meds)
        salida = {'modo': args.comando, 'ts': round(time.time(), 3), 'aceptada': ag.aceptada, 'motivo': ag.motivo,
                  'id': ag.id, 'n_cuadros': ag.n_cuadros, 'n_validos': ag.n_validos}
        # la pose solo se entrega si la medición fue aceptada
        salida.update({c: (getattr(ag, c) if ag.aceptada else None) for c in ('x_m', 'y_m', 'z_m', 'dth_deg')})
        salida.update({c: getattr(ag, c) for c in ('rango_x_m', 'rango_y_m', 'rango_z_m', 'rango_dth_deg')})
        salida.update({'rechazos': dict(ag.motivos_rechazo), 'calibrada': cam.calibrada,
                       'distorsion_corregida': cam.con_distorsion_corregida, 'camara': cam.origen})
        if args.comando == 'comparar':
            esperado = md.Esperado(args.esperado_z_cm, args.esperado_x_cm, args.esperado_dth)
            fila = md.registrar_comparacion(args.csv, ag, esperado, cam, args.offset_cm, args.observaciones)
            salida['esperado'] = {'z_cm': esperado.z_cm, 'x_cm': esperado.x_cm, 'dth_deg': esperado.dth_deg}
            salida['errores'] = {k: (float(fila[k]) if fila[k] != '' else None) for k in ('err_z_cm', 'err_x_cm', 'err_dth_deg')}
            salida['offset_cm'] = float(fila['offset_cm']) if fila['offset_cm'] != '' else None
            if salida['offset_cm'] is None and cam.calibrada:
                print('AVISO: sin desfase de la regla (--offset-cm): el error de z incluye la distancia entre el frente de la '
                      'lente y el centro óptico.', file=sys.stderr)
            print(f'fila añadida a {args.csv}', file=sys.stderr)
        print(json.dumps(_redondeo(salida), ensure_ascii=False))
        return 0 if ag.aceptada else 2
    except (md.ErrorMedicion, ErrorCalibracion, ErrorYaml, md.ht.ErrorHerramienta) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\ninterrumpido', file=sys.stderr)
        return 1


def _fuente(args, md, abrir_camara):
    if args.imagen:
        return md.fotogramas_imagen(args.imagen)
    if args.video:
        return md.fotogramas_video(args.video)
    if abrir_camara is None:
        import cv2
        origen = args.camara if args.camara is not None else '0'
        origen = int(origen) if str(origen).isdigit() else origen

        def abrir_camara():
            cap = cv2.VideoCapture(origen)
            if args.ancho:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.ancho)
            if args.alto:
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.alto)
            return cap
    return md.fotogramas_camara(abrir_camara)


def _camara(args, md, primero):
    if args.camara_yaml:
        if args.fov_h is not None:
            raise md.ErrorMedicion('usar --camara-yaml o --fov-h, no ambos')
        return md.CamaraTag.desde_yaml(args.camara_yaml, args.tamano_mm)
    if args.fov_h is None or args.tamano_mm is None:
        raise md.ErrorMedicion('indicar --camara-yaml, o --fov-h y --tamano-mm (sin calibrar, solo para pruebas)')
    alto, ancho = primero.shape[:2]
    return md.CamaraTag.desde_fov(ancho, alto, args.fov_h, args.tamano_mm)


def _continuo(args, md, cam, criterios, primero, fotogramas):
    filtro = md.FiltroMediana(args.ventana) if args.ventana else None
    validos, n, t0 = 0, 0, time.monotonic()

    def cuadros():
        yield primero
        yield from fotogramas

    for cuadro in cuadros():
        m = cam.medir(cuadro, args.tag_id, criterios)
        n += 1
        validos += m.valido
        salida = {'modo': 'continuo', 'n': n, 'ts': round(m.ts, 3), 'valido': m.valido, 'motivo': m.motivo, 'id': m.id,
                  'x_m': m.x_m, 'y_m': m.y_m, 'z_m': m.z_m, 'dth_deg': m.dth_deg, 'margen': m.margen, 'hamming': m.hamming}
        if filtro is not None:
            salida['filtrada'] = filtro.agregar(m)
        print(json.dumps(_redondeo(salida), ensure_ascii=False), flush=True)
        if (args.max_cuadros and n >= args.max_cuadros) or (args.segundos and time.monotonic() - t0 >= args.segundos):
            break
    print(f'{validos} de {n} cuadros válidos', file=sys.stderr)
    return 0 if validos else 2


if __name__ == '__main__':
    sys.exit(main())
