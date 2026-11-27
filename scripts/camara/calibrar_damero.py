#!/usr/bin/env python3
"""Calibra la cámara con un damero: focal, punto principal y DISTORSIÓN del lente.

Usar cuando la validación con el tag a los lados del cuadro falla (`calibrar_focal.py validar`): el método de la regla
no corrige la distorsión. Procedimiento: docs/procedimiento_calibracion_damero.md.

    # 0) Generar el damero para imprimir al 100 % (SVG a tamaño real) y medir con regla el cuadro impreso:
    python3 scripts/camara/calibrar_damero.py crear --cols 9 --filas 6 --cuadro-mm 20 --salida experimentos/damero/

    # 1) Tomar imágenes: mover e inclinar el damero frente a la cámara; guarda solo cuando está quieto y es una pose nueva
    python3 scripts/camara/calibrar_damero.py capturar --camara 0 --ancho 640 --alto 480 --salida experimentos/dia03_damero/

    # 2) Calcular y guardar camara_calibrada.yaml (no sobrescribe sin --sobrescribir):
    python3 scripts/camara/calibrar_damero.py calcular --imagenes experimentos/dia03_damero/ --cuadro-mm 20

    # 3) Validar con imágenes NUEVAS, y luego con el tag a los lados (calibrar_focal.py validar --camara-yaml ... --tamano-mm 59.5)
    python3 scripts/camara/calibrar_damero.py validar --camara-yaml experimentos/dia03_damero/camara_calibrada.yaml \\
        --imagenes experimentos/dia03_damero_validacion/

`--cols` y `--filas` son las esquinas INTERIORES (un damero de 10x7 cuadros tiene 9x6). Códigos de salida: 0 bien;
1 error o datos no válidos; 2 la validación NO cumple; 3 faltan dependencias.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def construir_parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='comando', required=True)

    def patron(q, cuadro=True):
        q.add_argument('--cols', type=int, default=9, help='esquinas interiores por fila (defecto 9)')
        q.add_argument('--filas', type=int, default=6, help='esquinas interiores por columna (defecto 6)')
        if cuadro:
            q.add_argument('--cuadro-mm', type=float, default=20.0,
                           help='lado del cuadro IMPRESO medido con regla (defecto 20: el damero 9x6 cabe en una hoja A4); no afecta a la focal ni a la distorsión')

    c = sub.add_parser('crear', help='genera el damero en PNG y SVG a tamaño real')
    patron(c)
    c.add_argument('--salida', default='damero', help='carpeta de salida')

    k = sub.add_parser('capturar', help='toma automática: el damero debe estar quieto y en una pose nueva')
    patron(k)
    k.add_argument('--camara', default='0', help='índice, ruta (/dev/video0) o pipeline GStreamer')
    k.add_argument('--ancho', type=int)
    k.add_argument('--alto', type=int)
    k.add_argument('--objetivo', type=int, default=20, help='imágenes a guardar (10 a 100)')
    k.add_argument('--max-segundos', type=float, default=300.0)
    k.add_argument('--salida', required=True)

    q = sub.add_parser('calcular', help='calibra con las imágenes de una carpeta')
    patron(q)
    q.add_argument('--imagenes', required=True)
    q.add_argument('--modelo', choices=('simple', 'completo'), default='simple',
                   help="simple = k1, k2 (defecto, estable con pocas vistas); completo = k1, k2, p1, p2, k3")
    q.add_argument('--salida', help='camara_calibrada.yaml (por defecto dentro de la carpeta de imágenes)')
    q.add_argument('--sobrescribir', action='store_true')

    v = sub.add_parser('validar', help='error de reproyección en imágenes nuevas')
    v.add_argument('--camara-yaml', required=True)
    v.add_argument('--imagenes', required=True)
    v.add_argument('--tolerancia-px', type=float, default=0.7, help='error de reproyección rms máximo (defecto 0.7)')
    return p


def main(argv=None):
    args = construir_parser().parse_args(argv)
    try:
        from vision import calibracion_damero as dm
        from vision.calibracion_focal import ErrorCalibracion, guardar_camara
        from comun.yaml_estricto import ErrorYaml
    except ImportError as e:
        print(f'faltan dependencias de visión: {e}\n  instalar con: bash scripts/preparar_entorno.sh --vision '
              '(o pip install -r requirements-vision.txt)', file=sys.stderr)
        return 3
    try:
        if args.comando == 'validar':
            r = dm.validar(args.camara_yaml, Path(args.imagenes), args.tolerancia_px)
            print(dm.informe_validacion(r))
            return 0 if r.ok else 2
        pat = dm.Patron(args.cols, args.filas, args.cuadro_mm / 1000)
        if args.comando == 'crear':
            salida = Path(args.salida)
            salida.mkdir(parents=True, exist_ok=True)
            base = salida / f'damero_{args.cols}x{args.filas}_{args.cuadro_mm:g}mm'
            dm.ht.guardar_png(base.with_suffix('.png'), dm.imagen_damero(pat))
            base.with_suffix('.svg').write_text(dm.svg_damero(pat), encoding='utf-8')
            print(f'{base.with_suffix(".png")} y {base.with_suffix(".svg")}\nImprima el SVG al 100 % (sin "ajustar a la página") '
                  f'en una hoja que quepa ({(args.cols + 3) * args.cuadro_mm:g} x {(args.filas + 3) * args.cuadro_mm:g} mm), '
                  'péguelo en una superficie RÍGIDA y PLANA y mida con regla el lado de un cuadro.')
            return 0
        if args.comando == 'capturar':
            import cv2

            def abrir():
                origen = int(args.camara) if str(args.camara).isdigit() else args.camara
                cap = cv2.VideoCapture(origen)
                if args.ancho:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.ancho)
                if args.alto:
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.alto)
                return cap

            print('Mueva e incline el damero frente a la cámara: inclínelo en varias direcciones, acérquelo y aléjelo y llévelo '
                  'hasta los bordes y esquinas del cuadro. Se guarda solo cuando está quieto y en una pose nueva. Ctrl-C termina.')
            try:
                guardadas = dm.capturar(abrir, pat, Path(args.salida), objetivo=args.objetivo, max_s=args.max_segundos)
            except KeyboardInterrupt:
                print('\ninterrumpido: las imágenes ya guardadas se conservan')
                return 1
            print(f'\n{len(guardadas)} imágenes en {args.salida}\nsiguiente: python3 scripts/camara/calibrar_damero.py calcular '
                  f'--imagenes {args.salida} --cols {args.cols} --filas {args.filas} --cuadro-mm {args.cuadro_mm:g}')
            return 0 if len(guardadas) >= dm.MIN_IMAGENES_ERROR else 1
        carpeta = Path(args.imagenes)
        destino = Path(args.salida) if args.salida else carpeta / 'camara_calibrada.yaml'
        if destino.exists() and not args.sobrescribir:
            print(f'error: {destino} ya existe; use --salida otra ruta o --sobrescribir', file=sys.stderr)
            return 1
        r = dm.calcular(carpeta, pat, args.modelo)
        print(dm.informe(r))
        guardar_camara(str(destino), r.parametros)
        print(f'\nguardado: {destino}')
        return 0
    except (ErrorCalibracion, ErrorYaml, dm.ht.ErrorHerramienta) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\ninterrumpido', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
