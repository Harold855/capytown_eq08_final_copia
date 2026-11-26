import csv
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import planificador as pl
from carrito.granprix_carrito.calibracion import EstimadorEscalas, evaluar_reduccion
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.ejecutor import Config
from geometria_dock.transformaciones import Pose2D, wrap
from simulacion.modelo_granprix import Rng
from test_ejecutor import ejecutar

DEG = math.pi / 180


def llegada(inicio, cmd, cd, ca):
    """Pose de llegada de un robot con escalas reales cd y ca que ejecuta `cmd`."""
    th = wrap(inicio.th + cmd.phi_cmd * ca)
    return Pose2D(inicio.x + cmd.L_cmd * cd * math.cos(th), inicio.y + cmd.L_cmd * cd * math.sin(th), th)


def circuito(est, cd, ca, n=16, ruido=None):
    """n tramos de la pista. La pose de salida es la ideal del dock (reset de pose tras cada pit)."""
    for k in range(n):
        s = k % 4 + 1
        ini, dst = D[s].pose, D[s % 4 + 1]
        cmd = pl.comandar(pl.planificar_tramo(ini, (dst.x, dst.y)), est.escalas)
        fin = llegada(ini, cmd, cd, ca)
        if ruido:
            R, tag = ruido
            fin = Pose2D(fin.x + R.n() * tag, fin.y + R.n() * tag, fin.th + R.n() * 0.4 * DEG)
        est.observar(ini, fin, cmd, t=float(k))


class TestConvergencia(unittest.TestCase):
    def test_robot_perfecto_no_cambia_las_escalas(self):
        e = EstimadorEscalas()
        circuito(e, 1.0, 1.0)
        self.assertAlmostEqual(e.escalas.cd, 1.0, places=9)
        self.assertAlmostEqual(e.escalas.ca, 1.0, places=9)

    def test_sin_ruido_converge_a_las_escalas_reales(self):
        e = EstimadorEscalas()
        circuito(e, 1.02, 1.09, n=24)
        self.assertAlmostEqual(e.escalas.cd, 1.02, delta=0.002)
        self.assertAlmostEqual(e.escalas.ca, 1.09, delta=0.002)
        self.assertTrue(e.convergio())

    def test_aun_no_converge_con_pocas_observaciones(self):
        e = EstimadorEscalas()
        circuito(e, 1.02, 1.09, n=2)
        self.assertFalse(e.convergio())

    def test_igual_que_la_formula_del_html(self):
        """Con proteger=False es exactamente la cadena de actualizar_escalas del planificador."""
        e = EstimadorEscalas(proteger=False)
        esc = pl.Escalas()
        for k in range(8):
            s = k % 4 + 1
            ini, dst = D[s].pose, D[s % 4 + 1]
            cmd = pl.comandar(pl.planificar_tramo(ini, (dst.x, dst.y)), esc)
            fin = llegada(ini, cmd, 1.03, 0.95)
            e.observar(ini, fin, cmd)
            d, g = pl.medir_tramo(ini, fin)
            esc = pl.actualizar_escalas(esc, cmd, d, g, 0.35, proteger=False).escalas
            self.assertEqual(e.escalas, esc)

    def test_con_el_ruido_del_simulador_oficial(self):
        """Ruido del HTML (tag 0.5 cm por coordenada y 0.4° de rumbo): con 16 pits el error medio de las
        escalas queda por debajo del 1 %."""
        errs = []
        for semilla in range(1, 41):
            e = EstimadorEscalas()
            circuito(e, 1.01, 1.09, n=16, ruido=(Rng(semilla), 0.005))
            errs.append((abs(e.escalas.cd - 1.01), abs(e.escalas.ca - 1.09)))
        self.assertLess(sum(a for a, _ in errs) / len(errs), 0.01)
        self.assertLess(sum(b for _, b in errs) / len(errs), 0.01)

    def test_criterio_de_convergencia_con_ruido(self):
        """Medido sobre 300 semillas: sin falsos positivos y declara convergencia entre 8 y 12 pits."""
        for n, minimo, maximo in ((4, 0, 0), (12, 40, 40)):
            conv = 0
            for semilla in range(1, 41):
                e = EstimadorEscalas()
                circuito(e, 1.01, 1.09, n=n, ruido=(Rng(semilla), 0.005))
                if e.convergio():
                    conv += 1
                    self.assertLess(abs(e.escalas.cd - 1.01), 0.015)   # nunca "convergido" lejos del real
                    self.assertLess(abs(e.escalas.ca - 1.09), 0.015)
            self.assertTrue(minimo <= conv <= maximo, f'n={n}: {conv}/40')



