"""Calibración de focal de extremo a extremo con una cámara sintética de parámetros CONOCIDOS.

Cámara 'real': 640x480, campo de visión 63°, tag impreso de 59.5 mm, regla apoyada en el frente de la lente
(el centro óptico queda 1.8 cm detrás). El procedimiento debe recuperar esos valores. Necesita OpenCV y
pupil-apriltags; si faltan, se omite.
"""
import math
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
try:
    import numpy as np
    from simulacion import apriltag_sintetico as s
    from vision import calibrar as cal
    from vision import calibracion_focal as cf
    s.detector()
    HAY = True
except Exception as e:  # noqa: BLE001
    HAY, MOTIVO = False, repr(e)

FOV_REAL, TAG_REAL_M, OFFSET_M = 63.0, 0.0595, 0.018
ANCHO, ALTO = 640, 480


def imagen(distancia_regla_cm, semilla, tag_id=3, yaw=2.0, fov=FOV_REAL, x=None, k1=0.0):
    """Foto del tag con el 'robot' real: z verdadera = regla + offset. `x`: desplazamiento lateral del tag (m)."""
    rng = np.random.default_rng(semilla)
    lateral = rng.uniform(-0.01, 0.01) if x is None else x
    t = (lateral, rng.uniform(-0.01, 0.01), distancia_regla_cm / 100 + OFFSET_M)
    return s.renderizar(tag_id, s.rot_y(yaw + rng.uniform(-2, 2)), t, ANCHO, ALTO, fov, desenfoque_px=0.8, ruido=3.0,
                        semilla=int(rng.integers(1 << 30)), tamano_m=TAG_REAL_M, k1=k1)


