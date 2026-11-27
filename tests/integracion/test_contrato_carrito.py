"""Valida los mensajes del carrito contra los modelos pydantic del contrato del docente.

Usa la copia en vendor/granprix. Si pydantic no está instalado, las pruebas se omiten.
Requiere: pip install pydantic (basta, no hace falta instalar pc-race).
"""
import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(RAIZ / 'vendor' / 'granprix' / 'pc-race'))
import mensajes_contrato as mc

try:
    from contrato import modelos, topicos
    HAY_PYDANTIC = True
except ImportError:  # pydantic ausente
    HAY_PYDANTIC = False


@unittest.skipUnless(HAY_PYDANTIC, 'pydantic no instalado')
class TestContratoCarrito(unittest.TestCase):
    def test_solicitud_en_grados(self):
        m = modelos.SolicitudMsg.model_validate(mc.solicitud(8, 2, .021, -.012, math.radians(1.8), 'A'))
        self.assertAlmostEqual(m.pose.dth, 1.8)
        self.assertEqual(m.dock, 2)

    def test_telemetria(self):
        modelos.TelemetriaMsg.model_validate(mc.telemetria(8, 1.0, 0.4, .1, v=.1, w=0., bateria=7.9, cd=1.01, ca=.99))

    def test_eventos(self):
        modelos.EventoMsg.model_validate(mc.evento_intervencion(8, 'web'))
        modelos.EventoMsg.model_validate(mc.evento_pit(8, 'pit_ok', 2))
        modelos.EventoMsg.model_validate(mc.evento_pit(8, 'reintento', 3))

    def test_vuelta(self):
        modelos.VueltaMsg.model_validate(mc.vuelta(8, 1, 100., 196.4, [1, 2, 3, 4]))

    def test_topicos_los_reconoce_race_control(self):
        r = topicos.interpretar(mc.topico_equipo(8, 'evento'))
        self.assertEqual((r.origen, r.numero, r.canal), ('carrito', 8, 'evento'))
        r = topicos.interpretar(mc.topico_solicitud(3))
        self.assertEqual((r.origen, r.numero, r.canal), ('estacion', 3, 'solicitud'))

    def test_rechazos_propios(self):
        with self.assertRaises(ValueError):
            mc.evento_intervencion(8, 'otro')
        with self.assertRaises(ValueError):
            mc.solicitud(8, 5, 0, 0, 0)
        with self.assertRaises(ValueError):
            mc.vuelta(8, 1, 10., 9.)
        with self.assertRaises(ValueError):
            mc.solicitud(8, 1, float('nan'), 0, 0)


if __name__ == '__main__':
    unittest.main()
