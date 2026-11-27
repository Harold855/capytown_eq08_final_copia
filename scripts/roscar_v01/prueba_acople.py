#!/usr/bin/env python3
"""Ensayo del acople fino en UNA estación. No es controlador de carrera.

    python3 scripts/roscar_v01/prueba_acople.py simular --dx -0.06 --dy 0.02 --dth 8 --cd 1.01 --ca 1.09
    python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --marcos carrito/config/marcos.yaml
    python3 scripts/roscar_v01/prueba_acople.py ensayo --estacion 2 --marcos ... --ejecutar --zona-segura

simular: robot simulado, sin ROS.
ensayo:  lee /tag/pose, muestra la pose y la corrección prevista. Sin --ejecutar NO publica ningún comando.
         Con --ejecutar --zona-segura mueve el robot (zona despejada, parada física a mano, nada más publicando velocidades).
Salida: 0 acople válido, 1 no válido o error. Con --csv añade la parada al CSV (el que lee analizar_acople.py).
"""
import argparse
import math
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from carrito.granprix_carrito.acople import (MedidorTag, acoplar, cargar_acople, mover_con_ejecutor,  # noqa: E402
                                             planificar_correccion)
from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo  # noqa: E402
from carrito.granprix_carrito.configuracion import cargar_carrito  # noqa: E402
from carrito.granprix_carrito.gestor_reset import dth_de_cuaternion  # noqa: E402
from carrito.granprix_carrito.pose_dock import LocalizadorDock  # noqa: E402
from carrito.granprix_carrito.transformacion_camara_dock import cargar_marcos  # noqa: E402
from comun.yaml_estricto import ErrorYaml  # noqa: E402

ROBOT = 'eq08-roscar'


def mostrar(res):
    def fila(p):
        return 'sin tag' if p is None else f'dx={p.dx * 100:+6.2f} cm  dy={p.dy * 100:+6.2f} cm  dth={p.dth_deg:+6.2f}°'
    print(f'Inicial : {fila(res.pose_inicial)}')
    for i in res.intentos:
        cmds = ' + '.join(f'giro {math.degrees(c.phi_cmd):+.1f}° avance {c.L_cmd * 100:+.1f} cm' for c in i.efectivos)
        print(f'Corr. {i.n}: {cmds or "(sin movimiento)"}\n          -> {fila(i.pose_despues)}')
    print(f'Resultado: {"VÁLIDO" if res.exito else "NO VÁLIDO"} (motivo: {res.motivo}), {res.correcciones} correcciones, '
          f'{res.duracion_s:.1f} s')


def terminar(res, estacion, cal, csv):
    mostrar(res)
    if csv:
        csv.parent.mkdir(parents=True, exist_ok=True)
        cal.cerrar_parada(estacion, res)
        cal.exportar_paradas(str(csv), anexar=True)
        print(f'Parada añadida a {csv}')
    return 0 if res.exito else 1


def simular(a, cfg, escalas):
    from simulacion.robot_simulado import RobotSimulado
    from geometria_dock.transformaciones import Pose2D
    r = RobotSimulado(Pose2D(0, 0, 0), a.estacion, a.cd, a.ca, 0.01, 0.01, 0.002, 0.25, 0.0, a.semilla)
    r.colocar_en_dock(a.dx, a.dy, a.dth)
    res = acoplar(r.medir, r.mover, cfg, escalas, r.reloj)
    return terminar(res, a.estacion, CalibradorTramo(_estimador(escalas)), a.csv)


def _estimador(escalas):
    from carrito.granprix_carrito.calibracion import EstimadorEscalas
    return EstimadorEscalas(escalas)


