import re
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / 'scripts' / 'jetcobot_v01'
sys.path.insert(0, str(SCRIPTS))
import cronometro_ciclo as cc
import diagnostico_jetcobot as dj


class TestDiagnostico(unittest.TestCase):
    ok = ([0, -20, 30, 0, 10, -45], [140, -10, 260, -170, 0, -40], 100, 1)

    def niveles(self, *args, **kw):
        return [n for n, _ in dj.evaluar(*args, **kw)]

    def test_todo_ok(self):
        self.assertEqual(set(self.niveles(*self.ok, en_movimiento=0)), {'OK'})

    def test_servos_apagados_es_falla(self):
        self.assertIn('FALLA', self.niveles(self.ok[0], self.ok[1], 100, 0))

    def test_lectura_invalida_es_falla(self):
        self.assertIn('FALLA', self.niveles(None, self.ok[1], 100, 1))
        self.assertIn('FALLA', self.niveles(self.ok[0], [1, 2], 100, 1))
        self.assertIn('FALLA', self.niveles(self.ok[0], self.ok[1], -1, 1))

    def test_fuera_de_limites_y_movimiento_son_avisos(self):
        n = self.niveles([200, 0, 0, 0, 0, 0], self.ok[1], 100, 1, en_movimiento=1, fallos_lectura=2)
        self.assertEqual(n.count('AVISO'), 3)

    def test_latencias(self):
        r = dj.resumen_latencias([0.01, 0.02, 0.03, 0.04])
        self.assertEqual(r['n'], 4); self.assertAlmostEqual(r['max_ms'], 40.0)
        self.assertIsNone(dj.resumen_latencias([]))

    def test_modo_simulado_termina_bien(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(dj.main(['--simular', '--lecturas', '3', '--salida', str(Path(d) / 'x.txt')]), 0)

    def test_el_diagnostico_es_de_solo_lectura(self):
        """El script no debe contener ninguna orden de movimiento, de pinza ni de apagado."""
        fuente = (SCRIPTS / 'diagnostico_jetcobot.py').read_text(encoding='utf-8')
        prohibidas = [r'send_angle', r'send_coord', r'set_gripper', r'\.power_off\(', r'\.power_on\(', r'release_all',
                      r'release_servo', r'focus_servo', r'jog_', r'sync_send', r'set_color', r'set_fresh_mode']
        encontradas = [t for t in prohibidas if re.search(t, fuente)]
        self.assertEqual(encontradas, [])


class TestCronometro(unittest.TestCase):
    def test_fases(self):
        f = cc.calcular_fases([('inicio', 0.0), ('a', 2.0), ('b', 5.5)])
        self.assertEqual([round(x[2], 2) for x in f], [0.0, 2.0, 3.5])

    def test_medir_con_reloj_falso(self):
        reloj = iter([100.0, 102.5, 107.0]).__next__
        t = cc.medir(['inicio', 'a', 'b'], entrada=lambda _: '', reloj=reloj)
        self.assertEqual(t, [('inicio', 0.0), ('a', 2.5), ('b', 7.0)])

    def test_marcas_por_rol(self):
        self.assertEqual(len(cc.MARCAS[2]), 6)
        self.assertEqual(cc.MARCAS[1][-1], 'brazo_libre')

    def test_guardar_csv(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 't.csv'
            cc.guardar(ruta, [['f', 2, '1', 'manual', 'inicio', '0.000', '0.000']])
            cc.guardar(ruta, [['f', 2, '2', 'manual', 'inicio', '0.000', '0.000']])
            self.assertEqual(len(ruta.read_text().splitlines()), 3)


if __name__ == '__main__':
    unittest.main()
