"""Nodo ROS 2 del reset de pose contra un SUSTITUTO mínimo de rclpy y de los mensajes.

Demuestra que el cableado del nodo (parámetros, suscripciones, servicio, temporizador, TF, estado) hace lo que el
autor cree que hace la API. NO demuestra que la API real de ROS 2 esté bien usada: eso solo se comprueba en un
Pi5 o contenedor con ROS 2 Humble.
"""
import importlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir
from test_gestor_reset import CAM, INCL, MAP_ODOM_REAL, TAG, cuaternion_de_matriz, mapa_real, odom_de
from carrito.granprix_carrito import gestor_reset as gr

SEMILLA = RAIZ / 'carrito' / 'config' / 'marcos.yaml'


import ros_falso as rf
from ros_falso import Mensaje, Node, Ns


def setUpModule():
    global nodo_mod
    rf.instalar()
    nodo_mod = importlib.import_module('carrito.nodos.nodo_reset_pose')


def tearDownModule():
    rf.desinstalar('carrito.nodos.nodo_reset_pose')


def odom_msg(t, pose, frame='odom', hijo='base_footprint'):
    sec, nano = int(t), int(round((t - int(t)) * 1e9))
    q = gr.cuaternion_de_yaw(pose.th)
    return Ns(header=Ns(frame_id=frame, stamp=Ns(sec=sec, nanosec=nano)), child_frame_id=hijo,
              pose=Ns(pose=Ns(position=Ns(x=pose.x, y=pose.y, z=0.0), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3]))))


def tag_msg(t, robot_dock):
    x, y, z, _, R = tag_visto(robot_dock, CAM, TAG, INCL, h_tag=0.14)
    q = cuaternion_de_matriz(R)
    sec, nano = int(t), int(round((t - int(t)) * 1e9))
    return Ns(header=Ns(stamp=Ns(sec=sec, nanosec=nano)),
              pose=Ns(position=Ns(x=x, y=y, z=z), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3])))


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        texto = SEMILLA.read_text(encoding='utf-8')
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: null', 'x_m: 0.10\n  y_m: 0.01\n  yaw_deg: 0.5', 1)
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: 0.0', 'x_m: 0.38\n  y_m: 0.0\n  yaw_deg: 1.0', 1)
        texto = texto.replace('inclinacion_deg: 0.0', 'inclinacion_deg: 6.0', 1)
        self.marcos = str(Path(self.dir.name) / 'marcos.yaml')
        Path(self.marcos).write_text(texto, encoding='utf-8')
        Node.sobrescribe = {'marcos_yaml': self.marcos}
        self.addCleanup(lambda: setattr(Node, 'sobrescribe', {}))

    def crear(self, **parametros):
        Node.sobrescribe = {'marcos_yaml': self.marcos, **parametros}
        return nodo_mod.NodoResetPose()

    @staticmethod
    def callback(nodo, topico):
        return next(cb for _, t, cb in nodo.subs if t == topico)


class TestArranque(Base):
    def test_sin_marcos_o_con_la_semilla_sin_medir_no_arranca(self):
        Node.sobrescribe = {}
        with self.assertRaisesRegex(ValueError, 'marcos_yaml'):
            nodo_mod.NodoResetPose()
        Node.sobrescribe = {'marcos_yaml': str(SEMILLA)}
        with self.assertRaisesRegex(Exception, 'falta medir'):
            nodo_mod.NodoResetPose()

    def test_se_suscribe_y_expone_lo_esperado(self):
        n = self.crear()
        self.assertEqual({t for _, t, _ in n.subs}, {'/odom', '/tag/pose', '/pit/dock'})
        self.assertEqual([nombre for _, nombre, _ in n.servicios], ['~/aplicar'])
        self.assertEqual([t for _, t, _ in n.pubs], ['~/estado'])
        self.assertAlmostEqual(n.timers[0][0], 1 / 20)

    def test_los_parametros_se_pueden_cambiar(self):
        n = self.crear(odom_topic='/odom_corregida', retardo_odom_s=0.5, base_frame='base_link')
        self.assertIn('/odom_corregida', {t for _, t, _ in n.subs})
        self.assertEqual(n.gestor._retardo, 0.5)


