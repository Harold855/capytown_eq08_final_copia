import math
import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito import planificador as pl
from carrito.granprix_carrito.docks import DOCKS_HTML
from geometria_dock.transformaciones import Pose2D, wrap

D = DOCKS_HTML


class TestTramo(unittest.TestCase):
    def test_los_cuatro_tramos_nominales(self):
        for e, s in ((1, 2), (2, 3), (3, 4), (4, 1)):
            t = pl.planificar_tramo(D[e].pose, (D[s].x, D[s].y))
            self.assertAlmostEqual(t.phi, math.pi / 2); self.assertAlmostEqual(t.L, 2.0)

    def test_destino_coincidente_no_gira(self):
        t = pl.planificar_tramo(Pose2D(1, 1, 0.7), (1, 1))
        self.assertEqual((t.phi, t.L), (0.0, 0.0))

    def test_siempre_el_giro_mas_corto(self):
        t = pl.planificar_tramo(Pose2D(0, 0, 3.1), (-1, -0.05))   # destino casi a 180°
        self.assertLess(abs(t.phi), math.pi)
        t = pl.planificar_tramo(Pose2D(0, 0, math.radians(170)), (math.cos(math.radians(-170)), math.sin(math.radians(-170))))
        self.assertAlmostEqual(math.degrees(t.phi), 20.0, places=6)

    def test_cuatro_cuadrantes(self):
        for destino, esperado in (((1, 1), 45), ((-1, 1), 135), ((-1, -1), -135), ((1, -1), -45)):
            self.assertAlmostEqual(math.degrees(pl.planificar_tramo(Pose2D(0, 0, 0), destino).phi), esperado, places=6)

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            pl.planificar_tramo(Pose2D(0, 0, 0), (float('nan'), 0))
        with self.assertRaises(ValueError):
            Pose2D(0, float('inf'), 0)

    def test_pose_prevista_recorre_los_docks(self):
        pose = D[1].pose
        for e in (2, 3, 4, 1):
            tr = pl.planificar_tramo(pose, (D[e].x, D[e].y))
            pose = pl.pose_prevista(pose, tr)
            self.assertAlmostEqual(pose.x, D[e].x); self.assertAlmostEqual(pose.y, D[e].y)
            self.assertAlmostEqual(wrap(pose.th - D[e].rumbo), 0.0)


class TestComando(unittest.TestCase):
    def test_compensacion_y_tiempos(self):
        c = pl.comandar(pl.Tramo(math.pi / 2, 2.0), pl.Escalas(cd=1.01, ca=0.988))
        self.assertAlmostEqual(c.L_cmd, 2.0 / 1.01); self.assertAlmostEqual(c.phi_cmd, (math.pi / 2) / 0.988)
        self.assertAlmostEqual(c.t_avance, c.L_cmd / 0.10); self.assertAlmostEqual(c.t_giro, c.phi_cmd / 0.5)

    def test_signo_del_giro(self):
        self.assertEqual(pl.comandar(pl.Tramo(-1.0, 1.0)).w, -0.5)
        self.assertEqual(pl.comandar(pl.Tramo(1.0, 1.0)).w, 0.5)
        self.assertEqual(pl.comandar(pl.Tramo(0.0, 1.0)).w, 0.0)

    def test_limites_de_velocidad(self):
        for v, w in ((0.21, 0.5), (0.10, 0.81), (0.0, 0.5), (0.10, 0.0), (float('nan'), 0.5)):
            with self.assertRaises(ValueError):
                pl.comandar(pl.Tramo(1.0, 1.0), v=v, w=w)
        pl.comandar(pl.Tramo(1.0, 1.0), v=0.20, w=0.80)   # los máximos sí valen

    def test_escalas_invalidas(self):
        for cd, ca in ((0, 1), (1, -1), (float('nan'), 1)):
            with self.assertRaises(ValueError):
                pl.Escalas(cd, ca)

    def test_presupuesto_del_html(self):
        """Con 6 s de pit: 116.57 s por vuelta y 466.27 s en cuatro vueltas (contexto del equipo)."""
        t = pl.tiempo_vuelta(pl.planificar_vuelta(D), 6.0)
        self.assertAlmostEqual(t, 116.57, delta=0.01)
        self.assertAlmostEqual(4 * t, 466.27, delta=0.01)


