import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito.eventos_mision import RegistroEventos
from comun.yaml_estricto import ErrorYaml
from evidencia import archivos_falsos as af
from evidencia import verificar_evidencias as ve
from carrito.granprix_carrito.registro_experimental import RegistroExperimental
from simulacion.mision_simulada import Mundo

SPEC = ve.cargar_spec()
YAML = Path(ve.ESPEC_DEFECTO)


def textos(inf, nivel='FALLA'):
    return ' | '.join(f'{h.item}: {h.detalle}' for h in inf.hallazgos if h.nivel == nivel)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def ruta(self, *p):
        return os.path.join(self.dir, *p)

    def verificar(self, **kw):
        return ve.verificar(self.dir, SPEC, **kw)


class TestSpec(Base):
    def test_el_yaml_por_defecto_coincide_con_los_valores_por_defecto(self):
        self.assertEqual(SPEC, ve.Spec())

    def cargar(self, cambios):
        texto = YAML.read_text(encoding='utf-8')
        for a, b in cambios.items():
            assert a in texto, a
            texto = texto.replace(a, b, 1)
        Path(self.ruta('s.yaml')).write_text(texto, encoding='utf-8')
        return ve.cargar_spec(self.ruta('s.yaml'))

    def test_valores_cargados(self):
        s = self.cargar({'vueltas: 4 ': 'vueltas: 2 ', 'fps_min: 15.0': 'fps_min: 24.0', '"/imu"': '"/imu/data"'})
        self.assertEqual((s.vueltas, s.fps_min), (2, 24.0))
        self.assertEqual(next(r for r in s.requeridos if r.nombre == 'imu').topics, ('/imu/data',))

    def test_yaml_estricto(self):
        casos = {'versión': {'version: 1': 'version: 3'}, 'clave desconocida': {'vueltas: 4 ': 'vueltas: 4\nextra: 1\n'},
                 'duplicada': {'ancho_min: 640': 'ancho_min: 640\n  ancho_min: 320'}, 'topic sin barra': {'"/odom"': '"odom"'},
                 'topics vacío': {'topics: ["/odom"]': 'topics: []'}, 'hz negativo': {'hz_min: 5.0}\n    imu': 'hz_min: -1}\n    imu'},
                 'fps cero': {'fps_min: 15.0': 'fps_min: 0'}, 'cobertura > 1': {'cobertura_min: 0.9': 'cobertura_min: 1.5'},
                 'columnas no lista': {'columnas: []': 'columnas: x'}}
        for nombre, c in casos.items():
            with self.assertRaises(ErrorYaml, msg=nombre):
                self.cargar(c)


class TestNombres(unittest.TestCase):
    def test_numero_de_vuelta(self):
        for nombre, n in (('lap01.mp4', 1), ('vuelta_02', 2), ('Lap-3', 3), ('v4', 4), ('evidencia_final', None),
                          ('tanda', None), ('bags', None), ('video.mp4', None)):
            self.assertEqual(ve.num_vuelta(nombre), n, nombre)

    def test_en_carpetas_contenedoras_la_v_suelta_no_cuenta(self):
        self.assertIsNone(ve.num_vuelta('evidencia_v1', estricto=True))
        self.assertEqual(ve.num_vuelta('vuelta_2', estricto=True), 2)