class TestFlujo(Base):
    ROBOT = desde_grados(0.02, -0.015, 3.0)

    def alimentar(self, n, hasta=2.0, hz=20, pose=None):
        pose = pose or odom_de(mapa_real(2, self.ROBOT))
        cb = self.callback(n, '/odom')
        for k in range(int(hasta * hz) + 1):
            n.ns = int(k / hz * 1e9)
            cb(odom_msg(k / hz, pose))

    def llamar(self, n, ahora_s):
        n.ns = int(ahora_s * 1e9)
        resp = Ns(success=None, message='')
        n.servicios[0][2](Ns(), resp)
        return resp

    def test_flujo_completo_hasta_el_tf(self):
        n = self.crear()
        n.timers[0][1]()
        self.assertEqual(n.tf.enviados, [])                                      # sin referencia no se publica ningún TF
        self.alimentar(n)
        self.callback(n, '/tag/pose')(tag_msg(1.0, self.ROBOT))
        self.callback(n, '/pit/dock')(Mensaje(2))
        resp = self.llamar(n, 1.1)
        self.assertTrue(resp.success, resp.message)
        self.assertIsNone(json.loads(resp.message)['motivo'])
        n.ns = int(1.2e9)
        n.timers[0][1]()
        t = n.tf.enviados[-1]
        self.assertEqual((t.header.frame_id, t.child_frame_id), ('map', 'odom'))
        self.assertAlmostEqual(t.transform.translation.x, MAP_ODOM_REAL.x, delta=4e-3)
        self.assertAlmostEqual(t.transform.translation.y, MAP_ODOM_REAL.y, delta=4e-3)
        self.assertEqual(t.transform.translation.z, 0.0)
        yaw = gr.yaw_de_cuaternion(t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w)
        self.assertAlmostEqual(yaw, MAP_ODOM_REAL.th, delta=math.radians(0.3))
        self.assertEqual((t.header.stamp.sec, t.header.stamp.nanosec), (1, 200000000))
        estado = json.loads(n.pubs[0][2].enviados[-1].data)
        self.assertEqual((estado['inicializado'], estado['n_resets']), (True, 1))

    def test_el_tf_compone_con_la_odometria_para_dar_la_pose_en_el_mapa(self):
        n = self.crear()
        self.alimentar(n)
        self.callback(n, '/tag/pose')(tag_msg(1.0, self.ROBOT))
        self.callback(n, '/pit/dock')(Mensaje(2))
        self.llamar(n, 1.1)
        n.timers[0][1]()
        t = n.tf.enviados[-1].transform
        mo = Pose2D(t.translation.x, t.translation.y, gr.yaw_de_cuaternion(t.rotation.x, t.rotation.y, t.rotation.z, t.rotation.w))
        creida = componer(mo, odom_de(mapa_real(2, self.ROBOT)))
        real = mapa_real(2, self.ROBOT)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 4e-3)

    def test_rechazos_llegan_en_la_respuesta_y_no_publican_tf(self):
        n = self.crear()
        self.alimentar(n)
        resp = self.llamar(n, 1.1)
        self.assertFalse(resp.success)
        self.assertEqual(json.loads(resp.message)['motivo'], 'ESTACION_INVALIDA')       # nadie publicó /pit/dock
        self.callback(n, '/pit/dock')(Mensaje(2))
        self.assertEqual(json.loads(self.llamar(n, 1.1).message)['motivo'], 'SIN_TAG')
        self.callback(n, '/tag/pose')(tag_msg(1.0, desde_grados(0.40, 0.0, 0.0)))
        r = self.llamar(n, 1.1)
        self.assertFalse(r.success)
        self.assertEqual(json.loads(r.message)['motivo'], 'FUERA_DE_DOCK')
        n.timers[0][1]()
        self.assertEqual(n.tf.enviados, [])
        self.assertTrue(any('rechazado' in a for a in n.reg.advertencias))

    def test_un_robot_en_movimiento_se_rechaza_con_el_salto_reportado(self):
        n = self.crear()
        cb = self.callback(n, '/odom')
        for k in range(41):
            n.ns = int(k / 20 * 1e9)
            cb(odom_msg(k / 20, odom_de(mapa_real(2, desde_grados(0.02 + 0.2 * k / 20, -0.015, 3.0)))))
        self.callback(n, '/tag/pose')(tag_msg(1.0, self.ROBOT))
        self.callback(n, '/pit/dock')(Mensaje(2))
        self.assertEqual(json.loads(self.llamar(n, 1.1).message)['motivo'], 'ROBOT_NO_QUIETO')

    def test_odometria_con_marcos_equivocados_o_cuaternion_invalido_se_descarta(self):
        n = self.crear()
        cb = self.callback(n, '/odom')
        p = odom_de(mapa_real(2, self.ROBOT))
        cb(odom_msg(1.0, p, frame='odom_otra'))
        cb(odom_msg(1.0, p, hijo='base_link'))
        malo = odom_msg(1.0, p)
        malo.pose.pose.orientation = Ns(x=0.0, y=0.0, z=0.0, w=0.0)
        cb(malo)
        self.assertEqual(n.gestor.estado()['odom_muestras'], 0)
        cb(odom_msg(1.0, p, frame='/odom'))                                         # la barra inicial se tolera
        self.assertEqual(n.gestor.estado()['odom_muestras'], 1)
        self.assertTrue(n.reg.advertencias)

    def test_con_el_marco_base_configurado(self):
        n = self.crear(base_frame='base_link')
        self.callback(n, '/odom')(odom_msg(1.0, Pose2D(0, 0, 0), hijo='base_link'))
        self.assertEqual(n.gestor.estado()['odom_muestras'], 1)

    def test_sello_de_llegada_en_lugar_del_del_mensaje(self):
        n = self.crear(odom_sello_llegada=True, tag_sello_llegada=True)
        n.ns = int(50 * 1e9)
        self.callback(n, '/odom')(odom_msg(999.0, Pose2D(0, 0, 0)))
        n.ns = int(50.1 * 1e9)
        self.callback(n, '/odom')(odom_msg(999.0, Pose2D(0, 0, 0)))
        self.assertIsNotNone(n.gestor.odom_en(50.05))
        self.assertIsNone(n.gestor.odom_en(999.0))

    def test_tag_con_cuaternion_invalido_o_valores_no_finitos(self):
        n = self.crear()
        malo = tag_msg(1.0, self.ROBOT)
        malo.pose.orientation = Ns(x=0.0, y=0.0, z=0.0, w=0.0)
        self.callback(n, '/tag/pose')(malo)
        nan = tag_msg(1.0, self.ROBOT)
        nan.pose.position = Ns(x=float('nan'), y=0.0, z=0.3)
        self.callback(n, '/tag/pose')(nan)
        self.assertIsNone(n.gestor._tag)

    def test_el_tag_llega_con_el_dth_del_detector(self):
        n = self.crear()
        self.callback(n, '/tag/pose')(tag_msg(1.0, self.ROBOT))
        esperado = tag_visto(self.ROBOT, CAM, TAG, INCL, h_tag=0.14)[3]
        self.assertAlmostEqual(n.gestor._tag[1]['dth_deg'], esperado, places=6)


if __name__ == '__main__':
    unittest.main()