class TestEstimador(unittest.TestCase):
    def ciclo(self, esc, real_cd, real_ca):
        cmd = pl.comandar(pl.Tramo(math.pi / 2, 2.0), esc)
        return cmd, cmd.L_cmd * real_cd, cmd.phi_cmd * real_ca

    def test_converge_a_la_escala_real(self):
        esc = pl.Escalas()
        for _ in range(40):
            cmd, d, a = self.ciclo(esc, 1.02, 1.08)
            esc = pl.actualizar_escalas(esc, cmd, d, a).escalas
        self.assertAlmostEqual(esc.cd, 1.02, places=3); self.assertAlmostEqual(esc.ca, 1.08, places=3)

    def test_con_valor_nominal_converge_sesgado(self):
        """Error típico: usar el giro nominal en lugar del comandado."""
        esc = pl.Escalas()
        for _ in range(60):
            cmd = pl.comandar(pl.Tramo(math.pi / 2, 2.0), esc)
            falso = pl.Comando(math.pi / 2, cmd.L_cmd, cmd.v, cmd.w, cmd.t_giro, cmd.t_avance)
            esc = pl.actualizar_escalas(esc, falso, cmd.L_cmd * 1.02, cmd.phi_cmd * 1.09).escalas
        self.assertAlmostEqual(esc.ca, math.sqrt(1.09), delta=0.005)

    def test_paso_maximo_y_limites(self):
        esc = pl.Escalas()
        cmd = pl.comandar(pl.Tramo(math.pi / 2, 2.0), esc)
        r = pl.actualizar_escalas(esc, cmd, cmd.L_cmd * 1.4, cmd.phi_cmd * 1.4, alpha=1.0)
        self.assertAlmostEqual(r.escalas.cd, 1.0 + pl.PASO_MAX_ESCALA)
        self.assertAlmostEqual(r.escalas.ca, 1.0 + pl.PASO_MAX_ESCALA)

    def test_rechaza_atipicas_y_comandos_pequenos(self):
        esc = pl.Escalas()
        cmd = pl.comandar(pl.Tramo(math.pi / 2, 2.0), esc)
        r = pl.actualizar_escalas(esc, cmd, cmd.L_cmd * 3.0, -cmd.phi_cmd)
        self.assertEqual((r.uso_cd, r.uso_ca), (False, False)); self.assertEqual(r.escalas, esc)
        peq = pl.comandar(pl.Tramo(0.05, 0.05), esc)
        r = pl.actualizar_escalas(esc, peq, 0.05, 0.05)
        self.assertEqual((r.motivo_cd, r.motivo_ca), ('distancia_comandada_pequena', 'giro_comandado_fuera_de_rango'))
        r = pl.actualizar_escalas(esc, pl.comandar(pl.Tramo(0.0, 0.0), esc), 0.0, 0.0, proteger=False)
        self.assertEqual((r.uso_cd, r.uso_ca), (False, False))

    def test_sin_proteger_es_la_formula_del_html(self):
        esc = pl.Escalas(1.0, 1.0)
        cmd = pl.comandar(pl.Tramo(math.pi / 2, 2.0), esc)
        r = pl.actualizar_escalas(esc, cmd, cmd.L_cmd * 1.3, cmd.phi_cmd * 1.3, 0.35, proteger=False)
        self.assertAlmostEqual(r.escalas.cd, 1.0 + 0.35 * (1.3 - 1.0)); self.assertAlmostEqual(r.escalas.ca, 1.0 + 0.35 * 0.3)

    def test_giro_negativo(self):
        esc = pl.Escalas()
        cmd = pl.comandar(pl.Tramo(-math.pi / 2, 2.0), esc)
        r = pl.actualizar_escalas(esc, cmd, cmd.L_cmd, cmd.phi_cmd * 1.04)
        self.assertTrue(r.uso_ca); self.assertGreater(r.escalas.ca, 1.0)

    def test_alpha_invalido(self):
        cmd = pl.comandar(pl.Tramo(1.0, 1.0))
        for a in (0, 1.5, float('nan')):
            with self.assertRaises(ValueError):
                pl.actualizar_escalas(pl.Escalas(), cmd, 1.0, 1.0, a)

    def test_medir_tramo(self):
        d, g = pl.medir_tramo(Pose2D(0, 0, math.radians(170)), Pose2D(3, 4, math.radians(-170)))
        self.assertAlmostEqual(d, 5.0); self.assertAlmostEqual(math.degrees(g), 20.0)


class TestAcople(unittest.TestCase):
    def test_tolerancias_son_inclusivas_y_simultaneas(self):
        self.assertTrue(pl.acople_valido(0.04, 0, 6.0))
        self.assertFalse(pl.acople_valido(0.0401, 0, 0))
        self.assertFalse(pl.acople_valido(0, 0, 6.1))
        self.assertFalse(pl.acople_valido(0.03, 0.03, 0))      # 4.24 cm
        self.assertTrue(pl.acople_valido(0, 0, 359.0))         # -1° envuelto

    def test_sin_error_no_hay_primitivas(self):
        self.assertEqual(pl.planificar_acople(0.0, 0.0, 0.0), [])

    def test_solo_rotar_si_esta_en_la_cruz(self):
        p = pl.planificar_acople(0.002, 0.0, 10.0)
        self.assertEqual([x.tipo for x in p], ['giro']); self.assertAlmostEqual(math.degrees(p[0].valor), -10.0)

    def test_llega_a_la_cruz_en_muchas_poses(self):
        rng = random.Random(5)
        for _ in range(300):
            dx, dy, dth = rng.uniform(-.08, .08), rng.uniform(-.08, .08), rng.uniform(-12, 12)
            for rev in (False, True):
                fin = pl.aplicar_primitivas(Pose2D(dx, dy, math.radians(dth)), pl.planificar_acople(dx, dy, dth, permitir_reversa=rev))
                # por debajo de 1 cm no se avanza (min_dist): el residuo puede llegar a 1 cm, muy dentro de los 4 cm
                self.assertLess(math.hypot(fin.x, fin.y), 0.002 if math.hypot(dx, dy) >= 0.01 else 0.0101)
                self.assertLess(abs(math.degrees(fin.th)), 0.6)
                self.assertTrue(pl.acople_valido(fin.x, fin.y, math.degrees(fin.th)))

    def test_reversa_si_el_objetivo_esta_atras(self):
        # el carrito pasó 3 cm de la cruz, mirando hacia adelante
        sin = pl.planificar_acople(0.03, 0.0, 0.0)
        con = pl.planificar_acople(0.03, 0.0, 0.0, permitir_reversa=True)
        self.assertGreater(sum(abs(p.valor) for p in sin if p.tipo == 'giro'), math.radians(300))   # gira ~180° dos veces
        self.assertEqual([p.tipo for p in con], ['avance']); self.assertAlmostEqual(con[0].valor, -0.03)

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            pl.planificar_acople(float('nan'), 0, 0)
        with self.assertRaises(ValueError):
            pl.aplicar_primitivas(Pose2D(0, 0, 0), [pl.Primitiva('salto', 1.0)])


if __name__ == '__main__':
    unittest.main()