class TestMp4(Base):
    def info(self, **kw):
        ruta = self.ruta('a.mp4')
        af.mp4_minimo(ruta, **kw)
        return ve.inspeccionar_mp4(ruta)

    def test_lee_resolucion_fps_y_duracion(self):
        i = self.info(ancho=1280, alto=720, fps=30.0, duracion_s=12.5)
        self.assertEqual((i['ancho'], i['alto'], i['muestras']), (1280, 720, 375))
        self.assertAlmostEqual(i['fps'], 30.0)
        self.assertAlmostEqual(i['duracion_s'], 12.5)

    def test_los_fallos_conocidos(self):
        casos = {'cortado': (dict(truncar_bytes=50), 'cortado'), 'sin moov': (dict(sin_moov=True), 'moov'),
                 'sin imágenes': (dict(mdat_bytes=0), 'mdat vacío')}
        for nombre, (kw, texto) in casos.items():
            with self.assertRaisesRegex(ve.ErrorArchivo, texto, msg=nombre):
                self.info(**kw)

    def test_archivos_que_no_son_mp4(self):
        Path(self.ruta('v.mp4')).write_bytes(b'')
        with self.assertRaisesRegex(ve.ErrorArchivo, 'vacío'):
            ve.inspeccionar_mp4(self.ruta('v.mp4'))
        Path(self.ruta('t.mp4')).write_bytes(b'esto no es un video, es texto plano de relleno')
        with self.assertRaises(ve.ErrorArchivo):
            ve.inspeccionar_mp4(self.ruta('t.mp4'))
        Path(self.ruta('c.mp4')).write_bytes(b'\x00\x00\x00')
        with self.assertRaisesRegex(ve.ErrorArchivo, 'cortado'):
            ve.inspeccionar_mp4(self.ruta('c.mp4'))


class TestBag(Base):
    def bag(self, topics=None, **kw):
        carpeta = self.ruta('bag')
        af.bag_falso(carpeta, topics or {'/odom': 20.0, '/imu': 25.0}, 1000.0, 10.0, **kw)
        return ve.inspeccionar_bag(carpeta)

    def test_cuenta_los_mensajes_de_verdad(self):
        i = self.bag()
        self.assertEqual((i['topics']['/odom']['real'], i['topics']['/imu']['real'], i['formato'], i['metadata']), (200, 250, 'sqlite3', True))
        self.assertAlmostEqual(i['fin_s'] - i['inicio_s'], 10.0, delta=0.1)
        self.assertEqual(i['problemas'], [])

    def test_bag_sin_mensajes_con_metadatos_que_mienten(self):
        i = self.bag(vacios=('/odom',), metadata_cuentas={'/odom': 200})
        self.assertEqual((i['topics']['/odom']['real'], i['topics']['/odom']['meta']), (0, 200))

    def test_sin_metadata_se_avisa_pero_se_cuenta(self):
        i = self.bag(metadata=False)
        self.assertEqual(i['topics']['/odom']['real'], 200)
        self.assertTrue(any('metadata.yaml' in t for n, t in i['problemas'] if n == 'FALLA'))

    def test_base_de_datos_corrupta_o_ausente(self):
        self.bag()
        Path(self.ruta('bag', 'bag_0.db3')).write_bytes(b'basura' * 100)
        self.assertTrue(any('no se puede leer' in t for _, t in ve.inspeccionar_bag(self.ruta('bag'))['problemas']))
        os.remove(self.ruta('bag', 'bag_0.db3'))
        self.assertTrue(any('no existe' in t for _, t in ve.inspeccionar_bag(self.ruta('bag'))['problemas']))

    def test_mensajes_con_contenido_vacio(self):
        self.bag()
        con = sqlite3.connect(self.ruta('bag', 'bag_0.db3'))
        con.execute("UPDATE messages SET data = x'' WHERE id <= 30")
        con.commit()
        con.close()
        self.assertEqual(ve.inspeccionar_bag(self.ruta('bag'))['topics']['/odom']['vacios'], 30)

    def test_bag_dividido_en_varios_archivos(self):
        self.bag()
        os.rename(self.ruta('bag', 'bag_0.db3'), self.ruta('bag', 'bag_1.db3'))
        af.bag_falso(self.ruta('otro'), {'/odom': 20.0, '/imu': 25.0}, 1010.0, 10.0)
        os.rename(self.ruta('otro', 'bag_0.db3'), self.ruta('bag', 'bag_0.db3'))
        meta = Path(self.ruta('bag', 'metadata.yaml'))
        meta.write_text(meta.read_text().replace('- bag_0.db3', '- bag_0.db3\n  - bag_1.db3'))
        i = ve.inspeccionar_bag(self.ruta('bag'))
        self.assertEqual(i['topics']['/odom']['real'], 400)
        self.assertAlmostEqual(i['fin_s'] - i['inicio_s'], 20.0, delta=0.2)

    def test_formato_mcap_solo_revisa_metadata(self):
        self.bag()
        meta = Path(self.ruta('bag', 'metadata.yaml'))
        meta.write_text(meta.read_text().replace('sqlite3', 'mcap'))
        i = ve.inspeccionar_bag(self.ruta('bag'))
        self.assertIsNone(i['topics']['/odom']['real'])
        self.assertTrue(any('mcap' in t for _, t in i['problemas']))