def escribir_capturas(carpeta, distancias, cuadros=1, semilla0=0, lectura_regla=None, posicion='centro', x=None,
                      k1=0.0, anexar=False):
    """Guarda las imágenes y el CSV. `lectura_regla` simula el error de lectura de la regla (cm)."""
    (Path(carpeta) / 'imagenes').mkdir(exist_ok=True)
    filas = [] if anexar else ['imagen,distancia_cm,posicion']
    for i, d in enumerate(distancias):
        for k in range(cuadros):
            nombre = f'imagenes/d{d:g}_{posicion}_{k}.png'
            s.ht.guardar_png(Path(carpeta) / nombre, imagen(d, semilla0 + 10 * i + k, x=x, k1=k1))
            leida = d + (lectura_regla[i] if lectura_regla else 0.0)
            filas.append(f'{nombre},{leida:g},{posicion}')
    csv_ = Path(carpeta) / 'capturas.csv'
    with open(csv_, 'a' if anexar else 'w', encoding='utf-8') as f:
        f.write('\n'.join(filas) + '\n')
    return csv_


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.d = Path(self.dir.name)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles (pip install -r requirements-vision.txt)')
class TestCalcular(Base):
    F_REAL = cf.focal_desde_fov(ANCHO, FOV_REAL)

    def test_recupera_focal_y_offset(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], cuadros=3)
        r = cal.calcular(csv_, 59.5)
        self.assertAlmostEqual(r.parametros.fx / self.F_REAL, 1.0, delta=0.01)
        self.assertAlmostEqual(r.parametros.fov_h_deg, FOV_REAL, delta=1.0)
        self.assertAlmostEqual(r.ajuste.offset_cm, OFFSET_M * 100, delta=0.4)
        self.assertLess(r.ajuste.rms_cm, 0.3)
        self.assertEqual((r.parametros.ancho, r.parametros.alto, r.n_imagenes), (640, 480, 18))
        self.assertEqual(r.ajuste.advertencias, ())

    def test_el_resultado_se_guarda_y_se_recarga(self):
        r = cal.calcular(escribir_capturas(self.d, [15, 20, 25, 30, 35, 40]), 59.5)
        ruta = str(self.d / 'camara_calibrada.yaml')
        cf.guardar_camara(ruta, r.parametros)
        self.assertEqual(cf.cargar_camara(ruta).tupla(), r.parametros.tupla())
        self.assertIn('--fx', cal.comando_herramienta(r.parametros))

    def test_un_tamano_de_tag_mal_medido_sesga_la_focal_en_la_misma_proporcion(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40])
        bueno = cal.calcular(csv_, 59.5).parametros.fx
        malo = cal.calcular(csv_, 60.0).parametros.fx      # se dio el nominal en vez del medido
        self.assertAlmostEqual(malo / bueno, 59.5 / 60.0, delta=0.002)

    def test_la_calibracion_mejora_z_frente_a_suponer_un_fov(self):
        """Con el fov supuesto de 70° la z sale mal; con la focal ajustada, bien (validado con distancias NUEVAS)."""
        r = cal.calcular(escribir_capturas(self.d, [15, 20, 25, 30, 35, 40]), 59.5)
        cam = self.d / 'camara_calibrada.yaml'
        cf.guardar_camara(str(cam), r.parametros)
        nueva = self.d / 'val'
        nueva.mkdir()
        csv_val = escribir_capturas(nueva, [17, 22, 27, 33, 38], semilla0=500)
        v = cal.validar(str(cam), csv_val)
        self.assertTrue(v.ok, cal.informe_validacion(v))
        self.assertLess(v.max_error_cm, 0.6)
        # contraste: sin calibrar (fov 70° supuesto, sin offset)
        caps = cal.cargar_capturas(cal.leer_csv(csv_val))
        grupos, _ = cal.medir_grupos(caps, (cf.focal_desde_fov(ANCHO, 70.0),) * 2 + (320.0, 240.0), 0.0595, None)
        sin = max(abs(np.median([z for z, _ in g]) - d) for (d, _), g in grupos.items())
        self.assertGreater(sin, 2.0)

    def test_una_lectura_de_regla_muy_equivocada_se_rechaza(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], lectura_regla=[0, 0, 0, 8.0, 0, 0])
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'error de'):
            cal.calcular(csv_, 59.5)

    def test_errores_pequenos_de_regla_se_toleran(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], lectura_regla=[0.1, -0.1, 0.1, -0.1, 0.1, -0.1])
        r = cal.calcular(csv_, 59.5)
        self.assertAlmostEqual(r.parametros.fx / self.F_REAL, 1.0, delta=0.02)

    def test_distancias_insuficientes(self):
        with self.assertRaises(cf.ErrorCalibracion):
            cal.calcular(escribir_capturas(self.d, [25, 30]), 59.5)
        with self.assertRaises(cf.ErrorCalibracion):
            cal.calcular(escribir_capturas(self.d, [25, 25.0, 25]), 59.5)

    def test_si_a_una_distancia_no_se_ve_el_tag_lo_dice(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30])
        for k in range(3):
            s.ht.guardar_png(self.d / 'imagenes' / f'd30_centro_{k}.png', np.full((ALTO, ANCHO), 200, np.uint8))
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'a 30 cm no se detectó'):
            cal.calcular(csv_, 59.5)

    def test_imagenes_sin_tag_en_otras_distancias_solo_avisan(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], cuadros=2)   # 2 cuadros: uno sin tag no anula la distancia
        s.ht.guardar_png(self.d / 'imagenes' / 'd25_centro_0.png', np.full((ALTO, ANCHO), 200, np.uint8))
        r = cal.calcular(csv_, 59.5)
        self.assertEqual(r.sin_tag, ('d25_centro_0.png',))
        self.assertTrue(any('sin tag' in a for a in r.ajuste.advertencias))

    def test_tag_muy_inclinado_da_aviso(self):
        (self.d / 'imagenes').mkdir()
        filas = ['imagen,distancia_cm']
        for i, d in enumerate([15, 20, 25, 30, 35, 40]):
            nombre = f'imagenes/d{d}.png'
            s.ht.guardar_png(self.d / nombre, imagen(d, i, yaw=35.0))
            filas.append(f'{nombre},{d}')
        (self.d / 'capturas.csv').write_text('\n'.join(filas) + '\n', encoding='utf-8')
        r = cal.calcular(self.d / 'capturas.csv', 59.5)
        self.assertTrue(any('girado' in a for a in r.ajuste.advertencias))

    def test_las_capturas_laterales_no_entran_al_ajuste_y_se_avisa(self):
        escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], cuadros=2)
        csv_ = escribir_capturas(self.d, [20, 30], posicion='izq', x=-0.06, semilla0=700, anexar=True)
        r = cal.calcular(csv_, 59.5)
        self.assertEqual(r.n_imagenes, 12)                      # solo las centradas
        self.assertTrue(any('posición distinta de centro' in a for a in r.ajuste.advertencias))
        self.assertAlmostEqual(r.parametros.fx / self.F_REAL, 1.0, delta=0.01)

    def test_sin_capturas_centradas_falla(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30], posicion='izq', x=-0.05)
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'centro'):
            cal.calcular(csv_, 59.5)

    def test_tamano_de_tag_absurdo(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30], cuadros=1)
        for mm in (0.0, 4.0, 600.0, float('nan'), 0.06):   # 0.06 = metros dados como milímetros
            with self.assertRaises(cf.ErrorCalibracion, msg=str(mm)):
                cal.calcular(csv_, mm)

    def test_imagenes_de_tamanos_distintos(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30], cuadros=1)
        s.ht.guardar_png(self.d / 'imagenes' / 'd20_centro_0.png', np.full((240, 320), 200, np.uint8))
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'tamaños distintos'):
            cal.calcular(csv_, 59.5)

    def test_validar_rechaza_otra_resolucion_y_calibracion_mala(self):
        r = cal.calcular(escribir_capturas(self.d, [15, 20, 25, 30, 35, 40]), 59.5)
        cam = r.parametros
        malo = cf.ParametrosCamara(cam.ancho, cam.alto, cf.focal_desde_fov(ANCHO, 70.0), cf.focal_desde_fov(ANCHO, 70.0),
                                   cam.cx, cam.cy, cam.tamano_tag_m, 0.0, 0.0, 6, cam.rango_cm, 'x')
        ruta = self.d / 'mala.yaml'
        cf.guardar_camara(str(ruta), malo)
        nueva = self.d / 'val'
        nueva.mkdir()
        csv_val = escribir_capturas(nueva, [17, 27, 37], semilla0=900)
        v = cal.validar(str(ruta), csv_val)
        self.assertFalse(v.ok)                                   # fov supuesto de 70° y sin offset: no cumple
        otra = cf.ParametrosCamara(320, 240, cam.fx / 2, cam.fy / 2, 160.0, 120.0, cam.tamano_tag_m, 0.0, 0.0, 6,
                                   cam.rango_cm, 'x')
        cf.guardar_camara(str(ruta), otra)
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'resolución'):
            cal.validar(str(ruta), csv_val)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestFueraDeEje(Base):
    """La distorsión del lente no cambia la focal ajustada ni el residuo, pero aparece fuera del eje."""

    def calibrar(self, k1):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40], k1=k1)
        cam = self.d / 'camara.yaml'
        cf.guardar_camara(str(cam), cal.calcular(csv_, 59.5).parametros)
        return cam

    def validar(self, cam, k1, x, posicion):
        carpeta = self.d / f'val_{posicion}'
        carpeta.mkdir()
        return cal.validar(str(cam), escribir_capturas(carpeta, [20, 30], posicion=posicion, x=x, k1=k1, semilla0=800),
                           tolerancia_cm=1.0)

    def test_lente_sin_distorsion_cumple_en_todo_el_cuadro(self):
        cam = self.calibrar(0.0)
        for pos, x in (('centro', 0.0), ('izq', -0.10), ('der', 0.10)):
            v = self.validar(cam, 0.0, x, pos)
            self.assertTrue(v.ok, f'{pos}: {cal.informe_validacion(v)}')

    def test_lente_con_barril_cumple_en_el_centro_pero_no_a_los_lados(self):
        cam = self.calibrar(-0.4)
        self.assertTrue(self.validar(cam, -0.4, 0.0, 'centro').ok)            # el centro NO delata la distorsión
        lado = self.validar(cam, -0.4, 0.10, 'der')
        self.assertFalse(lado.ok, cal.informe_validacion(lado))              # el lado sí
        self.assertGreater(lado.max_error_cm, 1.0)

    def test_validar_separa_las_posiciones_y_avisa_si_solo_hay_centro(self):
        cam = self.calibrar(0.0)
        solo = self.validar(cam, 0.0, 0.0, 'centro')
        self.assertIn('solo hay capturas centradas', cal.informe_validacion(solo))
        csv_ = escribir_capturas(self.d, [20], posicion='centro', semilla0=40)
        escribir_capturas(self.d, [20], posicion='der', x=0.06, semilla0=41, anexar=True)
        v = cal.validar(str(cam), csv_)
        self.assertEqual({f[1] for f in v.filas}, {'centro', 'der'})
        self.assertNotIn('solo hay capturas centradas', cal.informe_validacion(v))


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestCsv(Base):
    def escribir(self, texto, con_imagen=True):
        if con_imagen:
            (self.d / 'a.png').write_bytes(b'x')
        (self.d / 'c.csv').write_text(texto, encoding='utf-8')
        return self.d / 'c.csv'

    def test_valido(self):
        self.assertEqual(cal.leer_csv(self.escribir('imagen,distancia_cm\na.png,25.5\n'))[0][1:], (25.5, 'centro'))   # formato antiguo
        self.assertEqual(cal.leer_csv(self.escribir('imagen,distancia_cm,posicion\na.png,25.5, IZQ \n'))[0][1:], (25.5, 'izq'))
        self.assertEqual(cal.leer_csv(self.escribir('imagen,distancia_cm,posicion\na.png,25.5,\n'))[0][2], 'centro')

    def test_malos(self):
        casos = ['imagen,metros\na.png,0.25\n', 'imagen,distancia_cm\na.png,abc\n', 'imagen,distancia_cm\na.png,0.25\n',
                 'imagen,distancia_cm\na.png,500\n', 'imagen,distancia_cm\na.png,nan\n', 'imagen,distancia_cm\n',
                 'imagen,distancia_cm\nno_existe.png,25\n', 'imagen,distancia_cm\na.png,25,extra\n', '',
                 'imagen,distancia_cm,posicion\na.png,25\n', 'imagen,posicion,distancia_cm\na.png,centro,25\n']
        for texto in casos:
            with self.assertRaises(cf.ErrorCalibracion, msg=repr(texto)):
                cal.leer_csv(self.escribir(texto))
        with self.assertRaises(cf.ErrorCalibracion):
            cal.leer_csv(self.d / 'no_hay.csv')


