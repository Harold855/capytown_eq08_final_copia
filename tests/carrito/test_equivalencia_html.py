"""El port en Python (con NUESTRO planificador y estimador) debe reproducir el simulate() original del HTML."""
import json
import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from simulacion.modelo_granprix import mulberry32, simular

REF = json.loads((Path(__file__).parent / 'referencia_html.json').read_text(encoding='utf-8'))


class TestEquivalenciaConElHtml(unittest.TestCase):
    def test_generador_aleatorio_es_determinista_y_uniforme(self):
        a, b = mulberry32(7), mulberry32(7)
        va = [a() for _ in range(1000)]
        self.assertEqual(va, [b() for _ in range(1000)])
        self.assertTrue(all(0 <= x < 1 for x in va))
        self.assertAlmostEqual(sum(va) / 1000, 0.5, delta=0.05)

    def test_todos_los_casos_coinciden(self):
        self.assertEqual(len(REF['casos']), 18)
        for caso in REF['casos']:
            with self.subTest(params=caso['params'], semilla=caso['seed'], modo=caso['mode']):
                mios = simular(caso['p'], caso['mode'], caso['laps'], caso['seed'])
                self.assertEqual(len(mios), len(caso['recs']))
                for a, b in zip(mios, caso['recs']):
                    self.assertEqual((a['k'], a['ok'], a['retry']), (b['k'], b['ok'], b['retry']))
                    for campo in ('err', 'herr', 'pitTime', 't1', 'cd', 'ca'):
                        self.assertTrue(math.isclose(a[campo], b[campo], rel_tol=1e-9, abs_tol=1e-9),
                                        f'{campo}: {a[campo]} != {b[campo]}')

    def test_cifras_del_contexto_del_equipo(self):
        """Semilla 7, modo recal, parámetros por defecto: 479.653 s, cd 1.011667, ca 0.985804."""
        caso = next(c for c in REF['casos'] if (c['params'], c['seed'], c['mode']) == ('A', 7, 'recal'))
        r = simular(caso['p'], 'recal', 4, 7)
        self.assertAlmostEqual(r[-1]['t1'], 479.653, places=3)
        self.assertAlmostEqual(r[-1]['cd'], 1.011667, places=6)
        self.assertAlmostEqual(r[-1]['ca'], 0.985804, places=6)

    def test_modo_invalido(self):
        with self.assertRaises(ValueError):
            simular(REF['casos'][0]['p'], 'otro', 1, 1)


if __name__ == '__main__':
    unittest.main()
