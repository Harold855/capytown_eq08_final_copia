"""Matemática y archivo de la calibración de focal. No necesita OpenCV."""
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun.yaml_estricto import ErrorYaml
from vision import calibracion_focal as cf

ANCHO, ALTO = 640, 480
F_REAL = cf.focal_desde_fov(ANCHO, 63.0)


def modelo(f_real=F_REAL, offset=1.8, ruido=0.0):
    """z estimada con la focal supuesta f: proporcional a f / f_real (cámara pin-hole)."""
    def z_est(distancias):
        def inner(f):
            return [(f / f_real) * (d + offset) + ruido * ((-1) ** i) for i, d in enumerate(distancias)]
        return inner
    return z_est


class TestRegresion(unittest.TestCase):
    def test_recta_exacta(self):
        k, b, rms = cf.regresion([1, 2, 3, 4], [3, 5, 7, 9])
        self.assertAlmostEqual(k, 2); self.assertAlmostEqual(b, 1); self.assertAlmostEqual(rms, 0, places=9)

    def test_sin_variacion_en_x(self):
        with self.assertRaises(cf.ErrorCalibracion):
            cf.regresion([5, 5, 5], [1, 2, 3])


class TestAjuste(unittest.TestCase):
    D = [15, 20, 25, 30, 35, 40]

    def ajustar(self, d=None, f0=None, **kw):
        d = d or self.D
        return cf.ajustar_focal(d, modelo(**kw)(d), f0 or cf.focal_desde_fov(ANCHO, 70.0), ANCHO)

    def test_recupera_la_focal_y_el_offset(self):
        a = self.ajustar()
        self.assertAlmostEqual(a.f_px, F_REAL, delta=0.01)
        self.assertAlmostEqual(a.offset_cm, 1.8, delta=0.001)
        self.assertLess(a.rms_cm, 1e-6)
        self.assertEqual(a.advertencias, ())

    def test_no_depende_del_punto_de_partida(self):
        for fov in (40.0, 70.0, 110.0):
            self.assertAlmostEqual(self.ajustar(f0=cf.focal_desde_fov(ANCHO, fov)).f_px, F_REAL, delta=0.01, msg=str(fov))

    def test_ruido_pequeno_da_resultado_cercano(self):
        a = self.ajustar(ruido=0.1)
        self.assertAlmostEqual(a.f_px / F_REAL, 1.0, delta=0.01)
        self.assertAlmostEqual(a.offset_cm, 1.8, delta=0.3)

    def test_offset_negativo_y_cero(self):
        self.assertAlmostEqual(self.ajustar(offset=-1.0).offset_cm, -1.0, delta=0.001)
        self.assertAlmostEqual(self.ajustar(offset=0.0).offset_cm, 0.0, delta=0.001)

    def test_pocas_distancias_o_rango_corto_o_invalidas(self):
        for d in ([20, 30], [20, 20, 20], [20, 22, 24, 26], [20, 30, 40, float('nan')], [20, 30, -40], []):
            with self.assertRaises(cf.ErrorCalibracion, msg=str(d)):
                cf.ajustar_focal(d, modelo()(d) if len(d) and all(math.isfinite(v) and v > 0 for v in d) else (lambda f: []),
                                 500.0, ANCHO)

    def test_rango_corto_pero_valido_da_aviso(self):
        a = self.ajustar(d=[20, 24, 28, 32])      # 12 cm: resoluble pero poco determinado
        self.assertTrue(any('rango' in x for x in a.advertencias))

    def test_mediciones_incoherentes_no_se_aceptan(self):
        d = self.D
        z = modelo()(d)

        def mala(f):
            v = z(f)
            v[3] += 8.0 * (f / F_REAL)          # un punto con la regla mal leída por 8 cm
            return v
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'error de'):
            cf.ajustar_focal(d, mala, 500.0, ANCHO)

    def test_z_que_no_crece_con_la_regla_falla(self):
        with self.assertRaises(cf.ErrorCalibracion):
            cf.ajustar_focal(self.D, lambda f: [30, 28, 26, 24, 22, 20], 500.0, ANCHO)

    def test_offset_enorme_y_fov_absurdo_dan_aviso(self):
        a = self.ajustar(offset=9.0)
        self.assertTrue(any('offset' in x for x in a.advertencias))
        a = self.ajustar(f_real=cf.focal_desde_fov(ANCHO, 30.0))
        self.assertTrue(any('campo de visión' in x for x in a.advertencias))

    def test_el_tamano_del_tag_sesga_la_focal_uno_a_uno(self):
        """Dar un tag 1 % más grande que el real hace que la focal salga 1 % más chica: hay que medirlo bien."""
        d = self.D
        z_real = modelo()(d)
        # con el tamaño dado L' = 1.01 L, z_est se multiplica por 1.01
        a = cf.ajustar_focal(d, lambda f: [1.01 * v for v in z_real(f)], 500.0, ANCHO)
        self.assertAlmostEqual(a.f_px / F_REAL, 1 / 1.01, delta=1e-6)


