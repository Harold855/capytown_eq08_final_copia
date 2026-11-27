import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mensajes_contrato as mcon
from carrito.granprix_carrito import transformacion_camara_dock as mc
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.pose_dock import LocalizadorDock, PoseDock
from carrito.granprix_carrito.reset_pose import ResetPose
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir

CAM, TAG = Pose2D(0.10, 0.01, math.radians(0.5)), Pose2D(0.38, 0.0, math.radians(1.0))
MARCOS = mc.Marcos(mc.Montaje(CAM, math.radians(6)), TAG)


def medicion(robot, estacion=2):
    x, y, z, dth, _ = tag_visto(robot, CAM, TAG, math.radians(6), h_tag=0.14)
    return {'aceptada': True, 'id': estacion, 'x_m': x, 'y_m': y, 'z_m': z, 'dth_deg': dth}


class TestPoseDesdeTag(unittest.TestCase):
    def test_recupera_la_pose_y_su_error(self):
        robot = desde_grados(0.02, -0.01, 3.0)
        p = LocalizadorDock(MARCOS).pose_desde_tag(medicion(robot))
        self.assertEqual((p.estacion, p.fuente, p.cerca), (2, 'tag', True))
        self.assertAlmostEqual(p.dx, 0.02, delta=2e-3)
        self.assertAlmostEqual(p.dy, -0.01, delta=2e-3)
        self.assertAlmostEqual(p.dth_deg, 3.0, delta=0.2)
        pos, ang = p.error
        self.assertAlmostEqual(pos, math.hypot(0.02, 0.01), delta=3e-3)
        self.assertAlmostEqual(ang, 3.0, delta=0.2)
        self.assertTrue(p.en_tolerancia)

    def test_la_tolerancia_pide_posicion_y_angulo_a_la_vez(self):
        loc = LocalizadorDock(MARCOS)
        self.assertFalse(loc.pose_desde_tag(medicion(desde_grados(0.05, 0.0, 0.0))).en_tolerancia)
        self.assertFalse(loc.pose_desde_tag(medicion(desde_grados(0.0, 0.0, 8.0))).en_tolerancia)
        self.assertTrue(loc.pose_desde_tag(medicion(desde_grados(0.03, 0.0, 5.0))).en_tolerancia)

    def test_formato_del_contrato(self):
        p = LocalizadorDock(MARCOS).pose_desde_tag(medicion(desde_grados(0.02, -0.01, 3.0)))
        c = p.a_contrato()
        self.assertEqual(set(c), {'dx', 'dy', 'dth'})
        self.assertAlmostEqual(c['dth'], p.dth_deg)
        msg = mcon.solicitud(8, p.estacion, p.dx, p.dy, p.dth, 'A')                       # dth en radianes -> grados
        for k in ('dx', 'dy', 'dth'):
            self.assertAlmostEqual(msg['pose'][k], c[k], places=9)

    def test_en_las_cuatro_estaciones_y_estacion_explicita(self):
        loc = LocalizadorDock(MARCOS)
        robot = desde_grados(0.01, 0.02, -2.0)
        for est in (1, 2, 3, 4):
            p = loc.pose_desde_tag(medicion(robot, est))
            esperado = componer(D[est].pose, robot)
            self.assertAlmostEqual(p.mapa.x, esperado.x, delta=3e-3)
            self.assertAlmostEqual(p.mapa.y, esperado.y, delta=3e-3)
        self.assertEqual(loc.pose_desde_tag({**medicion(robot), 'id': 1}, estacion=3).estacion, 3)

    def test_fuera_del_dock_o_medicion_no_aceptada(self):
        loc = LocalizadorDock(MARCOS)
        self.assertFalse(loc.pose_desde_tag(medicion(desde_grados(0.4, 0.0, 0.0))).cerca)
        with self.assertRaises(ValueError):
            loc.pose_desde_tag({**medicion(desde_grados(0, 0, 0)), 'aceptada': False})


