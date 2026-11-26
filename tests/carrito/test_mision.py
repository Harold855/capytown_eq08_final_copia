import csv
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito import mision as ms
from carrito.granprix_carrito.mision import ConfigMision, Mision, Tiempos, cargar_mision
from comun.yaml_estricto import ErrorYaml

SEMILLA = RAIZ / 'carrito' / 'config' / 'mision.yaml'
DEJA = {1: 'A', 2: 'B', 3: 'C', 4: None}


def yaml_con(cambios):
    texto = SEMILLA.read_text(encoding='utf-8')
    for a, b in cambios.items():
        assert a in texto, a
        texto = texto.replace(a, b, 1)
    return texto


def cargar_texto(texto):
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / 'm.yaml'
        ruta.write_text(texto, encoding='utf-8')
        return cargar_mision(str(ruta))


class TestConfig(unittest.TestCase):
    def test_la_semilla_yaml_coincide_con_los_valores_por_defecto(self):
        self.assertEqual(cargar_mision(str(SEMILLA)), ConfigMision())

    def test_no_se_puede_aflojar_el_reto(self):
        with self.assertRaises(ValueError):
            ConfigMision(tiempos=Tiempos(tanda_max_s=721.0))
        with self.assertRaises(ValueError):
            ConfigMision(tiempos=Tiempos(pit_max_s=10.5))
        with self.assertRaises(ErrorYaml):
            cargar_texto(yaml_con({'tanda_max_s: 720.0': 'tanda_max_s: 900.0'}))

    def test_la_cadena_de_piezas_debe_cerrar(self):
        with self.assertRaisesRegex(ErrorYaml, 'no cierra'):
            cargar_texto(yaml_con({'E3: {trae: B, deja: C}': 'E3: {trae: B, deja: D}'}))
        with self.assertRaises(ErrorYaml):
            cargar_texto(yaml_con({'E4: {trae: C, deja: null}': 'E4: {trae: C, deja: A}'}))

    def test_yaml_estricto(self):
        casos = {'clave desconocida': {'vueltas: 4': 'vueltas: 4\nextra: 1'}, 'clave duplicada': {'vueltas: 4': 'vueltas: 4\nvueltas: 3'},
                 'versión': {'version: 1': 'version: 2'}, 'sin estación': {'  E4: {trae: C, deja: null}': ''},
                 'plazo cero': {'midiendo_s: 4.0': 'midiendo_s: 0'}, 'equipo cero': {'equipo: 8 ': 'equipo: 0 '},
                 'vueltas 11': {'vueltas: 4': 'vueltas: 11'}, 'booleano': {'requiere_enlace: true': 'requiere_enlace: si'}}
        for nombre, cambios in casos.items():
            with self.assertRaises(ErrorYaml, msg=nombre):
                cargar_texto(yaml_con(cambios))

    def test_valores_cargados(self):
        c = cargar_texto(yaml_con({'vueltas: 4': 'vueltas: 2', 'enlace_max_s: 2.0': 'enlace_max_s: 1.5', 'reset_reintentos: 3': 'reset_reintentos: 0'}))
        self.assertEqual((c.vueltas, c.seguridad.enlace_max_s, c.tiempos.reset_reintentos), (2, 1.5, 0))


