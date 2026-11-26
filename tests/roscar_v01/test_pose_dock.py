import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(RAIZ / 'tests' / 'carrito'))
import pose_dock
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D, desde_grados

CAM, TAG = Pose2D(0.10, 0.01, math.radians(0.5)), Pose2D(0.38, 0.0, 0.0)
SEMILLA = RAIZ / 'carrito' / 'config' / 'marcos.yaml'


def correr(*args, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    anterior = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = pose_dock.main(list(args))
    finally:
        sys.stdin = anterior
    return rc, out.getvalue(), err.getvalue()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        texto = SEMILLA.read_text(encoding='utf-8')
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: null', 'x_m: 0.10\n  y_m: 0.01\n  yaw_deg: 0.5', 1)
        texto = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: 0.0', 'x_m: 0.38\n  y_m: 0.0\n  yaw_deg: 0.0', 1)
        self.marcos = str(Path(self.dir.name) / 'marcos.yaml')
        Path(self.marcos).write_text(texto, encoding='utf-8')

    def medicion(self, robot, estacion=2, **cambio):
        x, y, z, dth, _ = tag_visto(robot, CAM, TAG)
        return {'modo': 'una', 'aceptada': True, 'motivo': None, 'id': estacion, 'x_m': x, 'y_m': y, 'z_m': z, 'dth_deg': dth,
                **cambio}


class TestConvertir(Base):
    def test_desde_la_entrada_estandar(self):
        rc, out, _ = correr('convertir', '--marcos', self.marcos, stdin=json.dumps(self.medicion(desde_grados(0.02, -0.01, 3.0))))
        d = json.loads(out)
        self.assertEqual(rc, 0)
        self.assertAlmostEqual(d['dock']['dx_m'], 0.02, places=4)
        self.assertAlmostEqual(d['dock']['dy_m'], -0.01, places=4)
        self.assertAlmostEqual(d['dock']['dth_deg'], 3.0, places=2)
        self.assertTrue(d['cerca_del_dock'])
        self.assertAlmostEqual(d['mapa']['x_m'], 2.42, places=3)                       # dock 2 en (2.40, 0.40, 0°)

    def test_con_banderas_y_estacion_explicita(self):
        m = self.medicion(desde_grados(0.0, 0.0, 0.0))
        rc, out, _ = correr('convertir', '--marcos', self.marcos, '--x-m', str(m['x_m']), '--y-m', str(m['y_m']), '--z-m',
                            str(m['z_m']), '--dth-deg', str(m['dth_deg']), '--estacion', '3')
        d = json.loads(out)
        self.assertEqual((rc, d['estacion']), (0, 3))
        self.assertAlmostEqual(d['mapa']['x_m'], 2.40, places=3)
        self.assertAlmostEqual(d['mapa']['y_m'], 2.40, places=3)
        self.assertAlmostEqual(d['mapa']['th_deg'], 90.0, places=2)

    def test_fuera_del_dock_sale_con_2(self):
        rc, out, _ = correr('convertir', '--marcos', self.marcos, '--json', json.dumps(self.medicion(desde_grados(0.4, 0.0, 0.0))))
        self.assertEqual(rc, 2)
        self.assertFalse(json.loads(out)['cerca_del_dock'])

    def test_errores_dan_codigo_1(self):
        bueno = self.medicion(desde_grados(0.0, 0.0, 0.0))
        casos = [('convertir', '--marcos', self.marcos, '--json', '{no es json'),
                 ('convertir', '--marcos', self.marcos, '--json', json.dumps({**bueno, 'aceptada': False, 'motivo': 'sin_tag'})),
                 ('convertir', '--marcos', self.marcos, '--json', json.dumps({**bueno, 'z_m': None})),
                 ('convertir', '--marcos', self.marcos, '--json', json.dumps({**bueno, 'id': None})),
                 ('convertir', '--marcos', self.marcos, '--json', json.dumps(bueno), '--estacion', '7'),
                 ('convertir', '--marcos', str(SEMILLA), '--json', json.dumps(bueno)),
                 ('convertir', '--marcos', str(Path(self.dir.name) / 'no.yaml'), '--json', json.dumps(bueno))]
        for args in casos:
            rc, _, err = correr(*args)
            self.assertEqual(rc, 1, f'{args}: {err}')
            self.assertIn('error:', err)


class TestMontaje(Base):
    def test_recupera_el_montaje_desde_una_medicion_de_referencia(self):
        verdad = Pose2D(0.11, -0.015, math.radians(1.5))
        x, y, z, dth, _ = tag_visto(desde_grados(0, 0, 0), verdad, TAG)
        med = {'aceptada': True, 'id': 2, 'x_m': x, 'y_m': y, 'z_m': z, 'dth_deg': dth}
        rc, out, _ = correr('montaje', '--tag-en-dock', '0.38,0,0', '--json', json.dumps(med))
        self.assertEqual(rc, 0)
        self.assertIn('x_m: 0.110', out)
        self.assertIn('y_m: -0.015', out)
        self.assertIn('yaw_deg: 1.5', out)
        self.assertIn('inclinacion_deg: 0', out)

    def test_el_resultado_se_pega_en_marcos_yaml_y_carga(self):
        med = self.medicion(desde_grados(0, 0, 0))
        rc, out, _ = correr('montaje', '--tag-en-dock', '0.38,0,0', '--json', json.dumps(med))
        texto = SEMILLA.read_text(encoding='utf-8')
        cam, tag = out.split('tag_en_dock:')
        bloque = lambda s: [l.strip() for l in s.splitlines() if l.startswith('  ')]
        nuevo = texto.replace('x_m: null\n  y_m: null\n  yaw_deg: null\n  inclinacion_deg: 0.0', '\n  '.join(bloque(cam)), 1)
        nuevo = nuevo.replace('x_m: null\n  y_m: null\n  yaw_deg: 0.0', '\n  '.join(bloque(tag)), 1)
        ruta = Path(self.dir.name) / 'completo.yaml'
        ruta.write_text(nuevo, encoding='utf-8')
        from carrito.granprix_carrito import marcos as mc
        m = mc.cargar_marcos(str(ruta))
        self.assertAlmostEqual(m.montaje.pose.x, 0.10, places=3)

    def test_argumentos_mal_escritos_los_rechaza_argparse(self):
        for args in (('montaje', '--tag-en-dock', '0.38,0', '--json', '{}'), ('montaje', '--tag-en-dock', 'a,b,c')):
            with self.assertRaises(SystemExit):
                correr(*args)

    def test_medicion_no_aceptada_o_sin_pose(self):
        for med in ({'aceptada': False, 'motivo': 'sin_tag'}, {'aceptada': True, 'x_m': None, 'y_m': 0, 'z_m': 0.3, 'dth_deg': 0}):
            rc, _, err = correr('montaje', '--tag-en-dock', '0.38,0,0', '--json', json.dumps(med))
            self.assertEqual(rc, 1)
            self.assertIn('error:', err)


if __name__ == '__main__':
    unittest.main()
