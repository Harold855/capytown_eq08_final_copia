#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import rclpy  # noqa: E402
from geometry_msgs.msg import PoseStamped, TransformStamped  # noqa: E402,F401
from nav_msgs.msg import Odometry  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import qos_profile_sensor_data  # noqa: E402
from std_msgs.msg import Int32, String  # noqa: E402
from std_srvs.srv import Trigger  # noqa: E402
from tf2_ros import TransformBroadcaster  # noqa: E402

from carrito.granprix_carrito.gestor_reset import (GestorReset, cuaternion_de_yaw, dth_de_cuaternion,  # noqa: E402
                                                   yaw_de_cuaternion)
from carrito.granprix_carrito.transformacion_camara_dock import cargar_marcos  # noqa: E402
from carrito.granprix_carrito.pose_dock import LocalizadorDock  # noqa: E402
from carrito.granprix_carrito.reset_pose import ResetPose  # noqa: E402
from geometria_dock.transformaciones import Pose2D  # noqa: E402

PARAMETROS = {
    'marcos_yaml': '', 'odom_topic': '/odom', 'tag_topic': '/tag/pose', 'dock_topic': '/pit/dock', 'map_frame': 'map',
    'odom_frame': 'odom', 'base_frame': 'base_footprint', 'retardo_odom_s': 0.0, 'ventana_quieto_s': 0.3,
    'edad_max_tag_s': 1.0, 'salto_max_m': 0.15, 'salto_max_deg': 20.0, 'tf_hz': 20.0, 'odom_sello_llegada': False,
    'tag_sello_llegada': False,
}


def _seg(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


class NodoResetPose(Node):
    def __init__(self):
        super().__init__('reset_pose')
        for nombre, defecto in PARAMETROS.items():
            self.declare_parameter(nombre, defecto)
        p = {nombre: self.get_parameter(nombre).value for nombre in PARAMETROS}
        if not p['marcos_yaml']:
            raise ValueError('falta el parámetro marcos_yaml (ruta de carrito/config/marcos.yaml con el montaje medido)')
        self.p = p
        marcos = cargar_marcos(p['marcos_yaml'])
        reset = ResetPose(salto_max_m=p['salto_max_m'], salto_max_deg=p['salto_max_deg'])
        self.gestor = GestorReset(LocalizadorDock(marcos, reset), p['retardo_odom_s'], p['ventana_quieto_s'],
                                  p['edad_max_tag_s'])
        self.estacion = 0
        self._ruido = {'odom': 0, 'tag': 0}
        self.tf = TransformBroadcaster(self)
        self.estado_pub = self.create_publisher(String, '~/estado', 10)
        self.create_subscription(Odometry, p['odom_topic'], self._odom, qos_profile_sensor_data)
        self.create_subscription(PoseStamped, p['tag_topic'], self._tag, qos_profile_sensor_data)
        self.create_subscription(Int32, p['dock_topic'], self._dock, 10)
        self.create_service(Trigger, '~/aplicar', self._aplicar)
        self.create_timer(1.0 / p['tf_hz'], self._publicar_tf)

    def _ahora(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def _avisar(self, clave, texto):
        self._ruido[clave] += 1
        if self._ruido[clave] % 100 == 1:
            self.get_logger().warning(f'{texto} (ocurrencia {self._ruido[clave]})')

    def _odom(self, msg):
        if msg.header.frame_id.lstrip('/') != self.p['odom_frame'] or msg.child_frame_id.lstrip('/') != self.p['base_frame']:
            self._avisar('odom', f'/odom con marcos {msg.header.frame_id!r} -> {msg.child_frame_id!r}; se esperaba '
                                 f"{self.p['odom_frame']!r} -> {self.p['base_frame']!r}: se descarta")
            return
        o = msg.pose.pose.orientation
        try:
            yaw = yaw_de_cuaternion(o.x, o.y, o.z, o.w)
        except ValueError:
            self._avisar('odom', 'cuaternión de /odom no unitario: se descarta')
            return
        t = self._ahora() if self.p['odom_sello_llegada'] else _seg(msg.header.stamp)
        self.gestor.agregar_odom(t, Pose2D(msg.pose.pose.position.x, msg.pose.pose.position.y, yaw))

    def _tag(self, msg):
        o, pos = msg.pose.orientation, msg.pose.position
        try:
            dth = dth_de_cuaternion(o.x, o.y, o.z, o.w)
        except ValueError:
            self._avisar('tag', 'cuaternión de /tag/pose no unitario: se descarta')
            return
        t = self._ahora() if self.p['tag_sello_llegada'] else _seg(msg.header.stamp)
        if not self.gestor.agregar_tag(t, pos.x, pos.y, pos.z, dth):
            self._avisar('tag', '/tag/pose con valores no finitos: se descarta')

    def _dock(self, msg):
        self.estacion = int(msg.data)

    def _aplicar(self, solicitud, respuesta):
        r = self.gestor.aplicar(self._ahora(), self.estacion)
        respuesta.success = bool(r.aceptado)
        cuerpo = {'motivo': r.motivo, 'estacion': self.estacion}
        if r.reset is not None and r.reset.salto_m is not None:
            cuerpo.update(salto_m=round(r.reset.salto_m, 4), salto_deg=round(r.reset.salto_deg, 3))
        respuesta.message = json.dumps(cuerpo)
        self.estado_pub.publish(String(data=json.dumps(self.gestor.estado(self._ahora()))))
        nivel = self.get_logger().info if r.aceptado else self.get_logger().warning
        nivel(f'reset de pose en E{self.estacion}: {"aceptado" if r.aceptado else "rechazado"} {respuesta.message}')
        return respuesta

    def _publicar_tf(self):
        mo = self.gestor.map_odom
        if mo is None:
            return
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = self.p['map_frame']
        t.child_frame_id = self.p['odom_frame']
        t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = mo.x, mo.y, 0.0
        (t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z,
         t.transform.rotation.w) = cuaternion_de_yaw(mo.th)
        self.tf.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    nodo = NodoResetPose()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
