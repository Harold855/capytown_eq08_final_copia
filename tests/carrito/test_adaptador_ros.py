"""Adaptador ROS 2 de la máquina del pit contra un SUSTITUTO mínimo de rclpy y de los mensajes.

Demuestra el cableado (parámetros, tópicos, JSON del contrato, servicios, ciclo) que el autor cree que tiene. NO demuestra
que la API real de ROS 2 esté bien usada ni que el puente MQTT del curso use estos nombres: nunca se ejecutó con ROS.
"""
import csv
import importlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ros_falso as rf
from carrito.granprix_carrito.docks import DOCKS_HTML, dock_a_mapa
from carrito.granprix_carrito.gestor_reset import cuaternion_de_dth, cuaternion_de_yaw
from carrito.granprix_carrito.maquina_pit import Estado
from carrito.granprix_carrito.pose_dock import PoseDock
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, desde_grados
from ros_falso import Mensaje, Node, Ns

E = Estado
SIM = str(RAIZ / 'carrito' / 'config' / 'marcos_sim.yaml')
CAM, TAG, INCL = Pose2D(0.10, 0.0, 0.0), Pose2D(0.38, 0.0, 0.0), math.radians(20.05)
am = None


def setUpModule():
    global am
    rf.instalar()
    am = importlib.import_module('carrito.granprix_carrito.adaptador_ros')


def tearDownModule():
    rf.desinstalar('carrito.granprix_carrito.adaptador_ros')


def js(**kw):
    return Mensaje(json.dumps(kw))


def tag_msg(dx, dy, deg):
    x, y, z, dth, _ = tag_visto(desde_grados(dx, dy, deg), CAM, TAG, INCL)
    q = cuaternion_de_dth(dth)
    return Ns(header=Ns(stamp=Ns(sec=0, nanosec=0)),
              pose=Ns(position=Ns(x=x, y=y, z=z), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3])))


def odom_msg(x=0.0, y=0.0, yaw=0.0):
    q = cuaternion_de_yaw(yaw)
    return Ns(pose=Ns(pose=Ns(position=Ns(x=x, y=y, z=0.0), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3]))))


class Base(unittest.TestCase):
    def crear(self, **parametros):
        Node.sobrescribe = {'marcos_yaml': SIM, **parametros}
        self.addCleanup(lambda: setattr(Node, 'sobrescribe', {}))
        self.t = [1000.0]
        parche = mock.patch('time.monotonic', lambda: self.t[0])
        parche.start()
        self.addCleanup(parche.stop)
        self.nodo = am._clase_nodo()()
        return self.nodo

    def cb(self, topico):
        return self.nodo.callback(topico)

    def pub(self, topico):
        return self.nodo.publicador(topico).enviados


class TestCableado(Base):
    def test_declara_las_interfaces(self):
        n = self.crear()
        suscritos = {t for _, t, _ in n.subs}
        self.assertEqual(suscritos, {'/odom', '/tag/pose', '/granprix/enlace', '/granprix/turno', '/granprix/bandera',
                                     '/granprix/estacion_estado', '/granprix/resultado'})
        publicados = {t for _, t, _ in n.pubs}
        self.assertTrue({'/cmd_vel', '/granprix/solicitud', '/granprix/evento', '/granprix/vuelta', '/granprix/telemetria',
                         '/pit/estado', '/pit/dock'} <= publicados)
        self.assertEqual({nombre for _, nombre, _ in n.servicios}, {'~/reiniciar', '~/parar'})
        self.assertEqual(sorted(round(p, 3) for p, _ in n.timers), [0.05, 0.2])
        self.assertEqual(n.clientes[0][1], '/reset_pose/aplicar')

    def test_exige_los_marcos(self):
        Node.sobrescribe = {}
        self.addCleanup(lambda: setattr(Node, 'sobrescribe', {}))
        with self.assertRaisesRegex(ValueError, 'marcos_yaml'):
            am._clase_nodo()()

    def test_los_marcos_sin_medir_se_rechazan(self):
        with self.assertRaisesRegex(ValueError, 'falta medir'):
            self.crear(marcos_yaml=str(RAIZ / 'carrito' / 'config' / 'marcos.yaml'))

    def test_salida_twist(self):
        n = self.crear()
        n.publicar(0.1, -0.3)
        m = self.pub('/cmd_vel')[-1]
        self.assertEqual((m.linear.x, m.angular.z, m.linear.y, m.angular.x), (0.1, -0.3, 0.0, 0.0))

    def test_detener_publica_ceros(self):
        n = self.crear()
        n.detener()
        enviados = self.pub('/cmd_vel')
        self.assertEqual(len(enviados), 5)
        self.assertTrue(all(m.linear.x == 0.0 and m.angular.z == 0.0 for m in enviados))


