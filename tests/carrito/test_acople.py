import dataclasses
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import acople as ac
from carrito.granprix_carrito.acople import ConfigAcople, MedidorTag, acoplar, planificar_correccion
from carrito.granprix_carrito.configuracion import cargar_carrito
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.docks import dock_a_mapa, mapa_a_dock
from carrito.granprix_carrito.ejecutor import Config, Estado, Resultado
from carrito.granprix_carrito.planificador import Escalas
from carrito.granprix_carrito.pose_dock import PoseDock
from comun.yaml_estricto import ErrorYaml
from geometria_dock.transformaciones import Pose2D, desde_grados
from simulacion.robot_simulado import RobotSimulado
from test_ejecutor import Planta, Reloj

SEMILLA = RAIZ / 'carrito' / 'config' / 'acople.yaml'
CFG = ConfigAcople()


def pose(dx, dy, deg, est=1):
    return PoseDock(est, dx, dy, math.radians(deg), dock_a_mapa(D[est], dx, dy, deg), 'tag', True)


def robot(dx, dy, deg, **kw):
    r = RobotSimulado(Pose2D(0, 0, 0), 1, **kw)
    r.colocar_en_dock(dx, dy, deg)
    return r


def completo(cmd):
    return cmd, Resultado(Estado.COMPLETO, None, cmd.L_cmd, cmd.phi_cmd, cmd.t_total)


class Guion:
    """medir() devuelve lo guionado; mover() no mueve nada y cuenta las llamadas."""

    def __init__(self, poses, resultado=None, avanzar=1.0):
        self.poses, self.llamadas_mover, self.llamadas_medir, self.t, self.avanzar = list(poses), [], 0, 0.0, avanzar
        self.resultado = resultado

    def medir(self):
        self.llamadas_medir += 1
        return self.poses.pop(0) if len(self.poses) > 1 else self.poses[0]

    def mover(self, cmd):
        self.llamadas_mover.append(cmd)
        self.t += self.avanzar
        if self.resultado is not None:
            return cmd, self.resultado
        return completo(cmd)

    def reloj(self):
        return self.t