class TestVerificar(Base):
    def test_la_evidencia_completa_pasa(self):
        af.carpeta_simulada(self.dir)
        inf = self.verificar()
        self.assertTrue(inf.ok, textos(inf))
        self.assertEqual(len([h for h in inf.hallazgos if h.nivel == 'OK']), 12)
        self.assertIn('cobertura', textos(inf, 'AVISO'))

    def test_cada_defecto_conocido_se_detecta_con_su_mensaje(self):
        esperado = {'bag_vacio': 'sin mensajes de odometria', 'bag_sin_metadata': 'sin metadata.yaml', 'imu_ausente': 'sin mensajes de imu',
                    'video_truncado': 'cortado', 'video_sin_moov': 'moov', 'video_pequeno': '160x120', 'sin_video_vuelta3': 'video vuelta 3',
                    'csv_sin_filas': 'solo tiene el encabezado', 'sin_csv_vuelta2': 'eventos del pit vuelta 2',
                    'sin_bag_vuelta4': 'bag vuelta 4'}
        for defecto, texto in esperado.items():
            with self.subTest(defecto):
                with tempfile.TemporaryDirectory() as d:
                    af.carpeta_simulada(d, defectos=(defecto,))
                    inf = ve.verificar(d, SPEC)
                    self.assertFalse(inf.ok)
                    self.assertIn(texto, textos(inf))

    def test_bag_cuyo_metadata_miente_es_aviso_pero_el_bag_vacio_es_falla(self):
        af.carpeta_simulada(self.dir, defectos=('bag_metadata_miente',))
        inf = self.verificar()
        self.assertTrue(inf.ok)
        self.assertIn('metadata.yaml dice 5', textos(inf, 'AVISO'))
        with tempfile.TemporaryDirectory() as d:
            af.carpeta_simulada(d, defectos=('bag_vacio',))
            self.assertIn('bag vacío', textos(ve.verificar(d, SPEC)))

    def test_video_con_pocos_fps_o_demasiado_corto(self):
        af.carpeta_simulada(self.dir)
        af.mp4_minimo(self.ruta('videos', 'lap01.mp4'), fps=5.0, duracion_s=100.0)
        self.assertIn('5.0 fps', textos(self.verificar()))
        af.mp4_minimo(self.ruta('videos', 'lap01.mp4'), fps=15.0, duracion_s=4.0)
        self.assertIn('dura 4.0 s', textos(self.verificar()))
        af.mp4_minimo(self.ruta('videos', 'lap01.mp4'), fps=14.8, duracion_s=100.0)
        self.assertTrue(self.verificar().ok)                      # 14.8 fps está dentro de la holgura del 2 %

    def test_mensajes_con_el_contenido_vacio_son_falla(self):
        af.carpeta_simulada(self.dir)
        con = sqlite3.connect(self.ruta('bags', 'lap01', 'bag_0.db3'))
        con.execute("UPDATE messages SET data = x'' WHERE topic_id = 1 AND id % 2 = 0")
        con.commit()
        con.close()
        self.assertIn('mensajes con el contenido vacío', textos(self.verificar()))

    def test_frecuencia_demasiado_baja_es_falla(self):
        af.carpeta_simulada(self.dir, topics={**af.TOPICS_DEFECTO, '/odom': 1.0})
        self.assertIn('/odom: 1.00 Hz', textos(self.verificar()))

    def test_carpeta_inexistente_o_vacia(self):
        self.assertFalse(ve.verificar(self.ruta('no'), SPEC).ok)
        inf = self.verificar()
        self.assertFalse(inf.ok)
        self.assertTrue(all(k in textos(inf) for k in ('video vuelta 1', 'rosbag2', 'csv de eventos del pit')))

    def test_bag_unico_de_toda_la_tanda(self):
        af.carpeta_simulada(self.dir, bag_unico=True)
        inf = self.verificar()
        self.assertTrue(inf.ok, textos(inf))
        with tempfile.TemporaryDirectory() as d:
            af.carpeta_simulada(d, bag_unico=True, topics={k: v for k, v in af.TOPICS_DEFECTO.items() if k != '/imu'})
            self.assertIn('sin mensajes de imu', textos(ve.verificar(d, SPEC)))

    def test_archivos_sin_numero_de_vuelta(self):
        af.carpeta_simulada(self.dir)
        af.mp4_minimo(self.ruta('videos', 'grabacion.mp4'))
        self.assertIn('sin número de vuelta', textos(self.verificar(), 'AVISO'))

    def test_dos_videos_para_la_misma_vuelta(self):
        af.carpeta_simulada(self.dir)
        af.mp4_minimo(self.ruta('videos', 'vuelta_1.mp4'))
        self.assertIn('2 archivos para la misma vuelta', textos(self.verificar(), 'AVISO'))

    def test_csv_con_vuelta_equivocada_o_sin_columnas(self):
        af.carpeta_simulada(self.dir)
        p = Path(self.ruta('csv', 'lap02_pits.csv'))
        p.write_text(p.read_text().replace('\n2,', '\n3,'))
        self.assertIn('el archivo es de la vuelta 2', textos(self.verificar()))
        p.write_text('a,b\n1,2\n')
        self.assertIn('faltan columnas: vuelta', textos(self.verificar()))

    def test_un_csv_de_toda_la_tanda(self):
        af.carpeta_simulada(self.dir)
        for n in (1, 2, 3, 4):
            os.remove(self.ruta('csv', f'lap{n:02d}_pits.csv'))
        filas = ['vuelta,estacion'] + [f'{v},{e}' for v in (1, 2, 3, 4) for e in (1, 2, 3, 4)]
        Path(self.ruta('csv', 'pits_tanda.csv')).write_text('\n'.join(filas) + '\n')
        self.assertTrue(self.verificar().ok)
        Path(self.ruta('csv', 'pits_tanda.csv')).write_text('\n'.join(f for f in filas if not f.startswith('3,')) + '\n')
        self.assertIn('eventos del pit vuelta 3: 0 filas', textos(self.verificar()))

    def test_columnas_obligatorias_extra(self):
        af.carpeta_simulada(self.dir)
        s = replace(SPEC, columnas=('t_pit_s', 'no_existe'))
        self.assertIn('faltan columnas: no_existe', textos(ve.verificar(self.dir, s)))

    def test_otros_csv_se_ignoran(self):
        af.carpeta_simulada(self.dir)
        Path(self.ruta('sensores.csv')).write_text('t,x\n')
        self.assertTrue(self.verificar().ok)

    def test_eventos_ilegibles_y_registro_experimental(self):
        af.carpeta_simulada(self.dir)
        Path(self.ruta('eventos.jsonl')).write_text('{"ts":1,"tipo":"inicio","datos":{}}\nbasura\n{"ts":2,"tipo":"fin","datos":{}}\n')
        self.assertIn('línea 2', textos(self.verificar()))
        os.remove(self.ruta('eventos.jsonl'))
        r = RegistroExperimental(self.ruta('registro_experimental.jsonl'))
        r.agregar('mision', 'eq08-roscar', 'ana', 'ok')
        self.assertTrue(self.verificar().ok)
        Path(r.ruta).write_text(Path(r.ruta).read_text().replace('ana', 'eva'))
        self.assertIn('editada', textos(self.verificar()))