class TestFovYFocal(unittest.TestCase):
    def test_ida_y_vuelta(self):
        for fov in (45.0, 63.0, 90.0, 120.0):
            self.assertAlmostEqual(cf.fov_desde_focal(640, cf.focal_desde_fov(640, fov)), fov, places=9)

    def test_fov_invalido(self):
        for fov in (0.0, 180.0, -5.0):
            with self.assertRaises(ValueError):
                cf.focal_desde_fov(640, fov)


class TestArchivo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.ruta = os.path.join(self.dir.name, 'camara.yaml')
        a = cf.Ajuste(F_REAL, 1.8, 0.12, 2, (0.1, -0.1), ('aviso de prueba',))
        self.p = cf.parametros_desde_ajuste(a, ANCHO, ALTO, 0.0595, [15, 20, 25, 25], '2026-12-03T10:00:00')

    def escribir(self, texto):
        with open(self.ruta, 'w', encoding='utf-8') as f:
            f.write(texto)

    def test_ida_y_vuelta(self):
        cf.guardar_camara(self.ruta, self.p)
        q = cf.cargar_camara(self.ruta)
        self.assertEqual((q.ancho, q.alto, q.tamano_tag_m, q.n_distancias, q.rango_cm), (640, 480, 0.0595, 3, (15.0, 25.0)))
        self.assertAlmostEqual(q.fx, F_REAL); self.assertEqual(q.cx, 320); self.assertEqual(q.cy, 240)
        self.assertEqual(q.advertencias, ('aviso de prueba',))
        self.assertAlmostEqual(q.fov_h_deg, 63.0, places=2)
        self.assertEqual(q.tupla(), (q.fx, q.fy, 320.0, 240.0))
        self.assertEqual(os.listdir(self.dir.name), ['camara.yaml'])

    def test_el_archivo_no_lleva_secretos_y_es_legible(self):
        cf.guardar_camara(self.ruta, self.p)
        with open(self.ruta, encoding='utf-8') as f:
            texto = f.read()
        self.assertTrue(texto.startswith('# Calibración de la cámara'))
        self.assertIn('SIN distorsión', texto)

    def test_valores_dudosos_fallan_cerrado(self):
        cf.guardar_camara(self.ruta, self.p)
        with open(self.ruta, encoding='utf-8') as f:
            base = f.read()
        cambios = {
            'fx negativa': ('fx: ', 'fx: -'), 'versión 2': ('version: 1', 'version: 2'),
            'tag de 5 m': ('tamano_m: 0.0595', 'tamano_m: 5.0'), 'método distinto': ('metodo: regla', 'metodo: damero'),
            'clave desconocida': ('version: 1', 'version: 1\ndistorsion: 0.1'),
            'clave duplicada': ('version: 1', 'version: 1\nimagen: {ancho: 1, alto: 1}'),
            'cx fuera de la imagen': ('cx: 320.0', 'cx: 900.0'), 'ancho decimal': ('ancho: 640', 'ancho: 640.5'),
            'rango con un solo valor': ('rango_cm:\n  - 15\n  - 25', 'rango_cm:\n  - 15'),
        }
        for nombre, (a, b) in cambios.items():
            self.assertIn(a, base, nombre)
            self.escribir(base.replace(a, b, 1))
            with self.assertRaises(ValueError, msg=nombre):
                cf.cargar_camara(self.ruta)
        with self.assertRaises(ErrorYaml):
            cf.cargar_camara(os.path.join(self.dir.name, 'no_existe.yaml'))


