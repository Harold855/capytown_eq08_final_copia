import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import marcos as mc
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.docks import mapa_a_dock
from comun.yaml_estricto import ErrorYaml
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, componer, desde_grados

CAM = Pose2D(0.10, 0.01, math.radians(0.5))
TAG = Pose2D(0.38, 0.005, math.radians(2.0))
SEMILLA = RAIZ / 'carrito' / 'config' / 'marcos.yaml'


def marcos(incl=0.0, cam=CAM, tag=TAG, **kw):
    return mc.Marcos(mc.Montaje(cam, incl), tag, **kw)


def medir(robot, m, estacion=2, **kw):
    x, y, z, dth, _ = tag_visto(robot, m.montaje.pose, m.tag(estacion), m.montaje.inclinacion, **kw)
    return x, y, z, dth


class TestConversion(unittest.TestCase):
    def comprobar(self, m, robot, tol_m=1e-3, tol_deg=0.2, **kw):
        est = mc.pose_en_dock(m, 2, *medir(robot, m, **kw))
        self.assertAlmostEqual(est.x, robot.x, delta=tol_m)
        self.assertAlmostEqual(est.y, robot.y, delta=tol_m)
        self.assertAlmostEqual(math.degrees(est.th), math.degrees(robot.th), delta=tol_deg)

    def test_recupera_la_pose_en_la_zona_del_acople(self):
        for incl in (0.0, math.radians(10)):
            m = marcos(incl)
            for dx in (-0.04, 0.0, 0.04):
                for dy in (-0.04, 0.0, 0.04):
                    for deg in (-6.0, 0.0, 6.0):
                        with self.subTest(incl=incl, dx=dx, dy=dy, deg=deg):
                            self.comprobar(m, desde_grados(dx, dy, deg), tol_m=2e-3, h_tag=0.15)

    def test_exacto_sin_inclinacion(self):
        self.comprobar(marcos(), desde_grados(0.03, -0.02, 4.0), tol_m=1e-9, tol_deg=1e-9)

    def test_alineado_da_cero(self):
        m = marcos(cam=Pose2D(0.10, 0.0, 0.0), tag=Pose2D(0.38, 0.0, 0.0))
        est = mc.pose_en_dock(m, 2, 0.0, 0.0, 0.28, 0.0)
        self.assertEqual((round(est.x, 9), round(est.y, 9), round(est.th, 9)), (0.0, 0.0, 0.0))

    def test_signos(self):
        m = marcos(cam=Pose2D(0.10, 0.0, 0.0), tag=Pose2D(0.38, 0.0, 0.0))
        izq = mc.pose_en_dock(m, 2, *medir(desde_grados(0.0, 0.03, 0.0), m))
        self.assertGreater(izq.y, 0.029)
        giro = mc.pose_en_dock(m, 2, *medir(desde_grados(0.0, 0.0, 5.0), m))
        self.assertAlmostEqual(math.degrees(giro.th), 5.0, places=6)
        adelante = mc.pose_en_dock(m, 2, *medir(desde_grados(0.04, 0.0, 0.0), m))
        self.assertAlmostEqual(adelante.x, 0.04, places=6)
        self.assertEqual(mc.tag_en_camara(0.05, 0.0, 0.3, 0.0).y, -0.05)

    def test_error_de_montaje_se_propaga_como_se_espera(self):
        verdad, mal = marcos(), marcos(cam=Pose2D(CAM.x + 0.01, CAM.y, CAM.th))
        robot = desde_grados(0.0, 0.0, 0.0)
        est = mc.pose_en_dock(mal, 2, *medir(robot, verdad))
        self.assertAlmostEqual(est.x, -0.01, places=6)

    def test_pose_en_el_mapa_y_cerca_del_dock(self):
        m = marcos()
        robot = desde_grados(0.02, -0.01, 3.0)
        for est in (1, 2, 3, 4):
            r = mc.pose_robot(m, est, *medir(robot, m, estacion=est))
            esperado = componer(D[est].pose, robot)
            self.assertAlmostEqual(r.mapa.x, esperado.x, places=6)
            self.assertAlmostEqual(r.mapa.y, esperado.y, places=6)
            self.assertAlmostEqual(r.mapa.th, esperado.th, places=6)
            dx, dy, deg = mapa_a_dock(D[est], r.mapa)
            self.assertAlmostEqual(dx, 0.02, places=6)
            self.assertAlmostEqual(dy, -0.01, places=6)
            self.assertAlmostEqual(deg, 3.0, places=5)
            self.assertTrue(r.cerca)
        lejos = mc.pose_robot(m, 2, *medir(desde_grados(0.35, 0.0, 0.0), m))
        giro = mc.pose_robot(m, 2, *medir(desde_grados(0.0, 0.0, 60.0), m))
        self.assertFalse(lejos.cerca)
        self.assertFalse(giro.cerca)

    def test_estacion_invalida(self):
        with self.assertRaises(ValueError):
            mc.pose_robot(marcos(), 5, 0.0, 0.0, 0.28, 0.0)

    def test_tag_distinto_por_dock(self):
        m = marcos(por_dock={3: Pose2D(0.30, 0.0, 0.0)})
        self.assertEqual(m.tag(3).x, 0.30)
        self.assertEqual(m.tag(2), TAG)