class CamaraFalsa:
    """Cámara que 've' el tag a la distancia que indique la persona al responder el aviso."""
    def __init__(self, estado):
        self.e = estado
        self.liberada = False

    def isOpened(self):
        return self.e.get('abierta', True)

    def read(self):
        if self.e.get('muerta'):
            return False, None
        if self.e['oculto'] > 0:
            self.e['oculto'] -= 1          # el tag vuelve a verse tras N cuadros
            return True, np.full((ALTO, ANCHO), 200, np.uint8)
        self.e['n'] += 1
        return True, imagen(self.e['d'], self.e['n'])

    def release(self):
        self.liberada = True


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestCapturar(Base):
    def correr(self, distancias, estado=None, respuestas=None, **kw):
        estado = estado if estado is not None else {}
        estado.setdefault('oculto', 0); estado.setdefault('n', 0); estado.setdefault('d', 0)
        cam = CamaraFalsa(estado)
        mensajes, avisos = [], iter(respuestas) if respuestas else None

        def entrada(prompt):
            m = re.search(r'a ([\d.]+) cm', prompt)
            estado['d'] = float(m.group(1))
            if avisos is not None:
                return next(avisos)
            return ''
        r = cal.capturar(lambda: cam, distancias, self.d, leer_entrada=entrada, escribir=mensajes.append,
                         dormir=lambda s_: None, **kw)
        return r, cam, mensajes

    def test_toma_guiada_completa_y_se_puede_calcular(self):
        r, cam, msgs = self.correr([15, 20, 25, 30, 35, 40], cuadros=3, descartar=1)
        self.assertTrue(cam.liberada)
        self.assertTrue(any('resolución de captura: 640x480' in m for m in msgs))
        filas = cal.leer_csv(r)
        self.assertEqual(len(filas), 18)
        self.assertEqual(sorted({f[1] for f in filas}), [15, 20, 25, 30, 35, 40])
        res = cal.calcular(r, 59.5)
        self.assertAlmostEqual(res.parametros.fx / cf.focal_desde_fov(ANCHO, FOV_REAL), 1.0, delta=0.01)

    def test_reintenta_si_no_se_ve_el_tag(self):
        estado = {'oculto': 5}                 # los primeros 5 cuadros no ven el tag
        r, cam, msgs = self.correr([20], estado, cuadros=3, descartar=1)
        self.assertTrue(any('se necesitan al menos' in m for m in msgs))
        self.assertEqual(len(cal.leer_csv(r)), 3)

    def test_falla_tras_los_intentos(self):
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'no se vio el tag'):
            self.correr([20], {'oculto': 10 ** 6}, cuadros=3, descartar=1, intentos=2)

    def test_q_termina_conservando_lo_capturado(self):
        r, cam, _ = self.correr([15, 20, 25], respuestas=['', 'q'], cuadros=2, descartar=0)
        self.assertEqual(sorted({f[1] for f in cal.leer_csv(r)}), [15])
        self.assertTrue(cam.liberada)

    def test_camara_que_no_abre_o_muere(self):
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'no se pudo abrir'):
            self.correr([20], {'abierta': False})
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'dejó de entregar'):
            self.correr([20], {'muerta': True}, descartar=0)

    def test_posicion_se_anota_en_el_csv(self):
        r, _, _ = self.correr([20], cuadros=2, descartar=0, posicion='IZQ')
        self.assertEqual({f[2] for f in cal.leer_csv(r)}, {'izq'})

    def test_no_se_agrega_a_un_csv_de_formato_antiguo(self):
        (self.d / 'capturas.csv').write_text('imagen,distancia_cm\n', encoding='utf-8')
        with self.assertRaisesRegex(cf.ErrorCalibracion, 'otro encabezado'):
            self.correr([20], cuadros=2, descartar=0)

    def test_parametros_invalidos(self):
        for kw in ({'cuadros': 0}, {'cuadros': 500}, {'posicion': 'a la izquierda'}, {'posicion': 'a,b'}, {'posicion': ''}):
            with self.assertRaises(cf.ErrorCalibracion):
                self.correr([20], **kw)
        with self.assertRaises(cf.ErrorCalibracion):
            self.correr([0.3])      # metros en vez de centímetros

    def test_agrega_al_csv_existente_sin_repetir_el_encabezado(self):
        self.correr([15], cuadros=2, descartar=0)
        r, _, _ = self.correr([20], cuadros=2, descartar=0)
        texto = r.read_text(encoding='utf-8')
        self.assertEqual(texto.count('imagen,distancia_cm,posicion'), 1)
        self.assertEqual(len(cal.leer_csv(r)), 4)


