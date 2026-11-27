import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import transformacion_camara_dock as mc
from carrito.granprix_carrito import planificador as pl
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.reset_pose import ResetPose
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir

DEG = math.pi / 180


def cerca(a, b, tm=1e-9, td=1e-7):
    return abs(a.x - b.x) < tm and abs(a.y - b.y) < tm and abs(math.degrees(a.th - b.th)) < td


class TestInicializar(unittest.TestCase):
    def test_cerca_es_obligatorio(self):
        r = ResetPose()
        with self.assertRaises(TypeError):
            r.inicializar(D[1].pose, Pose2D(0, 0, 0))
        with self.assertRaises(TypeError):
            r.actualizar(D[1].pose, Pose2D(0, 0, 0))

    def test_sin_referencia_falla_cerrado(self):
        r = ResetPose()
        self.assertFalse(r.inicializado)
        with self.assertRaises(RuntimeError):
            r.pose_mapa(Pose2D(0, 0, 0))
        with self.assertRaises(RuntimeError):
            r.map_odom
        res = r.actualizar(Pose2D(1, 1, 0), Pose2D(0, 0, 0), cerca=True)
        self.assertEqual((res.aceptado, res.motivo), (False, 'SIN_REFERENCIA'))

    def test_la_pose_del_mapa_es_la_medida_en_el_instante_del_reset(self):
        r = ResetPose()
        medida, odom = D[1].pose, Pose2D(0.03, -0.02, 0.1)
        self.assertTrue(r.inicializar(medida, odom, cerca=True).aceptado)
        self.assertTrue(cerca(r.pose_mapa(odom), medida))
        self.assertEqual((r.inicializado, r.n_resets), (True, 1))

    def test_el_primer_reset_puede_ser_un_salto_grande(self):
        r = ResetPose()
        res = r.inicializar(D[1].pose, Pose2D(0, 0, 0), cerca=True)                                  # el odom arranca en el origen
        self.assertTrue(res.aceptado)
        self.assertIsNone(res.salto_m)

    def test_despues_de_reiniciar_el_odom_el_movimiento_se_compone(self):
        r = ResetPose()
        medida, odom0 = Pose2D(0.4, 0.4, -math.pi / 2), Pose2D(5.0, -3.0, 1.0)
        r.inicializar(medida, odom0, cerca=True)
        avance = Pose2D(1.0, 0.2, 0.3)
        odom1 = componer(odom0, avance)
        self.assertTrue(cerca(r.pose_mapa(odom1), componer(medida, avance)))

    def test_exige_cerca_del_dock_y_quietud_tambien_al_inicializar(self):
        r = ResetPose()
        self.assertEqual(r.inicializar(D[1].pose, Pose2D(0, 0, 0), cerca=False).motivo, 'FUERA_DE_DOCK')
        self.assertEqual(r.inicializar(D[1].pose, Pose2D(0, 0, 0), Pose2D(0.02, 0, 0), cerca=True).motivo, 'ROBOT_NO_QUIETO')
        self.assertFalse(r.inicializado)