class TestArchivoDamero(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.ruta = os.path.join(self.dir.name, 'camara.yaml')
        self.p = cf.ParametrosCamara(640, 480, 520.0, 520.0, 322.0, 238.0, None, None, None, None, None,
                                     '2026-12-03T11:00:00', ('aviso',), (-0.3, 0.08, 0.0, 0.0, 0.0),
                                     cf.DetalleDamero(9, 6, 0.025, 'simple', 0.12, 0.2, 20))

    def escribir(self, texto):
        with open(self.ruta, 'w', encoding='utf-8') as f:
            f.write(texto)

    def test_ida_y_vuelta(self):
        cf.guardar_camara(self.ruta, self.p)
        q = cf.cargar_camara(self.ruta)
        self.assertEqual(q.metodo, 'damero')
        self.assertEqual((q.fx, q.cx, q.cy, q.distorsion), (520.0, 322.0, 238.0, (-0.3, 0.08, 0.0, 0.0, 0.0)))
        self.assertEqual(q.damero, self.p.damero)
        self.assertIsNone(q.tamano_tag_m); self.assertIsNone(q.offset_cm)
        self.assertEqual(q.advertencias, ('aviso',))
        self.assertEqual(os.listdir(self.dir.name), ['camara.yaml'])

    def test_sin_validacion_cruzada(self):
        sin = cf.ParametrosCamara(*[getattr(self.p, f) for f in ('ancho', 'alto', 'fx', 'fy', 'cx', 'cy', 'tamano_tag_m',
                                                                  'offset_cm', 'rms_cm', 'n_distancias', 'rango_cm', 'fecha',
                                                                  'advertencias', 'distorsion')],
                                  cf.DetalleDamero(9, 6, 0.025, 'completo', 0.3, None, 12))
        cf.guardar_camara(self.ruta, sin)
        self.assertIsNone(cf.cargar_camara(self.ruta).damero.rms_validacion_px)

    def test_el_archivo_de_regla_sigue_funcionando_y_no_se_mezclan(self):
        regla = cf.parametros_desde_ajuste(cf.Ajuste(F_REAL, 1.8, 0.1, 2, (0.1,), ()), ANCHO, ALTO, 0.0595, [15, 20, 25])
        cf.guardar_camara(self.ruta, regla)
        self.assertEqual(cf.cargar_camara(self.ruta).metodo, 'regla')
        self.assertIsNone(cf.cargar_camara(self.ruta).distorsion)
        with open(self.ruta, encoding='utf-8') as f:
            base = f.read()
        self.escribir(base + 'distorsion: {k1: 0.1, k2: 0, p1: 0, p2: 0, k3: 0}\n')
        with self.assertRaisesRegex(ErrorYaml, 'no admite'):                      # regla + distorsión
            cf.cargar_camara(self.ruta)

    def test_damero_con_tag_o_sin_distorsion_falla(self):
        cf.guardar_camara(self.ruta, self.p)
        with open(self.ruta, encoding='utf-8') as f:
            base = f.read()
        self.escribir(base + 'tag: {tamano_m: 0.06}\n')
        with self.assertRaisesRegex(ErrorYaml, 'no lleva'):
            cf.cargar_camara(self.ruta)
        sin = base[:base.index('distorsion:')] + base[base.index('ajuste:'):]
        self.escribir(sin)
        with self.assertRaisesRegex(ErrorYaml, 'requiere'):
            cf.cargar_camara(self.ruta)

    def test_valores_dudosos_fallan_cerrado(self):
        cf.guardar_camara(self.ruta, self.p)
        with open(self.ruta, encoding='utf-8') as f:
            base = f.read()
        cambios = {
            'k1 absurdo': ('k1: -0.3', 'k1: -9.0'), 'p1 enorme': ('p1: 0.0', 'p1: 0.5'), 'k2 texto': ('k2: 0.08', 'k2: "0.08"'),
            'k3 nan': ('k3: 0.0', 'k3: .nan'), 'modelo desconocido': ('modelo: simple', 'modelo: raro'),
            'patrón cuadrado de 2': ('cols: 9', 'cols: 2'), 'cuadro de 1 m': ('cuadro_m: 0.025', 'cuadro_m: 1.0'),
            'clave de distorsión desconocida': ('k1:', 'k0:'), 'rms negativo': ('rms_px: 0.12', 'rms_px: -1'),
            'imágenes decimal': ('n_imagenes: 20', 'n_imagenes: 20.5'), 'método desconocido': ('metodo: damero', 'metodo: magia'),
        }
        for nombre, (a, b) in cambios.items():
            self.assertIn(a, base, nombre)
            self.escribir(base.replace(a, b, 1))
            with self.assertRaises(ValueError, msg=nombre):
                cf.cargar_camara(self.ruta)


if __name__ == '__main__':
    unittest.main()
