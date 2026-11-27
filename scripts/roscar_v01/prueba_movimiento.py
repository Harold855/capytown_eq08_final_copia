#!/usr/bin/env python3
"""Ensayo supervisado de UN movimiento en una zona despejada. No es controlador de carrera."""
import argparse
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import signal
import time
import sys


def argumentos():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('modo',choices=['recta','giro'])
    p.add_argument('--distancia',type=float,default=.25,help='metros, 0 < d <= 2')
    p.add_argument('--grados',type=float,default=15.,help='ángulo con signo, magnitud <= 90')
    p.add_argument('--velocidad',type=float,help='magnitud m/s o rad/s; por defecto .10 o .50')
    p.add_argument('--ejecutar',action='store_true',help='sin esta opción solo calcula, no publica')
    p.add_argument('--zona-segura',action='store_true',help='confirmación humana: espacio libre, parada física disponible, autorizado, sin otros controles')
    p.add_argument('--csv',type=Path,default=Path('experimentos/dia01_roscar/movimientos_odom.csv'))
    p.add_argument('--topic-cmd',default='/cmd_vel',help='tópico de órdenes; con twist_mux, usar la entrada autorizada que indique la plantilla')
    p.add_argument('--topic-odom',default='/odom')
    a=p.parse_args()
    q=a.distancia if a.modo=='recta' else math.radians(a.grados)
    v=a.velocidad if a.velocidad is not None else (.10 if a.modo=='recta' else .50)
    if not math.isfinite(q) or not math.isfinite(v) or not 0<v<=(.10 if a.modo=='recta' else .50) or not (0<q<=2 if a.modo=='recta' else 0<abs(q)<=math.pi/2):
        p.error('Magnitud o velocidad fuera de límites de ensayo (.10 m/s, .50 rad/s, 2 m, 90 grados).')
    dur=abs(q)/v
    if dur>25: p.error('Duración máxima por ensayo: 25 s')
    if a.ejecutar and not a.zona_segura: p.error('Para mover físicamente requiere --zona-segura')
    return a,q,v,dur


def main():
    a,q,v,dur=argumentos()
    print(f'Ensayo {a.modo}: orden={q:.5f} SI, velocidad={v:.3f}, duración={dur:.3f}s')
    if not a.ejecutar:
        print('SOLO CÁLCULO. No se enviaron comandos ROS.')
        return 0
    import rclpy
    from rclpy.node import Node
    from rclpy.signals import SignalHandlerOptions
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node=Node('granprix_ensayo_v01')
    pub=None
    started=False
    interrupted=False
    last=None
    received_at=0.
    def stop_signal(*_):
        nonlocal interrupted
        interrupted=True
    signal.signal(signal.SIGINT,stop_signal)
    signal.signal(signal.SIGTERM,stop_signal)
    def odom(msg):
        nonlocal last,received_at
        p=msg.pose.pose.position; o=msg.pose.pose.orientation
        yaw=math.atan2(2*(o.w*o.z+o.x*o.y),1-2*(o.y*o.y+o.z*o.z))
        last=(p.x,p.y,yaw)
        received_at=time.monotonic()
    sub=node.create_subscription(Odometry,a.topic_odom,odom,qos_profile_sensor_data)
    def tick(s=.05):
        rclpy.spin_once(node,timeout_sec=s)
    def wait(sec):
        end=time.monotonic()+sec
        while time.monotonic()<end and not interrupted: tick()
    def other_publishers():
        return [i for i in node.get_publishers_info_by_topic(a.topic_cmd) if not (i.node_name==node.get_name() and i.node_namespace==node.get_namespace())]
    before=after=None
    status='ABORTADO'
    elapsed=0.
    t0=None
    try:
        wait(2.)
        if interrupted: raise RuntimeError('Interrumpido antes de mover')
        if other_publishers(): raise RuntimeError(f'Ya hay publicadores de {a.topic_cmd}. Coordinar y no ejecutar en paralelo.')
        types=dict(node.get_topic_names_and_types()).get(a.topic_cmd,[])
        if 'geometry_msgs/msg/Twist' not in types: raise RuntimeError(f'{a.topic_cmd} Twist no detectado; revisar driver')
        if last is None or time.monotonic()-received_at>.5: raise RuntimeError(f'{a.topic_odom} no disponible o desactualizado')
        pub=node.create_publisher(Twist,a.topic_cmd,10)
        wait(1.)
        if interrupted or other_publishers() or pub.get_subscription_count()<1: raise RuntimeError('Sin suscriptor compatible, interrupción o publicador concurrente')
        if last is None or time.monotonic()-received_at>.5: raise RuntimeError('Odometría no actualizada')
        before=last
        msg=Twist()
        if a.modo=='recta': msg.linear.x=v
        else: msg.angular.z=math.copysign(v,q)
        t0=time.monotonic()
        started=True
        next_send=t0
        while not interrupted and time.monotonic()-t0<dur:
            now=time.monotonic()
            if now-received_at>.5 or other_publishers() or pub.get_subscription_count()<1:
                raise RuntimeError('Pérdida de odometría/driver o publicador concurrente')
            if now>=next_send:
                pub.publish(msg)
                next_send=now+.05
            tick(.01)
        status='INTERRUMPIDO' if interrupted else 'COMPLETO'
    except Exception as exc:
        print(f'ABORTADO: {exc}',file=sys.stderr)
    finally:
        if started:
            elapsed=time.monotonic()-t0
            # Publicar ceros repetidamente incluso si se recibió Ctrl+C.
            end=time.monotonic()+1.5
            while time.monotonic()<end and rclpy.ok():
                pub.publish(Twist())
                tick(.05)
                time.sleep(.025)
            after=last if last is not None and time.monotonic()-received_at<=.5 else None
        node.destroy_node()
        if rclpy.ok(): rclpy.shutdown()
    if started:
        a.csv.parent.mkdir(parents=True,exist_ok=True)
        header=['fecha_utc','modo','orden_si','velocidad_si','duracion_plan_s','duracion_envio_s','x0_m','y0_m','yaw0_rad','x1_m','y1_m','yaw1_rad','dist_odom_m','giro_odom_deg','estado']
        dif_d=math.hypot(after[0]-before[0],after[1]-before[1]) if after else ''
        dif_a=math.degrees(math.atan2(math.sin(after[2]-before[2]),math.cos(after[2]-before[2]))) if after else ''
        with a.csv.open('a',newline='') as f:
            w=csv.writer(f)
            if f.tell()==0: w.writerow(header)
            w.writerow([datetime.now(timezone.utc).isoformat(),a.modo,q,v,dur,elapsed,*before,*(after or ('','','')),dif_d,dif_a,status])
        print(f'{status}. Odometría: distancia={dif_d}, giro={dif_a} grados. CSV: {a.csv}')
    return 0 if status=='COMPLETO' else 1

if __name__=='__main__': raise SystemExit(main())