class TestCobertura(Base):
    """Con los tiempos reales de una misión simulada: el video y el bag deben cubrir cada vuelta."""

    @classmethod
    def setUpClass(cls):
        cls.m = Mundo(escalas_ini=(1.01, 1.09))
        cls.m.correr()
        cls.vueltas = {v[0]: (v[1], v[2]) for v in cls.m.puerto.vueltas}

    def crear(self, bag_tarde_s=0.0, video_corto=1.0, bag_corto=1.0):
        d = self.dir
        r = RegistroEventos(lambda: 0.0, os.path.join(d, 'eventos.jsonl'))
        for e in self.m.fsm.eventos.eventos:
            r._f.write(json.dumps(e.a_dict()) + '\n')
        r.cerrar()
        for n, (ini, fin) in self.vueltas.items():
            dur = fin - ini
            af.mp4_minimo(os.path.join(d, 'videos', f'lap{n:02d}.mp4'), duracion_s=dur * (video_corto if n == 2 else 1.0))
            af.csv_pits(os.path.join(d, 'csv', f'lap{n:02d}_pits.csv'), n)
            tarde = bag_tarde_s if n == 3 else 0.0
            af.bag_falso(os.path.join(d, 'bags', f'lap{n:02d}'), af.TOPICS_DEFECTO, ini + tarde, dur * (bag_corto if n == 4 else 1.0) - tarde)

    def test_todo_cubierto(self):
        self.crear()
        inf = self.verificar()
        self.assertTrue(inf.ok, textos(inf))
        self.assertIn('tiempos de 4 vueltas', ' '.join(h.detalle for h in inf.hallazgos))
        self.assertEqual(textos(inf, 'AVISO'), '')

    def test_bag_que_empieza_tarde(self):
        self.crear(bag_tarde_s=20.0)
        self.assertIn('bag bags/lap03: no cubre', textos(self.verificar()))

    def test_bag_que_termina_antes(self):
        self.crear(bag_corto=0.5)
        self.assertIn('bag bags/lap04: no cubre', textos(self.verificar()))

    def test_video_mas_corto_que_la_vuelta(self):
        self.crear(video_corto=0.5)
        self.assertIn('video vuelta 2', textos(self.verificar()))

    def test_la_tolerancia_absorbe_unos_segundos(self):
        self.crear(bag_tarde_s=3.0)
        self.assertTrue(self.verificar().ok)

    def test_un_bag_de_la_tanda_debe_cubrirla_entera(self):
        self.crear()
        import shutil
        for n in (1, 2, 3, 4):
            shutil.rmtree(self.ruta('bags', f'lap{n:02d}'))
        ini, fin = min(v[0] for v in self.vueltas.values()), max(v[1] for v in self.vueltas.values())
        af.bag_falso(self.ruta('bags', 'tanda'), af.TOPICS_DEFECTO, ini, fin - ini)
        self.assertTrue(self.verificar().ok)
        af.bag_falso(self.ruta('bags', 'tanda'), af.TOPICS_DEFECTO, ini, (fin - ini) * 0.7)
        self.assertIn('no cubre', textos(self.verificar()))