class TestEntradas(Base):
    def test_turno_bandera_enlace_estacion_validos(self):
        n = self.crear()
        self.cb('/granprix/turno')(js(autorizado=True, tanda='t1'))
        self.cb('/granprix/bandera')(js(bandera='roja'))
        self.cb('/granprix/enlace')(Mensaje(True))
        self.cb('/granprix/estacion_estado')(js(estacion=2, estado='CAMBIANDO'))
        e = n.fsm.entorno
        self.assertEqual((e.autorizado, e.bandera, e.enlace, e.estaciones), (True, 'roja', True, {2: 'CAMBIANDO'}))

    def test_mensajes_invalidos_se_descartan_y_nunca_autorizan(self):
        n = self.crear()
        malos = [Mensaje('no es json'), Mensaje('[1, 2]'), js(otra=1), js(autorizado='true'), js(autorizado=1), Mensaje(None)]
        for m in malos:
            self.cb('/granprix/turno')(m)
        self.cb('/granprix/bandera')(js(bandera=3))
        self.cb('/granprix/estacion_estado')(js(estacion=True, estado='LIBRE'))
        self.cb('/granprix/estacion_estado')(js(estacion=2, estado=5))
        e = n.fsm.entorno
        self.assertEqual((e.autorizado, e.bandera, e.estaciones), (None, None, {}))

    def test_resultado_de_otro_equipo_se_ignora(self):
        n = self.crear()
        n.fsm.estado = E.ESPERANDO_RESULTADO
        self.cb('/granprix/resultado')(js(estacion=1, equipo=7, ok=True, pieza_dejo='A'))
        self.assertIsNone(n.fsm._res)
        self.cb('/granprix/resultado')(js(estacion=1, equipo=8, ok='si'))
        self.assertIsNone(n.fsm._res)
        self.cb('/granprix/resultado')(js(estacion=1, equipo=8, ok=True, pieza_dejo='A', t_cambio=5.8))
        self.assertEqual(n.fsm._res, (True, 'A'))

    def test_tag_se_convierte_a_pose_en_el_dock_de_la_estacion_actual(self):
        n = self.crear()
        self.cb('/tag/pose')(tag_msg(-0.05, 0.02, 4.0))
        (_, p), = list(n.fsm.medidor._lect)
        self.assertEqual(p.estacion, 1)
        self.assertAlmostEqual(p.dx, -0.05, delta=2e-3)
        self.assertAlmostEqual(p.dy, 0.02, delta=2e-3)
        self.assertAlmostEqual(p.dth_deg, 4.0, delta=0.3)

    def test_tag_con_cuaternion_invalido_se_descarta(self):
        n = self.crear()
        m = tag_msg(0, 0, 0)
        m.pose.orientation.w = 5.0
        self.cb('/tag/pose')(m)
        self.assertEqual(len(n.fsm.medidor._lect), 0)

    def test_odometria_vieja_o_ausente_no_es_ok(self):
        n = self.crear()
        self.assertFalse(n._odom_ok())
        q = cuaternion_de_yaw(0.3)
        msg = Ns(pose=Ns(pose=Ns(position=Ns(x=1.0, y=2.0, z=0.0), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3]))))
        self.cb('/odom')(msg)
        self.assertTrue(n._odom_ok())
        self.t[0] += 1.0
        self.assertFalse(n._odom_ok())