class TestMedicion(unittest.TestCase):
    def setUp(self):
        self.m = marcos()
        x, y, z, dth = medir(desde_grados(0.01, 0.02, 2.0), self.m, estacion=3)
        self.med = {'aceptada': True, 'id': 3, 'x_m': x, 'y_m': y, 'z_m': z, 'dth_deg': dth}

    def test_usa_el_id_como_estacion(self):
        r = mc.desde_medicion(self.m, self.med)
        self.assertAlmostEqual(r.dock.x, 0.01, places=6)
        self.assertAlmostEqual(r.mapa.x, componer(D[3].pose, desde_grados(0.01, 0.02, 2.0)).x, places=6)

    def test_formato_de_continuo_y_estacion_explicita(self):
        c = {k: v for k, v in self.med.items() if k != 'aceptada'}
        c['valido'] = True
        self.assertAlmostEqual(mc.desde_medicion(self.m, c, estacion=3).dock.y, 0.02, places=6)

    def test_rechaza_lo_dudoso(self):
        for cambio in ({'aceptada': False}, {'z_m': None}, {'x_m': None}, {'id': None}):
            with self.assertRaises(ValueError, msg=str(cambio)):
                mc.desde_medicion(self.m, {**self.med, **cambio})
        with self.assertRaises(ValueError):
            mc.desde_medicion(self.m, {k: v for k, v in self.med.items() if k != 'aceptada'})


class TestMontajeDesdeReferencia(unittest.TestCase):
    def test_recupera_el_montaje_con_inclinacion(self):
        for incl in (0.0, math.radians(8)):
            verdad = Pose2D(0.11, -0.015, math.radians(1.5))
            robot_ref = desde_grados(0.0, 0.0, 0.0)
            x, y, z, dth, _ = tag_visto(robot_ref, verdad, TAG, incl, h_tag=0.14)
            est = mc.montaje_desde_referencia(robot_ref, TAG, x, y, z, dth, incl)
            self.assertAlmostEqual(est.x, verdad.x, delta=2e-3)
            self.assertAlmostEqual(est.y, verdad.y, delta=2e-3)
            self.assertAlmostEqual(math.degrees(est.th), 1.5, delta=0.2)

    def test_con_el_robot_algo_corrido_del_centro(self):
        verdad = Pose2D(0.10, 0.0, 0.0)
        robot_ref = desde_grados(0.02, -0.01, 1.0)
        x, y, z, dth, _ = tag_visto(robot_ref, verdad, TAG)
        est = mc.montaje_desde_referencia(robot_ref, TAG, x, y, z, dth)
        self.assertAlmostEqual(est.x, 0.10, places=6)
        self.assertAlmostEqual(est.y, 0.0, places=6)


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def con(self, viejo, nuevo):
        texto = SEMILLA.read_text(encoding='utf-8')
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: null', 'x_m: 0.10\n  y_m: 0.01\n  yaw_deg: 0.5', 1)
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: 0.0', 'x_m: 0.38\n  y_m: 0.0\n  yaw_deg: 0.0', 1)
        if viejo:
            self.assertIn(viejo, texto, viejo)
            texto = texto.replace(viejo, nuevo, 1)
        ruta = os.path.join(self.dir.name, 'marcos.yaml')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        return ruta

    def test_la_semilla_falla_hasta_medir(self):
        with self.assertRaisesRegex(ErrorYaml, 'falta medir'):
            mc.cargar_marcos(str(SEMILLA))

    def test_carga_valida(self):
        m = mc.cargar_marcos(self.con('', ''))
        self.assertEqual((m.montaje.pose.x, m.montaje.pose.y), (0.10, 0.01))
        self.assertAlmostEqual(math.degrees(m.montaje.pose.th), 0.5)
        self.assertEqual((m.tag_en_dock.x, m.montaje.inclinacion, m.cerca_m, m.cerca_deg), (0.38, 0.0, 0.30, 45.0))

    def test_inclinacion_y_por_dock(self):
        m = mc.cargar_marcos(self.con('inclinacion_deg: 0.0', 'inclinacion_deg: 12.0'))
        self.assertAlmostEqual(math.degrees(m.montaje.inclinacion), 12.0)
        m = mc.cargar_marcos(self.con('por_dock: {}', 'por_dock: {E2: {x_m: 0.30, y_m: 0.0, yaw_deg: 0.0}}'))
        self.assertEqual((m.tag(2).x, m.tag(1).x), (0.30, 0.38))

    def test_valores_dudosos(self):
        casos = [('x_m: 0.10', 'x_m: 10'), ('x_m: 0.10', 'x_m: "0.10"'), ('yaw_deg: 0.5', 'yaw_deg: 90'),
                 ('inclinacion_deg: 0.0', 'inclinacion_deg: 80'), ('x_m: 0.38', 'x_m: 5.0'),
                 ('por_dock: {}', 'por_dock: {E7: {x_m: 0.3, y_m: 0.0, yaw_deg: 0.0}}'),
                 ('por_dock: {}', 'por_dock: {2: {x_m: 0.3, y_m: 0.0, yaw_deg: 0.0}}'),
                 ('por_dock: {}', 'por_dock: {E2: {x_m: null, y_m: 0.0, yaw_deg: 0.0}}'),
                 ('max_m: 0.30', 'max_m: 0'), ('max_deg: 45.0', 'max_deg: 120'), ('version: 1', 'version: 2'),
                 ('version: 1', 'version: 1\nversion: 1'), ('inclinacion_deg:', 'inclinacion:')]
        for viejo, nuevo in casos:
            with self.assertRaises(ErrorYaml, msg=nuevo):
                mc.cargar_marcos(self.con(viejo, nuevo))


if __name__ == '__main__':
    unittest.main()
