import csv
import math
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
from carrito.granprix_carrito import calibracion_tramo as ct
from carrito.granprix_carrito.acople import ConfigAcople, ResultadoAcople, acoplar
from carrito.granprix_carrito.calibracion import EstimadorEscalas
from carrito.granprix_carrito.calibracion_tramo import CalibradorTramo, error_normalizado
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.docks import dock_a_mapa
from carrito.granprix_carrito.planificador import Comando, Escalas, comandar, planificar_tramo
from carrito.granprix_carrito.pose_dock import PoseDock
from geometria_dock.transformaciones import Pose2D
from prueba_calibracion_adaptativa import simular_circuito

CMD = comandar(planificar_tramo(D[1].pose, (D[2].x, D[2].y)))      # E1 -> E2: +90°, 2 m


def pose(dx, dy, deg, est=2):
    return PoseDock(est, dx, dy, math.radians(deg), dock_a_mapa(D[est], dx, dy, deg), 'tag', True)


def acople(pre, post, correcciones=0):
    return ResultadoAcople(post is not None and post.en_tolerancia, None, (), pre, post, 1.0)


def calibrador():
    return CalibradorTramo(EstimadorEscalas(Escalas(), robot='t'))


class TestError(unittest.TestCase):
    def test_normalizado_uno_es_el_limite_del_reto(self):
        self.assertAlmostEqual(error_normalizado(0.04, 0.0), 1.0)
        self.assertAlmostEqual(error_normalizado(0.0, 6.0), 1.0)
        self.assertAlmostEqual(error_normalizado(0.02, 6.0), 1.0)    # manda el peor de los dos
        self.assertAlmostEqual(error_normalizado(0.02, 3.0), 0.5)


class TestObservacion(unittest.TestCase):
    def test_el_estimador_recibe_la_pose_de_llegada_ANTES_del_acople(self):
        c = calibrador()
        salida = D[1].pose
        c.salida(salida)
        c.comando(CMD)
        pre = pose(-0.10, 0.0, 0.0)             # llegó 10 cm corto
        post = pose(0.0, 0.0, 0.0)              # el acople lo dejó en el centro
        reg = c.cerrar_parada(2, acople(pre, post)).registro
        self.assertAlmostEqual(reg.dist_medida, math.hypot(pre.mapa.x - salida.x, pre.mapa.y - salida.y), places=9)
        self.assertAlmostEqual(reg.dist_medida, 1.90, places=9)               # no los 2.00 de la pose corregida
        self.assertAlmostEqual(reg.razon_cd, 0.95, places=9)

    def test_control_negativo_con_la_pose_posterior_se_vería_la_distancia_nominal(self):
        post = pose(0.0, 0.0, 0.0)
        self.assertAlmostEqual(math.hypot(post.mapa.x - D[1].x, post.mapa.y - D[1].y), 2.0, places=9)

    def test_los_movimientos_del_acople_no_alimentan_al_estimador(self):
        c = calibrador()
        c.salida(D[1].pose)
        c.comando(CMD)
        c.cerrar_parada(2, acople(pose(-0.05, 0, 0), pose(0, 0, 0)))
        self.assertEqual(len(c.estimador.registros), 1)
        self.assertEqual(c.estimador.registros[0].L_cmd, CMD.L_cmd)           # solo el comando del tramo

    def test_el_comando_se_consume_no_hay_doble_observacion(self):
        c = calibrador()
        c.salida(D[1].pose)
        c.comando(CMD)
        c.cerrar_parada(2, acople(pose(0, 0, 0), pose(0, 0, 0)))
        p = c.cerrar_parada(2, acople(pose(0, 0, 0), pose(0, 0, 0)))
        self.assertIsNone(p.registro)
        self.assertEqual(len(c.estimador.registros), 1)

    def test_primera_parada_sin_tramo_previo_solo_guarda_errores(self):
        c = calibrador()
        p = c.cerrar_parada(1, acople(pose(0.05, 0, 0, 1), pose(0.0, 0, 0, 1)))
        self.assertIsNone(p.registro)
        self.assertEqual(c.estimador.registros, ())
        self.assertAlmostEqual(p.err_pos_pre_m, 0.05)

    def test_la_salida_del_tramo_siguiente_es_la_medicion_posterior(self):
        c = calibrador()
        post = pose(0.01, 0.0, 0.0)
        c.cerrar_parada(1, acople(pose(0.05, 0, 0, 1), pose(0.0, 0, 0, 1)), post)
        c.comando(CMD)
        c.cerrar_parada(2, acople(pose(0, 0, 0), pose(0, 0, 0)))
        self.assertEqual(c.tramos[-1].inicio, post.mapa)

    def test_sin_medicion_posterior_usa_la_ultima_del_acople(self):
        c = calibrador()
        final = pose(0.005, 0.0, 0.0, 1)
        p = c.cerrar_parada(1, acople(pose(0.05, 0, 0, 1), final), None)
        self.assertAlmostEqual(p.err_pos_post_m, 0.005)
        c.comando(CMD)
        c.cerrar_parada(2, acople(pose(0, 0, 0), pose(0, 0, 0)))
        self.assertEqual(c.tramos[-1].inicio, final.mapa)

    def test_sin_ninguna_pose_final_el_siguiente_tramo_no_se_observa(self):
        c = calibrador()
        c.cerrar_parada(1, ResultadoAcople(False, 'SIN_TAG', (), None, None, 1.0), None)
        c.comando(CMD)
        p = c.cerrar_parada(2, acople(pose(0, 0, 0), pose(0, 0, 0)))
        self.assertEqual(p.registro.motivo_cd, 'medicion_invalida')
        self.assertEqual(c.estimador.escalas, Escalas())

    def test_tag_no_visto_al_llegar_no_cambia_las_escalas(self):
        c = calibrador()
        c.salida(D[1].pose)
        c.comando(CMD)
        p = c.cerrar_parada(2, ResultadoAcople(False, 'SIN_TAG', (), None, None, 1.0), None)
        self.assertEqual(p.registro.motivo_cd, 'medicion_invalida')
        self.assertEqual(c.estimador.escalas, Escalas())
        self.assertIsNone(p.err_pos_pre_m)
        self.assertIsNone(p.error_pre)

    def test_las_escalas_de_la_parada_son_las_posteriores_a_observar(self):
        c = calibrador()
        c.salida(D[1].pose)
        c.comando(replace(CMD))
        p = c.cerrar_parada(2, acople(pose(-0.10, 0, 0), pose(0, 0, 0)))
        self.assertEqual((p.cd, p.ca), (c.estimador.escalas.cd, c.estimador.escalas.ca))
        self.assertLess(p.cd, 1.0)      # llegó corto: la escala de distancia baja


