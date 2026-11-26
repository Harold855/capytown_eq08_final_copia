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
import ros_falso as rf
from ros_falso import Node, Ns

try:
    import cv2
    import numpy as np
    from carrito.granprix_carrito import gestor_reset as gr
    from simulacion import apriltag_sintetico as st
    from vision import calibracion_focal as cf
    st.detector()
    HAY = True
except Exception as e:  # noqa: BLE001
    HAY, MOTIVO = False, repr(e)

ANCHO, ALTO, FOV, TAG_M = 640, 480, 63.0, 0.0595
DIST = (-0.30, 0.08, 0.0, 0.0, 0.0)
SALTAR = 'OpenCV o pupil-apriltags no disponibles (pip install -r requirements-vision.txt)'
cam = None


def setUpModule():
    global cam
    rf.instalar()
    if HAY:
        cam = importlib.import_module('carrito.nodos.camara_apriltag_node')


def tearDownModule():
    rf.desinstalar('carrito.nodos.camara_apriltag_node')


def imagen_msg(img, encoding='mono8', sec=20, nano=0):
    if encoding == 'mono8':
        data, step = img.tobytes(), img.shape[1]
    else:
        color = np.dstack([img, img, img])
        data, step = color.tobytes(), img.shape[1] * 3
    return Ns(height=img.shape[0], width=img.shape[1], encoding=encoding, step=step, data=data,
              header=Ns(stamp=Ns(sec=sec, nanosec=nano), frame_id='camera_link'))


@unittest.skipUnless(HAY, SALTAR)
class TestImagenAGris(unittest.TestCase):
    def test_mono_rgb_y_bgr_dan_la_misma_imagen_si_el_color_es_gris(self):
        g = (np.arange(48, dtype=np.uint8).reshape(6, 8) * 5)
        for enc in ('mono8', 'rgb8', 'bgr8'):
            m = imagen_msg(g, enc)
            np.testing.assert_array_equal(cam.imagen_a_gris(m.height, m.width, m.encoding, m.step, m.data), g, enc)

    def test_el_orden_de_los_canales_importa(self):
        px = np.zeros((2, 2, 3), np.uint8)
        px[..., 0] = 255                                                          # canal 0 al máximo
        rgb = cam.imagen_a_gris(2, 2, 'rgb8', 6, px.tobytes())                    # canal 0 = rojo
        bgr = cam.imagen_a_gris(2, 2, 'bgr8', 6, px.tobytes())                    # canal 0 = azul
        self.assertEqual((int(rgb[0, 0]), int(bgr[0, 0])), (76, 29))

    def test_respeta_el_step_con_relleno(self):
        g = np.arange(12, dtype=np.uint8).reshape(3, 4)
        con_relleno = np.hstack([g, np.full((3, 2), 255, np.uint8)])
        np.testing.assert_array_equal(cam.imagen_a_gris(3, 4, 'mono8', 6, con_relleno.tobytes()), g)

    def test_rechaza_lo_inconsistente(self):
        buenos = np.zeros((4, 4), np.uint8).tobytes()
        casos = [(4, 4, '16UC1', 4, buenos), (4, 4, 'bgra8', 16, buenos), (4, 4, 'mono8', 3, buenos),
                 (4, 4, 'mono8', 4, buenos[:10]), (0, 4, 'mono8', 4, buenos), (4, 4, 'rgb8', 4, buenos)]
        for caso in casos:
            with self.assertRaises(ValueError, msg=str(caso[2:4])):
                cam.imagen_a_gris(*caso)