class TestConfig(unittest.TestCase):
    def test_los_valores_por_defecto_son_validos(self):
        self.assertEqual(CFG.reintentos, 2)

    def test_no_se_puede_aflojar_el_reto(self):
        for kw in (dict(tol_pos_m=0.05), dict(tol_ang_deg=7.0), dict(reintentos=3), dict(v=0.21), dict(w=0.81)):
            with self.assertRaises(ValueError, msg=str(kw)):
                ConfigAcople(**kw)

    def test_valores_invalidos(self):
        for kw in (dict(ganancia_pos=1.2), dict(ganancia_ang=0.0), dict(reversa_max_m=-0.01), dict(lecturas_max=0),
                   dict(presupuesto_s=0.0), dict(error_max_m=float('nan')), dict(reintentos=-1)):
            with self.assertRaises(ValueError, msg=str(kw)):
                ConfigAcople(**kw)

    def test_la_semilla_yaml_carga_y_coincide_con_los_valores_por_defecto(self):
        mov, _ = cargar_carrito()
        self.assertEqual(ac.cargar_acople(str(SEMILLA), mov), CFG)

    def test_velocidad_distinta_a_movimiento_se_rechaza(self):
        mov, _ = cargar_carrito()
        texto = SEMILLA.read_text().replace('v: 0.10', 'v: 0.08')
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'a.yaml'
            ruta.write_text(texto)
            with self.assertRaisesRegex(ErrorYaml, 'no coincide'):
                ac.cargar_acople(str(ruta), mov)
            self.assertEqual(ac.cargar_acople(str(ruta)).v, 0.08)    # sin movimiento no se compara

    def test_yaml_estricto(self):
        casos = {'tolerancia mayor que el reto': SEMILLA.read_text().replace('pos_m: 0.03', 'pos_m: 0.05'),
                 'clave desconocida': SEMILLA.read_text().replace('reintentos: 2', 'reintentos: 2\nextra: 1'),
                 'clave duplicada': SEMILLA.read_text().replace('reintentos: 2', 'reintentos: 2\nreintentos: 1'),
                 'tres reintentos': SEMILLA.read_text().replace('reintentos: 2', 'reintentos: 3'),
                 'sección faltante': SEMILLA.read_text().replace('minimos:', 'otros:')}
        with tempfile.TemporaryDirectory() as d:
            for nombre, texto in casos.items():
                ruta = Path(d) / 'a.yaml'
                ruta.write_text(texto)
                with self.assertRaises(ErrorYaml, msg=nombre):
                    ac.cargar_acople(str(ruta))

    def test_presupuesto_null_significa_sin_limite(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / 'a.yaml'
            ruta.write_text(SEMILLA.read_text().replace('presupuesto_s: 4.0', 'presupuesto_s: null'))
            self.assertIsNone(ac.cargar_acople(str(ruta)).presupuesto_s)


class TestPlan(unittest.TestCase):
    def test_dentro_de_tolerancia_no_corrige_y_no_mueve(self):
        g = Guion([pose(0.02, -0.01, 3.0)])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertTrue(r.exito)
        self.assertIsNone(r.motivo)
        self.assertEqual((r.correcciones, g.llamadas_mover), (0, []))

    def test_solo_angulo_gira_en_sentido_contrario_al_error(self):
        for deg in (10.0, -10.0):
            (c,) = planificar_correccion(pose(0.01, 0.0, deg), Escalas(), CFG)
            self.assertAlmostEqual(math.degrees(c.phi_cmd), -deg, places=6)
            self.assertEqual(c.L_cmd, 0.0)

    def test_detras_del_dock_avanza_sin_giro_final(self):
        (c,) = planificar_correccion(pose(-0.08, 0.0, 0.0), Escalas(), CFG)
        self.assertAlmostEqual(c.L_cmd, 0.08, places=9)
        self.assertAlmostEqual(c.phi_cmd, 0.0, places=9)

    def test_sobrepaso_corto_usa_marcha_atras(self):
        (c,) = planificar_correccion(pose(0.07, 0.0, 0.0), Escalas(), CFG)
        self.assertAlmostEqual(c.L_cmd, -0.07, places=9)
        self.assertGreater(c.t_avance, 0)                      # la duración sigue siendo positiva
        self.assertAlmostEqual(c.t_avance, 0.7, places=9)

    def test_sobrepaso_largo_no_gira_180(self):
        g = Guion([pose(0.20, 0.0, 0.0)])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertEqual(r.motivo, 'GIRO_EXCESIVO')    # 0.20 m > reversa_max_m: habría que girar casi 180°
        self.assertEqual(g.llamadas_mover, [])

    def test_sin_reversa_el_sobrepaso_corto_tambien_se_rechaza(self):
        g = Guion([pose(0.07, 0.0, 0.0)])
        r = acoplar(g.medir, g.mover, dataclasses.replace(CFG, reversa_max_m=0.0), reloj=g.reloj)
        self.assertEqual(r.motivo, 'GIRO_EXCESIVO')

    def test_compensa_con_las_escalas(self):
        (a,) = planificar_correccion(pose(-0.08, 0.0, 0.0), Escalas(), CFG)
        (b,) = planificar_correccion(pose(-0.08, 0.0, 0.0), Escalas(cd=1.25), CFG)
        self.assertAlmostEqual(b.L_cmd, a.L_cmd / 1.25, places=9)
        (a,) = planificar_correccion(pose(0.0, 0.0, 10.0), Escalas(), CFG)
        (b,) = planificar_correccion(pose(0.0, 0.0, 10.0), Escalas(ca=1.1), CFG)
        self.assertAlmostEqual(b.phi_cmd, a.phi_cmd / 1.1, places=9)

    def test_la_ganancia_escala_el_avance_y_el_giro_final(self):
        medio = dataclasses.replace(CFG, ganancia_pos=0.5, ganancia_ang=0.5)
        a = planificar_correccion(pose(-0.08, 0.04, 10.0), Escalas(), CFG)
        b = planificar_correccion(pose(-0.08, 0.04, 10.0), Escalas(), medio)
        self.assertEqual(len(a), 2)
        self.assertAlmostEqual(b[0].L_cmd, a[0].L_cmd * 0.5, places=9)
        self.assertAlmostEqual(b[0].phi_cmd, a[0].phi_cmd, places=9)           # el giro de alineación no se escala
        self.assertAlmostEqual(b[1].phi_cmd, a[1].phi_cmd * 0.5, places=9)

    def test_ningun_comando_supera_los_limites_del_reto(self):
        rng = random.Random(1)
        for _ in range(300):
            p = pose(rng.uniform(-0.28, 0.1), rng.uniform(-0.2, 0.2), rng.uniform(-44, 44))
            try:
                cmds = planificar_correccion(p, Escalas(1.1, 0.9), CFG)
            except ac._Rechazo:
                continue
            for c in cmds:
                self.assertLessEqual(c.v, 0.20)
                self.assertLessEqual(abs(c.w), 0.80)
                self.assertGreaterEqual(c.t_giro, 0)
                self.assertGreaterEqual(c.t_avance, 0)
                self.assertLessEqual(abs(math.degrees(c.phi_cmd)), CFG.giro_max_deg / 0.9 + 1e-6)


class TestCiclo(unittest.TestCase):
    def test_signos_y_geometria_de_extremo_a_extremo_contra_el_robot_simulado(self):
        """El robot simulado integra su propia cinemática: no comparte código con planificar_acople."""
        for dx in (-0.12, -0.05, 0.0, 0.03, 0.08):
            for dy in (-0.05, 0.0, 0.04):
                for deg in (-15.0, 0.0, 9.0):
                    r = robot(dx, dy, deg)
                    res = acoplar(r.medir, r.mover, CFG, reloj=r.reloj)
                    self.assertTrue(res.exito, msg=(dx, dy, deg, res.motivo))
                    self.assertLessEqual(res.correcciones, 1, msg=(dx, dy, deg))
                    p = res.pose_final
                    self.assertLess(math.hypot(p.dx, p.dy), 0.005, msg=(dx, dy, deg))
                    self.assertLess(abs(p.dth_deg), 0.5, msg=(dx, dy, deg))

    def test_control_negativo_un_robot_con_el_giro_invertido_no_converge(self):
        r = robot(-0.06, 0.03, 8.0, ca=-1.0)
        res = acoplar(r.medir, r.mover, CFG, reloj=r.reloj)
        self.assertFalse(res.exito)

    def test_con_escalas_reales_desconocidas_converge_en_pocas_correcciones(self):
        res = acoplar(*(lambda r: (r.medir, r.mover))(robot(-0.08, 0.03, 10.0, cd=1.01, ca=1.09)), CFG, Escalas())
        self.assertTrue(res.exito)
        self.assertLessEqual(res.correcciones, 2)

    def test_montecarlo_con_ruido_de_movimiento_y_del_tag(self):
        rng = random.Random(11)
        n, ok, corr = 300, 0, 0
        for i in range(n):
            r = robot(rng.uniform(-0.10, 0.04), rng.uniform(-0.05, 0.05), rng.uniform(-12, 12), cd=1.01, ca=1.09,
                      ruido_d=0.01, ruido_a=0.01, ruido_tag_m=0.002, ruido_tag_deg=0.25, semilla=i)
            res = acoplar(r.medir, r.mover, CFG, Escalas(), r.reloj)
            ok += res.exito
            corr += res.correcciones
            if res.exito:                       # la medición decide, pero la pose verdadera no debe estar lejos del reto
                dx, dy, deg = mapa_a_dock(D[1], r.pose)
                self.assertLess(math.hypot(dx, dy), 0.045)
                self.assertLess(abs(deg), 6.5)
        self.assertGreaterEqual(ok / n, 0.98)
        self.assertLessEqual(corr / n, 1.5)

    def test_reintentos_agotados_hace_exactamente_1_mas_reintentos_correcciones(self):
        for reintentos in (0, 1, 2):
            g = Guion([pose(-0.10, 0.0, 0.0)])
            r = acoplar(g.medir, g.mover, dataclasses.replace(CFG, reintentos=reintentos, presupuesto_s=None), reloj=g.reloj)
            self.assertEqual(r.correcciones, 1 + reintentos)
            self.assertEqual(r.motivo, 'REINTENTOS_AGOTADOS')
            self.assertFalse(r.exito)
            self.assertEqual(len(g.llamadas_mover), 1 + reintentos)       # sin movimiento oculto

    def test_en_borde_cuenta_como_exito_pero_se_distingue(self):
        g = Guion([pose(-0.036, 0.0, 0.0)])     # fuera del margen interno (3 cm) y dentro del reto (4 cm)
        r = acoplar(g.medir, g.mover, dataclasses.replace(CFG, reintentos=0), reloj=g.reloj)
        self.assertTrue(r.exito)
        self.assertEqual(r.motivo, 'EN_BORDE')

    def test_el_limite_exacto_del_reto_es_valido(self):
        g = Guion([pose(-0.04, 0.0, 0.0)])
        r = acoplar(g.medir, g.mover, dataclasses.replace(CFG, reintentos=0), reloj=g.reloj)
        self.assertTrue(r.exito)

    def test_sin_tag_al_inicio_no_se_mueve(self):
        g = Guion([None])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertEqual((r.motivo, r.exito, g.llamadas_mover), ('SIN_TAG', False, []))
        self.assertEqual(g.llamadas_medir, CFG.lecturas_max)

    def test_un_tag_perdido_un_instante_se_reintenta_la_lectura(self):
        g = Guion([None, None, pose(0.01, 0.0, 0.0)])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertTrue(r.exito)

    def test_tag_perdido_tras_corregir_no_afirma_exito(self):
        g = Guion([pose(-0.10, 0.0, 0.0), None])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertEqual(r.motivo, 'SIN_TAG')
        self.assertFalse(r.exito)
        self.assertIsNone(r.pose_final)
        self.assertEqual(len(g.llamadas_mover), 1)

    def test_fuera_de_alcance_no_se_mueve(self):
        for p in (pose(-0.35, 0.0, 0.0), pose(0.0, 0.31, 0.0), pose(-0.05, 0.0, 50.0)):
            g = Guion([p])
            r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
            self.assertEqual((r.motivo, g.llamadas_mover), ('FUERA_DE_ALCANCE', []))

    def test_presupuesto_de_tiempo_impide_otra_correccion(self):
        g = Guion([pose(-0.10, 0.0, 0.0)], avanzar=3.0)
        r = acoplar(g.medir, g.mover, dataclasses.replace(CFG, presupuesto_s=2.0), reloj=g.reloj)
        self.assertEqual((r.motivo, r.correcciones), ('SIN_TIEMPO', 1))

    def test_parada_externa_antes_de_mover(self):
        g = Guion([pose(-0.10, 0.0, 0.0)])
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj, debe_parar=lambda: True)
        self.assertEqual((r.motivo, g.llamadas_mover), ('PARADA_EXTERNA', []))

    def test_movimiento_abortado_detiene_el_acople_y_no_afirma_pose(self):
        g = Guion([pose(-0.10, 0.0, 0.0)], resultado=Resultado(Estado.ABORTADO, 'ODOM_PERDIDA', 0.0, 0.0, 0.1))
        r = acoplar(g.medir, g.mover, CFG, reloj=g.reloj)
        self.assertEqual(r.motivo, 'MOVIMIENTO_ODOM_PERDIDA')
        self.assertFalse(r.exito)
        self.assertIsNone(r.pose_final)
        self.assertEqual(len(g.llamadas_mover), 1)
        self.assertEqual(g.llamadas_medir, 1)     # solo la medición inicial: tras un movimiento fallido no se vuelve a medir

    def test_comando_rechazado_por_el_ejecutor(self):
        def mover(cmd):
            raise ValueError('límites')
        r = acoplar(lambda: pose(-0.1, 0, 0), mover, CFG)
        self.assertEqual((r.motivo, r.exito, r.pose_final), ('COMANDO_INVALIDO', False, None))

    def test_registra_lo_enviado_y_lo_medido_en_cada_intento(self):
        r = robot(-0.08, 0.02, 6.0, cd=1.01, ca=1.09)
        res = acoplar(r.medir, r.mover, CFG, reloj=r.reloj)
        i = res.intentos[0]
        self.assertEqual(i.n, 1)
        self.assertIs(i.pose_antes, res.pose_inicial)
        self.assertEqual(len(i.efectivos), len(i.comandos))
        self.assertIs(i.pose_despues, res.pose_final)