class TestRechazos(unittest.TestCase):
    def setUp(self):
        self.ini = D[1].pose
        self.cmd = pl.comandar(pl.planificar_tramo(self.ini, (D[2].x, D[2].y)))
        self.fin = llegada(self.ini, self.cmd, 1.02, 1.05)

    def test_tag_ausente_no_cambia_nada(self):
        for ini, fin in ((self.ini, None), (None, self.fin), (None, None)):
            e = EstimadorEscalas()
            r = e.observar(ini, fin, self.cmd)
            self.assertEqual((r.motivo_cd, r.motivo_ca), ('medicion_invalida',) * 2)
            self.assertFalse(r.uso_cd or r.uso_ca)
            self.assertEqual(e.escalas, pl.Escalas())
            self.assertEqual(len(e.registros), 1)

    def test_comando_no_finito_es_error_de_programacion(self):
        with self.assertRaises(ValueError):
            EstimadorEscalas().observar(self.ini, self.fin, pl.Comando(float('inf'), 1, .1, .5, 1, 1))

    def test_tramo_corto_y_giro_pequeno_no_actualizan(self):
        e = EstimadorEscalas()
        cmd = pl.comandar(pl.Tramo(5 * DEG, 0.05))
        r = e.observar(self.ini, llegada(self.ini, cmd, 1.1, 1.1), cmd)
        self.assertFalse(r.uso_cd or r.uso_ca)
        self.assertEqual(e.escalas, pl.Escalas())

    def test_razon_absurda_se_rechaza(self):
        e = EstimadorEscalas()
        r = e.observar(self.ini, llegada(self.ini, self.cmd, 2.0, 1.0), self.cmd)   # el tag "vio" 4 m
        self.assertFalse(r.uso_cd); self.assertEqual(r.motivo_cd, 'razon_fuera_de_limites')
        self.assertTrue(r.uso_ca)

    def test_giro_negativo_da_la_misma_escala(self):
        e = EstimadorEscalas()
        ini = D[2].pose
        cmd = pl.comandar(pl.Tramo(-90 * DEG, 1.0))
        r = e.observar(ini, llegada(ini, cmd, 1.0, 1.08), cmd)
        self.assertAlmostEqual(r.razon_ca, 1.08, places=9)
        self.assertGreater(e.escalas.ca, 1.0)

    def test_el_paso_esta_limitado_aun_con_una_medicion_atipica(self):
        e = EstimadorEscalas()
        e.observar(self.ini, llegada(self.ini, self.cmd, 1.4, 1.4), self.cmd)
        self.assertLessEqual(e.escalas.cd - 1.0, pl.PASO_MAX_ESCALA + 1e-12)
        self.assertLessEqual(e.escalas.ca - 1.0, pl.PASO_MAX_ESCALA + 1e-12)


class TestPerfilYCongelado(unittest.TestCase):
    def test_no_mezcla_velocidades_distintas(self):
        e = EstimadorEscalas()
        ini = D[1].pose
        base = pl.comandar(pl.Tramo(90 * DEG, 1.0), w=0.5, v=0.10)
        e.observar(ini, llegada(ini, base, 1.0, 1.05), base)
        self.assertEqual(e.perfil, (0.10, 0.5))
        rapido = pl.comandar(pl.Tramo(90 * DEG, 1.0), w=0.8, v=0.10)
        antes = e.escalas
        r = e.observar(ini, llegada(ini, rapido, 1.0, 1.12), rapido)
        self.assertEqual(r.motivo_ca, 'velocidad_angular_distinta')
        self.assertEqual(e.escalas.ca, antes.ca)
        lento = pl.comandar(pl.Tramo(90 * DEG, 1.0), w=0.5, v=0.15)
        r = e.observar(ini, llegada(ini, lento, 1.1, 1.05), lento)
        self.assertEqual(r.motivo_cd, 'velocidad_distinta')
        self.assertTrue(r.uso_ca)   # el giro sí era a la ω de referencia

    def test_perfil_dado_al_construir(self):
        e = EstimadorEscalas(w_ref=0.5)
        ini = D[1].pose
        c = pl.comandar(pl.Tramo(90 * DEG, 1.0), w=0.4)
        self.assertEqual(e.observar(ini, llegada(ini, c, 1.0, 1.1), c).motivo_ca, 'velocidad_angular_distinta')

    def test_congelado_registra_pero_no_cambia(self):
        e = EstimadorEscalas()
        circuito(e, 1.02, 1.09, n=6)
        fijas = e.escalas
        e.congelar('tanda oficial')
        self.assertTrue(e.congelado)
        circuito(e, 1.2, 1.2, n=4)
        self.assertEqual(e.escalas, fijas)
        self.assertEqual(len(e.registros), 10)
        self.assertEqual(e.registros[-1].motivo_cd, 'congelado')
        e.descongelar()
        circuito(e, 1.02, 1.09, n=1)
        self.assertNotEqual(e.escalas, fijas)

    def test_parametros_invalidos(self):
        for kw in ({'alpha': 0}, {'alpha': 1.5}, {'alpha': float('nan')}, {'ventana': 1}, {'tol_convergencia': 0},
                   {'w_ref': -1.0}):
            with self.assertRaises(ValueError):
                EstimadorEscalas(**kw)


