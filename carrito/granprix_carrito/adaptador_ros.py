#!/usr/bin/env python3
"""Nodo `maquina_pit`: conecta el núcleo (maquina_pit.py) con ROS 2. No hay puente MQTT propio: los mensajes del contrato
viajan como JSON en `std_msgs/String` hacia y desde el `puente_mqtt` del curso. Los NOMBRES de esos tópicos son nuestros y
provisionales (el curso aún no publica la plantilla); cámbialos por parámetros. Un solo hilo (rclpy.spin): sin cerrojos."""
import json
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))    # mensajes_contrato.py: constructores del contrato

from carrito.granprix_carrito.gestor_reset import dth_de_cuaternion, yaw_de_cuaternion  # noqa: E402

DOCK_CADA_S = 1.0
PARAMETROS = {
    'carrito_dir': str(RAIZ / 'carrito' / 'config'), 'robot': 'eq08-roscar', 'marcos_yaml': '', 'mision_yaml': '', 'acople_yaml': '',
    'odom_topic': '/odom', 'tag_topic': '/tag/pose', 'cmd_topic': '/cmd_vel', 'reset_service': '/reset_pose/aplicar',
    'turno_topic': '/granprix/turno', 'bandera_topic': '/granprix/bandera', 'enlace_topic': '/granprix/enlace',
    'estacion_topic': '/granprix/estacion_estado', 'resultado_topic': '/granprix/resultado',
    'solicitud_topic': '/granprix/solicitud', 'evento_topic': '/granprix/evento', 'vuelta_topic': '/granprix/vuelta',
    'telemetria_topic': '/granprix/telemetria', 'estado_topic': '/pit/estado', 'dock_topic': '/pit/dock',
    'hz': 20.0, 'telemetria_hz': 5.0, 'odom_max_s': 0.75, 'lecturas': 3, 'espera_s': 0.8, 'timeout_tag_s': 3.0,
    'resultados_dir': '',
}