class TestConOdometria(unittest.TestCase):
    def setUp(self):
        self.loc = LocalizadorDock(MARCOS)
        self.real = componer(D[2].pose, desde_grados(0.015, -0.01, 2.0))
        self.odom = Pose2D(0.05, -0.03, 0.04)
        self.tag = self.loc.pose_desde_tag(medicion(desde_grados(0.015, -0.01, 2.0)))

    def test_sin_referencia_falla_cerrado(self):
        with self.assertRaises(RuntimeError):
            self.loc.pose_desde_odom(2, self.odom)

    def test_despues_del_reset_la_odometria_da_la_misma_pose(self):
        self.assertTrue(self.loc.aplicar_reset(self.tag, self.odom).aceptado)
        o = self.loc.pose_desde_odom(2, self.odom)
        self.assertEqual((o.fuente, o.desplazamiento_odom_m), ('odom', 0.0))
        self.assertAlmostEqual(o.dx, self.tag.dx, places=9)
        self.assertAlmostEqual(o.dy, self.tag.dy, places=9)
        self.assertAlmostEqual(o.dth, self.tag.dth, places=9)

    def test_el_movimiento_se_compone_y_se_mide_el_desplazamiento(self):
        self.loc.aplicar_reset(self.tag, self.odom)
        avance = Pose2D(0.2, 0.0, 0.0)
        o = self.loc.pose_desde_odom(2, componer(self.odom, avance))
        esperado = componer(invertir(D[2].pose), componer(self.real, avance))
        self.assertAlmostEqual(o.dx, esperado.x, delta=3e-3)
        self.assertAlmostEqual(o.dy, esperado.y, delta=3e-3)
        self.assertAlmostEqual(o.desplazamiento_odom_m, 0.2, places=9)
        self.assertTrue(o.cerca)

    def test_la_pose_se_expresa_en_el_dock_pedido(self):
        self.loc.aplicar_reset(self.tag, self.odom)
        en3 = self.loc.pose_desde_odom(3, self.odom)
        self.assertFalse(en3.cerca)
        self.assertGreater(math.hypot(en3.dx, en3.dy), 1.5)
        with self.assertRaises(ValueError):
            self.loc.pose_desde_odom(5, self.odom)

    def test_la_deriva_crece_con_el_desplazamiento_y_un_nuevo_reset_la_corrige(self):
        self.loc.aplicar_reset(self.tag, self.odom)
        avance_real = Pose2D(0.10, 0.0, math.radians(1.0))
        real2 = componer(self.real, avance_real)
        odom2 = componer(self.odom, Pose2D(0.105, 0.0, math.radians(1.0)))                # la odometría avanza 5 % de más
        esperado = componer(invertir(D[2].pose), real2)
        con_deriva = self.loc.pose_desde_odom(2, odom2)
        error = math.hypot(con_deriva.dx - esperado.x, con_deriva.dy - esperado.y)
        self.assertGreater(error, 0.004)
        self.assertLess(error, 0.008)
        robot2 = componer(invertir(D[2].pose), real2)
        nueva = self.loc.pose_desde_tag(medicion(desde_grados(robot2.x, robot2.y, math.degrees(robot2.th))))
        self.assertTrue(self.loc.aplicar_reset(nueva, odom2).aceptado)
        corregida = self.loc.pose_desde_odom(2, odom2)
        self.assertLess(math.hypot(corregida.dx - esperado.x, corregida.dy - esperado.y), 3e-3)
        self.assertEqual(corregida.desplazamiento_odom_m, 0.0)

    def test_solo_se_hace_reset_con_poses_del_tag(self):
        self.loc.aplicar_reset(self.tag, self.odom)
        o = self.loc.pose_desde_odom(2, self.odom)
        with self.assertRaises(ValueError):
            self.loc.aplicar_reset(o, self.odom)

    def test_propaga_los_rechazos_y_no_cambia_el_estado(self):
        self.loc.aplicar_reset(self.tag, self.odom)
        antes = self.loc.pose_desde_odom(2, self.odom)
        lejos = self.loc.pose_desde_tag(medicion(desde_grados(0.30, 0.0, 0.0)))
        self.assertEqual(self.loc.aplicar_reset(lejos, self.odom).motivo, 'FUERA_DE_DOCK')
        movido = self.loc.aplicar_reset(self.tag, self.odom, Pose2D(0.05 + 0.02, -0.03, 0.04))
        self.assertEqual(movido.motivo, 'ROBOT_NO_QUIETO')
        despues = self.loc.pose_desde_odom(2, self.odom)
        self.assertEqual((antes.dx, antes.dy, antes.dth), (despues.dx, despues.dy, despues.dth))
        self.assertEqual(self.loc.reset.n_resets, 1)

    def test_usa_el_reset_que_se_le_da(self):
        reset = ResetPose(salto_max_m=0.5)
        loc = LocalizadorDock(MARCOS, reset)
        self.assertIs(loc.reset, reset)


if __name__ == '__main__':
    unittest.main()