class TestIntegracionConElEjecutor(unittest.TestCase):
    """Ejecutor real con una planta continua (escalas reales, giro y avance por tiempo) y un reloj falso."""

    def correr(self, dx, dy, deg, cd=1.01, ca=1.09, escalas=Escalas(1.01, 1.09), cfg=CFG):
        reloj = Reloj()
        planta = Planta(reloj, dock_a_mapa(D[1], dx, dy, deg), cd, ca)

        def medir():
            q = planta.hasta_ahora()
            ex, ey, edeg = mapa_a_dock(D[1], q)
            return PoseDock(1, ex, ey, math.radians(edeg), q, 'tag', True)

        mover = ac.mover_con_ejecutor(planta, reloj, reloj.dormir, Config(), cfg)
        return acoplar(medir, mover, cfg, escalas, reloj), planta

    def test_converge_con_el_ejecutor_real(self):
        res, planta = self.correr(-0.06, 0.02, 8.0)
        self.assertTrue(res.exito)
        self.assertEqual(res.correcciones, 1)
        self.assertLess(math.hypot(res.pose_final.dx, res.pose_final.dy), 0.006)
        self.assertLess(abs(res.pose_final.dth_deg), 0.8)
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))

    def test_marcha_atras_real_por_el_ejecutor(self):
        res, planta = self.correr(0.07, 0.0, 0.0)
        self.assertTrue(res.exito)
        self.assertLess(min(v for _, v, _ in planta.publicado), 0)
        self.assertLess(abs(res.pose_final.dx), 0.006)

    def test_nunca_se_publica_por_encima_de_los_limites(self):
        res, planta = self.correr(-0.10, 0.04, 12.0, cd=0.9, ca=0.9, escalas=Escalas())
        for _, v, w in planta.publicado:
            self.assertLessEqual(abs(v), 0.20 + 1e-12)
            self.assertLessEqual(abs(w), 0.80 + 1e-12)
        self.assertLessEqual(res.correcciones, 3)

    def test_marcha_atras_solo_si_la_configuracion_la_permite(self):
        res, planta = self.correr(0.07, 0.0, 0.0, cfg=dataclasses.replace(CFG, reversa_max_m=0.0))
        self.assertEqual(res.motivo, 'GIRO_EXCESIVO')
        self.assertEqual(planta.publicado, [])

    def test_movimiento_abortado_por_el_ejecutor_se_propaga(self):
        reloj = Reloj()
        planta = Planta(reloj, dock_a_mapa(D[1], -0.1, 0, 0), 1.0, 1.0)
        mover = ac.mover_con_ejecutor(planta, reloj, reloj.dormir, Config(), CFG, odom_ok=lambda: False)
        res = acoplar(lambda: pose(-0.1, 0, 0), mover, CFG, reloj=reloj)
        self.assertEqual(res.motivo, 'MOVIMIENTO_ODOM_PERDIDA')
        self.assertFalse(res.exito)

    def test_al_parar_se_avisa_despues_de_cada_movimiento(self):
        reloj, avisos = Reloj(), []
        planta = Planta(reloj, dock_a_mapa(D[1], -0.1, 0, 0), 1.0, 1.0)
        mover = ac.mover_con_ejecutor(planta, reloj, reloj.dormir, Config(), CFG, al_parar=lambda: avisos.append(reloj()))
        mover(planificar_correccion(pose(-0.1, 0, 0), Escalas(), CFG)[0])
        self.assertEqual(len(avisos), 1)
        self.assertGreater(avisos[0], 100.0 + 1.0)      # después de avanzar 10 cm a 0.1 m/s