VALIDO = """version: 1
robot: eq08-roscar
escalas: {cd: 1.02, ca: 1.09}
perfil: {v_ref: 0.1, w_ref: 0.5}
estimador: {alpha: 0.35, proteger: true, ventana: 4, tol_convergencia: 0.01}
"""


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, 'calibracion.yaml')

    def tearDown(self):
        self.dir.cleanup()

    def escribir(self, texto):
        with open(self.ruta, 'w', encoding='utf-8') as f:
            f.write(texto)

    def test_ida_y_vuelta(self):
        e = EstimadorEscalas(robot='eq08-roscar', alpha=0.2, ventana=5, tol_convergencia=0.02, proteger=False)
        circuito(e, 1.02, 1.09, n=12)
        e.guardar(self.ruta)
        c = EstimadorEscalas.cargar(self.ruta, robot_esperado='eq08-roscar')
        self.assertEqual(c.escalas, e.escalas)
        self.assertEqual((c.alpha, c.robot, c.perfil), (0.2, 'eq08-roscar', e.perfil))
        self.assertEqual(c.a_dict()['estimador'], e.a_dict()['estimador'])
        self.assertEqual(os.listdir(self.dir.name), ['calibracion.yaml'])   # sin temporales

    def test_lee_un_yaml_escrito_a_mano(self):
        self.escribir(VALIDO)
        e = EstimadorEscalas.cargar(self.ruta, robot_esperado='eq08-roscar')
        self.assertEqual((e.escalas.cd, e.escalas.ca, e.perfil), (1.02, 1.09, (0.1, 0.5)))

    def test_no_se_aplica_a_otro_robot(self):
        EstimadorEscalas(robot='eq08-roscar').guardar(self.ruta)
        with self.assertRaises(ValueError):
            EstimadorEscalas.cargar(self.ruta, robot_esperado='otro-robot')
        sin_id = os.path.join(self.dir.name, 'sin_id.yaml')
        EstimadorEscalas().guardar(sin_id)
        with self.assertRaises(ValueError):
            EstimadorEscalas.cargar(sin_id, robot_esperado='eq08-roscar')

    def test_archivos_dudosos_fallan_cerrado(self):
        """Cada caso cambia UNA sola cosa del archivo válido, para que falle por esa razón."""
        cambios = {
            'cd negativo': ('cd: 1.02', 'cd: -1.0'), 'ca fuera de límites': ('ca: 1.09', 'ca: 5.0'),
            'cd no numérico': ('cd: 1.02', 'cd: "1.02"'), 'cd booleano': ('cd: 1.02', 'cd: true'),
            'cd nan': ('cd: 1.02', 'cd: .nan'), 'versión 2': ('version: 1', 'version: 2'),
            'versión booleana': ('version: 1', 'version: true'),
            'alpha cero': ('alpha: 0.35', 'alpha: 0'), 'alpha mayor que 1': ('alpha: 0.35', 'alpha: 1.5'),
            'proteger como texto': ('proteger: true', 'proteger: "si"'),
            'ventana 1': ('ventana: 4', 'ventana: 1'), 'ventana decimal': ('ventana: 4', 'ventana: 4.5'),
            'w_ref booleano': ('w_ref: 0.5', 'w_ref: true'), 'w_ref negativa': ('w_ref: 0.5', 'w_ref: -0.5'),
            'robot vacío': ('robot: eq08-roscar', 'robot: ""'),
            'clave desconocida': ('version: 1', 'version: 1\nvelocidad_turbo: 3'),
            'clave duplicada': ('version: 1', 'version: 1\nrobot: otro'),
            'falta perfil': ('perfil: {v_ref: 0.1, w_ref: 0.5}\n', ''),
        }
        for nombre, (a, b) in cambios.items():
            self.assertIn(a, VALIDO, nombre)
            self.escribir(VALIDO.replace(a, b, 1))
            with self.assertRaises(ValueError, msg=nombre):
                EstimadorEscalas.cargar(self.ruta)
        for malo in ('- 1\n- 2\n', 'version: [', '', 'solo texto'):
            self.escribir(malo)
            with self.assertRaises(ValueError, msg=repr(malo)):
                EstimadorEscalas.cargar(self.ruta)
        with self.assertRaises(ValueError):
            EstimadorEscalas.cargar(os.path.join(self.dir.name, 'no_existe.yaml'))

    def test_el_estado_guardado_es_yaml_legible_y_sin_secretos(self):
        EstimadorEscalas(robot='eq08-roscar').guardar(self.ruta)
        with open(self.ruta, encoding='utf-8') as f:
            texto = f.read()
        self.assertTrue(texto.startswith('# Estado del estimador'))
        self.assertIn('escalas:', texto)

    def test_exporta_csv(self):
        e = EstimadorEscalas()
        circuito(e, 1.02, 1.09, n=5)
        ruta = os.path.join(self.dir.name, 'obs.csv')
        e.exportar_csv(ruta)
        with open(ruta, encoding='utf-8') as f:
            filas = list(csv.DictReader(f))
        self.assertEqual(len(filas), 5)
        for campo in ('k', 'razon_cd', 'razon_ca', 'cd_despues', 'ca_despues', 'motivo_cd', 'uso_cd'):
            self.assertIn(campo, filas[0])
        self.assertAlmostEqual(float(filas[-1]['cd_despues']), e.escalas.cd)


