import argparse
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'roscar_v01'))
import registrar_medicion as rm
import analizar_movimientos as am


def args(**kw):
    base = dict(modo='recta', robot='R4', superficie='carton', corrida='1', auto=False, distancia_comandada=1.0,
                giro_comandado=None, velocidad_m_s=.1, velocidad_rad_s=None, distancia_fisica=.96, giro_fisico=None,
                desvio_lateral_cm=1.5, distancia_odom=.95, giro_odom=None, estado='COMPLETO', observaciones='')
    base.update(kw)
    return argparse.Namespace(**base)


class TestRegistro(unittest.TestCase):
    def test_fila_valida(self):
        fila = rm.construir_fila(args())
        self.assertEqual(len(fila), len(rm.CABECERA))
        self.assertEqual(fila[rm.CABECERA.index('distancia_fisica_m')], .96)

    def test_centimetros_se_rechazan(self):
        with self.assertRaises(ValueError):
            rm.construir_fila(args(distancia_fisica=96.))

    def test_giro_exige_medida(self):
        with self.assertRaises(ValueError):
            rm.construir_fila(args(modo='giro', giro_fisico=None))

    def test_auto_toma_odometria(self):
        ultimo = {'modo': 'recta', 'orden_si': '0.25', 'velocidad_si': '0.1', 'dist_odom_m': '0.24',
                  'giro_odom_deg': '0.3', 'estado': 'COMPLETO'}
        fila = rm.construir_fila(args(distancia_comandada=None, distancia_odom=None, estado=''), ultimo)
        self.assertEqual(fila[rm.CABECERA.index('distancia_comandada_m')], .25)
        self.assertEqual(fila[rm.CABECERA.index('distancia_odom_m')], .24)

    def test_auto_modo_distinto(self):
        with self.assertRaises(ValueError):
            rm.construir_fila(args(), {'modo': 'giro', 'orden_si': '0.2', 'velocidad_si': '0.5',
                                       'dist_odom_m': '', 'giro_odom_deg': '', 'estado': 'COMPLETO'})

    def test_anexar_crea_cabecera_y_rechaza_otra(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'm.csv'
            rm.anexar(rm.construir_fila(args()), ruta)
            rm.anexar(rm.construir_fila(args(corrida='2')), ruta)
            self.assertEqual(len(list(csv.reader(ruta.open()))), 3)
            ruta.write_text('otra,cabecera\n')
            with self.assertRaises(ValueError):
                rm.anexar(rm.construir_fila(args()), ruta)


class TestAnalisis(unittest.TestCase):
    def filas(self):
        out = []
        for i, fis in enumerate([.96, .97, .95]):
            f = dict(zip(rm.CABECERA, rm.construir_fila(args(corrida=str(i), distancia_fisica=fis, estado='COMPLETO'))))
            out.append(f)
        out.append(dict(zip(rm.CABECERA, rm.construir_fila(args(corrida='9', distancia_fisica=.5, estado='ABORTADO')))))
        return out

    def test_ignora_no_completo(self):
        r = am.analizar(self.filas())
        (m,) = [v for (modo, *_), v in r.items() if modo == 'recta']
        self.assertEqual(m['fisico/comandado']['n'], 3)
        self.assertAlmostEqual(m['fisico/comandado']['media'], .96, places=3)

    def test_incluir_todo(self):
        r = am.analizar(self.filas(), incluir_todo=True)
        (m,) = [v for (modo, *_), v in r.items() if modo == 'recta']
        self.assertEqual(m['fisico/comandado']['n'], 4)

    def test_vacio(self):
        self.assertEqual(am.analizar([]), {})


if __name__ == '__main__':
    unittest.main()
