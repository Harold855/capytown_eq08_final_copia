"""medir_tag: calidad, agregación, filtro, evidencia y línea de comandos, con una cámara sintética CONOCIDA.

Cámara 'real': 640x480, fx = fy = 522.19 (63°), distorsión k1 = -0.40, k2 = 0.10; tag impreso de 59.5 mm; la regla se
apoya en el frente de la lente (el centro óptico queda 1.8 cm detrás). Necesita OpenCV; si falta, se omite.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'camara'))
try:
    import numpy as np
    from simulacion import apriltag_sintetico as st
    from vision import calibracion_focal as cf
    from vision import medicion as md
    st.detector()
    HAY = True
except Exception as e:  # noqa: BLE001
    HAY, MOTIVO = False, repr(e)

ANCHO, ALTO, FOV = 640, 480, 63.0
TAG_M, OFFSET_M = 0.0595, 0.018
DIST = (-0.40, 0.10, 0.0, 0.0, 0.0)
SALTAR = 'OpenCV o pupil-apriltags no disponibles (pip install -r requirements-vision.txt)'


def foto(z_cm=28.0, x_m=0.0, yaw=2.0, tag_id=3, dist=DIST, semilla=1, ruido=3.0, desenfoque=0.8):
    """Tag a z_cm de la regla (z real = regla + offset) y x_m del eje, visto por la cámara con distorsión."""
    return st.renderizar(tag_id, st.rot_y(yaw), (x_m, 0.0, z_cm / 100 + OFFSET_M), ANCHO, ALTO, FOV, desenfoque_px=desenfoque,
                         ruido=ruido, semilla=semilla, tamano_m=TAG_M, dist=dist)


def med(valido=True, z=0.28, x=0.0, y=0.0, dth=0.0, id=3, motivo=None, ts=0.0):
    if valido:
        return md.Medicion(ts, True, None, id, x, y, z, dth, 100.0, 0, 1e-8)
    return md.Medicion(ts, False, motivo or 'sin_tag')


def yaml_damero(carpeta):
    F = cf.focal_desde_fov(ANCHO, FOV)
    p = cf.ParametrosCamara(ANCHO, ALTO, F, F, ANCHO / 2, ALTO / 2, None, None, None, None, None, '2026-12-03T10:00:00', (),
                            DIST, cf.DetalleDamero(9, 6, 0.02, 'simple', 0.1, 0.1, 20))
    ruta = str(Path(carpeta) / 'damero.yaml')
    cf.guardar_camara(ruta, p)
    return ruta


def yaml_regla(carpeta):
    a = cf.Ajuste(cf.focal_desde_fov(ANCHO, FOV), OFFSET_M * 100, 0.1, 2, (0.1,), ())
    ruta = str(Path(carpeta) / 'regla.yaml')
    cf.guardar_camara(ruta, cf.parametros_desde_ajuste(a, ANCHO, ALTO, TAG_M, [15, 20, 25, 30]))
    return ruta


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls.dir.name)
        cls.yaml_d, cls.yaml_r = yaml_damero(cls.base), yaml_regla(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()


@unittest.skipUnless(HAY, SALTAR)
class TestMedir(Base):
    def test_corrige_la_distorsion_fuera_del_eje(self):
        """Tag a 10 cm del eje: con la calibración de damero z sale bien; con el fov aproximado y sin corrección, no."""
        z_real = 0.28 + OFFSET_M
        buena = md.CamaraTag.desde_yaml(self.yaml_d, 59.5).medir(foto(x_m=0.10))
        self.assertTrue(buena.valido)
        self.assertAlmostEqual(buena.z_m, z_real, delta=0.005)
        self.assertAlmostEqual(buena.x_m, 0.10, delta=0.005)
        aprox = md.CamaraTag.desde_fov(ANCHO, ALTO, FOV, 59.5).medir(foto(x_m=0.10))
        self.assertGreater(abs(aprox.z_m - z_real), 0.01)                         # sin corregir: más de 1 cm

    def test_con_calibracion_de_regla_y_lente_sin_distorsion(self):
        cam = md.CamaraTag.desde_yaml(self.yaml_r)
        self.assertAlmostEqual(cam.offset_cm, 1.8, places=6)
        self.assertFalse(cam.con_distorsion_corregida)
        m = cam.medir(foto(z_cm=30.0, x_m=0.0, dist=None))
        self.assertAlmostEqual(m.z_m - OFFSET_M, 0.30, delta=0.004)

    def test_pose_valida_lleva_sus_datos_de_calidad(self):
        m = md.CamaraTag.desde_yaml(self.yaml_d, 59.5).medir(foto(), tag_id=3)
        self.assertEqual((m.valido, m.motivo, m.id, m.hamming), (True, None, 3, 0))
        self.assertGreater(m.margen, 60)
        self.assertLess(m.error_pose, 1e-5)

    def test_sin_tag_otro_id_y_varios(self):
        cam = md.CamaraTag.desde_yaml(self.yaml_d, 59.5)
        vacia = np.full((ALTO, ANCHO), 200, np.uint8)
        self.assertEqual(cam.medir(vacia).motivo, 'sin_tag')
        self.assertEqual(cam.medir(foto(tag_id=3), tag_id=4).motivo, 'otro_id')
        dos = np.minimum(foto(tag_id=1, x_m=-0.08, z_cm=40, dist=None), foto(tag_id=2, x_m=0.08, z_cm=40, dist=None))
        cam2 = md.CamaraTag.desde_fov(ANCHO, ALTO, FOV, 59.5)
        self.assertEqual(cam2.medir(dos).motivo, 'varios_tags')
        self.assertTrue(cam2.medir(dos, tag_id=2).valido)                         # con el id pedido sí se mide ese
        for m in (cam.medir(vacia), cam.medir(foto(), tag_id=4)):
            self.assertIsNone(m.x_m); self.assertIsNone(m.z_m)                    # sin pose conjeturada

    def test_poca_calidad_no_entrega_pose(self):
        cam = md.CamaraTag.desde_yaml(self.yaml_d, 59.5)
        oscura = (200 - (200 - foto(dist=DIST).astype(np.float32)) * 0.2).clip(0, 255).astype(np.uint8)   # 20 % de contraste
        m = cam.medir(oscura)
        self.assertEqual((m.valido, m.motivo), (False, 'margen_bajo'))
        self.assertLess(m.margen, 30)
        self.assertIsNone(m.z_m)
        self.assertTrue(cam.medir(oscura, criterios=md.Criterios(margen_min=0)).valido)   # bajando el umbral se mide
        self.assertEqual(cam.medir(foto(), criterios=md.Criterios(error_pose_max=1e-12)).motivo, 'error_pose')

    def test_hamming_y_sin_pose_con_detecciones_simuladas(self):
        cam = md.CamaraTag.desde_fov(ANCHO, ALTO, FOV, 59.5)
        base = {'id': 3, 'centro': [0, 0], 'esquinas': [], 'margen': 100.0, 'hamming': 1,
                'pose': {'x': 0.0, 'y': 0.0, 'z': 0.3, 'dth': 0.0, 'error': 1e-8}}
        with mock.patch.object(md.ht, 'detectar_en', return_value=[base]):
            self.assertEqual(cam.medir(foto()).motivo, 'hamming')
            self.assertTrue(cam.medir(foto(), criterios=md.Criterios(hamming_max=1)).valido)
        with mock.patch.object(md.ht, 'detectar_en', return_value=[dict(base, hamming=0, pose=None)]):
            self.assertEqual(cam.medir(foto()).motivo, 'sin_pose')

    def test_imagen_de_otra_resolucion_es_error(self):
        cam = md.CamaraTag.desde_yaml(self.yaml_d, 59.5)
        with self.assertRaisesRegex(md.ErrorMedicion, 'calibrada para 640x480'):
            cam.medir(np.zeros((240, 320), np.uint8))

    def test_tamano_del_tag(self):
        with self.assertRaisesRegex(md.ErrorMedicion, '--tamano-mm'):
            md.CamaraTag.desde_yaml(self.yaml_d)                                    # damero: no lo guarda
        with self.assertRaisesRegex(md.ErrorMedicion, 'van ligados'):
            md.CamaraTag.desde_yaml(self.yaml_r, 60.0)                              # regla se hizo con 59.5
        md.CamaraTag.desde_yaml(self.yaml_r, 59.5)                                  # el mismo: bien
        for mm in (1.0, 700.0):
            with self.assertRaises(md.ErrorMedicion):
                md.CamaraTag.desde_yaml(self.yaml_d, mm)

    def test_criterios_invalidos(self):
        for kw in ({'margen_min': -1}, {'margen_min': float('nan')}, {'hamming_max': 9}, {'error_pose_max': 0}):
            with self.assertRaises(md.ErrorMedicion):
                md.Criterios(**kw)


@unittest.skipUnless(HAY, SALTAR)
class TestAgregar(unittest.TestCase):
    def test_todos_buenos(self):
        ag = md.agregar([med(z=0.28 + 0.0005 * i, dth=0.1 * i) for i in range(10)])
        self.assertTrue(ag.aceptada)
        self.assertEqual((ag.n_cuadros, ag.n_validos, ag.id), (10, 10, 3))
        self.assertAlmostEqual(ag.z_m, 0.28 + 0.0005 * 4.5)                         # mediana
        self.assertAlmostEqual(ag.rango_z_m, 0.0045)

    def test_toleran_algunos_cuadros_invalidos_y_los_cuenta(self):
        ag = md.agregar([med()] * 8 + [med(valido=False, motivo='sin_tag')] * 2)
        self.assertTrue(ag.aceptada)
        self.assertEqual(ag.motivos_rechazo, (('sin_tag', 2),))

    def test_pocos_validos(self):
        ag = md.agregar([med()] * 6 + [med(valido=False, motivo='margen_bajo')] * 4)     # 60 % < 70 %
        self.assertEqual((ag.aceptada, ag.motivo), (False, 'pocos_cuadros_validos'))
        self.assertIsNotNone(ag.z_m)                                                      # se conserva para diagnosticar

    def test_ninguno_valido(self):
        ag = md.agregar([med(valido=False, motivo='sin_tag')] * 5)
        self.assertEqual((ag.aceptada, ag.motivo, ag.n_validos, ag.z_m), (False, 'sin_cuadros_validos', 0, None))

    def test_inestable(self):
        z = md.agregar([med(z=0.28), med(z=0.28), med(z=0.29), med(z=0.28)])               # un cuadro a 1 cm
        self.assertEqual(z.motivo, 'inestable_posicion')
        x = md.agregar([med(x=0.0), med(x=0.0), med(x=0.0), med(x=0.03)])
        self.assertEqual(x.motivo, 'inestable_posicion')
        a = md.agregar([med(dth=0.0), med(dth=0.0), med(dth=6.0), med(dth=0.0)])
        self.assertEqual(a.motivo, 'inestable_angulo')
        self.assertFalse(z.aceptada or x.aceptada or a.aceptada)

    def test_la_mediana_ignora_un_atipico_pero_el_rango_lo_delata(self):
        ag = md.agregar([med(z=0.28)] * 9 + [med(z=0.40)])
        self.assertAlmostEqual(ag.z_m, 0.28)
        self.assertFalse(ag.aceptada)                                                      # no se acepta sin mirar

    def test_ids_distintos(self):
        self.assertEqual(md.agregar([med(id=1), med(id=2), med(id=1)]).motivo, 'ids_distintos')

    def test_vacio(self):
        with self.assertRaises(md.ErrorMedicion):
            md.agregar([])

    def test_umbrales_ajustables(self):
        meds = [med(z=0.28), med(z=0.28), med(z=0.29)]
        self.assertFalse(md.agregar(meds).aceptada)
        self.assertTrue(md.agregar(meds, disp_pos_m=0.02).aceptada)


@unittest.skipUnless(HAY, SALTAR)
class TestFiltro(unittest.TestCase):
    def test_mediana_movil_y_arranque(self):
        f = md.FiltroMediana(ventana=3)
        self.assertIsNone(f.agregar(med(z=0.30)))
        self.assertIsNone(f.agregar(med(z=0.28)))
        self.assertAlmostEqual(f.agregar(med(z=0.29))['z_m'], 0.29)
        self.assertAlmostEqual(f.agregar(med(z=0.50))['z_m'], 0.29)                        # el atípico no mueve la mediana
        self.assertEqual(f.agregar(med(z=0.28))['n'], 3.0)

    def test_un_cuadro_invalido_no_borra_pero_varios_seguidos_si(self):
        f = md.FiltroMediana(ventana=5)
        for _ in range(4):
            f.agregar(med())
        self.assertIsNotNone(f.agregar(med(valido=False)))
        self.assertIsNotNone(f.agregar(med()))
        for _ in range(4):
            r = f.agregar(med(valido=False))
        self.assertIsNotNone(r)
        self.assertIsNone(f.agregar(med(valido=False)))                                   # 5 seguidos: olvida; no hay pose vieja
        self.assertIsNone(f.agregar(med()))

    def test_ventana_invalida(self):
        for v in (0, 101):
            with self.assertRaises(md.ErrorMedicion):
                md.FiltroMediana(v)


@unittest.skipUnless(HAY, SALTAR)
class TestEvidencia(Base):
    def setUp(self):
        self.csv = str(self.base / f'ev_{self._testMethodName}.csv')
        self.cam = md.CamaraTag.desde_yaml(self.yaml_r)

    def agregado(self, z_cm=30.0, dth=0.0, x_cm=0.0, aceptada=True, **kw):
        return md.Agregado(aceptada, None if aceptada else 'inestable_posicion', 10, 10, 3, x_cm / 100, 0.0, z_cm / 100, dth,
                           0.001, 0.001, 0.002, 0.5, **kw)

    def test_calcula_errores_y_resta_el_desfase_de_la_regla(self):
        fila = md.registrar_comparacion(self.csv, self.agregado(z_cm=31.9, dth=1.0, x_cm=0.4), md.Esperado(30.0, 0.0, 0.0), self.cam)
        self.assertEqual(fila['offset_cm'], '1.80')                                       # tomado de la calibración
        self.assertAlmostEqual(float(fila['err_z_cm']), 0.1, places=3)                    # 31.9 - 1.8 - 30
        self.assertAlmostEqual(float(fila['err_x_cm']), 0.4, places=3)
        self.assertAlmostEqual(float(fila['err_dth_deg']), 1.0, places=2)

    def test_offset_manual_y_sin_desfase(self):
        cam = md.CamaraTag.desde_yaml(self.yaml_d, 59.5)                                   # el damero no trae offset
        sin = md.registrar_comparacion(self.csv, self.agregado(z_cm=31.8), md.Esperado(30.0), cam)
        self.assertEqual(sin['offset_cm'], '')
        self.assertAlmostEqual(float(sin['err_z_cm']), 1.8, places=3)                      # incluye el desfase
        con = md.registrar_comparacion(self.csv, self.agregado(z_cm=31.8), md.Esperado(30.0), cam, offset_cm=1.8)
        self.assertAlmostEqual(float(con['err_z_cm']), 0.0, places=3)

    def test_se_guardan_tambien_las_no_aceptadas(self):
        md.registrar_comparacion(self.csv, self.agregado(aceptada=False), md.Esperado(30.0), self.cam, observaciones='luz baja')
        with open(self.csv, encoding='utf-8') as f:
            filas = f.read().splitlines()
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0].split(',')[0], 'fecha')
        self.assertIn('inestable_posicion', filas[1]); self.assertIn('luz baja', filas[1])

    def test_valores_esperados_invalidos(self):
        for args in ((0.28,), (200.0,), (30.0, 80.0), (30.0, 0.0, 120.0), (float('nan'),)):
            with self.assertRaises(md.ErrorMedicion, msg=str(args)):
                md.Esperado(*args)

    def test_observaciones_con_comas_y_csv_ajeno(self):
        with self.assertRaises(md.ErrorMedicion):
            md.registrar_comparacion(self.csv, self.agregado(), md.Esperado(30.0), self.cam, observaciones='a,b')
        ajeno = self.base / 'ajeno.csv'
        ajeno.write_text('a,b,c\n1,2,3\n', encoding='utf-8')
        with self.assertRaisesRegex(md.ErrorMedicion, 'otras columnas'):
            md.registrar_comparacion(str(ajeno), self.agregado(), md.Esperado(30.0), self.cam)

    def test_resumen(self):
        for z, dth in ((30.2, 0.3), (29.9, -0.5), (30.4, 0.8), (29.6, 1.0)):
            md.registrar_comparacion(self.csv, self.agregado(z_cm=z + 1.8, dth=dth), md.Esperado(30.0, 0.0, 0.0), self.cam)
        md.registrar_comparacion(self.csv, self.agregado(z_cm=40.0, aceptada=False), md.Esperado(30.0, 0.0, 0.0), self.cam)
        r = md.resumen(self.csv)
        self.assertEqual((r.n_filas, r.n_aceptadas), (5, 4))                                # la no aceptada no cuenta
        self.assertAlmostEqual(r.errores['err_z_cm']['max_abs'], 0.4, places=3)
        self.assertAlmostEqual(r.errores['err_dth_deg']['max_abs'], 1.0, places=2)
        self.assertTrue(r.cumple)
        self.assertFalse(md.resumen(self.csv, tol_cm=0.3).cumple)
        self.assertFalse(md.resumen(self.csv, tol_deg=0.5).cumple)
        texto = md.informe_resumen(r)
        self.assertIn('CUMPLE', texto); self.assertIn('solo 4 mediciones aceptadas', texto)

    def test_resumen_sin_aceptadas_o_con_archivo_malo(self):
        md.registrar_comparacion(self.csv, self.agregado(aceptada=False), md.Esperado(30.0), self.cam)
        self.assertFalse(md.resumen(self.csv).cumple)
        with self.assertRaises(md.ErrorMedicion):
            md.resumen(str(self.base / 'no_existe.csv'))
        malo = self.base / 'malo.csv'
        malo.write_text('x,y\n1,2\n', encoding='utf-8')
        with self.assertRaises(md.ErrorMedicion):
            md.resumen(str(malo))
        with self.assertRaises(md.ErrorMedicion):
            md.resumen(self.csv, tol_cm=0)


class CamaraFalsa:
    def __init__(self, frames, abierta=True, muere_tras=None):
        self.frames, self.i, self.abierta, self.muere_tras, self.liberada, self.lecturas = frames, 0, abierta, muere_tras, False, 0

    def isOpened(self):
        return self.abierta

    def read(self):
        self.lecturas += 1
        if self.muere_tras is not None and self.lecturas > self.muere_tras:
            return False, None
        f = self.frames[self.i % len(self.frames)]
        self.i += 1
        return True, f

    def release(self):
        self.liberada = True


@unittest.skipUnless(HAY, SALTAR)
class TestFuentes(Base):
    def test_descarta_los_primeros_y_libera(self):
        cam = CamaraFalsa([np.full((4, 4), i, np.uint8) for i in range(10)])
        gen = md.fotogramas_camara(lambda: cam, descartar=3)
        self.assertEqual(int(next(gen)[0, 0]), 3)
        gen.close()
        self.assertTrue(cam.liberada)

    def test_camara_que_no_abre_o_muere(self):
        with self.assertRaisesRegex(md.ErrorMedicion, 'no se pudo abrir'):
            next(md.fotogramas_camara(lambda: CamaraFalsa([], abierta=False)))
        gen = md.fotogramas_camara(lambda: CamaraFalsa([np.zeros((4, 4), np.uint8)], muere_tras=5), descartar=3)
        next(gen); next(gen)
        with self.assertRaisesRegex(md.ErrorMedicion, 'dejó de entregar'):
            next(gen)

    def test_imagen_y_video(self):
        ruta = self.base / 'f.png'
        st.ht.guardar_png(ruta, foto())
        self.assertEqual(next(md.fotogramas_imagen(str(ruta))).shape[:2], (ALTO, ANCHO))
        with self.assertRaises(st.ht.ErrorHerramienta):
            next(md.fotogramas_imagen(str(self.base / 'no.png')))
        with self.assertRaises(md.ErrorMedicion):
            next(md.fotogramas_video(str(self.base / 'no.avi')))
        import cv2
        video = str(self.base / 'v.avi')
        w = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 5.0, (ANCHO, ALTO))
        if not w.isOpened():
            self.skipTest('este OpenCV no escribe MJPG')
        for i in range(4):
            w.write(cv2.cvtColor(foto(semilla=i), cv2.COLOR_GRAY2BGR))
        w.release()
        self.assertEqual(len(list(md.fotogramas_video(video))), 4)


@unittest.skipUnless(HAY, SALTAR)
class TestCli(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.frames = [foto(x_m=0.10, semilla=i) for i in range(4)]
        cls.vacios = [np.full((ALTO, ANCHO), 200, np.uint8)]

    def cli(self, *args, frames=None, **kw):
        import importlib
        import medir_tag
        importlib.reload(medir_tag)
        cam = CamaraFalsa(frames if frames is not None else self.frames)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = medir_tag.main(list(args), abrir_camara=lambda: cam)
        return rc, out.getvalue(), err.getvalue(), cam

    def test_una_medicion_aceptada(self):
        rc, out, err, cam = self.cli('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--tag-id', '3', '--cuadros', '4')
        d = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertTrue(d['aceptada'] and d['calibrada'] and d['distorsion_corregida'])
        self.assertAlmostEqual(d['z_m'], 0.28 + OFFSET_M, delta=0.006)
        self.assertAlmostEqual(d['x_m'], 0.10, delta=0.006)
        self.assertEqual((d['n_cuadros'], d['n_validos']), (4, 4))
        self.assertTrue(cam.liberada)
        self.assertNotIn('SIN calibrar', err)

    def test_no_aceptada_no_entrega_pose(self):
        rc, out, _, _ = self.cli('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--cuadros', '3', frames=self.vacios)
        d = json.loads(out)
        self.assertEqual(rc, 2)
        self.assertEqual((d['aceptada'], d['motivo'], d['z_m'], d['x_m'], d['dth_deg']), (False, 'sin_cuadros_validos', None, None, None))
        self.assertEqual(d['rechazos'], {'sin_tag': 3})

    def test_sin_calibrar_avisa(self):
        rc, out, err, _ = self.cli('una', '--fov-h', '63', '--tamano-mm', '59.5', '--cuadros', '2')
        self.assertIn('SIN calibrar', err)
        self.assertFalse(json.loads(out)['calibrada'])

    def test_continuo_con_filtro(self):
        rc, out, err, cam = self.cli('continuo', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--ventana', '3', '--max-cuadros', '5')
        filas = [json.loads(l) for l in out.splitlines()]
        self.assertEqual((rc, len(filas)), (0, 5))
        self.assertTrue(all(f['valido'] for f in filas))
        self.assertIsNone(filas[0]['filtrada']); self.assertIsNone(filas[1]['filtrada'])
        self.assertAlmostEqual(filas[4]['filtrada']['x_m'], 0.10, delta=0.006)
        self.assertIn('5 de 5 cuadros válidos', err)
        self.assertTrue(cam.liberada)

    def test_continuo_sin_ver_el_tag_sale_con_2(self):
        rc, out, _, _ = self.cli('continuo', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--max-cuadros', '3', frames=self.vacios)
        self.assertEqual(rc, 2)
        self.assertTrue(all(json.loads(l)['motivo'] == 'sin_tag' for l in out.splitlines()))

    def test_comparar_guarda_evidencia_y_resumen_la_evalua(self):
        csv_ = str(self.base / 'ev_cli.csv')
        base = ['comparar', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--cuadros', '3', '--esperado-z-cm', '28',
                '--esperado-x-cm', '10', '--esperado-dth', '2', '--offset-cm', '1.8', '--csv', csv_]
        rc, out, err, _ = self.cli(*base, '--observaciones', 'lado derecho')
        d = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertLess(abs(d['errores']['err_z_cm']), 0.6)
        self.assertLess(abs(d['errores']['err_x_cm']), 0.6)
        self.assertLess(abs(d['errores']['err_dth_deg']), 2.0)
        self.cli(*base)
        self.cli(*base, frames=self.vacios)                                              # una no aceptada: también se guarda
        rc, out, _, _ = self.cli('resumen', '--csv', csv_)
        self.assertEqual(rc, 0)
        self.assertIn('3 mediciones, 2 aceptadas (1 no aceptadas', out)
        rc, out, _, _ = self.cli('resumen', '--csv', csv_, '--tol-cm', '0.0001')
        self.assertEqual(rc, 2)

    def test_comparar_sin_offset_avisa(self):
        rc, _, err, _ = self.cli('comparar', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--cuadros', '2',
                                 '--esperado-z-cm', '28', '--csv', str(self.base / 'ev_sin.csv'))
        self.assertIn('sin desfase de la regla', err)

    def test_una_imagen_de_archivo(self):
        ruta = self.base / 'una.png'
        st.ht.guardar_png(ruta, foto(x_m=0.0))
        rc, out, _, _ = self.cli('una', '--imagen', str(ruta), '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5')
        d = json.loads(out)
        self.assertEqual((rc, d['n_cuadros']), (0, 1))

    def test_errores_dan_codigo_1(self):
        casos = [('una',),                                                                                           # sin cámara
                 ('una', '--camara-yaml', self.yaml_d),                                                              # damero sin tamaño
                 ('una', '--camara-yaml', self.yaml_r, '--tamano-mm', '60'),                                         # tamaño distinto
                 ('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--fov-h', '63'),                      # ambos
                 ('una', '--camara-yaml', str(self.base / 'no.yaml'), '--tamano-mm', '59.5'),
                 ('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--cuadros', '0'),
                 ('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--margen-min', '-3'),
                 ('comparar', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', '--esperado-z-cm', '0.28',
                  '--csv', str(self.base / 'x.csv')),                                                                # metros por cm
                 ('resumen', '--csv', str(self.base / 'no_hay.csv'))]
        for args in casos:
            rc, _, err, _ = self.cli(*args)
            self.assertEqual(rc, 1, f'{args}: {err}')
            self.assertIn('error:', err)

    def test_resolucion_distinta_a_la_calibracion(self):
        rc, _, err, _ = self.cli('una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5', frames=[np.zeros((240, 320), np.uint8)])
        self.assertEqual(rc, 1)
        self.assertIn('320x240', err)

    def test_camara_que_no_abre(self):
        import importlib
        import medir_tag
        importlib.reload(medir_tag)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = medir_tag.main(['una', '--camara-yaml', self.yaml_d, '--tamano-mm', '59.5'],
                                abrir_camara=lambda: CamaraFalsa([], abierta=False))
        self.assertEqual(rc, 1)
        self.assertIn('no se pudo abrir la cámara', err.getvalue())


if __name__ == '__main__':
    unittest.main()
