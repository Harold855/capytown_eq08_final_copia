"""Calibración con damero de extremo a extremo con una cámara sintética de parámetros y distorsión CONOCIDOS.

Cámara 'real': 640x480, fx = fy = 522.19 (63°), punto principal en el centro, distorsión k1 = -0.30, k2 = 0.08.
Necesita OpenCV; si falta, se omite.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import cv2
    import numpy as np
    from simulacion import apriltag_sintetico as st
    from simulacion import damero_sintetico as ds
    from vision import calibracion_damero as dm
    from vision import calibracion_focal as cf
    from vision import calibrar as cal
    from vision import herramienta as hv
    HAY = True
except Exception as e:  # noqa: BLE001
    HAY, MOTIVO = False, repr(e)

ANCHO, ALTO = 640, 480
F = 522.19
K = np.array([[F, 0, ANCHO / 2], [0, F, ALTO / 2], [0, 0, 1.0]]) if HAY else None
DIST = (-0.30, 0.08, 0.0, 0.0, 0.0)
PATRON = dm.Patron(9, 6, 0.02) if HAY else None
SALTAR = 'OpenCV no disponible (pip install -r requirements-vision.txt)'


def fotos(n, semilla, dist=DIST, **kw):
    poses = ds.poses_aleatorias(n, PATRON, K, ANCHO, ALTO, semilla=semilla)
    return poses, [(f'{i:02d}.png', ds.renderizar(PATRON, rv, tv, K, dist, ANCHO, ALTO, semilla=semilla * 100 + i, **kw))
                   for i, (rv, tv) in enumerate(poses)]


def guardar(carpeta, imgs):
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    for nombre, img in imgs:
        dm.ht.guardar_png(Path(carpeta) / nombre, img)


@unittest.skipUnless(HAY, SALTAR)
class TestPatronYDamero(unittest.TestCase):
    def test_patron_invalido(self):
        for args in ((2, 6, 0.02), (9, 60, 0.02), (6, 6, 0.02), (9, 6, 0.0), (9, 6, 1.0), (9, 6, float('nan'))):
            with self.assertRaises(cf.ErrorCalibracion, msg=str(args)):
                dm.Patron(*args)

    def test_el_damero_que_se_imprime_se_detecta(self):
        for cols, filas in ((9, 6), (7, 5)):
            p = dm.Patron(cols, filas, 0.025)
            e = dm.encontrar_esquinas(dm.imagen_damero(p), p)
            self.assertIsNotNone(e)
            self.assertEqual(len(e), cols * filas)

    def test_el_svg_tiene_tamano_real(self):
        svg = dm.svg_damero(dm.Patron(9, 6, 0.025))
        self.assertIn('width="300.000mm"', svg)           # (9 + 1 cuadros + 2 de margen) * 25 mm
        self.assertIn('height="225.000mm"', svg)          # (6 + 1 cuadros + 2 de margen) * 25 mm
        self.assertEqual(svg.count('<rect x='), 35)       # 10 x 7 = 70 cuadros alternados: 35 negros

    def test_orientacion_invertida_no_se_detecta(self):
        e = dm.encontrar_esquinas(dm.imagen_damero(PATRON), dm.Patron(6, 9, 0.02))
        self.assertTrue(e is None or len(e) == 54)


@unittest.skipUnless(HAY, SALTAR)
class TestCalibrar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.poses, cls.imgs = fotos(20, 1)
        cls.esq, cls.nom, cls.sin, cls.w, cls.h = dm._detectar_todas(cls.imgs, PATRON)
        cls.res = dm.calibrar(cls.esq, cls.nom, PATRON, cls.w, cls.h, 'simple', cls.sin)

    def test_recupera_la_camara(self):
        p = self.res.parametros
        self.assertAlmostEqual(p.fx / F, 1.0, delta=0.01)
        self.assertAlmostEqual(p.cx, ANCHO / 2, delta=2.0)
        self.assertAlmostEqual(p.cy, ALTO / 2, delta=2.0)
        self.assertAlmostEqual(p.distorsion[0], -0.30, delta=0.02)
        self.assertAlmostEqual(p.distorsion[1], 0.08, delta=0.05)
        self.assertEqual(p.distorsion[2:], (0.0, 0.0, 0.0))                   # modelo simple: sin tangencial ni k3
        self.assertLess(p.damero.rms_px, 0.3)
        self.assertLess(p.damero.rms_validacion_px, 0.3)
        self.assertEqual(p.metodo, 'damero')

    def test_cuantifica_cuanto_distorsiona(self):
        self.assertGreater(self.res.desplazamiento_esquina_px, 30.0)          # k1 = -0.3 mueve la esquina decenas de px
        self.assertNotIn('regla ya bastaba', dm.informe(self.res))

    def test_con_poca_distorsion_lo_dice(self):
        _, imgs = fotos(15, 4, dist=(-0.004, 0.0, 0, 0, 0))
        esq, nom, sin, w, h = dm._detectar_todas(imgs, PATRON)
        r = dm.calibrar(esq, nom, PATRON, w, h)
        self.assertLess(r.desplazamiento_esquina_px, dm.DESPLAZAMIENTO_DESPRECIABLE_PX)
        self.assertIn('regla ya bastaba', dm.informe(r))

    def test_modelo_completo_recupera_tambien_la_tangencial(self):
        d = (-0.25, 0.05, 0.002, -0.001, 0.0)
        _, imgs = fotos(25, 6, dist=d)
        esq, nom, sin, w, h = dm._detectar_todas(imgs, PATRON)
        r = dm.calibrar(esq, nom, PATRON, w, h, 'completo', sin)
        p = r.parametros
        self.assertAlmostEqual(p.fx / F, 1.0, delta=0.02)
        self.assertAlmostEqual(p.distorsion[2], 0.002, delta=0.002)
        self.assertAlmostEqual(p.distorsion[3], -0.001, delta=0.002)
        self.assertLess(p.damero.rms_px, 0.3)

    def test_una_imagen_con_esquinas_mal_localizadas_se_descarta(self):
        mala = [e.copy() for e in self.esq]
        mala[3] = mala[3] + np.random.default_rng(0).normal(0, 4.0, mala[3].shape).astype(np.float32)
        r = dm.calibrar(mala, self.nom, PATRON, self.w, self.h)
        self.assertIn(self.nom[3], r.descartadas)
        self.assertEqual(r.parametros.damero.n_imagenes, len(self.esq) - len(r.descartadas))
        self.assertAlmostEqual(r.parametros.fx / F, 1.0, delta=0.01)
        self.assertTrue(any('descartada' in a for a in r.parametros.advertencias))
        # control: sin rechazo, esa sola imagen estropea la calibración
        _, K0, D0, _, _ = dm._calibrar_cv(mala, PATRON, self.w, self.h, 'simple')
        self.assertGreater(abs(K0[0, 0] / F - 1.0), 0.01)

    def test_no_descarta_mas_de_un_cuarto(self):
        mala = [e + np.random.default_rng(i).normal(0, 4.0, e.shape).astype(np.float32) if i % 2 == 0 else e
                for i, e in enumerate(self.esq)]
        try:
            r = dm.calibrar(mala, self.nom, PATRON, self.w, self.h)
            self.assertLessEqual(len(r.descartadas), 5)
        except cf.ErrorCalibracion as e:
            self.assertIn('reproyección', str(e))      # con la mitad de las imágenes mal, rechaza el conjunto

    def test_ruido_excesivo_en_todas_las_imagenes_falla(self):
        ruido = [e + np.random.default_rng(i).normal(0, 3.0, e.shape).astype(np.float32) for i, e in enumerate(self.esq)]
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'reproyección'):
            dm.calibrar(ruido, self.nom, PATRON, self.w, self.h)

    def test_pocas_imagenes(self):
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'al menos 10'):
            dm.calibrar(self.esq[:9], self.nom[:9], PATRON, self.w, self.h)

    def test_pocas_pero_suficientes_avisa(self):
        r = dm.calibrar(self.esq[:12], self.nom[:12], PATRON, self.w, self.h)
        self.assertTrue(any(a.startswith('solo ') and 'imágenes (<' in a for a in r.parametros.advertencias))
        self.assertIsNone(r.parametros.damero.rms_validacion_px)                  # sin validación cruzada con < 15

    def test_damero_siempre_de_frente_no_determina_la_focal(self):
        _, imgs = fotos(14, 8)                                                     # inclinación hasta 40°...
        poses = ds.poses_aleatorias(14, PATRON, K, ANCHO, ALTO, semilla=8, inclinacion_max_deg=6.0)
        frente = [(f'{i}.png', ds.renderizar(PATRON, rv, tv, K, DIST, ANCHO, ALTO, semilla=i)) for i, (rv, tv) in enumerate(poses)]
        esq, nom, sin, w, h = dm._detectar_todas(frente, PATRON)
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'inclinado'):
            dm.calibrar(esq, nom, PATRON, w, h)

    def test_cobertura_pobre_avisa_y_dice_donde_falta(self):
        rng = np.random.default_rng(3)
        imgs = []
        for i in range(14):                                                        # siempre en el centro del cuadro
            ang = np.radians(rng.uniform(18, 35)); eje = np.array([1.0, 0, 0]) if i % 2 else np.array([0, 1.0, 0])
            rv = eje * ang * (1 if i % 4 < 2 else -1)
            R, _ = cv2.Rodrigues(rv)
            tv = np.array([0, 0, 0.45]) - R @ np.array([(PATRON.cols - 1) * 0.01, (PATRON.filas - 1) * 0.01, 0])
            imgs.append((f'{i}.png', ds.renderizar(PATRON, rv, tv, K, DIST, ANCHO, ALTO, semilla=i)))
        esq, nom, sin, w, h = dm._detectar_todas(imgs, PATRON)
        r = dm.calibrar(esq, nom, PATRON, w, h)
        self.assertLess(r.celdas_cubiertas, dm.COBERTURA_AVISO_CELDAS)
        aviso = [a for a in r.parametros.advertencias if 'zonas' in a][0]
        self.assertIn('arriba-izquierda', aviso)

    def test_modelo_desconocido(self):
        with self.assertRaises(cf.ErrorCalibracion):
            dm.calibrar(self.esq, self.nom, PATRON, self.w, self.h, 'magico')


@unittest.skipUnless(HAY, SALTAR)
class TestCarpetaYArchivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls.dir.name)
        cls.poses, cls.imgs = fotos(20, 1)
        guardar(cls.base / 'cal', cls.imgs)
        cls.res = dm.calcular(cls.base / 'cal', PATRON)
        cls.yaml = str(cls.base / 'camara.yaml')
        cf.guardar_camara(cls.yaml, cls.res.parametros)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_calcular_desde_carpeta_y_recargar(self):
        q = cf.cargar_camara(self.yaml)
        self.assertEqual(q.distorsion, self.res.parametros.distorsion)
        self.assertAlmostEqual(q.fx / F, 1.0, delta=0.01)

    def test_imagenes_sin_damero_solo_avisan(self):
        d = self.base / 'con_basura'
        guardar(d, self.imgs + [('zz_vacia.png', np.full((ALTO, ANCHO), 120, np.uint8))])
        r = dm.calcular(d, PATRON)
        self.assertEqual(r.sin_damero, ('zz_vacia.png',))
        self.assertTrue(any('sin damero' in a for a in r.parametros.advertencias))

    def test_carpeta_vacia_ausente_o_tamanos_mezclados(self):
        (self.base / 'vacia').mkdir()
        for ruta in (self.base / 'vacia', self.base / 'no_existe'):
            with self.assertRaises(cf.ErrorCalibracion):
                dm.calcular(ruta, PATRON)
        d = self.base / 'mezcla'
        guardar(d, self.imgs[:12] + [('chica.png', np.full((240, 320), 120, np.uint8))])
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'tamaños distintos'):
            dm.calcular(d, PATRON)

    def test_patron_equivocado_dice_que_revise_cols_y_filas(self):
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'INTERIORES'):
            dm.calcular(self.base / 'cal', dm.Patron(11, 8, 0.02))

    def test_validar_con_imagenes_nuevas(self):
        _, nuevas = fotos(8, 50)
        guardar(self.base / 'val', nuevas)
        v = dm.validar(self.yaml, self.base / 'val')
        self.assertTrue(v.ok, dm.informe_validacion(v))
        self.assertLess(v.rms_px, 0.4)

    def test_validar_detecta_una_distorsion_mal_calibrada(self):
        _, nuevas = fotos(8, 50)
        guardar(self.base / 'val3', nuevas)
        p = self.res.parametros
        sin_dist = cf.ParametrosCamara(p.ancho, p.alto, p.fx, p.fy, p.cx, p.cy, None, None, None, None, None, 'x', (),
                                       (0.0, 0.0, 0.0, 0.0, 0.0), p.damero)
        ruta = str(self.base / 'sin_dist.yaml')
        cf.guardar_camara(ruta, sin_dist)
        v = dm.validar(ruta, self.base / 'val3')
        self.assertFalse(v.ok, dm.informe_validacion(v))                 # k1 = -0.3 ignorada: 0.89 px > 0.7 px
        self.assertGreater(v.rms_px, 0.7)

    def test_validar_NO_detecta_un_error_de_escala_de_la_focal(self):
        """Limitación real: un 10 % de error en la focal casi no cambia la reproyección (se compensa con la
        distancia estimada). Por eso el informe dice que la escala se valida con distancias medidas."""
        _, nuevas = fotos(8, 50)
        guardar(self.base / 'val4', nuevas)
        p = self.res.parametros
        mala = cf.ParametrosCamara(p.ancho, p.alto, p.fx * 1.1, p.fy * 1.1, p.cx, p.cy, None, None, None, None, None, 'x',
                                   (), p.distorsion, p.damero)
        ruta = str(self.base / 'focal_mala.yaml')
        cf.guardar_camara(ruta, mala)
        v = dm.validar(ruta, self.base / 'val4')
        self.assertTrue(v.ok, dm.informe_validacion(v))
        self.assertIn('NO la escala', dm.informe_validacion(v))

    def test_validar_rechaza_otra_resolucion_y_metodo_regla(self):
        _, nuevas = fotos(8, 50)
        guardar(self.base / 'val2', nuevas)
        guardar(self.base / 'chicas', [(f'{i}.png', np.full((240, 320), 120, np.uint8)) for i in range(2)])
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'son 320x240'):
            dm.validar(self.yaml, self.base / 'chicas')
        regla = cf.parametros_desde_ajuste(cf.Ajuste(F, 1.8, 0.1, 2, (0.1,), ()), ANCHO, ALTO, 0.0595, [15, 20, 25])
        ruta_regla = str(self.base / 'regla.yaml')
        cf.guardar_camara(ruta_regla, regla)
        with self.assertRaisesRegex(cf.ErrorCalibracion, "método 'regla'"):
            dm.validar(ruta_regla, self.base / 'val2')


@unittest.skipUnless(HAY, SALTAR)
class TestCorrector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, imgs = fotos(20, 1)
        esq, nom, sin, w, h = dm._detectar_todas(imgs, PATRON)
        cls.cam = dm.calibrar(esq, nom, PATRON, w, h).parametros

    def test_la_imagen_corregida_coincide_con_la_ideal(self):
        rv, tv = ds.poses_aleatorias(1, PATRON, K, ANCHO, ALTO, semilla=77)[0]
        ideal = ds.renderizar(PATRON, rv, tv, K, (0, 0, 0, 0, 0), ANCHO, ALTO, ruido=0, desenfoque_px=0)
        distorsionada = ds.renderizar(PATRON, rv, tv, K, DIST, ANCHO, ALTO, ruido=0, desenfoque_px=0)
        corregida = hv.Corrector(self.cam)(distorsionada)
        e_ideal = dm.encontrar_esquinas(ideal, PATRON).reshape(-1, 2)
        e_dist = dm.encontrar_esquinas(distorsionada, PATRON).reshape(-1, 2)
        e_corr = dm.encontrar_esquinas(corregida, PATRON).reshape(-1, 2)
        self.assertGreater(np.linalg.norm(e_dist - e_ideal, axis=1).max(), 5.0)     # distorsionada: lejos
        self.assertLess(np.linalg.norm(e_corr - e_ideal, axis=1).max(), 0.6)        # corregida: a medio píxel

    def test_sin_distorsion_devuelve_la_misma_imagen_y_valida_el_tamano(self):
        regla = cf.parametros_desde_ajuste(cf.Ajuste(F, 1.8, 0.1, 2, (0.1,), ()), ANCHO, ALTO, 0.0595, [15, 20, 25])
        img = np.zeros((ALTO, ANCHO), np.uint8)
        self.assertIs(hv.Corrector(regla)(img), img)
        with self.assertRaisesRegex(ValueError, 'imagen es 320x240'):
            hv.Corrector(self.cam)(np.zeros((240, 320), np.uint8))

    def test_pose_tag_calibrada_pide_el_tamano_si_es_de_damero(self):
        img = np.zeros((ALTO, ANCHO), np.uint8)
        with self.assertRaisesRegex(ValueError, 'tamaño del tag'):
            hv.pose_tag_calibrada(img, self.cam)
        self.assertIsNone(hv.pose_tag_calibrada(img, self.cam, tamano_m=0.0595))      # imagen vacía: sin tag, sin error


@unittest.skipUnless(HAY, SALTAR)
class TestCierreConElTag(unittest.TestCase):
    """Lo que importa: el error de z fuera del eje que el método de la regla no corrige, baja con el damero."""
    TAG_M, OFFSET_M = 0.0595, 0.018
    DISTORSION = (-0.40, 0.10, 0.0, 0.0, 0.0)

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.base = Path(cls.dir.name)
        _, imgs = fotos(20, 2, dist=cls.DISTORSION)
        guardar(cls.base / 'cal', imgs)
        cls.yaml_damero = str(cls.base / 'damero.yaml')
        cf.guardar_camara(cls.yaml_damero, dm.calcular(cls.base / 'cal', PATRON).parametros)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def foto_tag(self, dist_regla_cm, lateral_m, semilla):
        t = (lateral_m, 0.0, dist_regla_cm / 100 + self.OFFSET_M)
        return st.renderizar(3, st.rot_y(2.0), t, ANCHO, ALTO, 63.0, desenfoque_px=0.8, ruido=3.0, semilla=semilla,
                             tamano_m=self.TAG_M, dist=self.DISTORSION)

    def csv_validacion(self, nombre):
        carpeta = self.base / nombre
        (carpeta / 'imagenes').mkdir(parents=True)
        filas = ['imagen,distancia_cm,posicion']
        for pos, x in (('centro', 0.0), ('izq', -0.10), ('der', 0.10)):
            for i, d in enumerate((20, 30)):
                n = f'imagenes/{pos}_{d}.png'
                st.ht.guardar_png(carpeta / n, self.foto_tag(d, x, 10 * i + len(pos)))
                filas.append(f'{n},{d},{pos}')
        (carpeta / 'c.csv').write_text('\n'.join(filas) + '\n', encoding='utf-8')
        return carpeta / 'c.csv'

    def test_el_damero_corrige_el_error_fuera_del_eje(self):
        csv_ = self.csv_validacion('v1')
        # 1) con el método de la regla (sin corregir distorsión) la validación falla a los lados
        regla_csv = self.base / 'regla' / 'c.csv'
        (self.base / 'regla' / 'imagenes').mkdir(parents=True)
        filas = ['imagen,distancia_cm,posicion']
        for i, d in enumerate((15, 20, 25, 30, 35, 40)):
            n = f'imagenes/r{d}.png'
            st.ht.guardar_png(self.base / 'regla' / n, self.foto_tag(d, 0.0, 200 + i))
            filas.append(f'{n},{d},centro')
        regla_csv.write_text('\n'.join(filas) + '\n', encoding='utf-8')
        yaml_regla = str(self.base / 'regla.yaml')
        cf.guardar_camara(yaml_regla, cal.calcular(regla_csv, 59.5).parametros)
        v_regla = cal.validar(yaml_regla, csv_)
        self.assertFalse(v_regla.ok, cal.informe_validacion(v_regla))
        self.assertGreater(v_regla.max_error_cm, 1.0)
        # 2) con la calibración de damero (corrige la distorsión) cumple en todo el cuadro
        v = cal.validar(self.yaml_damero, csv_, tamano_mm=59.5)
        self.assertTrue(v.ok, cal.informe_validacion(v))
        self.assertLess(v.max_error_cm, 0.7)
        self.assertTrue(v.corregida)
        self.assertTrue(v.offset_estimado)
        self.assertAlmostEqual(v.offset_cm, self.OFFSET_M * 100, delta=0.5)         # recupera el offset de la regla
        self.assertEqual({f[1] for f in v.filas}, {'centro', 'izq', 'der'})

    def test_desde_la_linea_de_comandos_con_el_yaml_del_damero(self):
        sys.path.insert(0, str(RAIZ / 'scripts' / 'camara'))
        import importlib
        import calibrar_focal
        importlib.reload(calibrar_focal)
        csv_ = self.csv_validacion('v3')
        base = ['validar', '--camara-yaml', self.yaml_damero, '--csv', str(csv_)]
        self.assertEqual(calibrar_focal.main(base + ['--tamano-mm', '59.5']), 0)
        self.assertEqual(calibrar_focal.main(base), 1)                          # el damero no guarda el tamaño del tag

    def test_con_damero_hace_falta_el_tamano_del_tag(self):
        csv_ = self.csv_validacion('v2')
        with self.assertRaisesRegex(cf.ErrorCalibracion, '--tamano-mm'):
            cal.validar(self.yaml_damero, csv_)
        for mm in (0.0, 1000.0, float('nan')):
            with self.assertRaises(cf.ErrorCalibracion):
                cal.validar(self.yaml_damero, csv_, tamano_mm=mm)


class CamaraDamero:
    """Reproduce una secuencia de fotogramas: por cada pose, algunos fotogramas quietos y otros movidos."""
    def __init__(self, frames, abierta=True):
        self.frames, self.i, self.abierta, self.liberada = frames, 0, abierta, False

    def isOpened(self):
        return self.abierta

    def read(self):
        if self.i >= len(self.frames):
            return False, None
        f = self.frames[self.i]
        self.i += 1
        return True, f

    def release(self):
        self.liberada = True


@unittest.skipUnless(HAY, SALTAR)
class TestCapturar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.poses = ds.poses_aleatorias(14, PATRON, K, ANCHO, ALTO, semilla=9)
        cls.quieto = [[ds.renderizar(PATRON, rv, tv, K, DIST, ANCHO, ALTO, semilla=10 * i + j) for j in range(3)]
                      for i, (rv, tv) in enumerate(cls.poses)]
        cls.movido = [ds.renderizar(PATRON, rv, tv + np.array([0.01, 0.0, 0]), K, DIST, ANCHO, ALTO, semilla=999 + i)
                      for i, (rv, tv) in enumerate(cls.poses)]
        cls.vacio = np.full((ALTO, ANCHO), 120, np.uint8)

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.d = Path(self.dir.name)
        self.t = [0.0]
        self.msgs = []

    def correr(self, frames, **kw):
        cam = CamaraDamero(frames)

        def dormir(s):
            self.t[0] += s
        r = dm.capturar(lambda: cam, PATRON, self.d, escribir=self.msgs.append, dormir=dormir, reloj=lambda: self.t[0], **kw)
        return r, cam

    def secuencia(self, indices):
        out = []
        for i in indices:
            out += [self.movido[i], self.quieto[i][0], self.quieto[i][1], self.quieto[i][2], self.vacio]
        return out

    def test_guarda_solo_poses_quietas_y_nuevas(self):
        frames = self.secuencia(range(12))
        r, cam = self.correr(frames, objetivo=12)
        self.assertEqual(len(r), 12)
        self.assertTrue(cam.liberada)
        self.assertEqual(sorted(p.name for p in r), [f'damero_{i:02d}.png' for i in range(12)])
        self.assertTrue(any('resolución de captura: 640x480' in m for m in self.msgs))
        calib = dm.calcular(self.d, PATRON)                               # lo capturado sirve para calibrar
        self.assertAlmostEqual(calib.parametros.fx / F, 1.0, delta=0.02)

    def test_no_guarda_la_misma_pose_dos_veces(self):
        frames = self.secuencia(range(12)) + self.secuencia(range(12))     # se repite todo
        r, _ = self.correr(frames, objetivo=10)
        self.assertEqual(len(r), 10)
        n = len(list(self.d.glob('damero_*.png')))
        self.assertEqual(n, 10)

    def test_no_guarda_si_se_mueve_o_no_se_ve(self):
        frames = [self.movido[0], self.vacio, self.movido[1], self.vacio, self.movido[2]] * 60
        r, _ = self.correr(frames, objetivo=10, max_s=5.0)
        self.assertEqual(r, [])
        self.assertTrue(any('tiempo agotado' in m for m in self.msgs))

    def test_tiempo_agotado_avisa_y_conserva_lo_guardado(self):
        r, _ = self.correr(self.secuencia(range(12)) * 3, objetivo=12, max_s=3.0, intervalo_s=0.2)
        self.assertLess(len(r), 12)
        self.assertTrue(any('tiempo agotado' in m for m in self.msgs))

    def test_la_camara_muere_o_no_abre(self):
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'dejó de entregar'):
            self.correr(self.secuencia(range(2)), objetivo=10, max_s=1000)
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'no se pudo abrir'):
            dm.capturar(lambda: CamaraDamero([], abierta=False), PATRON, self.d, escribir=print)

    def test_objetivo_invalido(self):
        for o in (0, 5, 500):
            with self.assertRaises(cf.ErrorCalibracion):
                self.correr([], objetivo=o)

    def test_los_nombres_continuan_si_ya_hay_imagenes(self):
        self.correr(self.secuencia(range(10)), objetivo=10)
        r, _ = self.correr(self.secuencia(range(10, 14)) + self.secuencia(range(6)), objetivo=10)
        self.assertEqual(sorted(p.name for p in r), [f'damero_{i:02d}.png' for i in range(10, 20)])
        self.assertEqual(len(list(self.d.glob('damero_*.png'))), 20)


@unittest.skipUnless(HAY, SALTAR)
class TestCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.d = Path(self.dir.name)
        sys.path.insert(0, str(RAIZ / 'scripts' / 'camara'))
        import importlib
        import calibrar_damero
        importlib.reload(calibrar_damero)
        self.cli = calibrar_damero.main

    def test_crear_calcular_validar_y_no_sobrescribir(self):
        self.assertEqual(self.cli(['crear', '--cols', '9', '--filas', '6', '--cuadro-mm', '20', '--salida', str(self.d / 'imp')]), 0)
        self.assertEqual(sorted(p.suffix for p in (self.d / 'imp').iterdir()), ['.png', '.svg'])
        _, imgs = fotos(16, 1)
        guardar(self.d / 'cal', imgs)
        args = ['calcular', '--imagenes', str(self.d / 'cal'), '--cuadro-mm', '20']
        self.assertEqual(self.cli(args), 0)
        yaml_ = self.d / 'cal' / 'camara_calibrada.yaml'
        self.assertTrue(yaml_.is_file())
        self.assertEqual(self.cli(args), 1)                                # no pisa
        self.assertEqual(self.cli(args + ['--sobrescribir']), 0)
        _, nuevas = fotos(6, 60)
        guardar(self.d / 'val', nuevas)
        self.assertEqual(self.cli(['validar', '--camara-yaml', str(yaml_), '--imagenes', str(self.d / 'val')]), 0)
        self.assertEqual(self.cli(['validar', '--camara-yaml', str(yaml_), '--imagenes', str(self.d / 'val'),
                                   '--tolerancia-px', '0.0001']), 2)

    def test_errores_dan_codigo_1(self):
        self.assertEqual(self.cli(['calcular', '--imagenes', str(self.d / 'no_existe')]), 1)
        self.assertEqual(self.cli(['validar', '--camara-yaml', str(self.d / 'no.yaml'), '--imagenes', str(self.d)]), 1)
        self.assertEqual(self.cli(['crear', '--cols', '6', '--filas', '6', '--salida', str(self.d / 'x')]), 1)   # cuadrado


if __name__ == '__main__':
    unittest.main()
