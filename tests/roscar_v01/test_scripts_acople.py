"""Pruebas de prueba_acople.py, prueba_calibracion_adaptativa.py y analizar_acople.py.

El modo `ensayo` de prueba_acople.py se prueba contra un rclpy SUSTITUTO y un mundo simulado (escena 3D independiente del tag):
demuestra que el cableado hace lo que el autor cree, no que la API real de ROS 2 esté bien usada.
"""
import contextlib
import csv
import importlib.util
import io
import math
import signal
import sys
import tempfile
import unittest
import xml.dom.minidom as minidom
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(RAIZ / 'tests' / 'carrito'))
import analizar_acople as aa
import prueba_acople as pa
import prueba_calibracion_adaptativa as pca
import ros_falso as rf
from carrito.granprix_carrito.calibracion_tramo import CAMPOS_PARADAS
from carrito.granprix_carrito.gestor_reset import cuaternion_de_dth
from escena_dock import tag_visto
from geometria_dock.transformaciones import Pose2D

MARCOS_SIM = str(RAIZ / 'carrito' / 'config' / 'marcos_sim.yaml')


def correr(modulo, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = modulo.main(list(args))
    return rc, out.getvalue(), err.getvalue()


def leer_csv(ruta):
    with open(ruta, newline='') as f:
        return list(csv.DictReader(f))


class TestPruebaAcopleSimulada(unittest.TestCase):
    def test_simula_y_anexa_paradas_al_csv(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 'sub' / 'p.csv')
            for _ in range(2):
                rc, out, _ = correr(pa, '--csv', ruta, 'simular', '--dx', '-0.06', '--dy', '0.02', '--dth', '8', '--ca', '1.09')
                self.assertEqual(rc, 0)
                self.assertIn('VÁLIDO', out)
            filas = leer_csv(ruta)
            self.assertEqual(len(filas), 2)
            self.assertEqual(list(filas[0]), list(CAMPOS_PARADAS))
            self.assertEqual(filas[0]['exito'], 'True')

    def test_un_robot_que_no_responde_da_codigo_1(self):
        rc, out, _ = correr(pa, 'simular', '--dx', '-0.10', '--cd', '0.01')    # casi no avanza
        self.assertEqual(rc, 1)
        self.assertIn('NO VÁLIDO', out)

    def test_ensayo_fisico_exige_zona_segura(self):
        with self.assertRaises(SystemExit) as c, contextlib.redirect_stderr(io.StringIO()):
            pa.main(['ensayo', '--estacion', '2', '--ejecutar'])
        self.assertEqual(c.exception.code, 2)

    def test_acople_yaml_invalido_da_error_claro(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'a.yaml'
            ruta.write_text('version: 1\n')
            rc, _, err = correr(pa, '--acople', str(ruta), 'simular')
            self.assertEqual(rc, 1)
            self.assertIn('ERROR', err)

    @unittest.skipIf(importlib.util.find_spec('rclpy') is not None, 'hay ROS 2 real: la prueba espera su ausencia')
    def test_sin_ros_el_ensayo_lo_dice(self):
        rc, _, err = correr(pa, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM)
        self.assertEqual(rc, 1)
        self.assertIn('falta ROS 2', err)


class Mundo:
    """Robot en el marco del dock 2; Twist con las escalas reales; tag emulado con la escena 3D independiente."""

    def __init__(self, dx, dy, deg, cd=1.01, ca=1.09, ve_tag=True, odom_hasta=float('inf')):
        self.pose, self.cd, self.ca, self.t = Pose2D(dx, dy, math.radians(deg)), cd, ca, 5000.0
        self.ve_tag, self.odom_hasta, self.nodo, self._tag_t = ve_tag, odom_hasta, None, -1.0
        self.twists = []

    def reloj(self):
        return self.t

    def twist(self):
        pub = next((p for _, t, p in self.nodo.pubs if t == '/cmd_vel'), None)
        if pub is None or not pub.enviados:
            return 0.0, 0.0
        m = pub.enviados[-1]
        return m.linear.x, m.angular.z

    def spin_once(self, nodo, timeout_sec=0):
        dt = max(timeout_sec, 1e-3)
        v, w = self.twist()
        th = self.pose.th + w * self.ca * dt
        self.pose = Pose2D(self.pose.x + v * self.cd * dt * math.cos(th), self.pose.y + v * self.cd * dt * math.sin(th), th)
        self.t += dt
        if self.t < self.odom_hasta:
            nodo.callback('/odom')(rf.Mensaje())
        if self.ve_tag and self.t - self._tag_t >= 0.1:
            self._tag_t = self.t
            x, y, z, dth, _ = tag_visto(self.pose, Pose2D(0.10, 0.0, 0.0), Pose2D(0.38, 0.0, 0.0), math.radians(20.05))
            m = rf.PoseStamped()
            m.pose.position.x, m.pose.position.y, m.pose.position.z = x, y, z
            (m.pose.orientation.x, m.pose.orientation.y, m.pose.orientation.z, m.pose.orientation.w) = cuaternion_de_dth(dth)
            nodo.callback('/tag/pose')(m)

    def dock(self):
        return self.pose.x, self.pose.y, math.degrees(self.pose.th)


class TestEnsayoRos(unittest.TestCase):
    def setUp(self):
        rf.instalar()
        self.senales = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}

    def tearDown(self):
        rf.desinstalar()
        for s, h in self.senales.items():
            signal.signal(s, h)

    def ejecutar(self, mundo, *args):
        crear = rf.Node.__init__

        def init(nodo, nombre):
            crear(nodo, nombre)
            mundo.nodo = nodo
        import rclpy
        with mock.patch.object(rf.Node, '__init__', init), mock.patch('time.monotonic', mundo.reloj), \
                mock.patch.object(rclpy, 'spin_once', mundo.spin_once):
            return correr(pa, *args)

    def test_acopla_con_el_ejecutor_real_y_el_tag_emulado(self):
        mundo = Mundo(-0.06, 0.02, 8.0)
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 'p.csv')
            rc, out, err = self.ejecutar(mundo, '--csv', ruta, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM,
                                         '--ejecutar', '--zona-segura')
            self.assertEqual(rc, 0, msg=out + err)
            dx, dy, deg = mundo.dock()
            self.assertLess(math.hypot(dx, dy), 0.04)
            self.assertLess(abs(deg), 6.0)
            self.assertEqual(leer_csv(ruta)[0]['exito'], 'True')
        pub = next(p for _, t, p in mundo.nodo.pubs if t == '/cmd_vel')
        for m in pub.enviados:
            self.assertLessEqual(abs(m.linear.x), 0.20)
            self.assertLessEqual(abs(m.angular.z), 0.80)
        self.assertEqual((pub.enviados[-1].linear.x, pub.enviados[-1].angular.z), (0.0, 0.0))

    def test_sin_ejecutar_solo_calcula_y_no_crea_publicador(self):
        mundo = Mundo(-0.06, 0.02, 8.0)
        rc, out, _ = self.ejecutar(mundo, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM)
        self.assertIn('SOLO CÁLCULO', out)
        self.assertIn('correccion', out)
        self.assertEqual([t for _, t, _ in mundo.nodo.pubs if t == '/cmd_vel'], [])
        self.assertEqual(mundo.dock(), (-0.06, 0.02, 8.0))

    def test_sin_tag_no_se_mueve_y_no_publica(self):
        mundo = Mundo(-0.06, 0.02, 8.0, ve_tag=False)
        rc, out, err = self.ejecutar(mundo, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM, '--ejecutar', '--zona-segura')
        self.assertEqual(rc, 1)
        self.assertIn('SIN_TAG', out)
        pub = next(p for _, t, p in mundo.nodo.pubs if t == '/cmd_vel')
        self.assertEqual(pub.enviados, [])                      # ni siquiera ceros: no movió ni pisó a nadie

    def test_otro_publicador_de_velocidades_aborta_antes_de_mover(self):
        mundo = Mundo(-0.06, 0.02, 8.0)
        otro = rf.Ns(node_name='otro', node_namespace='/')
        with mock.patch.object(rf.Node, 'get_publishers_info_by_topic', lambda self, t: [otro]):
            rc, _, err = self.ejecutar(mundo, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM, '--ejecutar', '--zona-segura')
        self.assertEqual(rc, 1)
        self.assertIn('publicadores', err)
        self.assertEqual(mundo.dock(), (-0.06, 0.02, 8.0))

    def test_odometria_perdida_durante_el_movimiento_detiene_con_ceros(self):
        mundo = Mundo(-0.10, 0.0, 0.0)
        mundo.odom_hasta = mundo.t + 3.3                     # la odometría se corta en pleno avance (empieza hacia t+3.0)
        rc, out, _ = self.ejecutar(mundo, 'ensayo', '--estacion', '2', '--marcos', MARCOS_SIM, '--ejecutar', '--zona-segura')
        self.assertEqual(rc, 1)
        self.assertIn('ODOM_PERDIDA', out)
        pub = next(p for _, t, p in mundo.nodo.pubs if t == '/cmd_vel')
        self.assertEqual((pub.enviados[-1].linear.x, pub.enviados[-1].angular.z), (0.0, 0.0))

    def test_marcos_sin_medir_da_error_claro(self):
        mundo = Mundo(-0.06, 0.02, 8.0)
        rc, _, err = self.ejecutar(mundo, 'ensayo', '--estacion', '2', '--marcos', str(RAIZ / 'carrito' / 'config' / 'marcos.yaml'))
        self.assertEqual(rc, 1)
        self.assertIn('falta medir', err)


