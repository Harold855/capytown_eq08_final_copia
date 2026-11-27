import re
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / 'scripts' / 'roscar_v01' / 'diagnostico_roscar.py'
sys.path.insert(0, str(SCRIPT.parent))
import diagnostico_roscar as dr


def niveles(d):
    return [n for n, _ in dr.evaluar(d)]


def mensajes(d, nivel):
    return [m for n, m in dr.evaluar(d) if n == nivel]


class TestDiagnosticoRoscar(unittest.TestCase):
    def base(self):
        return dr.simulado('ok', {'r': None, 'b_eff': None})

    def test_escenario_sano_sin_fallas(self):
        self.assertNotIn('FALLA', niveles(self.base()))

    def test_escenario_malo_tiene_fallas(self):
        n = niveles(dr.simulado('mal', {'r': None, 'b_eff': None}))
        self.assertGreaterEqual(n.count('FALLA'), 5)

    def test_factores_coinciden_con_el_log_de_rc1(self):
        kl, ka = dr.factores(0.03145, 0.2138)
        self.assertAlmostEqual(kl, 0.9677, places=4)
        self.assertAlmostEqual(ka, 1.0863, places=4)

    def test_sin_placa_es_falla(self):
        d = self.base(); d['nodos'] = ['/odom_corrector']
        self.assertTrue(any('YB_Car_Node' in m for m in mensajes(d, 'FALLA')))

    def test_dos_correctores_es_falla(self):
        d = self.base(); d['nodos'] = ['/YB_Car_Node', '/odom_corrector', '/odom_corrector']
        self.assertTrue(any('2 /odom_corrector' in m for m in mensajes(d, 'FALLA')))

    def test_otro_publicador_en_cmd_vel_es_aviso(self):
        d = self.base(); d['publicadores_cmd_vel'] = ['/teleop_key']
        self.assertTrue(any('teleop_key' in m for m in mensajes(d, 'AVISO')))

    def test_sin_odometria_es_falla(self):
        d = self.base(); d['frecuencias']['/odom'] = {'n': 0, 'hz': 0.0, 'periodo_max_s': None}
        self.assertTrue(any('/odom' in m for m in mensajes(d, 'FALLA')))

    def test_odometria_lenta_es_aviso(self):
        d = self.base(); d['frecuencias']['/odom'] = {'n': 10, 'hz': 3.0, 'periodo_max_s': 0.5}
        self.assertTrue(any('por debajo' in m for m in mensajes(d, 'AVISO')))

    def test_robot_en_movimiento_es_aviso(self):
        d = self.base(); d['ultimo']['/odom'] = {'vx': 0.1, 'wz': 0.0}
        self.assertTrue(any('movimiento' in m for m in mensajes(d, 'AVISO')))

    def test_calibracion_conocida_se_etiqueta(self):
        d = self.base()
        self.assertTrue(any('ROSCar 4' in m for _, m in dr.evaluar(d)))
        d['params'] = {'wheel_radius': 0.0316, 'wheel_separation': 0.2332}
        self.assertTrue(any('otro grupo' in m for m in mensajes(d, 'AVISO')))
        d['params'] = {'wheel_radius': 0.023, 'wheel_separation': 0.135}
        self.assertTrue(any('NO es una calibración' in m for m in mensajes(d, 'FALLA')))

    def test_calibracion_distinta_de_la_esperada_es_falla(self):
        d = self.base(); d['esperado'] = {'r': 0.0311, 'b_eff': None}
        self.assertTrue(any('distinto del esperado' in m for m in mensajes(d, 'FALLA')))

    def test_parametros_ilegibles_son_aviso(self):
        d = self.base(); d['params'] = {}
        self.assertTrue(any('no se pudieron leer' in m for m in mensajes(d, 'AVISO')))

    def test_hora_antigua_es_aviso(self):
        d = self.base(); d['fecha'] = '2026-07-15T11:52:47'
        self.assertNotIn('hora del sistema parece mal', ' '.join(mensajes(d, 'AVISO')))
        d['fecha'] = '2025-07-15T11:52:47'
        self.assertTrue(any('hora del sistema parece mal' in m for m in mensajes(d, 'AVISO')))

    def test_battery_state_ausente_pide_adaptador(self):
        self.assertTrue(any('adaptador' in m for m in mensajes(self.base(), 'AVISO')))

    def test_parsear_param(self):
        self.assertEqual(dr.parsear_param('Double value is: 0.03145\n'), 0.03145)
        self.assertEqual(dr.parsear_param('Double value is: 3.0e-5'), 3.0e-5)
        self.assertIsNone(dr.parsear_param('Node not found'))
        self.assertIsNone(dr.parsear_param(''))

    def test_estadisticas(self):
        e = dr.estadisticas([0.0, 0.1, 0.2, 0.5], 5.0)
        self.assertEqual(e['n'], 4); self.assertAlmostEqual(e['hz'], 3 / 0.5); self.assertAlmostEqual(e['periodo_max_s'], 0.3)
        self.assertEqual(dr.estadisticas([], 5.0)['hz'], 0.0)
        self.assertIsNone(dr.estadisticas([1.0], 5.0)['hz'])

    def test_main_simulado_codigos_de_salida(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(dr.main(['--simular', 'ok', '--salida', str(Path(t) / 'a.txt')]), 0)
            self.assertEqual(dr.main(['--simular', 'mal', '--salida', str(Path(t) / 'b.txt')]), 1)

    def test_el_diagnostico_es_de_solo_lectura(self):
        """No debe crear publicadores, publicar, cambiar parámetros ni llamar servicios."""
        fuente = SCRIPT.read_text(encoding='utf-8')
        prohibidas = [r'create_publisher', r'\.publish\(', r'topic pub', r'param set', r'param load',
                      r'service call', r'create_client', r'Twist\(', r'node kill', r'lifecycle set']
        self.assertEqual([t for t in prohibidas if re.search(t, fuente)], [])


if __name__ == '__main__':
    unittest.main()
