#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carrito.granprix_carrito.gestor_reset import cuaternion_de_dth  # noqa: E402

CANALES = {'mono8': 1, 'rgb8': 3, 'bgr8': 3}
PARAMETROS = {
    'camara_yaml': '', 'tamano_mm': 0.0, 'tag_id': 0, 'image_topic': '/camera/image_raw', 'tag_topic': '/tag/pose',
    'frame_id': 'camera_optical_frame', 'margen_min': 30.0, 'hamming_max': 0, 'ventana': 5, 'estado_s': 2.0,
}


def imagen_a_gris(alto, ancho, encoding, step, datos):
    import cv2
    import numpy as np
    canales = CANALES.get(encoding)
    if canales is None:
        raise ValueError(f'codificación {encoding!r} no soportada (mono8, rgb8, bgr8)')
    if alto <= 0 or ancho <= 0 or step < ancho * canales or len(datos) < alto * step:
        raise ValueError('imagen inconsistente: dimensiones, step y datos no concuerdan')
    a = np.frombuffer(bytes(datos[:alto * step]), np.uint8).reshape(alto, step)[:, :ancho * canales]
    if canales == 1:
        return a.copy()
    a = np.ascontiguousarray(a.reshape(alto, ancho, 3))
    return cv2.cvtColor(a, cv2.COLOR_RGB2GRAY if encoding == 'rgb8' else cv2.COLOR_BGR2GRAY)


def _clase_nodo():
    from geometry_msgs.msg import PoseStamped
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
    from std_msgs.msg import String

    from vision.medicion import CamaraTag, Criterios, ErrorMedicion, FiltroMediana

    class CamaraAprilTag(Node):
        def __init__(self):
            super().__init__('camara_apriltag')
            for nombre, defecto in PARAMETROS.items():
                self.declare_parameter(nombre, defecto)
            p = {nombre: self.get_parameter(nombre).value for nombre in PARAMETROS}
            if not p['camara_yaml']:
                raise ValueError('falta el parámetro camara_yaml (camara_calibrada.yaml de la calibración de la cámara)')
            self.p = p
            self.camara = CamaraTag.desde_yaml(p['camara_yaml'], p['tamano_mm'] or None)
            self.criterios = Criterios(p['margen_min'], int(p['hamming_max']))
            self.filtro = FiltroMediana(int(p['ventana']))
            self.tag_id = int(p['tag_id']) or None
            self.conteo = {}
            self.pub = self.create_publisher(PoseStamped, p['tag_topic'], 10)
            self.estado_pub = self.create_publisher(String, '~/estado', 10)
            self.create_subscription(Image, p['image_topic'], self._imagen, qos_profile_sensor_data)
            self.create_timer(p['estado_s'], self._estado)

        def _contar(self, clave):
            self.conteo[clave] = self.conteo.get(clave, 0) + 1
            if clave in ('imagen_invalida', 'resolucion') and self.conteo[clave] % 100 == 1:
                self.get_logger().warning(f'imagen descartada por {clave} (ocurrencia {self.conteo[clave]})')

        def _imagen(self, msg):
            try:
                gris = imagen_a_gris(msg.height, msg.width, msg.encoding, msg.step, msg.data)
            except ValueError:
                self._contar('imagen_invalida')
                return
            stamp = msg.header.stamp
            try:
                med = self.camara.medir(gris, self.tag_id, self.criterios, ts=stamp.sec + stamp.nanosec * 1e-9)
            except ErrorMedicion:
                self._contar('resolucion')
                return
            self._contar('valido' if med.valido else med.motivo)
            pose = self.filtro.agregar(med)
            if pose is None:
                return
            m = PoseStamped()
            m.header.stamp, m.header.frame_id = stamp, self.p['frame_id']
            m.pose.position.x, m.pose.position.y, m.pose.position.z = pose['x_m'], pose['y_m'], pose['z_m']
            (m.pose.orientation.x, m.pose.orientation.y, m.pose.orientation.z,
             m.pose.orientation.w) = cuaternion_de_dth(pose['dth_deg'])
            self.pub.publish(m)

        def _estado(self):
            self.estado_pub.publish(String(data=json.dumps(self.conteo)))

    return CamaraAprilTag


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    nodo = _clase_nodo()()
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