class TestMedidorTag(unittest.TestCase):
    def hacer(self, llegadas, **kw):
        """llegadas: [(t, PoseDock)] que `dormir` entrega al pasar el tiempo."""
        t = [0.0]
        pendientes = sorted(llegadas, key=lambda x: x[0])
        m = None

        def dormir(s):
            t[0] += s
            while pendientes and pendientes[0][0] <= t[0] + 1e-9:
                m.agregar(pendientes.pop(0)[1])
        m = MedidorTag(lambda: t[0], dormir, **kw)
        return m, t

    def test_ignora_lecturas_anteriores_al_reposo(self):
        m, t = self.hacer([], lecturas=2, espera_s=0.8, timeout_s=3.0)
        t[0] = 1.0
        m.agregar(pose(0.5, 0.0, 0.0))        # vieja: llegó antes de que el robot quedara quieto
        m.en_reposo()                          # reposo en t=1.0 -> se aceptan lecturas desde 1.8
        m.agregar(pose(0.4, 0.0, 0.0))        # llegó en t=1.0, durante la espera: tampoco vale
        self.assertIsNone(m.medir())           # con las dos viejas bastaría para `lecturas=2`: no deben contar

    def test_acepta_lecturas_a_partir_del_final_de_la_espera(self):
        m, t = self.hacer([(1.8, pose(0.01, 0, 0)), (1.9, pose(0.02, 0, 0))], lecturas=2, espera_s=0.8, timeout_s=3.0)
        t[0] = 1.0
        m.en_reposo()
        self.assertAlmostEqual(m.medir().dx, 0.015, places=9)

    def test_devuelve_la_mediana_de_las_lecturas_nuevas(self):
        poses = [pose(0.010, 0.0, 0.0), pose(0.50, 0.3, 30.0), pose(0.012, 0.0, 0.0), pose(0.011, 0.0, 0.0)]
        m, t = self.hacer([(2.0 + 0.1 * i, p) for i, p in enumerate(poses)], lecturas=3, espera_s=0.8, timeout_s=3.0)
        m.en_reposo()                          # t=0 -> desde 0.8
        p = m.medir()
        self.assertAlmostEqual(p.dx, 0.012, places=9)      # últimas 3 = 0.50, 0.012, 0.011 -> mediana 0.012
        self.assertAlmostEqual(p.dth_deg, 0.0, places=9)

    def test_la_mediana_descarta_un_atipico(self):
        poses = [pose(0.010, 0.0, 0.0), pose(0.50, 0.3, 30.0), pose(0.012, 0.0, 0.0)]
        m, _ = self.hacer([(2.0 + 0.1 * i, p) for i, p in enumerate(poses)], lecturas=3, espera_s=0.8)
        m.en_reposo()
        p = m.medir()
        self.assertAlmostEqual(p.dx, 0.012, places=9)
        self.assertAlmostEqual(p.dy, 0.0, places=9)

    def test_mapa_es_coherente_con_la_pose_en_el_dock(self):
        poses = [pose(0.02, -0.01, 3.0, 4)] * 3
        m, _ = self.hacer([(1.0 + 0.1 * i, p) for i, p in enumerate(poses)], lecturas=3, espera_s=0.0)
        p = m.medir()
        esperado = dock_a_mapa(D[4], 0.02, -0.01, 3.0)
        self.assertAlmostEqual(p.mapa.x, esperado.x, places=9)
        self.assertAlmostEqual(math.sin(p.mapa.th), math.sin(esperado.th), places=9)

    def test_sin_lecturas_devuelve_none_al_terminar_el_tiempo(self):
        m, t = self.hacer([], lecturas=2, timeout_s=1.0, espera_s=0.5)
        m.en_reposo()
        self.assertIsNone(m.medir())
        self.assertGreaterEqual(t[0], 1.5 - 0.05)

    def test_parametros_invalidos(self):
        for kw in (dict(lecturas=0), dict(espera_s=-1), dict(timeout_s=0)):
            with self.assertRaises(ValueError):
                MedidorTag(lambda: 0.0, lambda s: None, **kw)