def fila(**kw):
    base = dict(k=0, vuelta=1, estacion=1, err_pos_pre_m=0.10, err_ang_pre_deg=3.0, err_pos_post_m=0.01, err_ang_post_deg=0.5,
                err_norm_pre=2.5, err_norm_post=0.25, correcciones=1, exito=True, motivo='', cd=1.0, ca=1.0, uso_cd=True, uso_ca=True)
    base.update(kw)
    return base


def escribir(ruta, filas):
    with open(ruta, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_PARADAS)
        w.writeheader()
        w.writerows(filas)


class TestAnalizar(unittest.TestCase):
    def test_estadisticas_con_datos_conocidos(self):
        filas = [fila(), fila(err_norm_pre=0.5, err_norm_post=0.4, err_pos_pre_m=0.02, err_pos_post_m=0.016),
                 fila(err_norm_pre=2.0, err_norm_post=3.0, exito=False, correcciones=3, motivo='REINTENTOS_AGOTADOS'),
                 fila(err_norm_pre='', err_norm_post='', err_pos_pre_m='', err_pos_post_m='', err_ang_pre_deg='',
                      err_ang_post_deg='', motivo='SIN_TAG', exito=False, correcciones=0)]
        with tempfile.TemporaryDirectory() as d:
            escribir(Path(d) / 'p.csv', filas)
            e = aa.estadisticas(aa.leer(Path(d) / 'p.csv'))
        self.assertEqual((e['paradas'], e['completas'], e['validas'], e['correcciones']), (4, 3, 2, 5))
        self.assertEqual(e['ya_dentro'], 1)
        self.assertEqual((e['reduccion'].n, e['reduccion'].n_mejoran), (3, 2))
        self.assertEqual((e['reduccion_sin_dentro'].n, e['reduccion_sin_dentro'].n_mejoran), (2, 1))
        self.assertAlmostEqual(e['pos_pre_cm'][0], (10 + 2 + 10) / 3, places=9)
        self.assertEqual(e['motivos']['SIN_TAG'], 1)

    def test_percentil_por_rango_mas_cercano(self):
        self.assertEqual(aa.percentil(list(range(1, 21))), 19)
        self.assertEqual(aa.percentil([5.0]), 5.0)
        self.assertEqual(aa.percentil([3, 1, 2], 0.5), 2)
        self.assertIsNone(aa.percentil([]))

    def test_escribe_graficos_svg_validos_y_resumen(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'p.csv'
            escribir(ruta, [fila(k=i, cd=1.0 + 0.01 * i, ca=1.0 + 0.02 * i) for i in range(5)])
            rc, out, _ = correr(aa, str(ruta), '--salida', str(Path(d) / 'g'))
            self.assertEqual(rc, 0)
            self.assertIn('CUMPLE', out)
            for nombre in ('acople_errores.svg', 'escalas.svg'):
                dom = minidom.parse(str(Path(d) / 'g' / nombre))
                self.assertEqual(dom.documentElement.tagName, 'svg')
            barras = (Path(d) / 'g' / 'acople_errores.svg').read_text()
            self.assertEqual(barras.count('fill="#999"'), 5 + 1)          # 5 barras + 1 muestra de la leyenda

    def test_una_sola_parada_y_series_constantes_no_rompen(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'p.csv'
            escribir(ruta, [fila()])
            rc, _, err = correr(aa, str(ruta), '--salida', str(Path(d) / 'g'))
            self.assertEqual(rc, 0, msg=err)

    def test_archivo_inexistente_vacio_o_con_otro_formato(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(correr(aa, str(Path(d) / 'no.csv'))[0], 1)
            vacio = Path(d) / 'v.csv'
            escribir(vacio, [])
            self.assertEqual(correr(aa, str(vacio))[0], 1)
            malo = Path(d) / 'm.csv'
            malo.write_text('a,b\n1,2\n')
            rc, _, err = correr(aa, str(malo))
            self.assertEqual(rc, 1)
            self.assertIn('faltan columnas', err)
            texto = Path(d) / 't.csv'
            escribir(texto, [fila(err_norm_pre='abc')])
            self.assertEqual(correr(aa, str(texto))[0], 1)

    def test_lee_lo_que_escribe_prueba_calibracion_adaptativa(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = str(Path(d) / 'p.csv')
            self.assertEqual(correr(pca, 'simular', '--vueltas', '4', '--csv-paradas', ruta)[0], 0)
            rc, out, _ = correr(aa, ruta)
            self.assertEqual(rc, 0)
            self.assertIn('Paradas: 16', out)


class TestCalibracionAdaptativa(unittest.TestCase):
    def test_simular_resume_y_guarda_csv(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, _ = correr(pca, 'simular', '--vueltas', '6', '--csv-paradas', str(Path(d) / 'p.csv'),
                                '--csv-tramos', str(Path(d) / 't.csv'))
            self.assertEqual(rc, 0)
            self.assertIn('Escalas finales', out)
            self.assertEqual(len(leer_csv(Path(d) / 'p.csv')), 24)
            self.assertEqual(len(leer_csv(Path(d) / 't.csv')), 24)

    def test_repetir_reproduce_y_permite_otro_alpha(self):
        with tempfile.TemporaryDirectory() as d:
            t = str(Path(d) / 't.csv')
            correr(pca, 'simular', '--vueltas', '6', '--semilla', '3', '--csv-tramos', t)
            rc, out, _ = correr(pca, 'repetir', '--tramos', t, '--alpha', '0.2', '0.35', '0.5')
            self.assertEqual(rc, 0)
            self.assertEqual(out.count('alpha='), 3)
            for linea in out.splitlines():
                cd = float(linea.split('cd=')[1].split()[0])
                self.assertAlmostEqual(cd, 1.01, delta=0.03)

    def test_argumentos_invalidos(self):
        for args in (('simular', '--vueltas', '0'), ('simular', '--alpha', '1.5'), ('simular', '--cd', '0')):
            with self.assertRaises(SystemExit) as c, contextlib.redirect_stderr(io.StringIO()):
                pca.main(list(args))
            self.assertEqual(c.exception.code, 2)
        self.assertEqual(correr(pca, 'repetir', '--tramos', '/no/existe.csv')[0], 1)


if __name__ == '__main__':
    unittest.main()
