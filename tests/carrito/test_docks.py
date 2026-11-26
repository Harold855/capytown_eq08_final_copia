import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito.docks import DOCKS_HTML, Dock, cargar_json, dock_a_mapa, mapa_a_dock, siguiente, validar
from geometria_dock.transformaciones import Pose2D


class TestDocks(unittest.TestCase):
    def test_orden_antihorario_y_cierre(self):
        self.assertEqual([siguiente(i) for i in (1, 2, 3, 4)], [2, 3, 4, 1])
        with self.assertRaises(ValueError):
            siguiente(5)

    def test_rumbo_de_llegada_es_el_sentido_del_tramo_previo(self):
        for e in (1, 2, 3, 4):
            ant = DOCKS_HTML[{1: 4, 2: 1, 3: 2, 4: 3}[e]]
            d = DOCKS_HTML[e]
            self.assertAlmostEqual(math.cos(d.rumbo), math.cos(math.atan2(d.y - ant.y, d.x - ant.x)), places=9)
            self.assertAlmostEqual(math.sin(d.rumbo), math.sin(math.atan2(d.y - ant.y, d.x - ant.x)), places=9)

    def test_dock_a_mapa_en_el_origen_del_dock(self):
        p = dock_a_mapa(DOCKS_HTML[2], 0, 0, 0)
        self.assertAlmostEqual(p.x, 2.40); self.assertAlmostEqual(p.y, 0.40); self.assertAlmostEqual(p.th, 0.0)

    def test_dx_sigue_el_rumbo_y_dy_va_a_la_izquierda(self):
        p = dock_a_mapa(DOCKS_HTML[1], 0.03, 0.02, 0)      # E1 llega mirando al sur
        self.assertAlmostEqual(p.y, 0.37); self.assertAlmostEqual(p.x, 0.42)
        p = dock_a_mapa(DOCKS_HTML[3], 0.03, 0.02, 0)      # E3 llega mirando al norte
        self.assertAlmostEqual(p.y, 2.43); self.assertAlmostEqual(p.x, 2.38)

    def test_ida_y_vuelta(self):
        for e in (1, 2, 3, 4):
            dx, dy, dth = mapa_a_dock(DOCKS_HTML[e], dock_a_mapa(DOCKS_HTML[e], 0.021, -0.012, 4.5))
            self.assertAlmostEqual(dx, 0.021); self.assertAlmostEqual(dy, -0.012); self.assertAlmostEqual(dth, 4.5)

    def test_validar_rechaza_centimetros_y_docks_incompletos(self):
        with self.assertRaises(ValueError):
            validar({**DOCKS_HTML, 1: Dock(1, 40.0, 40.0, 0.0)})
        with self.assertRaises(ValueError):
            validar({1: DOCKS_HTML[1]})

    def test_cargar_json(self):
        datos = {'docks': [{'estacion': e, 'x': d.x, 'y': d.y, 'rumbo_deg': math.degrees(d.rumbo)} for e, d in DOCKS_HTML.items()]}
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / 'docks.json'
            ruta.write_text(json.dumps(datos))
            docks = cargar_json(str(ruta))
        self.assertAlmostEqual(docks[4].rumbo, math.pi)


if __name__ == '__main__':
    unittest.main()
