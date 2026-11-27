import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import gestor_reset as gr
from carrito.granprix_carrito import transformacion_camara_dock as mc
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.gestor_reset import GestorReset
from carrito.granprix_carrito.pose_dock import LocalizadorDock
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados, invertir, wrap

CAM, TAG, INCL = Pose2D(0.10, 0.01, math.radians(0.5)), Pose2D(0.38, 0.0, math.radians(1.0)), math.radians(6)
MARCOS = mc.Marcos(mc.Montaje(CAM, INCL), TAG)
MAP_ODOM_REAL = Pose2D(0.30, -0.20, 0.10)


def cuaternion_de_matriz(R):
    t = R[0][0] + R[1][1] + R[2][2]
    s = math.sqrt(t + 1.0) * 2
    return ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s)


def gestor(**kw):
    return GestorReset(LocalizadorDock(MARCOS), **kw)


def mapa_real(estacion, robot_dock):
    return componer(D[estacion].pose, robot_dock)


def odom_de(pose_mapa):
    return componer(invertir(MAP_ODOM_REAL), pose_mapa)


def medir(robot_dock):
    x, y, z, dth, _ = tag_visto(robot_dock, CAM, TAG, INCL, h_tag=0.14)
    return x, y, z, dth


def cargar_quieto(g, robot_dock, estacion=2, hasta=2.0, hz=20):
    p = odom_de(mapa_real(estacion, robot_dock))
    for k in range(int(hasta * hz) + 1):
        g.agregar_odom(k / hz, p)


class TestCuaterniones(unittest.TestCase):
    def test_yaw_ida_y_vuelta(self):
        for th in (-3.0, -1.0, 0.0, 0.5, 2.5, 3.1):
            self.assertAlmostEqual(gr.yaw_de_cuaternion(*gr.cuaternion_de_yaw(th)), th, places=9)

    def test_dth_coincide_con_la_formula_del_detector(self):
        for incl in (0.0, math.radians(6)):
            for dock in (desde_grados(0.02, -0.01, 3.0), desde_grados(-0.03, 0.04, -6.0)):
                *_, R = tag_visto(dock, CAM, TAG, incl, h_tag=0.14)
                esperado = math.degrees(math.atan2(R[0][2], R[2][2]))
                self.assertAlmostEqual(gr.dth_de_cuaternion(*cuaternion_de_matriz(R)), esperado, places=7)

    def test_cuaternion_de_dth_ida_y_vuelta(self):
        for dth in (-40.0, -3.0, 0.0, 2.5, 45.0):
            self.assertAlmostEqual(gr.dth_de_cuaternion(*gr.cuaternion_de_dth(dth)), dth, places=9)

    def test_rechaza_cuaterniones_no_validos(self):
        for q in ((0, 0, 0, 0), (0, 0, 0, 2), (float('nan'), 0, 0, 1)):
            with self.assertRaises(ValueError):
                gr.yaw_de_cuaternion(*q)
            with self.assertRaises(ValueError):
                gr.dth_de_cuaternion(*q)


