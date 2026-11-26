"""AprilTag sin robot: imágenes sintéticas con pose conocida pasadas por la herramienta del docente.

Necesita OpenCV y pupil-apriltags (requirements-vision.txt); si faltan, se omite. Solo usa tag36h11, la
familia del reto: la librería nativa aborta con memoria corrupta al mezclar familias en un proceso.
Valida la herramienta con una cámara ideal; NO valida la cámara real ni su calibración.
"""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
try:
    import numpy as np
    from simulacion import apriltag_sintetico as s
    import herramienta_apriltag as ht
    s.detector()
    HAY = True
except Exception as e:  # noqa: BLE001 - cualquier fallo de import/crear el detector = omitir
    HAY, MOTIVO = False, repr(e)


def escena(yaw=0.0, t=(0.0, 0.0, 0.28), tag_id=3, ancho=640, alto=480, fov=70.0, blur=0.8, ruido=3.0, semilla=1):
    return s.renderizar(tag_id, s.rot_y(yaw), t, ancho, alto, fov, desenfoque_px=blur, ruido=ruido, semilla=semilla)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles (pip install -r requirements-vision.txt)')
class TestDeteccion(unittest.TestCase):
    def test_lee_cada_id_en_la_escena_del_reto(self):
        for tag_id in (0, 1, 3, 7, 12, 100, 586):
            d = s.medir(escena(tag_id=tag_id), 70.0)
            self.assertIsNotNone(d, tag_id)
            self.assertEqual(d['id'], tag_id)
            self.assertEqual(d['hamming'], 0)

    def test_imagen_vacia_o_con_otro_id_no_da_pose(self):
        self.assertIsNone(s.medir(np.full((480, 640), 200, np.uint8), 70.0))
        self.assertIsNone(s.medir(escena(tag_id=3), 70.0, tag_id=4))

    def test_dos_tags_no_se_adivinan(self):
        """medir devuelve None si ve más de uno: es mejor no medir que medir el equivocado."""
        izq = escena(t=(-0.08, 0.0, 0.40), tag_id=1)
        der = escena(t=(0.08, 0.0, 0.40), tag_id=2)
        junta = np.minimum(izq, der)
        self.assertEqual(len(ht.detectar_en(s.detector(), junta, s.parametros_camara(640, 480, 70.0), s.TAMANO_M)), 2)
        self.assertIsNone(s.medir(junta, 70.0))

    def test_tag_demasiado_lejos_no_se_ve(self):
        self.assertIsNone(s.medir(escena(t=(0, 0, 3.0)), 70.0))

    def test_tag_detras_de_la_camara_es_error(self):
        with self.assertRaises(ValueError):
            escena(t=(0, 0, -0.2))


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestPose(unittest.TestCase):
    def test_pose_de_frente_y_con_giro_a_28_cm(self):
        for yaw in (0.0, 5.0, -5.0, 20.0, -20.0, 40.0, -40.0):
            d = s.medir(escena(yaw=yaw, t=(0.03, -0.01, 0.28)), 70.0)['pose']
            self.assertAlmostEqual(d['x'], 0.03, delta=0.001, msg=f'x yaw {yaw}')
            self.assertAlmostEqual(d['y'], -0.01, delta=0.001, msg=f'y yaw {yaw}')
            self.assertAlmostEqual(d['z'], 0.28, delta=0.002, msg=f'z yaw {yaw}')
            self.assertAlmostEqual(d['dth'], yaw, delta=2.0, msg=f'dth yaw {yaw}')

    def test_signo_de_dth(self):
        """Convención de la herramienta: dth > 0 cuando el tag gira como rot_y(+). Hay que confirmar físicamente
        qué sentido real es ese respecto del carrito y del dock antes de usarlo en la compensación."""
        self.assertGreater(s.medir(escena(yaw=25), 70.0)['pose']['dth'], 20)
        self.assertLess(s.medir(escena(yaw=-25), 70.0)['pose']['dth'], -20)

    def test_el_tag_a_la_derecha_da_x_positiva_y_mas_lejos_da_z_mayor(self):
        a = s.medir(escena(t=(0.05, 0, 0.28)), 70.0)['pose']
        b = s.medir(escena(t=(-0.05, 0, 0.28)), 70.0)['pose']
        c = s.medir(escena(t=(0.0, 0, 0.34)), 70.0)['pose']
        self.assertGreater(a['x'], 0.04); self.assertLess(b['x'], -0.04)
        self.assertAlmostEqual(c['z'], 0.34, delta=0.003)

    def test_precision_con_ruido_dentro_de_la_tolerancia_con_margen(self):
        """Muestras aleatorias en el entorno del dock: p95 del error de dth < 3° (tolerancia 6°) y de posición < 0.5 cm."""
        rng = np.random.default_rng(11)
        ex, ez, eth = [], [], []
        for i in range(30):
            z, x, yaw = rng.uniform(0.22, 0.34), rng.uniform(-0.06, 0.06), rng.uniform(-15, 15)
            d = s.medir(escena(yaw=yaw, t=(x, 0.0, z), semilla=i), 70.0)
            self.assertIsNotNone(d)
            ex.append(abs(d['pose']['x'] - x)); ez.append(abs(d['pose']['z'] - z)); eth.append(abs(d['pose']['dth'] - yaw))
        self.assertLess(np.percentile(eth, 95), 3.0)
        self.assertLess(np.percentile(ex, 95), 0.005)
        self.assertLess(np.percentile(ez, 95), 0.005)

    def test_la_resolucion_baja_empeora_el_angulo_pero_no_lo_rompe(self):
        rng = np.random.default_rng(5)
        errs = []
        for i in range(20):
            yaw = rng.uniform(-6, 6)
            d = s.medir(escena(yaw=yaw, ancho=320, alto=240, semilla=i), 70.0)
            self.assertIsNotNone(d)
            errs.append(abs(d['pose']['dth'] - yaw))
        self.assertLess(max(errs), 4.0)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestSensibilidadALaCalibracion(unittest.TestCase):
    """Lo que más puede estropear la medición real: la distancia z depende de la focal y del tamaño impreso."""

    def medir_con(self, fov_real, fov_supuesto, lado_real=0.06):
        original = s.LADO_IMAGEN_M
        s.LADO_IMAGEN_M = lado_real * (s.CELDAS_TAG + 2 * ht.MARGEN_CELDAS) / s.CELDAS_TAG
        try:
            img = escena(fov=fov_real, t=(0.0, 0.0, 0.28))
        finally:
            s.LADO_IMAGEN_M = original
        d = ht.detectar_en(s.detector(), img, s.parametros_camara(640, 480, fov_supuesto), s.TAMANO_M)[0]['pose']
        return abs(d['z'] - 0.28) * 100   # cm

    def test_con_la_calibracion_correcta_el_error_es_minimo(self):
        self.assertLess(self.medir_con(70, 70), 0.3)

    def test_un_fov_equivocado_un_6_por_ciento_come_la_mitad_de_la_tolerancia(self):
        """Hallazgo: 66° real y 70° supuesto -> ~2 cm de error en z (la tolerancia de acople es 4 cm)."""
        self.assertGreater(self.medir_con(66, 70), 1.5)
        self.assertGreater(self.medir_con(74, 70), 1.5)

    def test_un_fov_muy_equivocado_supera_la_tolerancia(self):
        self.assertGreater(self.medir_con(60, 70), 4.0)

    def test_un_tag_impreso_con_escala_equivocada_tambien_pesa(self):
        self.assertGreater(self.medir_con(70, 70, lado_real=0.057), 1.0)   # impresora al 95 %


if __name__ == '__main__':
    unittest.main()