def ensayo(a, cfg, mov, escalas):
    import rclpy
    from geometry_msgs.msg import PoseStamped, Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.signals import SignalHandlerOptions
    marcos = cargar_marcos(a.marcos)
    loc = LocalizadorDock(marcos)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nodo = Node('granprix_acople')
    interrumpido = False
    ultima_odom = [None]
    descartes = [0]

    def parar(*_):
        nonlocal interrumpido
        interrumpido = True
    signal.signal(signal.SIGINT, parar)
    signal.signal(signal.SIGTERM, parar)

    def dormir(s):
        fin = time.monotonic() + s
        while time.monotonic() < fin:
            rclpy.spin_once(nodo, timeout_sec=min(0.01, max(0.0, fin - time.monotonic())))

    medidor = MedidorTag(time.monotonic, dormir, a.lecturas, a.espera, a.timeout)

    def tag(msg):
        o, p = msg.pose.orientation, msg.pose.position
        try:
            dth = dth_de_cuaternion(o.x, o.y, o.z, o.w)
            medidor.agregar(loc.pose_desde_tag({'aceptada': True, 'x_m': p.x, 'y_m': p.y, 'z_m': p.z, 'dth_deg': dth}, a.estacion))
        except ValueError:
            descartes[0] += 1

    nodo.create_subscription(PoseStamped, a.topic_tag, tag, qos_profile_sensor_data)
    nodo.create_subscription(Odometry, a.topic_odom, lambda m: ultima_odom.__setitem__(0, time.monotonic()), qos_profile_sensor_data)
    pub = nodo.create_publisher(Twist, a.topic_cmd, 10) if a.ejecutar else None

    def otros():
        return [i for i in nodo.get_publishers_info_by_topic(a.topic_cmd)
                if not (i.node_name == nodo.get_name() and i.node_namespace == nodo.get_namespace())]

    def odom_ok():
        return ultima_odom[0] is not None and time.monotonic() - ultima_odom[0] <= 0.75

    class Salida:
        def publicar(self, v, w):
            msg = Twist()
            msg.linear.x, msg.angular.z = float(v), float(w)
            pub.publish(msg)

    res = None
    movio = [False]
    try:
        dormir(2.0)
        if interrumpido:
            raise RuntimeError('interrumpido antes de empezar')
        if not a.ejecutar:
            p = medidor.medir()
            if p is None:
                raise RuntimeError(f'sin tag en {a.topic_tag} (descartes: {descartes[0]})')
            print(f'Pose: dx={p.dx * 100:+.2f} cm dy={p.dy * 100:+.2f} cm dth={p.dth_deg:+.2f}°  (SOLO CÁLCULO, no se movió nada)')
            for c in planificar_correccion(p, escalas, cfg):
                print(f'  correccion: giro {math.degrees(c.phi_cmd):+.1f}° avance {c.L_cmd * 100:+.1f} cm ({c.t_total:.1f} s)')
            return 0 if p.en_tolerancia else 1
        if otros():
            raise RuntimeError(f'ya hay publicadores de {a.topic_cmd}: coordinar y no ejecutar en paralelo')
        if not odom_ok():
            raise RuntimeError(f'{a.topic_odom} no disponible o desactualizado')
        dormir(1.0)
        if pub.get_subscription_count() < 1:
            raise RuntimeError(f'nadie escucha en {a.topic_cmd}')
        base = mover_con_ejecutor(Salida(), time.monotonic, dormir, mov.ejecutor, cfg, odom_ok,
                                  lambda: interrumpido or bool(otros()), medidor.en_reposo)

        def mover(cmd):
            movio[0] = True
            return base(cmd)
        res = acoplar(medidor.medir, mover, cfg, escalas, time.monotonic, lambda: interrumpido)
    except (RuntimeError, ValueError) as e:
        print(f'ABORTADO: {e}', file=sys.stderr)
        return 1
    finally:
        if pub is not None and movio[0]:      # ceros solo si este script llegó a mover: no se pisa a otro controlador
            fin = time.monotonic() + 1.0
            while time.monotonic() < fin and rclpy.ok():
                pub.publish(Twist())
                rclpy.spin_once(nodo, timeout_sec=0.05)
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return terminar(res, a.estacion, CalibradorTramo(_estimador(escalas)), a.csv)


def comunes(p, suprimir=False):
    """Opciones válidas antes y después del subcomando; en el subcomando no pisan lo ya dado (SUPPRESS)."""
    d = {'default': argparse.SUPPRESS} if suprimir else {}
    p.add_argument('--acople', help='acople.yaml (por defecto el de carrito/config)', **d)
    p.add_argument('--csv', type=Path, help='añade la parada a este CSV', **d)
    p.add_argument('--sin-reversa', action='store_true', help='desactiva la marcha atrás aunque acople.yaml la permita', **d)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    comunes(p)
    sub = p.add_subparsers(dest='modo', required=True)
    s = sub.add_parser('simular')
    comunes(s, True)
    s.add_argument('--estacion', type=int, default=1, choices=(1, 2, 3, 4))
    s.add_argument('--dx', type=float, default=-0.06)
    s.add_argument('--dy', type=float, default=0.02)
    s.add_argument('--dth', type=float, default=8.0, help='grados')
    s.add_argument('--cd', type=float, default=1.0, help='escala real de distancia del robot simulado')
    s.add_argument('--ca', type=float, default=1.0)
    s.add_argument('--semilla', type=int, default=0)
    e = sub.add_parser('ensayo')
    comunes(e, True)
    e.add_argument('--estacion', type=int, required=True, choices=(1, 2, 3, 4))
    e.add_argument('--marcos', default='carrito/config/marcos.yaml')
    e.add_argument('--ejecutar', action='store_true', help='sin esta opción solo calcula, no publica')
    e.add_argument('--zona-segura', action='store_true', help='confirmación humana: espacio libre, parada física, autorizado')
    e.add_argument('--topic-tag', default='/tag/pose')
    e.add_argument('--topic-odom', default='/odom')
    e.add_argument('--topic-cmd', default='/cmd_vel', help='con twist_mux, la entrada autorizada que indique la plantilla')
    e.add_argument('--lecturas', type=int, default=3, help='mediciones del tag que se promedian tras quedar quieto')
    e.add_argument('--espera', type=float, default=0.8, help='s de reposo antes de aceptar lecturas')
    e.add_argument('--timeout', type=float, default=3.0, help='s máximos esperando las lecturas')
    a = p.parse_args(argv)
    if a.modo == 'ensayo' and a.ejecutar and not a.zona_segura:
        p.error('para mover físicamente requiere --zona-segura')
    if a.modo == 'ensayo' and (a.lecturas < 1 or a.espera < 0 or a.timeout <= 0):
        p.error('--lecturas >= 1, --espera >= 0, --timeout > 0')
    try:
        mov, est = cargar_carrito(robot_esperado=ROBOT)
        cfg = cargar_acople(a.acople, mov)
        if a.sin_reversa:
            import dataclasses
            cfg = dataclasses.replace(cfg, reversa_max_m=0.0)
        return simular(a, cfg, est.escalas) if a.modo == 'simular' else ensayo(a, cfg, mov, est.escalas)
    except ImportError as e:
        print(f'ERROR: falta ROS 2 (rclpy y mensajes) para el modo ensayo: {e}', file=sys.stderr)
        return 1
    except (ErrorYaml, OSError, ValueError) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