class TestBufferDeOdometria(unittest.TestCase):
    def test_interpola_posicion_y_angulo(self):
        g = gestor()
        g.agregar_odom(1.0, Pose2D(0.0, 0.0, 0.0))
        g.agregar_odom(2.0, Pose2D(1.0, 2.0, 0.4))
        p = g.odom_en(1.25)
        self.assertEqual((round(p.x, 9), round(p.y, 9), round(p.th, 9)), (0.25, 0.5, 0.1))
        self.assertEqual(g.odom_en(2.0).x, 1.0)
        self.assertEqual(g.odom_en(1.0).x, 0.0)

    def test_interpola_el_angulo_por_el_camino_corto(self):
        g = gestor()
        g.agregar_odom(0.0, Pose2D(0, 0, math.radians(179)))
        g.agregar_odom(1.0, Pose2D(0, 0, math.radians(-179)))
        self.assertAlmostEqual(abs(math.degrees(g.odom_en(0.5).th)), 180.0, places=6)

    def test_fuera_del_rango_o_vacio_es_none(self):
        g = gestor()
        self.assertIsNone(g.odom_en(1.0))
        g.agregar_odom(1.0, Pose2D(0, 0, 0))
        g.agregar_odom(2.0, Pose2D(0, 0, 0))
        self.assertIsNone(g.odom_en(0.9))
        self.assertIsNone(g.odom_en(2.1))

    def test_descarta_duplicados_desordenados_y_no_finitos(self):
        g = gestor()
        self.assertTrue(g.agregar_odom(1.0, Pose2D(0, 0, 0)))
        for t in (1.0, 0.5, float('nan'), float('inf')):
            self.assertFalse(g.agregar_odom(t, Pose2D(1, 1, 0)))
        self.assertEqual(g.odom_descartadas, 4)
        self.assertEqual(g.odom_en(1.0).x, 0)

    def test_olvida_lo_viejo(self):
        g = gestor(buffer_s=2.0)
        for k in range(100):
            g.agregar_odom(k * 0.1, Pose2D(0, 0, 0))
        self.assertIsNone(g.odom_en(5.0))
        self.assertIsNotNone(g.odom_en(9.0))

    def test_parametros_invalidos(self):
        for kw in ({'ventana_quieto_s': 0}, {'edad_max_tag_s': -1}, {'buffer_s': float('nan')}, {'retardo_odom_s': -0.1},
                   {'retardo_odom_s': 5.0}):
            with self.assertRaises(ValueError):
                gestor(**kw)


class TestAplicar(unittest.TestCase):
    def setUp(self):
        self.robot = desde_grados(0.02, -0.015, 3.0)
        self.g = gestor()
        cargar_quieto(self.g, self.robot)
        self.g.agregar_tag(1.0, *medir(self.robot))

    def test_inicializa_y_recupera_map_odom(self):
        self.assertIsNone(self.g.map_odom)
        r = self.g.aplicar(1.1, 2)
        self.assertEqual((r.aceptado, r.motivo), (True, None))
        mo = self.g.map_odom
        self.assertAlmostEqual(mo.x, MAP_ODOM_REAL.x, delta=4e-3)
        self.assertAlmostEqual(mo.y, MAP_ODOM_REAL.y, delta=4e-3)
        self.assertAlmostEqual(wrap(mo.th - MAP_ODOM_REAL.th), 0.0, delta=math.radians(0.3))
        self.assertTrue(r.pose.en_tolerancia)

    def test_la_pose_creida_sigue_al_robot_despues_del_reset(self):
        self.g.aplicar(1.1, 2)
        avance = Pose2D(0.1, 0.0, 0.0)
        odom_nueva = componer(odom_de(mapa_real(2, self.robot)), avance)
        real = componer(mapa_real(2, self.robot), avance)
        creida = componer(self.g.map_odom, odom_nueva)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 4e-3)

    def test_motivos_de_rechazo_sin_tag_estacion_y_edad(self):
        g = gestor()
        cargar_quieto(g, self.robot)
        self.assertEqual(g.aplicar(1.0, 2).motivo, 'SIN_TAG')
        g.agregar_tag(1.0, *medir(self.robot))
        self.assertEqual(g.aplicar(1.1, 7).motivo, 'ESTACION_INVALIDA')
        self.assertEqual(g.aplicar(2.5, 2).motivo, 'TAG_VIEJO')
        self.assertEqual(g.aplicar(0.5, 2).motivo, 'TAG_FUTURO')
        self.assertIsNone(g.map_odom)
        self.assertFalse(g.agregar_tag(1.0, float('nan'), 0, 0.3, 0))

    def test_odometria_que_aun_no_llego_o_no_cubre(self):
        g = gestor()
        for k in range(10):
            g.agregar_odom(k / 20, odom_de(mapa_real(2, self.robot)))
        g.agregar_tag(1.0, *medir(self.robot))
        self.assertEqual(g.aplicar(1.1, 2).motivo, 'ODOM_INSUFICIENTE')
        g2 = gestor()
        for k in range(32, 40):
            g2.agregar_odom(k / 20, odom_de(mapa_real(2, self.robot)))
        g2.agregar_tag(1.8, *medir(self.robot))
        self.assertEqual(g2.aplicar(1.9, 2).motivo, 'ODOM_NO_CUBRE')

    def test_rechaza_si_el_robot_se_movia(self):
        g = gestor()
        for k in range(41):
            t = k / 20
            g.agregar_odom(t, odom_de(mapa_real(2, desde_grados(0.02 + 0.2 * t, -0.015, 3.0))))
        g.agregar_tag(1.0, *medir(self.robot))
        r = g.aplicar(1.1, 2)
        self.assertEqual((r.aceptado, r.motivo), (False, 'ROBOT_NO_QUIETO'))
        self.assertIsNone(g.map_odom)

    def test_fuera_del_dock_y_salto_excesivo(self):
        g = gestor()
        lejos = desde_grados(0.4, 0.0, 0.0)
        cargar_quieto(g, lejos)
        g.agregar_tag(1.0, *medir(lejos))
        self.assertEqual(g.aplicar(1.1, 2).motivo, 'FUERA_DE_DOCK')
        self.g.aplicar(1.1, 2)
        antes = self.g.map_odom
        self.g.agregar_tag(1.9, *medir(desde_grados(0.20, 0.0, 0.0)))
        self.assertEqual(self.g.aplicar(1.95, 2).motivo, 'SALTO_EXCESIVO')
        self.g.agregar_tag(1.95, *medir(desde_grados(0.40, 0.0, 0.0)))
        self.assertEqual(self.g.aplicar(1.98, 2).motivo, 'FUERA_DE_DOCK')
        self.assertEqual(self.g.map_odom, antes)
        self.assertEqual(self.g.localizador.reset.n_resets, 1)

    def test_un_segundo_reset_corrige_la_deriva(self):
        self.g.aplicar(1.1, 2)
        deriva = Pose2D(0.03, -0.02, math.radians(2))
        p = componer(odom_de(mapa_real(2, self.robot)), deriva)
        for k in range(41, 61):
            self.g.agregar_odom(k / 20, p)
        self.g.agregar_tag(2.5, *medir(self.robot))
        r = self.g.aplicar(2.6, 2)
        self.assertTrue(r.aceptado, r.motivo)
        self.assertGreater(r.reset.salto_m, 0.02)
        creida = componer(self.g.map_odom, p)
        real = mapa_real(2, self.robot)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 4e-3)
        self.assertEqual(self.g.localizador.reset.n_resets, 2)

    def test_estado(self):
        e = self.g.estado(1.1)
        self.assertEqual((e['inicializado'], e['map_odom'], e['ultimo_motivo']), (False, None, None))
        self.g.aplicar(1.1, 2)
        e = self.g.estado(1.1)
        self.assertEqual((e['inicializado'], e['n_resets'], e['edad_tag_s']), (True, 1, 0.1))
        self.assertIsNotNone(e['map_odom'])


