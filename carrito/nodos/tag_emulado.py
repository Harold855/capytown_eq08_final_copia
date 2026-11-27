#!/usr/bin/env python3
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from carrito.granprix_carrito.docks import DOCKS_HTML, Dock  # noqa: E402
from carrito.granprix_carrito.gestor_reset import cuaternion_de_dth, yaw_de_cuaternion  # noqa: E402
from carrito.granprix_carrito.transformacion_camara_dock import Marcos, cargar_marcos  # noqa: E402
from geometria_dock.transformaciones import Pose2D, componer, invertir  # noqa: E402


@dataclass(frozen=True)
class ModeloCamara:
    hfov_deg: float = 68.8
    vfov_deg: float = 54.9
    z_min_m: float = 0.10
    z_max_m: float = 0.60
    angulo_max_deg: float = 60.0


@dataclass(frozen=True)
class RuidoTag:
    sigma_pos_m: float = 0.001
    sigma_dth_deg: float = 0.5
    prob_perdida: float = 0.0

    def __post_init__(self) -> None:
        if min(self.sigma_pos_m, self.sigma_dth_deg) < 0 or not 0 <= self.prob_perdida <= 1:
            raise ValueError('sigmas >= 0 y prob_perdida en [0, 1]')


def medicion_emulada(marcos: Marcos, estacion: int, pose_mapa: Pose2D, docks: Dict[int, Dock] = DOCKS_HTML,
                     abajo_m: float = 0.0) -> Tuple[float, float, float, float]:
    robot_dock = componer(invertir(docks[estacion].pose), pose_mapa)
    tag_cam = componer(invertir(marcos.montaje.pose), componer(invertir(robot_dock), marcos.tag(estacion)))
    a = marcos.montaje.inclinacion
    z = tag_cam.x * math.cos(a) + abajo_m * math.sin(a)
    y = -tag_cam.x * math.sin(a) + abajo_m * math.cos(a)
    return -tag_cam.y, y, z, -math.degrees(tag_cam.th)


def es_visible(medicion: Tuple[float, float, float, float], modelo: ModeloCamara = ModeloCamara()) -> bool:
    x, y, z, dth = medicion
    return (modelo.z_min_m <= z <= modelo.z_max_m and abs(math.degrees(math.atan2(x, z))) <= modelo.hfov_deg / 2
            and abs(math.degrees(math.atan2(y, z))) <= modelo.vfov_deg / 2 and abs(dth) <= modelo.angulo_max_deg)


def ver_tag(marcos: Marcos, pose_mapa: Pose2D, modelo: ModeloCamara = ModeloCamara(), ruido: RuidoTag = RuidoTag(),
            rng: Optional[random.Random] = None, docks: Dict[int, Dock] = DOCKS_HTML,
            abajo_m: float = 0.0) -> Optional[Tuple[int, float, float, float, float]]:
    rng = rng or random.Random(0)
    mejor = None
    for est in docks:
        m = medicion_emulada(marcos, est, pose_mapa, docks, abajo_m)
        if es_visible(m, modelo) and (mejor is None or math.hypot(m[0], m[2]) < mejor[0]):
            mejor = (math.hypot(m[0], m[2]), est, m)
    if mejor is None or rng.random() < ruido.prob_perdida:
        return None
    _, est, (x, y, z, dth) = mejor
    return (est, x + rng.gauss(0, ruido.sigma_pos_m), y + rng.gauss(0, ruido.sigma_pos_m),
            z + rng.gauss(0, ruido.sigma_pos_m), dth + rng.gauss(0, ruido.sigma_dth_deg))


PARAMETROS = {
    'marcos_yaml': '', 'pose_topic': '/sim/pose', 'tag_topic': '/tag/pose', 'dock_topic': '/pit/dock',
    'publicar_dock': False, 'frame_id': 'camera_optical_frame', 'hz': 10.0, 'sigma_pos_m': 0.001, 'sigma_dth_deg': 0.5,
    'prob_perdida': 0.0, 'semilla': 0, 'abajo_m': 0.0, 'hfov_deg': 68.8, 'vfov_deg': 54.9, 'z_min_m': 0.10,
    'z_max_m': 0.60, 'angulo_max_deg': 60.0,
}


def _clase_nodo():
    from geometry_msgs.msg import PoseStamped
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from std_msgs.msg import Int32

    class TagEmulado(Node):
        def __init__(self):
            super().__init__('tag_emulado')
            for nombre, defecto in PARAMETROS.items():
                self.declare_parameter(nombre, defecto)
            p = {nombre: self.get_parameter(nombre).value for nombre in PARAMETROS}
            if not p['marcos_yaml']:
                raise ValueError('falta el parámetro marcos_yaml (use carrito/config/marcos_sim.yaml en el simulador)')
            self.p, self.marcos = p, cargar_marcos(p['marcos_yaml'])
            self.modelo = ModeloCamara(p['hfov_deg'], p['vfov_deg'], p['z_min_m'], p['z_max_m'], p['angulo_max_deg'])
            self.ruido = RuidoTag(p['sigma_pos_m'], p['sigma_dth_deg'], p['prob_perdida'])
            self.rng = random.Random(int(p['semilla']))
            self._ultima, self._nueva, self.descartadas = None, False, 0
            self.tag_pub = self.create_publisher(PoseStamped, p['tag_topic'], 10)
            self.dock_pub = self.create_publisher(Int32, p['dock_topic'], 10) if p['publicar_dock'] else None
            self.create_subscription(PoseStamped, p['pose_topic'], self._pose, qos_profile_sensor_data)
            self.create_timer(1.0 / p['hz'], self._tick)

        def _pose(self, msg):
            o = msg.pose.orientation
            try:
                yaw = yaw_de_cuaternion(o.x, o.y, o.z, o.w)
            except ValueError:
                self.descartadas += 1
                return
            if msg.header.frame_id.lstrip('/') != 'map':
                self.descartadas += 1
                return
            self._ultima, self._nueva = (msg.header.stamp, Pose2D(msg.pose.position.x, msg.pose.position.y, yaw)), True

        def _tick(self):
            if self._ultima is None or not self._nueva:
                return
            self._nueva = False
            stamp, pose = self._ultima
            visto = ver_tag(self.marcos, pose, self.modelo, self.ruido, self.rng, abajo_m=self.p['abajo_m'])
            if visto is None:
                return
            est, x, y, z, dth = visto
            m = PoseStamped()
            m.header.stamp, m.header.frame_id = stamp, self.p['frame_id']
            m.pose.position.x, m.pose.position.y, m.pose.position.z = x, y, z
            (m.pose.orientation.x, m.pose.orientation.y, m.pose.orientation.z,
             m.pose.orientation.w) = cuaternion_de_dth(dth)
            self.tag_pub.publish(m)
            if self.dock_pub is not None:
                self.dock_pub.publish(Int32(data=est))

    return TagEmulado


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