class TestEvaluacion(unittest.TestCase):
    def cargar(self, pares):
        c = calibrador()
        for k, (pre, post) in enumerate(pares):
            c.cerrar_parada(1, acople(pose(pre, 0, 0, 1), pose(post, 0, 0, 1)))
        return c

    def test_fraccion_de_paradas_que_mejoran(self):
        c = self.cargar([(0.10, 0.01), (0.08, 0.02), (0.06, 0.03), (0.05, 0.07)])
        e = c.evaluacion()
        self.assertEqual((e.n, e.n_mejoran), (4, 3))
        self.assertTrue(e.cumple)                    # 75 % >= 70 %

    def test_no_cumple_si_mejoran_menos_del_70(self):
        c = self.cargar([(0.10, 0.01), (0.08, 0.09), (0.06, 0.07)])
        self.assertFalse(c.evaluacion().cumple)

    def test_las_que_ya_llegaron_dentro_se_pueden_excluir(self):
        c = self.cargar([(0.10, 0.01), (0.02, 0.03), (0.01, 0.02), (0.08, 0.02)])
        self.assertEqual(c.evaluacion().n, 4)
        e = c.evaluacion(excluir_dentro=True)
        self.assertEqual((e.n, e.n_mejoran), (2, 2))
        self.assertEqual(c.evaluacion().n_ya_dentro, 2)

    def test_paradas_sin_medicion_se_omiten(self):
        c = self.cargar([(0.10, 0.01)])
        c.cerrar_parada(2, ResultadoAcople(False, 'SIN_TAG', (), None, None, 1.0), None)
        self.assertEqual(c.evaluacion().n, 1)


