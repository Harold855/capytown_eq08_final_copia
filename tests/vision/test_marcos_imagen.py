import math
import statistics
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'tests' / 'carrito'))
try:
    import numpy as np
    from carrito.granprix_carrito import marcos as mc
    from carrito.granprix_carrito.reset_pose import ResetPose
    from escena_dock import tag_visto
    from geometria_dock.transformaciones import Pose2D, componer, desde_grados
    from simulacion import apriltag_sintetico as st
    from vision import calibracion_focal as cf
    from vision import medicion as md
    st.detector()
    HAY = True
except Exception as e:  # noqa: BLE001
    HAY, MOTIVO = False, repr(e)

ANCHO, ALTO, FOV, TAG_M = 640, 480, 63.0, 0.0595
DIST = (-0.30, 0.08, 0.0, 0.0, 0.0)
INCL = math.radians(8) if HAY else 0.0


def marcos():
    return mc.Marcos(mc.Montaje(Pose2D(0.10, 0.01, math.radians(0.5)), INCL), Pose2D(0.38, 0.0, math.radians(2.0)))


def imagen(robot, m, estacion=2, semilla=0, dist=DIST):
    x, y, z, dth, R = tag_visto(robot, m.montaje.pose, m.tag(estacion), m.montaje.inclinacion, h_tag=0.15)
    return st.renderizar(estacion, np.array(R), (x, y, z), ANCHO, ALTO, FOV, desenfoque_px=0.8, ruido=3.0, semilla=semilla,
                         tamano_m=TAG_M, dist=dist)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles (pip install -r requirements-vision.txt)')
class TestCadenaCompleta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        F = cf.focal_desde_fov(ANCHO, FOV)
        p = cf.ParametrosCamara(ANCHO, ALTO, F, F, ANCHO / 2, ALTO / 2, None, None, None, None, None, 'x', (), DIST,
                                cf.DetalleDamero(9, 6, 0.02, 'simple', 0.1, 0.1, 20))
        cls.yaml = str(Path(cls.dir.name) / 'cam.yaml')
        cf.guardar_camara(cls.yaml, p)
        cls.cam = md.CamaraTag.desde_yaml(cls.yaml, 59.5)
        cls.m = marcos()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def estimar(self, robot, estacion=2, semilla=0):
        med = self.cam.medir(imagen(robot, self.m, estacion, semilla), tag_id=estacion)
        self.assertTrue(med.valido, med.motivo)
        d = {'aceptada': True, 'id': med.id, 'x_m': med.x_m, 'y_m': med.y_m, 'z_m': med.z_m, 'dth_deg': med.dth_deg}
        return mc.desde_medicion(self.m, d)

    def test_del_pixel_a_la_pose_en_el_dock(self):
        rng = np.random.default_rng(4)
        errs_pos, errs_ang = [], []
        for i in range(24):
            robot = desde_grados(rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(-8, 8))
            r = self.estimar(robot, semilla=i)
            errs_pos.append(math.hypot(r.dock.x - robot.x, r.dock.y - robot.y) * 100)
            errs_ang.append(abs(math.degrees(r.dock.th - robot.th)))
        print(f'\n  pose en el dock (24 poses, imágenes con distorsión): posición p95 {np.percentile(errs_pos, 95):.2f} cm, '
              f'máx {max(errs_pos):.2f} cm | ángulo p95 {np.percentile(errs_ang, 95):.2f}°, máx {max(errs_ang):.2f}°')
        self.assertLess(max(errs_pos), 1.5)
        self.assertLess(max(errs_ang), 2.5)

    def test_en_las_cuatro_estaciones(self):
        for est in (1, 2, 3, 4):
            robot = desde_grados(0.02, -0.03, 4.0)
            r = self.estimar(robot, estacion=est)
            esperado = componer(mc.DOCKS_HTML[est].pose, robot)
            self.assertLess(math.hypot(r.mapa.x - esperado.x, r.mapa.y - esperado.y), 0.015, est)
            self.assertLess(abs(math.degrees(r.mapa.th - esperado.th)), 2.5, est)

    def test_el_reset_con_una_medicion_real_corrige_la_odometria(self):
        robot = desde_grados(0.03, 0.02, -5.0)
        real = componer(mc.DOCKS_HTML[3].pose, robot)
        r = self.estimar(robot, estacion=3)
        odom = componer(real, Pose2D(0.08, -0.05, math.radians(5)))
        reset = ResetPose()
        self.assertTrue(reset.inicializar(r.mapa, odom, cerca=r.cerca).aceptado)
        creida = reset.pose_mapa(odom)
        self.assertLess(math.hypot(creida.x - real.x, creida.y - real.y), 0.015)
        self.assertGreater(math.hypot(odom.x - real.x, odom.y - real.y), 0.09)

    def test_sin_corregir_la_distorsion_se_nota_en_el_dock(self):
        sin_corregir = md.CamaraTag.desde_fov(ANCHO, ALTO, FOV, 59.5)
        robot = desde_grados(0.0, -0.05, 0.0)
        med = sin_corregir.medir(imagen(robot, self.m), tag_id=2)
        self.assertTrue(med.valido)
        d = {'aceptada': True, 'id': 2, 'x_m': med.x_m, 'y_m': med.y_m, 'z_m': med.z_m, 'dth_deg': med.dth_deg}
        mal = mc.desde_medicion(self.m, d).dock
        bien = self.estimar(robot).dock
        self.assertGreater(math.hypot(mal.x - robot.x, mal.y - robot.y), math.hypot(bien.x - robot.x, bien.y - robot.y))


if __name__ == '__main__':
    unittest.main()
