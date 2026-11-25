import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from geometria_dock.transformaciones import Pose2D, aplicar, componer, desde_grados, invertir, wrap


class TestTransformaciones(unittest.TestCase):
    def test_wrap(self):
        self.assertAlmostEqual(wrap(3 * math.pi / 2), -math.pi / 2)
        with self.assertRaises(ValueError):
            wrap(float('nan'))

    def test_componer_con_inversa_es_identidad(self):
        t = Pose2D(1.2, -0.7, 0.9)
        r = componer(t, invertir(t))
        self.assertAlmostEqual(r.x, 0); self.assertAlmostEqual(r.y, 0); self.assertAlmostEqual(r.th, 0)

    def test_aplicar_rotacion_90(self):
        x, y = aplicar(Pose2D(0, 0, math.pi / 2), (1, 0))
        self.assertAlmostEqual(x, 0); self.assertAlmostEqual(y, 1)

    def test_componer_es_asociativa_con_aplicar(self):
        a, b, p = Pose2D(1, 2, .3), Pose2D(-.5, .2, -1.1), (.4, .9)
        self.assertAlmostEqual(aplicar(componer(a, b), p)[0], aplicar(a, aplicar(b, p))[0])
        self.assertAlmostEqual(aplicar(componer(a, b), p)[1], aplicar(a, aplicar(b, p))[1])

    def test_desde_grados(self):
        self.assertAlmostEqual(desde_grados(0, 0, 90).th, math.pi / 2)

    def test_pose_no_finita(self):
        with self.assertRaises(ValueError):
            Pose2D(float('inf'), 0, 0)


if __name__ == '__main__':
    unittest.main()