class TestSalidas(Base):
    def test_solicitud_con_el_contrato(self):
        n = self.crear()
        pose = PoseDock(2, 0.021, -0.012, math.radians(1.8), dock_a_mapa(DOCKS_HTML[2], 0.021, -0.012, 1.8), 'tag', True)
        n.solicitud(2, pose, 'A')
        d = json.loads(self.pub('/granprix/solicitud')[-1].data)
        self.assertEqual((d['v'], d['equipo'], d['dock'], d['pieza_trae']), (1, 8, 2, 'A'))
        self.assertAlmostEqual(d['pose']['dx'], 0.021)
        self.assertAlmostEqual(d['pose']['dy'], -0.012)
        self.assertAlmostEqual(d['pose']['dth'], 1.8, places=6)                # en grados
        n.solicitud(1, pose, None)
        self.assertIsNone(json.loads(self.pub('/granprix/solicitud')[-1].data)['pieza_trae'])

    def test_evento_y_vuelta(self):
        n = self.crear()
        n.evento('pit_ok', 3)
        n.evento('reintento', 3)
        ev = [json.loads(m.data) for m in self.pub('/granprix/evento')]
        self.assertEqual([(e['tipo'], e['estacion'], e['equipo']) for e in ev], [('pit_ok', 3, 8), ('reintento', 3, 8)])
        n.vuelta(2, 100.0, 190.5, (1, 2, 3, 4))
        v = json.loads(self.pub('/granprix/vuelta')[-1].data)
        self.assertEqual((v['numero'], v['t_inicio'], v['t_fin'], v['estaciones']), (2, 100.0, 190.5, [1, 2, 3, 4]))

    def test_telemetria_lleva_la_odometria_y_el_estado(self):
        n = self.crear()
        n._telemetria()
        self.assertEqual(self.pub('/granprix/telemetria'), [])                  # sin odometría no hay pose que decir
        q = cuaternion_de_yaw(0.5)
        self.cb('/odom')(Ns(pose=Ns(pose=Ns(position=Ns(x=1.0, y=2.0, z=0.0), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3])))))
        n._telemetria()
        d = json.loads(self.pub('/granprix/telemetria')[-1].data)
        self.assertEqual((d['equipo'], d['estado'], d['vuelta']), (8, 'ESPERA', 1))
        self.assertAlmostEqual(d['pose']['theta'], 0.5)
        self.assertIn('cd', d)


class TestReset(Base):
    def test_servicio_no_listo_no_se_llama(self):
        n = self.crear()
        n.reset.disponible = False
        self.assertFalse(n.pedir_reset())
        self.assertEqual(n.reset.llamadas, [])

    def test_pide_y_lee_el_resultado_cuando_llega(self):
        n = self.crear()
        self.assertIsNone(n.resultado_reset())
        self.assertTrue(n.pedir_reset())
        self.assertIsNone(n.resultado_reset())
        f = n.reset.llamadas[0]
        f.listo, f.valor = True, Ns(success=False, message=json.dumps({'motivo': 'ODOM_INSUFICIENTE', 'estacion': 1}))
        self.assertEqual(n.resultado_reset(), (False, 'ODOM_INSUFICIENTE'))
        self.assertIsNone(n.resultado_reset())                                   # ya se consumió

    def test_mensaje_ilegible_no_rompe(self):
        n = self.crear()
        n.pedir_reset()
        f = n.reset.llamadas[0]
        f.listo, f.valor = True, Ns(success=True, message='???')
        self.assertEqual(n.resultado_reset(), (True, None))