def leer_json(texto):
    """Dict del JSON o None si no es un objeto JSON válido (se descarta: nunca autoriza nada)."""
    try:
        d = json.loads(texto)
    except (TypeError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def _clase_nodo():
    from geometry_msgs.msg import PoseStamped, Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from std_msgs.msg import Bool, Int32, String
    from std_srvs.srv import Trigger

    import mensajes_contrato as mc
    from carrito.granprix_carrito.acople import MedidorTag, cargar_acople
    from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo
    from carrito.granprix_carrito.configuracion import cargar_carrito
    from carrito.granprix_carrito.maquina_pit import Estado, MaquinaPit
    from carrito.granprix_carrito.mision import Mision, cargar_mision
    from carrito.granprix_carrito.pose_dock import LocalizadorDock
    from carrito.granprix_carrito.transformacion_camara_dock import cargar_marcos

    class Maquina(Node):
        def __init__(self):
            super().__init__('maquina_pit')
            for nombre, defecto in PARAMETROS.items():
                self.declare_parameter(nombre, defecto)
            p = {nombre: self.get_parameter(nombre).value for nombre in PARAMETROS}
            if not p['marcos_yaml']:
                raise ValueError('falta el parámetro marcos_yaml (carrito/config/marcos.yaml con el montaje medido)')
            self.p = p
            mov, estimador = cargar_carrito(p['carrito_dir'], p['robot'])
            cfg_mision = cargar_mision(p['mision_yaml'] or None)
            cfg_acople = cargar_acople(p['acople_yaml'] or None, mov)
            self.equipo = cfg_mision.equipo
            self.localizador = LocalizadorDock(cargar_marcos(p['marcos_yaml']))
            medidor = MedidorTag(time.monotonic, lambda s: None, int(p['lecturas']), p['espera_s'], p['timeout_tag_s'])
            self.calibrador = CalibradorTramo(estimador)
            self.pub_cmd = self.create_publisher(Twist, p['cmd_topic'], 10)
            self.pub = {k: self.create_publisher(String, p[f'{k}_topic'], 10) for k in ('solicitud', 'evento', 'vuelta', 'telemetria', 'estado')}
            self.pub_dock = self.create_publisher(Int32, p['dock_topic'], 10)
            self.reset = self.create_client(Trigger, p['reset_service'])
            self._reset_futuro = None
            self._t_odom, self._odom, self._ruido = None, None, {}
            self.fsm = MaquinaPit(Mision(cfg_mision), mov, cfg_acople, self.calibrador, medidor, self, self, time.monotonic,
                                  time.time, self._odom_ok)
            self._ultimo = None
            self._dock, self._t_dock = None, 0.0
            for tipo, clave, cb, qos in ((Odometry, 'odom', self._on_odom, qos_profile_sensor_data),
                                         (PoseStamped, 'tag', self._on_tag, qos_profile_sensor_data),
                                         (Bool, 'enlace', self._on_enlace, 10), (String, 'turno', self._on_turno, 10),
                                         (String, 'bandera', self._on_bandera, 10), (String, 'estacion', self._on_estacion, 10),
                                         (String, 'resultado', self._on_resultado, 10)):
                self.create_subscription(tipo, p[f'{clave}_topic'], cb, qos)
            self.create_service(Trigger, '~/reiniciar', self._srv_reiniciar)
            self.create_service(Trigger, '~/parar', self._srv_parar)
            self.create_timer(1.0 / p['hz'], self._tick)
            self.create_timer(1.0 / p['telemetria_hz'], self._telemetria)

        # ---------------- Salida (ejecutor) y Puerto (máquina)
        def publicar(self, v, w):
            m = Twist()
            m.linear.x, m.angular.z = float(v), float(w)
            self.pub_cmd.publish(m)

        def _enviar(self, canal, msg):
            self.pub[canal].publish(String(data=mc.a_json(msg)))

        def solicitud(self, estacion, pose, pieza_trae):
            self._enviar('solicitud', mc.solicitud(self.equipo, estacion, pose.dx, pose.dy, pose.dth, pieza_trae))

        def evento(self, tipo, estacion):
            self._enviar('evento', mc.evento_pit(self.equipo, tipo, estacion))

        def vuelta(self, numero, t_inicio, t_fin, estaciones):
            self._enviar('vuelta', mc.vuelta(self.equipo, numero, t_inicio, t_fin, estaciones))

        def pedir_reset(self):
            if not self.reset.service_is_ready():
                return False
            self._reset_futuro = self.reset.call_async(Trigger.Request())
            return True

        def resultado_reset(self):
            f = self._reset_futuro
            if f is None or not f.done():
                return None
            self._reset_futuro = None
            r = f.result()
            detalle = leer_json(r.message) or {}
            return bool(r.success), detalle.get('motivo')

        def aviso(self, nivel, texto):
            log = self.get_logger()
            (log.error if nivel == 'error' else log.warning if nivel == 'aviso' else log.info)(texto)

        # ---------------- Entradas
        def _avisar(self, clave, texto):
            self._ruido[clave] = self._ruido.get(clave, 0) + 1
            if self._ruido[clave] % 50 == 1:
                self.get_logger().warning(f'{texto} (ocurrencia {self._ruido[clave]})')

        def _odom_ok(self):
            return self._t_odom is not None and time.monotonic() - self._t_odom <= self.p['odom_max_s']

        def _on_odom(self, msg):
            o, pos = msg.pose.pose.orientation, msg.pose.pose.position
            try:
                self._odom = (pos.x, pos.y, yaw_de_cuaternion(o.x, o.y, o.z, o.w))
            except ValueError:
                return self._avisar('odom', 'cuaternión de /odom no unitario: se descarta')
            self._t_odom = time.monotonic()

        def _on_tag(self, msg):
            o, pos = msg.pose.orientation, msg.pose.position
            try:
                dth = dth_de_cuaternion(o.x, o.y, o.z, o.w)
                med = {'aceptada': True, 'x_m': pos.x, 'y_m': pos.y, 'z_m': pos.z, 'dth_deg': dth}
                self.fsm.recibir_tag(self.localizador.pose_desde_tag(med, self.fsm.mision.estacion))
            except ValueError:
                self._avisar('tag', '/tag/pose no válido: se descarta')

        def _on_enlace(self, msg):
            self.fsm.recibir_enlace(msg.data)

        def _campo(self, msg, clave, tipo):
            d = leer_json(msg.data)
            v = None if d is None else d.get(clave)
            if not isinstance(v, tipo) or isinstance(v, bool) != (tipo is bool):
                self._avisar(clave, f'mensaje sin {clave!r} válido: se descarta')
                return None, d
            return v, d

        def _on_turno(self, msg):
            v, _ = self._campo(msg, 'autorizado', bool)
            if v is not None:
                self.fsm.recibir_turno(v)

        def _on_bandera(self, msg):
            v, _ = self._campo(msg, 'bandera', str)
            if v is not None:
                self.fsm.recibir_bandera(v)

        def _on_estacion(self, msg):
            n, d = self._campo(msg, 'estacion', int)
            if n is not None and isinstance(d.get('estado'), str):
                self.fsm.recibir_estacion(n, d['estado'])

        def _on_resultado(self, msg):
            n, d = self._campo(msg, 'estacion', int)
            if n is not None and d.get('equipo') == self.equipo and isinstance(d.get('ok'), bool):
                self.fsm.recibir_resultado(n, d['ok'], d.get('pieza_dejo'), d['motivo'] if isinstance(d.get('motivo'), str) else None)

        # ---------------- Servicios y ciclo
        def _srv_reiniciar(self, peticion, respuesta):
            respuesta.success = self.fsm.reiniciar()
            respuesta.message = json.dumps(self.fsm.instantanea())
            return respuesta

        def _srv_parar(self, peticion, respuesta):
            self.fsm.parar()
            respuesta.success = True
            respuesta.message = json.dumps(self.fsm.instantanea())
            return respuesta

        def _tick(self):
            f = self.fsm
            antes = f.estado
            f.paso()
            ahora = time.monotonic()
            if f.mision.estacion != self._dock or ahora - self._t_dock >= DOCK_CADA_S:      # se repite: quien arranque tarde también se entera
                self._dock, self._t_dock = f.mision.estacion, ahora
                self.pub_dock.publish(Int32(data=int(self._dock)))
            if f.estado is not self._ultimo:
                self._ultimo = f.estado
                self.pub['estado'].publish(String(data=json.dumps(f.instantanea())))
            if f.estado is not antes and f.estado in (Estado.FIN, Estado.FALLA):
                self._guardar()

        def _telemetria(self):
            f = self.fsm
            if self._odom is None:
                return
            x, y, th = self._odom
            snap = f.instantanea()
            self._enviar('telemetria', mc.telemetria(self.equipo, x, y, th, estado=snap['estado'], vuelta=snap['vuelta'],
                                                     pieza=snap['pieza'], cd=snap['cd'], ca=snap['ca']))

        def _guardar(self):
            d = self.p['resultados_dir']
            if not d:
                return
            try:
                os.makedirs(d, exist_ok=True)
                self.fsm.mision.exportar_pits(os.path.join(d, 'pits.csv'))
                self.calibrador.exportar_paradas(os.path.join(d, 'paradas.csv'))
                self.calibrador.exportar_tramos(os.path.join(d, 'tramos.csv'))
            except OSError as e:
                self.get_logger().error(f'no se pudo guardar la evidencia en {d}: {e}')

        def detener(self):
            for _ in range(5):
                self.publicar(0.0, 0.0)

    return Maquina


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    nodo = _clase_nodo()()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            nodo.detener()
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