class TestGeneradores(unittest.TestCase):
    """`acoplar_pasos` es lo que avanza la máquina del pit un paso por tick: mismo resultado que el bloqueante, sin esperar."""

    def en_pasos(self, r, **kw):
        n = {'yields': 0, 'medir': 0, 'mover': 0}

        def medir():
            n['medir'] += 1
            yield
            return r.medir()

        def mover(cmd):
            n['mover'] += 1
            yield
            return r.mover(cmd)
        gen = ac.acoplar_pasos(medir, mover, CFG, Escalas(), r.reloj, **kw)
        try:
            while True:
                next(gen)
                n['yields'] += 1
        except StopIteration as fin:
            return fin.value, n

    def test_mismo_resultado_que_la_version_bloqueante(self):
        for i in range(10):
            a, b = robot(-0.08, 0.03, 9.0, cd=1.01, ca=1.09, ruido_d=0.01, ruido_a=0.01, ruido_tag_m=0.002, semilla=i), \
                robot(-0.08, 0.03, 9.0, cd=1.01, ca=1.09, ruido_d=0.01, ruido_a=0.01, ruido_tag_m=0.002, semilla=i)
            bloq = acoplar(a.medir, a.mover, CFG, Escalas(), a.reloj)
            gen, n = self.en_pasos(b)
            self.assertEqual((gen.exito, gen.motivo, gen.correcciones), (bloq.exito, bloq.motivo, bloq.correcciones))
            self.assertEqual(gen.pose_final, bloq.pose_final)
            self.assertEqual(n['yields'], n['medir'] + n['mover'])        # cada espera cede el control

    def test_con_pose_inicial_no_repite_la_primera_medicion(self):
        r = robot(0.01, 0.0, 1.0)
        res, n = self.en_pasos(r, pose_inicial=r.medir())
        self.assertTrue(res.exito)
        self.assertEqual(n['medir'], 0)

    def test_correr_devuelve_el_valor_y_duerme_entre_pasos(self):
        dormidas = []

        def g():
            yield
            yield
            return 7
        self.assertEqual(ac.correr(g(), dormidas.append, 0.05), 7)
        self.assertEqual(dormidas, [0.05, 0.05])

    def test_cancelar_a_mitad_del_movimiento_publica_cero(self):
        reloj = Reloj()
        planta = Planta(reloj, dock_a_mapa(D[1], -0.2, 0, 0), 1.0, 1.0)
        mover = ac.mover_con_ejecutor(planta, reloj, None, Config(), CFG)
        gen = mover(planificar_correccion(pose(-0.2, 0, 0), Escalas(), CFG)[0])
        for _ in range(10):
            next(gen)
            reloj.dormir(0.05)
        self.assertGreater(planta.publicado[-1][1], 0.0)             # avanzando
        gen.close()
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))

    def test_un_comando_rechazado_no_publica_nada(self):
        reloj = Reloj()
        planta = Planta(reloj, dock_a_mapa(D[1], -0.2, 0, 0), 1.0, 1.0)
        mover = ac.mover_con_ejecutor(planta, reloj, None, Config(), CFG)
        malo = dataclasses.replace(planificar_correccion(pose(-0.2, 0, 0), Escalas(), CFG)[0], v=0.5)
        with self.assertRaises(ValueError):
            next(mover(malo))
        self.assertEqual(planta.publicado, [])


