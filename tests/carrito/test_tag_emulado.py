import importlib
import math
import random
import statistics
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ros_falso as rf
from carrito.granprix_carrito import gestor_reset as gr
from carrito.granprix_carrito import transformacion_camara_dock as mc
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.gestor_reset import GestorReset
from carrito.granprix_carrito.pose_dock import LocalizadorDock
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir
from ros_falso import Mensaje, Node, Ns

te = None
SIM = RAIZ / 'carrito' / 'config' / 'marcos_sim.yaml'
CAM, TAG, INCL = Pose2D(0.10, 0.01, math.radians(0.5)), Pose2D(0.38, 0.0, math.radians(1.0)), math.radians(6)
MARCOS = mc.Marcos(mc.Montaje(CAM, INCL), TAG)


def setUpModule():
    global te
    rf.instalar()
    te = importlib.import_module('carrito.nodos.tag_emulado')


def tearDownModule():
    rf.desinstalar('carrito.nodos.tag_emulado')


class TestModelo(unittest.TestCase):
    def test_coincide_con_la_escena_fisica_3d_independiente(self):
        rng = random.Random(3)
        for _ in range(40):
            robot = desde_grados(rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), rng.uniform(-8, 8))
            x, y, z, dth, _ = tag_visto(robot, CAM, TAG, INCL, h_camara=0.12, h_tag=0.14)
            ex, ey, ez, edth = te.medicion_emulada(MARCOS, 2, componer(D[2].pose, robot), abajo_m=0.12 - 0.14)
            self.assertAlmostEqual(ex, x, delta=2e-3)
            self.assertAlmostEqual(ey, y, delta=2e-3)
            self.assertAlmostEqual(ez, z, delta=2e-3)
            self.assertAlmostEqual(edth, dth, delta=0.2)

    def test_la_cadena_inversa_devuelve_la_pose_exacta(self):
        for est in (1, 2, 3, 4):
            for abajo in (0.0, -0.03, 0.05):
                robot = desde_grados(0.03, -0.02, 4.0)
                med = te.medicion_emulada(MARCOS, est, componer(D[est].pose, robot), abajo_m=abajo)
                r = mc.pose_robot(MARCOS, est, *med)
                self.assertAlmostEqual(r.dock.x, 0.03, places=9)
                self.assertAlmostEqual(r.dock.y, -0.02, places=9)
                self.assertAlmostEqual(math.degrees(r.dock.th), 4.0, places=7)

    def test_alineado_el_tag_esta_a_28_cm_de_la_camara(self):
        m = mc.cargar_marcos(str(SIM))
        x, y, z, dth = te.medicion_emulada(m, 2, D[2].pose, abajo_m=0.0)
        self.assertAlmostEqual(x, 0.0, places=9)
        self.assertAlmostEqual(dth, 0.0, places=7)
        self.assertAlmostEqual(math.hypot(y, z), 0.28, places=6)                          # distancia a lo largo del eje óptico inclinado

    def test_el_montaje_del_simulador_carga(self):
        m = mc.cargar_marcos(str(SIM))
        self.assertEqual((m.montaje.pose.x, m.tag_en_dock.x), (0.10, 0.38))
        self.assertAlmostEqual(math.degrees(m.montaje.inclinacion), 20.05)


class TestVisibilidad(unittest.TestCase):
    def ver(self, pose_mapa, **kw):
        return te.ver_tag(MARCOS, pose_mapa, ruido=te.RuidoTag(0, 0, 0), **kw)

    def test_en_el_dock_se_ve_la_estacion_correcta(self):
        for est in (1, 2, 3, 4):
            v = self.ver(D[est].pose)
            self.assertEqual(v[0], est)
            self.assertAlmostEqual(v[3], 0.28, delta=0.03)

    def test_lejos_de_los_docks_no_se_ve_ninguno(self):
        self.assertIsNone(self.ver(Pose2D(1.4, 1.4, 0.0)))

    def test_de_espaldas_no_se_ve(self):
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.0, 180.0))))

    def test_girado_el_tag_sale_del_campo_de_vision_antes_que_del_angulo_de_vision(self):
        self.assertIsNotNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.0, 15.0))))
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.0, 40.0))))              # la cámara va 10 cm delante del eje de giro: el tag sale a >34.4°

    def test_el_limite_del_angulo_de_vision_del_tag_con_un_campo_amplio(self):
        amplio = te.ModeloCamara(hfov_deg=170.0, vfov_deg=170.0)
        self.assertIsNotNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.0, 40.0)), modelo=amplio))
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.0, 75.0)), modelo=amplio))

    def test_fuera_del_campo_de_vision_o_muy_cerca_o_muy_lejos(self):
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(0.0, 0.30, 0.0))))
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(0.30, 0.0, 0.0))))
        self.assertIsNone(self.ver(componer(D[2].pose, desde_grados(-0.40, 0.0, 0.0))))

    def test_se_elige_el_tag_mas_cercano(self):
        v = self.ver(componer(D[2].pose, desde_grados(0.05, 0.0, 0.0)))
        self.assertEqual(v[0], 2)