@unittest.skipUnless(HAY, SALTAR)
class TestNodo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        F = cf.focal_desde_fov(ANCHO, FOV)
        cls.yaml_d = str(Path(cls.dir.name) / 'damero.yaml')
        cf.guardar_camara(cls.yaml_d, cf.ParametrosCamara(ANCHO, ALTO, F, F, ANCHO / 2, ALTO / 2, None, None, None, None, None,
                                                          'x', (), DIST, cf.DetalleDamero(9, 6, 0.02, 'simple', 0.1, 0.1, 20)))

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def crear(self, **p):
        Node.sobrescribe = {'camara_yaml': self.yaml_d, 'tamano_mm': 59.5, 'ventana': 1, **p}
        return cam._clase_nodo()()

    @staticmethod
    def foto(x_m=0.05, z_m=0.30, yaw=4.0, tag_id=3, semilla=1, dist=DIST):
        return st.renderizar(tag_id, st.rot_y(yaw), (x_m, 0.0, z_m), ANCHO, ALTO, FOV, desenfoque_px=0.8, ruido=3.0, semilla=semilla,
                             tamano_m=TAG_M, dist=dist)

    def test_requiere_la_calibracion(self):
        Node.sobrescribe = {}
        with self.assertRaisesRegex(ValueError, 'camara_yaml'):
            cam._clase_nodo()()
        Node.sobrescribe = {'camara_yaml': self.yaml_d}
        with self.assertRaisesRegex(Exception, 'tamano-mm'):                            # damero: no guarda el tamaño del tag
            cam._clase_nodo()()

    def test_se_suscribe_y_publica_en_los_topicos_esperados(self):
        n = self.crear(image_topic='/usb_cam/image_raw')
        self.assertEqual([t for _, t, _ in n.subs], ['/usb_cam/image_raw'])
        self.assertEqual({t for _, t, _ in n.pubs}, {'/tag/pose', '~/estado'})

    def test_una_imagen_con_tag_publica_la_pose_con_la_hora_de_captura(self):
        n = self.crear(frame_id='camara_optica')
        n.callback('/camera/image_raw')(imagen_msg(self.foto(), sec=21, nano=250))
        m = n.publicador('/tag/pose').enviados[-1]
        self.assertEqual((m.header.frame_id, m.header.stamp.sec, m.header.stamp.nanosec), ('camara_optica', 21, 250))
        self.assertAlmostEqual(m.pose.position.x, 0.05, delta=0.006)
        self.assertAlmostEqual(m.pose.position.z, 0.30, delta=0.006)
        o = m.pose.orientation
        self.assertAlmostEqual(gr.dth_de_cuaternion(o.x, o.y, o.z, o.w), 4.0, delta=2.0)

    def test_rgb_y_bgr_publican_lo_mismo_que_mono(self):
        img = self.foto()
        n = self.crear()
        for enc in ('mono8', 'rgb8', 'bgr8'):
            n.callback('/camera/image_raw')(imagen_msg(img, enc))
        z = [m.pose.position.z for m in n.publicador('/tag/pose').enviados]
        self.assertEqual(len(z), 3)
        self.assertEqual(len(set(z)), 1)

    def test_corrige_la_distorsion_antes_de_medir(self):
        n = self.crear()
        n.callback('/camera/image_raw')(imagen_msg(self.foto(x_m=0.10)))
        m = n.publicador('/tag/pose').enviados[-1]
        self.assertAlmostEqual(m.pose.position.x, 0.10, delta=0.006)                    # con distorsión y lateral de 10 cm
        yaml_sin = str(Path(self.dir.name) / 'sin_correccion.yaml')                      # misma cámara, calibración SIN distorsión
        F = cf.focal_desde_fov(ANCHO, FOV)
        cf.guardar_camara(yaml_sin, cf.parametros_desde_ajuste(cf.Ajuste(F, 0.0, 0.1, 2, (0.1,), ()), ANCHO, ALTO, TAG_M, [15, 20, 25]))
        sin = self.crear(camara_yaml=yaml_sin, tamano_mm=0.0)
        sin.callback('/camera/image_raw')(imagen_msg(self.foto(x_m=0.10)))
        m2 = sin.publicador('/tag/pose').enviados[-1]
        self.assertGreater(abs(m2.pose.position.z - 0.30), 2 * abs(m.pose.position.z - 0.30))
        self.assertGreater(abs(m2.pose.position.z - 0.30), 0.005)

    def test_sin_tag_otro_id_o_resolucion_distinta_no_publican_y_se_cuentan(self):
        n = self.crear(tag_id=5)
        cb = n.callback('/camera/image_raw')
        cb(imagen_msg(np.full((ALTO, ANCHO), 200, np.uint8)))
        cb(imagen_msg(self.foto(tag_id=3)))
        cb(imagen_msg(np.zeros((240, 320), np.uint8)))
        malo = imagen_msg(self.foto())
        malo.encoding = '16UC1'
        cb(malo)
        self.assertEqual(n.publicador('/tag/pose').enviados, [])
        self.assertEqual(n.conteo, {'sin_tag': 1, 'otro_id': 1, 'resolucion': 1, 'imagen_invalida': 1})
        n.timers[0][1]()
        self.assertEqual(json.loads(n.publicador('~/estado').enviados[-1].data)['sin_tag'], 1)

    def test_el_filtro_espera_cuadros_y_da_la_mediana(self):
        n = self.crear(ventana=3)
        cb = n.callback('/camera/image_raw')
        for k in range(2):
            cb(imagen_msg(self.foto(semilla=k)))
        self.assertEqual(n.publicador('/tag/pose').enviados, [])
        cb(imagen_msg(self.foto(semilla=2)))
        self.assertEqual(len(n.publicador('/tag/pose').enviados), 1)

    def test_calidad_baja_no_publica(self):
        n = self.crear(margen_min=500.0)
        n.callback('/camera/image_raw')(imagen_msg(self.foto()))
        self.assertEqual(n.publicador('/tag/pose').enviados, [])
        self.assertEqual(n.conteo, {'margen_bajo': 1})

    def test_la_salida_la_consume_el_nodo_de_reset(self):
        n = self.crear()
        n.callback('/camera/image_raw')(imagen_msg(self.foto(x_m=0.03, z_m=0.28, yaw=2.0)))
        m = n.publicador('/tag/pose').enviados[-1]
        o = m.pose.orientation
        dth = gr.dth_de_cuaternion(o.x, o.y, o.z, o.w)
        from carrito.granprix_carrito.gestor_reset import GestorReset
        from carrito.granprix_carrito.pose_dock import LocalizadorDock
        from carrito.granprix_carrito import transformacion_camara_dock as mc
        from geometria_dock.transformaciones import Pose2D
        g = GestorReset(LocalizadorDock(mc.Marcos(mc.Montaje(Pose2D(0.10, 0.0, 0.0), 0.0), Pose2D(0.38, 0.0, 0.0))))
        self.assertTrue(g.agregar_tag(20.0, m.pose.position.x, m.pose.position.y, m.pose.position.z, dth))


if __name__ == '__main__':
    unittest.main()