@unittest.skipUnless(HAY, 'OpenCV o pupil-apriltags no disponibles')
class TestCli(Base):
    def cli(self, *args):
        sys.path.insert(0, str(RAIZ / 'scripts' / 'camara'))
        import importlib
        import calibrar_focal
        importlib.reload(calibrar_focal)
        return calibrar_focal.main(list(args))

    def test_calcular_validar_y_no_sobrescribe(self):
        csv_ = escribir_capturas(self.d, [15, 20, 25, 30, 35, 40])
        self.assertEqual(self.cli('calcular', '--csv', str(csv_), '--tamano-mm', '59.5'), 0)
        yaml_ = self.d / 'camara_calibrada.yaml'
        self.assertTrue(yaml_.is_file())
        self.assertEqual(self.cli('calcular', '--csv', str(csv_), '--tamano-mm', '59.5'), 1)       # no pisa
        self.assertEqual(self.cli('calcular', '--csv', str(csv_), '--tamano-mm', '59.5', '--sobrescribir'), 0)
        nueva = self.d / 'val'
        nueva.mkdir()
        val = escribir_capturas(nueva, [18, 28, 38], semilla0=300)
        self.assertEqual(self.cli('validar', '--camara-yaml', str(yaml_), '--csv', str(val)), 0)
        self.assertEqual(self.cli('validar', '--camara-yaml', str(yaml_), '--csv', str(val), '--tolerancia-cm', '0.0001'), 2)

    def test_errores_dan_codigo_1(self):
        self.assertEqual(self.cli('calcular', '--csv', str(self.d / 'no.csv'), '--tamano-mm', '60'), 1)
        self.assertEqual(self.cli('validar', '--camara-yaml', str(self.d / 'no.yaml'), '--csv', str(self.d / 'no.csv')), 1)


if __name__ == '__main__':
    unittest.main()