class TestCiclo(Base):
    def avanzar(self, n, s, enlace=True, tag=(0.0, 0.0, 0.0), odom=True):
        fin = self.t[0] + s
        ultimo = -1.0
        while self.t[0] < fin:
            if enlace and self.t[0] - ultimo >= 0.5:
                ultimo = self.t[0]
                self.cb('/granprix/turno')(js(autorizado=True))
                self.cb('/granprix/bandera')(js(bandera='verde'))
                self.cb('/granprix/enlace')(Mensaje(True))
            if odom and round(self.t[0] * 20) % 2 == 0:
                self.cb('/odom')(odom_msg())
            if tag and round(self.t[0] * 20) % 2 == 0:
                self.cb('/tag/pose')(tag_msg(*tag))
            for f in n.reset.llamadas:
                if not f.listo:
                    f.listo, f.valor = True, Ns(success=True, message=json.dumps({'motivo': None}))
            n._tick()
            self.t[0] += 0.05

    def test_de_la_autorizacion_al_primer_tramo_con_el_robot_en_el_dock(self):
        n = self.crear()
        self.avanzar(n, 0.3, enlace=False)
        self.assertEqual(n.fsm.estado, E.ESPERA)
        self.assertEqual(self.pub('/cmd_vel'), [])
        self.avanzar(n, 3.0)
        self.assertEqual(n.fsm.estado, E.ESPERANDO_RESULTADO)
        sol = json.loads(self.pub('/granprix/solicitud')[0].data)
        self.assertEqual((sol['dock'], sol['pieza_trae']), (1, None))
        self.assertAlmostEqual(sol['pose']['dx'], 0.0, delta=3e-3)
        self.cb('/granprix/resultado')(js(estacion=1, equipo=8, ok=True, pieza_dejo='A', t_cambio=5.8))
        self.avanzar(n, 6.0)
        self.assertEqual(n.fsm.estado, E.NAVEGANDO)
        self.assertEqual([json.loads(m.data)['tipo'] for m in self.pub('/granprix/evento')], ['pit_ok'])
        self.assertTrue(any(m.angular.z != 0.0 for m in self.pub('/cmd_vel')))
        self.assertEqual([m.data for m in self.nodo.publicador('/pit/dock').enviados][:2], [1, 2])
        estados = [json.loads(m.data)['estado'] for m in self.pub('/pit/estado')]
        self.assertEqual(estados[:2], ['ESPERA', 'MIDIENDO'])
        self.assertEqual(estados[-1], 'NAVEGANDO')

    def test_dock_y_estado_solo_se_publican_al_cambiar(self):
        n = self.crear()
        n._tick()
        n._tick()
        n._tick()
        self.assertEqual(len(self.pub('/pit/dock')), 1)
        self.assertEqual(len(self.pub('/pit/estado')), 1)

    def test_perder_el_enlace_en_marcha_frena_y_guarda_la_evidencia(self):
        with tempfile.TemporaryDirectory() as d:
            n = self.crear(resultados_dir=d)
            self.avanzar(n, 3.0)
            self.cb('/granprix/resultado')(js(estacion=1, equipo=8, ok=True, pieza_dejo='A'))
            self.avanzar(n, 6.0)
            self.assertEqual(n.fsm.estado, E.NAVEGANDO)
            self.avanzar(n, 3.0, enlace=False)
            self.assertEqual((n.fsm.estado, n.fsm.motivo), (E.FALLA, 'ENLACE_PERDIDO'))
            ultimo = self.pub('/cmd_vel')[-1]
            self.assertEqual((ultimo.linear.x, ultimo.angular.z), (0.0, 0.0))
            for nombre in ('pits.csv', 'paradas.csv', 'tramos.csv'):
                self.assertTrue((Path(d) / nombre).exists(), nombre)
            with open(Path(d) / 'pits.csv', newline='') as f:
                filas = list(csv.DictReader(f))
            self.assertEqual((filas[0]['estacion'], filas[0]['valido']), ('1', 'True'))

    def test_servicios_parar_y_reiniciar(self):
        n = self.crear()
        srv = {nombre: cb for _, nombre, cb in n.servicios}
        r = srv['~/reiniciar'](None, Ns(success=None, message=None))
        self.assertTrue(r.success)                                               # en ESPERA se puede
        self.avanzar(n, 1.0)
        self.assertNotEqual(n.fsm.estado, E.ESPERA)
        self.assertFalse(srv['~/reiniciar'](None, Ns(success=None, message=None)).success)      # en marcha no
        r = srv['~/parar'](None, Ns(success=None, message=None))
        self.assertEqual((r.success, n.fsm.estado, json.loads(r.message)['motivo']), (True, E.FALLA, 'PARADA_MANUAL'))
        self.assertTrue(srv['~/reiniciar'](None, Ns(success=None, message=None)).success)
        self.assertEqual(n.fsm.estado, E.ESPERA)


if __name__ == '__main__':
    unittest.main()