class TestMedidorSinEspera(unittest.TestCase):
    def test_intentar_no_bloquea_y_exige_lecturas_posteriores_al_reposo(self):
        t = [0.0]
        m = MedidorTag(lambda: t[0], lambda s: None, lecturas=2, espera_s=0.5)
        m.agregar(pose(0.01, 0, 0))
        m.en_reposo()
        self.assertIsNone(m.intentar())
        t[0] = 0.6
        m.agregar(pose(0.02, 0, 0))
        self.assertIsNone(m.intentar())          # solo una lectura nueva
        m.agregar(pose(0.04, 0, 0))
        self.assertAlmostEqual(m.intentar().dx, 0.03, places=9)

    def test_en_reposo_con_espera_cero_acepta_lecturas_desde_ahora(self):
        t = [5.0]
        m = MedidorTag(lambda: t[0], lambda s: None, lecturas=1, espera_s=0.8)
        m.agregar(pose(0.5, 0, 0))
        t[0] = 6.0
        m.en_reposo(0.0)
        self.assertIsNone(m.intentar())          # la lectura vieja no vale
        m.agregar(pose(0.02, 0, 0))
        self.assertAlmostEqual(m.intentar().dx, 0.02)

    def test_esperar_cede_el_control_y_vence_por_tiempo(self):
        t = [0.0]
        m = MedidorTag(lambda: t[0], lambda s: None, lecturas=1, espera_s=0.0, timeout_s=1.0)
        m.en_reposo()
        g, cedidas = m.esperar(), 0
        try:
            while True:
                next(g)
                cedidas += 1
                t[0] += 0.1
        except StopIteration as fin:
            self.assertIsNone(fin.value)
        self.assertGreaterEqual(cedidas, 9)


if __name__ == '__main__':
    unittest.main()