class TestRetardoDeLaOdometria(unittest.TestCase):
    """El robot se mueve hasta t = 0.9 s (verdadero) y se detiene. La odometría llega con 0.5 s de retardo."""
    RETARDO = 0.5

    def escena(self, retardo_param):
        final = desde_grados(0.02, -0.015, 3.0)
        inicio = desde_grados(-0.13, -0.015, 3.0)
        g = gestor(retardo_odom_s=retardo_param)
        for k in range(61):
            tau = k / 20
            t_real = max(0.0, tau - self.RETARDO)
            s = min(t_real / 0.9, 1.0)
            robot = Pose2D(inicio.x + s * (final.x - inicio.x), inicio.y, inicio.th)
            g.agregar_odom(tau, odom_de(mapa_real(2, robot)))
        g.agregar_tag(1.2, *medir(final))
        return g

    def test_con_el_retardo_correcto_se_acepta(self):
        g = self.escena(self.RETARDO)
        r = g.aplicar(1.3, 2)
        self.assertTrue(r.aceptado, r.motivo)
        self.assertAlmostEqual(g.map_odom.x, MAP_ODOM_REAL.x, delta=4e-3)

    def test_con_el_retardo_en_cero_el_robot_ya_detenido_parece_moverse(self):
        g = self.escena(0.0)
        r = g.aplicar(1.3, 2)
        self.assertEqual((r.aceptado, r.motivo), (False, 'ROBOT_NO_QUIETO'))


if __name__ == '__main__':
    unittest.main()