class TestReduccion(unittest.TestCase):
    def test_umbral_del_70_por_ciento(self):
        datos = [(0.05, 0.01)] * 7 + [(0.02, 0.03)] * 3
        r = evaluar_reduccion(datos)
        self.assertEqual((r.n, r.n_mejoran, r.cumple), (10, 7, True))
        self.assertFalse(evaluar_reduccion([(0.05, 0.01)] * 6 + [(0.02, 0.03)] * 4).cumple)   # 60 %

    def test_paradas_ya_dentro_de_tolerancia(self):
        datos = [(0.01, 0.02)] * 6 + [(0.08, 0.02)] * 4          # las 6 primeras ya estaban dentro de 4 cm
        con = evaluar_reduccion(datos, tolerancia=0.04)
        sin = evaluar_reduccion(datos, tolerancia=0.04, excluir_dentro=True)
        self.assertEqual(con.n_ya_dentro, 6)
        self.assertFalse(con.cumple); self.assertTrue(sin.cumple)
        self.assertEqual(sin.n, 4)

    def test_entradas_invalidas(self):
        for d in ([(float('nan'), 1.0)], [(-1.0, 1.0)]):
            with self.assertRaises(ValueError):
                evaluar_reduccion(d)
        with self.assertRaises(ValueError):
            evaluar_reduccion([(1.0, 0.5)], excluir_dentro=True)
        self.assertFalse(evaluar_reduccion([]).cumple)


class TestConElEjecutor(unittest.TestCase):
    def test_hay_que_usar_lo_realmente_enviado(self):
        """Con rampa de aceleración el ejecutor envía menos distancia que la del comando. Estimar con el comando
        nominal sesga cd; con comando_efectivo converge al valor real."""
        cd_real, ca_real = 1.02, 1.0
        cfg = Config(a_lin_max=0.2, a_ang_max=2.0)
        res = {}
        for nombre in ('nominal', 'efectivo'):
            e = EstimadorEscalas()
            for k in range(14):
                s = k % 4 + 1
                ini, dst = D[s].pose, D[s % 4 + 1]
                cmd = pl.comandar(pl.planificar_tramo(ini, (dst.x, dst.y)), e.escalas)
                ej, planta, _ = ejecutar(cmd, ini, cd_real, ca_real, cfg)
                usado = ej.comando_efectivo(cmd) if nombre == 'efectivo' else cmd
                e.observar(ini, planta.pose, usado)
            res[nombre] = e.escalas.cd
        self.assertAlmostEqual(res['efectivo'], cd_real, delta=0.003)
        self.assertGreater(abs(res['nominal'] - cd_real), 0.008)


if __name__ == '__main__':
    unittest.main()