class TestRuido(unittest.TestCase):
    def test_sin_ruido_es_exacto_y_con_semilla_es_reproducible(self):
        a = te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0, 0, 0))
        b = te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0, 0, 0))
        self.assertEqual(a, b)
        r1 = te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0.002, 1.0), rng=random.Random(5))
        r2 = te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0.002, 1.0), rng=random.Random(5))
        self.assertEqual(r1, r2)
        self.assertNotEqual(r1, a)

    def test_las_desviaciones_son_las_pedidas(self):
        rng = random.Random(1)
        limpio = te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0, 0, 0))
        muestras = [te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0.002, 1.0), rng=rng) for _ in range(3000)]
        for i, sigma in ((1, 0.002), (3, 0.002), (4, 1.0)):
            valores = [m[i] - limpio[i] for m in muestras]
            self.assertAlmostEqual(statistics.fmean(valores), 0.0, delta=sigma * 0.1)
            self.assertAlmostEqual(statistics.pstdev(valores), sigma, delta=sigma * 0.1)

    def test_perdida_de_deteccion(self):
        rng = random.Random(2)
        vistos = sum(te.ver_tag(MARCOS, D[2].pose, ruido=te.RuidoTag(0, 0, 0.3), rng=rng) is not None for _ in range(2000))
        self.assertAlmostEqual(vistos / 2000, 0.7, delta=0.04)

    def test_ruido_invalido(self):
        for args in ((-1, 0, 0), (0, -1, 0), (0, 0, 1.5), (0, 0, -0.1)):
            with self.assertRaises(ValueError):
                te.RuidoTag(*args)


class TestConElReset(unittest.TestCase):
    def test_emulador_mas_reset_recupera_la_pose_con_la_odometria_a_la_deriva(self):
        real_dock = desde_grados(0.025, -0.02, 3.0)
        real = componer(D[2].pose, real_dock)
        mo_real = Pose2D(0.3, -0.2, 0.1)
        odom = componer(invertir(mo_real), real)
        g = GestorReset(LocalizadorDock(MARCOS))
        for k in range(41):
            g.agregar_odom(k / 20, odom)
        est, x, y, z, dth = te.ver_tag(MARCOS, real, ruido=te.RuidoTag(0.001, 0.5), rng=random.Random(7))
        g.agregar_tag(1.0, x, y, z, dth)
        r = g.aplicar(1.1, est)
        self.assertTrue(r.aceptado, r.motivo)
        creida = componer(g.map_odom, odom)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 0.01)
        self.assertLess(abs(math.degrees(creida.th - real.th)), 1.5)


class TestNodo(unittest.TestCase):
    def crear(self, **parametros):
        Node.sobrescribe = {'marcos_yaml': str(SIM), 'sigma_pos_m': 0.0, 'sigma_dth_deg': 0.0, **parametros}
        return te._clase_nodo()()

    @staticmethod
    def pose_msg(pose, sec=10, nano=0, frame='map'):
        q = gr.cuaternion_de_yaw(pose.th)
        return Ns(header=Ns(frame_id=frame, stamp=Ns(sec=sec, nanosec=nano)),
                  pose=Ns(position=Ns(x=pose.x, y=pose.y), orientation=Ns(x=q[0], y=q[1], z=q[2], w=q[3])))

    def test_sin_marcos_no_arranca(self):
        Node.sobrescribe = {}
        with self.assertRaisesRegex(ValueError, 'marcos_yaml'):
            te._clase_nodo()()

    def test_publica_el_tag_con_la_hora_de_la_pose_y_el_formato_esperado(self):
        n = self.crear(publicar_dock=True)
        n.callback('/sim/pose')(self.pose_msg(componer(D[3].pose, desde_grados(0.02, -0.01, 3.0)), 12, 5000))
        n.timers[0][1]()
        m = n.publicador('/tag/pose').enviados[-1]
        self.assertEqual(m.header.frame_id, 'camera_optical_frame')
        self.assertEqual((m.header.stamp.sec, m.header.stamp.nanosec), (12, 5000))
        esperado = te.medicion_emulada(mc.cargar_marcos(str(SIM)), 3, componer(D[3].pose, desde_grados(0.02, -0.01, 3.0)))
        o = m.pose.orientation
        self.assertAlmostEqual(gr.dth_de_cuaternion(o.x, o.y, o.z, o.w), esperado[3], places=7)
        self.assertAlmostEqual(m.pose.position.z, esperado[2], places=9)
        self.assertEqual(n.publicador('/pit/dock').enviados[-1].data, 3)

    def test_no_publica_si_no_se_ve_ni_repite_la_misma_pose(self):
        n = self.crear()
        n.callback('/sim/pose')(self.pose_msg(Pose2D(1.4, 1.4, 0.0)))
        n.timers[0][1]()
        self.assertEqual(n.publicador('/tag/pose').enviados, [])
        n.callback('/sim/pose')(self.pose_msg(D[2].pose))
        n.timers[0][1]()
        n.timers[0][1]()
        self.assertEqual(len(n.publicador('/tag/pose').enviados), 1)

    def test_el_dock_no_se_publica_si_no_se_pide(self):
        n = self.crear()
        self.assertNotIn('/pit/dock', [t for _, t, _ in n.pubs])

    def test_descarta_poses_en_otro_marco_o_invalidas(self):
        n = self.crear()
        n.callback('/sim/pose')(self.pose_msg(D[2].pose, frame='odom'))
        malo = self.pose_msg(D[2].pose)
        malo.pose.orientation = Ns(x=0.0, y=0.0, z=0.0, w=0.0)
        n.callback('/sim/pose')(malo)
        n.timers[0][1]()
        self.assertEqual((n.descartadas, n.publicador('/tag/pose').enviados), (2, []))

    def test_los_parametros_del_ruido_llegan_al_modelo(self):
        n = self.crear(sigma_pos_m=0.003, prob_perdida=0.2, hfov_deg=50.0, semilla=9)
        self.assertEqual((n.ruido.sigma_pos_m, n.ruido.prob_perdida, n.modelo.hfov_deg), (0.003, 0.2, 50.0))


if __name__ == '__main__':
    unittest.main()