class TestCli(Base):
    def correr(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = ve.main(list(args))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_codigos_de_salida_y_json(self):
        af.carpeta_simulada(self.dir)
        salida = self.ruta('informe.json')
        rc, out, _ = self.correr(self.dir, '--json', salida)
        self.assertEqual(rc, 0)
        self.assertIn('EVIDENCIA COMPLETA', out)
        with open(salida) as f:
            d = json.load(f)
        self.assertEqual((d['ok'], d['fallas']), (True, 0))
        af.carpeta_simulada(self.dir, defectos=('bag_vacio',))
        rc, out, _ = self.correr(self.dir, '--json', salida)
        self.assertEqual(rc, 1)
        self.assertIn('EVIDENCIA INCOMPLETA', out)
        with open(salida) as f:
            self.assertFalse(json.load(f)['ok'])

    def test_spec_invalida_y_vueltas(self):
        rc, _, err = self.correr(self.dir, '--spec', self.ruta('no.yaml'))
        self.assertEqual(rc, 1)
        self.assertIn('ERROR', err)
        af.carpeta_simulada(self.dir, vueltas=2)
        self.assertEqual(self.correr(self.dir)[0], 1)                       # la spec pide 4
        self.assertEqual(self.correr(self.dir, '--vueltas', '2')[0], 0)

    def test_defecto_desconocido_en_el_generador(self):
        with self.assertRaises(ValueError):
            af.carpeta_simulada(self.dir, defectos=('inventado',))


if __name__ == '__main__':
    unittest.main()