class TestCsv(unittest.TestCase):
    def test_los_tramos_se_leen_tal_como_se_escribieron(self):
        c = calibrador()
        c.salida(Pose2D(0.4, 0.4, -1.2))
        c.comando(CMD)
        c.cerrar_parada(2, acople(pose(-0.02, 0.01, 2.0), pose(0, 0, 0)), t=12.5)
        c.comando(replace(CMD, L_cmd=1.5, t_avance=15.0))
        c.cerrar_parada(3, ResultadoAcople(False, 'SIN_TAG', (), None, None, 1.0), None)     # llegada sin tag: fin vacío
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 't.csv')
            c.exportar_tramos(ruta)
            leidos = ct.leer_tramos(ruta)
        self.assertEqual(len(leidos), 2)
        a, b = leidos[0], c.tramos[0]
        for x, y in ((a.inicio, b.inicio), (a.fin, b.fin)):
            self.assertAlmostEqual(x.x, y.x, places=9)
            self.assertAlmostEqual(x.th, y.th, places=9)
        self.assertAlmostEqual(a.cmd.L_cmd, CMD.L_cmd, places=9)
        self.assertAlmostEqual(a.cmd.phi_cmd, CMD.phi_cmd, places=9)
        self.assertEqual(a.t, 12.5)
        self.assertIsNone(leidos[1].fin)

    def test_repetir_con_el_mismo_alpha_reproduce_las_escalas(self):
        cal, _ = simular_circuito(vueltas=3, semilla=4)
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 't.csv')
            cal.exportar_tramos(ruta)
            est = EstimadorEscalas(Escalas(), 0.35, v_ref=0.10, w_ref=0.50)
            for tr in ct.leer_tramos(ruta):
                est.observar(tr.inicio, tr.fin, tr.cmd, tr.t)
        self.assertAlmostEqual(est.escalas.cd, cal.estimador.escalas.cd, places=9)
        self.assertAlmostEqual(est.escalas.ca, cal.estimador.escalas.ca, places=9)

    def test_csv_de_tramos_con_comando_invalido_se_rechaza(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 't.csv'
            ruta.write_text('k,t,v,w,L_cmd,phi_cmd,x0,y0,th0,x1,y1,th1\n0,,0.0,0.5,1,1,0,0,0,1,0,0\n')
            with self.assertRaisesRegex(ValueError, 'inválido'):
                ct.leer_tramos(str(ruta))

    def test_paradas_anexar_no_repite_el_encabezado(self):
        c = calibrador()
        c.cerrar_parada(1, acople(pose(0.05, 0, 0, 1), pose(0.0, 0, 0, 1)))
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 'p.csv')
            c.exportar_paradas(ruta, anexar=True)
            c.exportar_paradas(ruta, anexar=True)
            with open(ruta) as f:
                filas = list(csv.reader(f))
            self.assertEqual(len(filas), 3)
            self.assertEqual(filas[0], list(ct.CAMPOS_PARADAS))
            c.exportar_paradas(ruta)                     # sin anexar, sobrescribe
            with open(ruta) as f:
                self.assertEqual(len(list(csv.reader(f))), 2)


class TestLazoCerrado(unittest.TestCase):
    """Circuito completo simulado: tramo, acople, medición, estimador. El robot tiene escalas reales que el controlador desconoce."""

    def test_aprende_las_escalas_reales_y_baja_el_error_de_llegada(self):
        for semilla in range(5):
            cal, _ = simular_circuito(cd=1.01, ca=1.09, vueltas=8, semilla=semilla)
            e = cal.estimador.escalas
            self.assertAlmostEqual(e.cd, 1.01, delta=0.02, msg=semilla)
            self.assertAlmostEqual(e.ca, 1.09, delta=0.02, msg=semilla)
            ps = cal.paradas
            primera = sum(p.err_pos_pre_m for p in ps[:4]) / 4
            ultima = sum(p.err_pos_pre_m for p in ps[-8:]) / 8
            self.assertLess(ultima, primera / 2, msg=semilla)
            self.assertTrue(cal.evaluacion().cumple, msg=semilla)

    def test_la_convergencia_se_declara_en_la_mayoria_de_las_semillas(self):
        n = sum(simular_circuito(vueltas=8, semilla=s)[0].estimador.convergio() for s in range(10))
        self.assertGreaterEqual(n, 7)          # medido: 26 de 30; el criterio es provisional y depende del ruido

    def test_el_estimador_no_aprende_si_se_le_da_la_pose_posterior_al_acople(self):
        """Control negativo: con la pose corregida el tramo parece perfecto y las escalas no se descubren."""
        import prueba_calibracion_adaptativa as pca
        bien = abs(pca.simular_circuito(1.01, 1.09, 6, semilla=2)[0].estimador.escalas.ca - 1.09)

        class MalCalibrador(CalibradorTramo):
            def cerrar_parada(self, estacion, acople, post=None, vuelta=None, t=None):
                return super().cerrar_parada(estacion, replace(acople, pose_inicial=acople.pose_final), post, vuelta, t)
        original = pca.CalibradorTramo
        pca.CalibradorTramo = MalCalibrador
        try:
            mal = abs(pca.simular_circuito(1.01, 1.09, 6, semilla=2)[0].estimador.escalas.ca - 1.09)
        finally:
            pca.CalibradorTramo = original
        self.assertGreater(mal, 2 * bien + 0.01)

    def test_arrancar_con_las_escalas_caracterizadas_evita_la_primera_parada_fuera_de_alcance(self):
        for semilla in range(10):
            sin = simular_circuito(1.01, 1.09, 2, escalas_ini=(1.0, 1.0), semilla=semilla)[0]
            con = simular_circuito(1.01, 1.09, 2, escalas_ini=(1.01, 1.09), semilla=semilla)[0]
            self.assertGreater(sin.paradas[0].err_pos_pre_m, 0.12, msg=semilla)       # 9 % de giro a 2 m son ~28 cm (menos con el ruido)
            self.assertTrue(all(p.exito for p in con.paradas), msg=semilla)


if __name__ == '__main__':
    unittest.main()