class TestMision(unittest.TestCase):
    def pit(self, m, ok=True, pieza='auto', t=100.0):
        reg = m.abrir_pit(t)
        pieza = m.pieza_deja if pieza == 'auto' else pieza
        return reg, m.cerrar_pit(ok, pieza, t + 8.0)

    def test_recorre_las_16_paradas_en_orden_y_cierra_cuatro_vueltas(self):
        m, orden, cierres = Mision(), [], []
        for k in range(16):
            orden.append((m.vuelta, m.estacion, m.pieza_trae, m.pieza_deja))
            _, (pit, vuelta) = self.pit(m, t=100.0 + 10 * k)
            if vuelta:
                cierres.append((k, vuelta.numero))
            self.assertEqual(pit.mision_completa, k == 15)
        self.assertEqual([e for _, e, _, _ in orden], [1, 2, 3, 4] * 4)
        self.assertEqual([v for v, _, _, _ in orden], [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4)
        self.assertEqual([t for _, _, t, _ in orden[:4]], [None, 'A', 'B', 'C'])
        self.assertEqual([d for _, _, _, d in orden[:4]], ['A', 'B', 'C', None])
        self.assertEqual(cierres, [(3, 1), (7, 2), (11, 3), (15, 4)])
        self.assertTrue(m.completa)
        self.assertEqual(len(m.vueltas), 4)

    def test_no_esta_completa_hasta_cerrar_la_ultima_vuelta(self):
        m = Mision()
        for _ in range(15):
            self.pit(m)
            self.assertFalse(m.completa)
        self.pit(m)
        self.assertTrue(m.completa)

    def test_la_vuelta_lleva_sus_tiempos_y_las_estaciones_validas(self):
        m = Mision()
        for k in range(4):
            self.pit(m, ok=k != 1, pieza=None if k == 1 else 'auto', t=100.0 + 10 * k)
        v = m.vueltas[0]
        self.assertEqual((v.numero, v.t_inicio, v.t_fin), (1, 100.0, 138.0))
        self.assertEqual(v.estaciones, (1, 3, 4))                  # E2 no fue válida
        self.pit(m, t=200.0)
        self.assertEqual(m.t_inicio_vuelta, 200.0)                  # la siguiente vuelta empieza en su primer pit

    def test_resultado_no_ok_y_pieza_inesperada_se_distinguen(self):
        m = Mision()
        _, (pit, _) = self.pit(m, ok=False, pieza=None)
        self.assertEqual((pit.valido, pit.motivo), (False, 'RESULTADO_NO_OK'))
        _, (pit, _) = self.pit(m, pieza='Z')
        self.assertEqual((pit.valido, pit.motivo, pit.pieza_esperada, pit.pieza_recibida), (False, 'PIEZA_INESPERADA', 'B', 'Z'))
        _, (pit, _) = self.pit(m)
        self.assertTrue(pit.valido)

    def test_la_estacion_vacia_exige_pieza_nula(self):
        m = Mision()
        for _ in range(3):
            self.pit(m)
        _, (pit, _) = self.pit(m, pieza='C')                         # E4 debe dejar vacío
        self.assertFalse(pit.valido)

    def test_un_pit_invalido_avanza_la_mision_igual(self):
        m = Mision()
        self.pit(m, ok=False, pieza=None)
        self.assertEqual(m.estacion, 2)
        self.assertEqual(m.pits_invalidos, 1)

    def test_siguiente_estacion_y_reinicio(self):
        m = Mision()
        self.assertEqual(m.siguiente_estacion, 2)
        for _ in range(7):
            self.pit(m)
        self.assertEqual((m.estacion, m.vuelta, m.siguiente_estacion), (4, 2, 1))
        m.reiniciar()
        self.assertEqual((m.estacion, m.vuelta, m.completa, m.pits, m.vueltas), (1, 1, False, [], []))

    def test_una_mision_de_dos_vueltas(self):
        m = Mision(replace(ConfigMision(), vueltas=2))
        for _ in range(7):
            self.pit(m)
        self.assertFalse(m.completa)
        self.pit(m)
        self.assertTrue(m.completa)

    def test_exporta_pits_csv_con_las_columnas_de_la_evidencia(self):
        m = Mision()
        reg, _ = self.pit(m)
        reg.t_pit_s, reg.err_pos_pre_m, reg.cd, reg.valido = 8.1, 0.012, 1.01, True
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 'pits.csv')
            m.exportar_pits(ruta)
            with open(ruta, newline='') as f:
                filas = list(csv.DictReader(f))
        self.assertEqual(list(filas[0]), list(ms.CAMPOS_PITS))
        for c in ('vuelta', 'estacion', 't_llegada', 't_pit_s', 'err_pos_pre_m', 'err_pos_post_m', 'reintentos', 'cd', 'ca'):
            self.assertIn(c, filas[0])
        self.assertEqual((filas[0]['vuelta'], filas[0]['estacion'], float(filas[0]['t_pit_s'])), ('1', '1', 8.1))


if __name__ == '__main__':
    unittest.main()