class TestActualizar(unittest.TestCase):
    def setUp(self):
        self.r = ResetPose()
        self.r.inicializar(D[2].pose, Pose2D(0, 0, 0), cerca=True)

    def test_corrige_la_deriva_de_la_odometria(self):
        real = componer(D[2].pose, desde_grados(0.02, -0.01, 2.0))
        odom = Pose2D(0.05, 0.03, 0.06)                                                   # la odometría creía otra cosa
        res = self.r.actualizar(real, odom, cerca=True)
        self.assertTrue(res.aceptado)
        self.assertTrue(cerca(self.r.pose_mapa(odom), real))
        self.assertEqual(self.r.n_resets, 2)
        self.assertGreater(res.salto_m, 0.0)

    def test_usa_la_odometria_del_final_de_la_ventana_si_se_da(self):
        real = D[2].pose
        ini, fin = Pose2D(0.100, 0.0, 0.0), Pose2D(0.102, 0.001, 0.001)
        self.assertTrue(self.r.actualizar(real, ini, fin, cerca=True).aceptado)
        self.assertTrue(cerca(self.r.pose_mapa(fin), real))

    def test_rechaza_un_robot_que_se_mueve(self):
        antes = self.r.map_odom
        res = self.r.actualizar(D[2].pose, Pose2D(0, 0, 0), Pose2D(0.01, 0, 0), cerca=True)
        self.assertEqual((res.aceptado, res.motivo), (False, 'ROBOT_NO_QUIETO'))
        res = self.r.actualizar(D[2].pose, Pose2D(0, 0, 0), Pose2D(0, 0, math.radians(2)), cerca=True)
        self.assertEqual(res.motivo, 'ROBOT_NO_QUIETO')
        self.assertEqual((self.r.map_odom, self.r.n_resets), (antes, 1))

    def test_rechaza_un_salto_sospechoso_y_no_cambia_el_estado(self):
        antes = self.r.map_odom
        lejos = componer(D[2].pose, desde_grados(0.30, 0.0, 0.0))
        res = self.r.actualizar(lejos, Pose2D(0, 0, 0), cerca=True)
        self.assertEqual((res.aceptado, res.motivo), (False, 'SALTO_EXCESIVO'))
        self.assertAlmostEqual(res.salto_m, 0.30, places=6)
        girado = componer(D[2].pose, desde_grados(0.0, 0.0, 30.0))
        self.assertEqual(self.r.actualizar(girado, Pose2D(0, 0, 0), cerca=True).motivo, 'SALTO_EXCESIVO')
        self.assertEqual((self.r.map_odom, self.r.n_resets), (antes, 1))

    def test_rechaza_fuera_del_dock(self):
        self.assertEqual(self.r.actualizar(D[2].pose, Pose2D(0, 0, 0), cerca=False).motivo, 'FUERA_DE_DOCK')

    def test_umbrales_ajustables_y_validados(self):
        r = ResetPose(salto_max_m=0.5)
        r.inicializar(D[2].pose, Pose2D(0, 0, 0), cerca=True)
        self.assertTrue(r.actualizar(componer(D[2].pose, desde_grados(0.30, 0.0, 0.0)), Pose2D(0, 0, 0), cerca=True).aceptado)
        for kw in ({'salto_max_m': 0}, {'salto_max_deg': -1}, {'quieto_max_m': float('nan')}, {'quieto_max_deg': 0}):
            with self.assertRaises(ValueError):
                ResetPose(**kw)


class TestConLaCadenaCompleta(unittest.TestCase):
    def test_del_tag_al_reset_y_al_siguiente_tramo(self):
        m = mc.Marcos(mc.Montaje(Pose2D(0.10, 0.01, 0.01), math.radians(5)), Pose2D(0.38, 0.0, 0.02))
        real_dock = desde_grados(0.025, -0.015, 3.0)
        real = componer(D[2].pose, real_dock)
        x, y, z, dth, _ = tag_visto(real_dock, m.montaje.pose, m.tag(2), m.montaje.inclinacion, h_tag=0.15)
        pr = mc.pose_robot(m, 2, x, y, z, dth)
        self.assertTrue(pr.cerca)
        reset = ResetPose()
        deriva = componer(real, Pose2D(0.06, -0.04, math.radians(4)))                      # la odometría acumuló error
        self.assertTrue(reset.inicializar(pr.mapa, deriva, cerca=pr.cerca).aceptado)
        creida = reset.pose_mapa(deriva)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 3e-3)
        destino = (D[3].x, D[3].y)
        verdad = pl.planificar_tramo(real, destino)
        con_reset = pl.planificar_tramo(creida, destino)
        sin_reset = pl.planificar_tramo(deriva, destino)
        self.assertLess(abs(con_reset.phi - verdad.phi), math.radians(0.5))
        self.assertLess(abs(con_reset.L - verdad.L), 0.005)
        self.assertGreater(abs(sin_reset.phi - verdad.phi), math.radians(2))


if __name__ == '__main__':
    unittest.main()
