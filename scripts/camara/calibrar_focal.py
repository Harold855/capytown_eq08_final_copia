#!/usr/bin/env python3
"""Calibra la focal de la cámara con un AprilTag y distancias medidas con regla (sin damero).

    # 1) Tomar las capturas (guía interactiva; solo lee la cámara, no mueve ningún robot):
    python3 scripts/camara/calibrar_focal.py capturar --camara 0 --ancho 640 --alto 480 \\
        --distancias 15,20,25,30,35,40 --tamano-mm 59.5 --salida experimentos/dia03_camara/

    # 2) Calcular la focal y el offset de la regla (no sobrescribe un resultado existente):
    python3 scripts/camara/calibrar_focal.py calcular --csv experimentos/dia03_camara/capturas.csv --tamano-mm 59.5

    # 3) Validar con capturas NUEVAS en otra carpeta: otras distancias y el tag también a los LADOS del cuadro
    #    (--posicion izq / der) a la misma distancia: z debe salir igual; si no, el lente distorsiona.
    python3 scripts/camara/calibrar_focal.py validar --camara-yaml experimentos/dia03_camara/camara_calibrada.yaml \\
        --csv experimentos/dia03_camara_validacion/capturas.csv

`--tamano-mm` es el lado del cuadrado NEGRO del tag impreso, medido con regla o calibre (no el nominal).
También se puede calcular a partir de imágenes tomadas por otro medio (p. ej. un nodo de ROS) con un CSV
`imagen,distancia_cm`. Procedimiento completo: docs/procedimiento_calibracion_camara.md.

Códigos de salida: 0 bien; 1 error o datos no válidos; 2 la validación NO cumple; 3 faltan dependencias.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))


def _distancias(texto):
    try:
        return [float(x) for x in texto.split(',') if x.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(f'distancias mal escritas: {texto!r} (ejemplo: 15,20,25,30,35,40)')


def construir_parser():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='comando', required=True)

    c = sub.add_parser('capturar', help='toma capturas guiadas con la cámara')
    c.add_argument('--camara', default='0', help='índice, ruta (/dev/video0) o pipeline GStreamer')
    c.add_argument('--ancho', type=int, help='ancho pedido a la cámara')
    c.add_argument('--alto', type=int, help='alto pedido a la cámara')
    c.add_argument('--distancias', type=_distancias, required=True, help='en cm, separadas por comas (mínimo 3, ideal 6)')
    c.add_argument('--tamano-mm', type=float, required=True, help='lado del cuadrado negro medido con regla o calibre')
    c.add_argument('--tag-id', type=int, help='id del tag (si hay más de uno a la vista)')
    c.add_argument('--cuadros', type=int, default=10, help='cuadros por distancia')
    c.add_argument('--posicion', default='centro', help='dónde está el tag en el cuadro: centro (para calibrar), izq, der, arriba, abajo (para validar)')
    c.add_argument('--salida', required=True, help='carpeta donde se guardan imágenes/ y capturas.csv')

    k = sub.add_parser('calcular', help='ajusta la focal y el offset a partir de las capturas')
    k.add_argument('--csv', required=True, help='capturas.csv (imagen,distancia_cm)')
    k.add_argument('--tamano-mm', type=float, required=True)
    k.add_argument('--tag-id', type=int)
    k.add_argument('--fov-inicial', type=float, default=70.0, help='punto de partida del ajuste; no cambia el resultado')
    k.add_argument('--salida', help='camara_calibrada.yaml (por defecto junto al CSV)')
    k.add_argument('--sobrescribir', action='store_true', help='permite reemplazar un resultado existente')

    v = sub.add_parser('validar', help='comprueba la calibración con capturas nuevas')
    v.add_argument('--camara-yaml', required=True)
    v.add_argument('--csv', required=True)
    v.add_argument('--tag-id', type=int)
    v.add_argument('--tolerancia-cm', type=float, default=1.0, help='error máximo admitido en z (defecto 1 cm)')
    return p


def main(argv=None):
    args = construir_parser().parse_args(argv)
    try:
        from vision import calibrar as cal
        from vision.calibracion_focal import ErrorCalibracion, guardar_camara
        from comun.yaml_estricto import ErrorYaml
    except ImportError as e:
        print(f'faltan dependencias de visión: {e}\n  instalar con: bash scripts/preparar_entorno.sh --vision '
              '(o pip install -r requirements-vision.txt)', file=sys.stderr)
        return 3
    try:
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

            ruta = cal.capturar(abrir, args.distancias, Path(args.salida), cuadros=args.cuadros, tag_id=args.tag_id,
                                tamano_mm=args.tamano_mm, posicion=args.posicion)
            print(f'\ncapturas en {ruta}\nsiguiente: python3 scripts/camara/calibrar_focal.py calcular --csv {ruta} '
                  f'--tamano-mm {args.tamano_mm:g}')
            return 0
        if args.comando == 'calcular':
            destino = Path(args.salida) if args.salida else Path(args.csv).with_name('camara_calibrada.yaml')
            if destino.exists() and not args.sobrescribir:
                print(f'error: {destino} ya existe; use --salida otra ruta o --sobrescribir', file=sys.stderr)
                return 1
            r = cal.calcular(Path(args.csv), args.tamano_mm, args.tag_id, args.fov_inicial)
            print(cal.informe_calculo(r))
            guardar_camara(str(destino), r.parametros)
            print(f'\nguardado: {destino}\nusar con la herramienta del docente:\n  {cal.comando_herramienta(r.parametros)}')
            return 0
        r = cal.validar(args.camara_yaml, Path(args.csv), args.tag_id, args.tolerancia_cm)
        print(cal.informe_validacion(r))
        return 0 if r.ok else 2
    except (ErrorCalibracion, ErrorYaml, cal.ht.ErrorHerramienta) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\ninterrumpido', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
