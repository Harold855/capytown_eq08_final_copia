import math
import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito import planificador as pl
from carrito.granprix_carrito.docks import DOCKS_HTML as D
from carrito.granprix_carrito.ejecutor import Config, Estado, EjecutorMovimiento, ejecutar_hasta_el_final
from geometria_dock.transformaciones import Pose2D, wrap


class Reloj:
    def __init__(self, t=100.0):
        self.t = t

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.t += s


class Planta:
    """Robot ideal: integra por tramos constantes lo que se le publica, con escalas reales cd y ca."""

    def __init__(self, reloj, pose, cd=1.0, ca=1.0):
        self.reloj, self.pose, self.cd, self.ca = reloj, pose, cd, ca
        self.v = self.w = 0.0
        self.t = None
        self.publicado = []

    def _avanzar(self):
        if self.t is not None:
            dt = self.reloj() - self.t
            x, y, th = self.pose.x, self.pose.y, self.pose.th
            th2 = th + self.w * self.ca * dt
            self.pose = Pose2D(x + self.v * self.cd * dt * math.cos(th), y + self.v * self.cd * dt * math.sin(th), wrap(th2))
        self.t = self.reloj()

    def publicar(self, v, w):
        self._avanzar()
        self.v, self.w = v, w
        self.publicado.append((self.reloj(), v, w))

    def hasta_ahora(self):
        self._avanzar()
        return self.pose


def ejecutar(cmd, pose=Pose2D(0, 0, 0), cd=1.0, ca=1.0, cfg=Config(), jitter=0.0, semilla=1):
    r = Reloj()
    pl_ = Planta(r, pose, cd, ca)
    ej = EjecutorMovimiento(pl_, r, cfg)
    rng = random.Random(semilla)
    ej.iniciar(cmd)
    while ej.paso() not in (Estado.COMPLETO, Estado.ABORTADO, Estado.DETENIDO):
        r.dormir(cfg.periodo_s * (1 + rng.uniform(-jitter, jitter)))
    return ej, pl_, r


CMD = pl.comandar(pl.Tramo(math.pi / 2, 2.0))


class TestSecuencia(unittest.TestCase):
    def test_gira_luego_avanza_con_pausa_y_asentamiento(self):
        ej, planta, _ = ejecutar(CMD)
        self.assertEqual(ej.estado, Estado.COMPLETO)
        comandos = [(round(v, 6), round(w, 6)) for _, v, w in planta.publicado]
        iw = [i for i, (v, w) in enumerate(comandos) if w != 0]
        iv = [i for i, (v, w) in enumerate(comandos) if v != 0]
        self.assertLess(max(iw), min(iv))                      # el giro va primero
        self.assertTrue(all(v == 0 for v, _ in comandos[max(iw) + 1:min(iv)]))   # pausa en cero entre ambos
        self.assertEqual(comandos[-1], (0.0, 0.0))             # termina en ceros

    def test_ejecuta_lo_comandado(self):
        ej, _, _ = ejecutar(CMD)
        r = ej.resultado()
        self.assertAlmostEqual(r.L_ejecutada, CMD.L_cmd, places=6)
        self.assertAlmostEqual(r.phi_ejecutado, CMD.phi_cmd, places=6)

    def test_giro_negativo(self):
        cmd = pl.comandar(pl.Tramo(-math.pi / 2, 1.0))
        ej, planta, _ = ejecutar(cmd)
        self.assertTrue(all(w <= 0 for _, _, w in planta.publicado))
        self.assertAlmostEqual(ej.resultado().phi_ejecutado, cmd.phi_cmd, places=6)

    def test_solo_avance_o_solo_giro(self):
        ej, planta, _ = ejecutar(pl.comandar(pl.Tramo(0.0, 0.5)))
        self.assertEqual(ej.estado, Estado.COMPLETO); self.assertFalse(any(w for _, _, w in planta.publicado))
        ej, planta, _ = ejecutar(pl.comandar(pl.Tramo(1.0, 0.0)))
        self.assertEqual(ej.estado, Estado.COMPLETO); self.assertFalse(any(v for _, v, _ in planta.publicado))

    def test_frecuencia_de_publicacion(self):
        _, planta, _ = ejecutar(CMD)
        t = [x[0] for x in planta.publicado]
        self.assertTrue(all(abs((b - a) - 0.05) < 1e-9 for a, b in zip(t, t[1:])))

    def test_comando_nulo_completa_tras_el_asentamiento(self):
        ej, _, _ = ejecutar(pl.comandar(pl.Tramo(0.0, 0.0)))
        self.assertEqual(ej.estado, Estado.COMPLETO)


class TestPrecision(unittest.TestCase):
    def test_con_robot_ideal_llega_a_los_docks(self):
        pose = D[1].pose
        for e in (2, 3, 4, 1):
            cmd = pl.comandar(pl.planificar_tramo(pose, (D[e].x, D[e].y)))
            _, planta, _ = ejecutar(cmd, pose)
            pose = planta.pose
            self.assertLess(math.hypot(pose.x - D[e].x, pose.y - D[e].y), 0.005)
            self.assertLess(abs(math.degrees(wrap(pose.th - D[e].rumbo))), 0.1)

    def test_el_ultimo_paso_ajustado_reduce_el_error_de_cuantizacion(self):
        def error(ajustar):
            c = Config(ajustar_ultimo_paso=ajustar)
            tot = 0.0
            for n in range(40):
                ph = math.radians(80 + n * 0.37)
                cmd = pl.comandar(pl.Tramo(ph, 0.0))
                _, planta, _ = ejecutar(cmd, cfg=c)
                tot += abs(planta.pose.th - ph)
            return tot / 40
        self.assertLess(error(True), error(False) / 5)

    def test_con_jitter_del_temporizador_el_error_se_mantiene_pequeno(self):
        errs = []
        for s in range(50):
            _, planta, _ = ejecutar(pl.comandar(pl.Tramo(math.pi / 2, 2.0)), jitter=0.3, semilla=s)
            errs.append((abs(math.degrees(planta.pose.th) - 90.0), math.hypot(planta.pose.x - 0.0, planta.pose.y) ))
        self.assertLess(max(e[0] for e in errs), 2.0)     # grados de rumbo con ±30 % de jitter
        # tras girar 90° y avanzar 2 m el robot queda a ~2 m del origen en y; el error es la desviación
        self.assertLess(max(abs(e[1] - 2.0) for e in errs), 0.05)

    def test_escalas_reales_se_compensan(self):
        """Robot con cd=1.02 y ca=1.09: sin compensar se pasa; con las escalas correctas llega."""
        sin = ejecutar(pl.comandar(pl.Tramo(math.pi / 2, 2.0)), cd=1.02, ca=1.09)[1].pose
        con = ejecutar(pl.comandar(pl.Tramo(math.pi / 2, 2.0), pl.Escalas(1.02, 1.09)), cd=1.02, ca=1.09)[1].pose
        self.assertGreater(abs(math.degrees(sin.th) - 90), 5)
        self.assertLess(abs(math.degrees(con.th) - 90), 0.1)
        self.assertLess(abs(math.hypot(con.x, con.y) - 2.0), 0.01)

    def test_lazo_completo_planificador_ejecutor_estimador(self):
        """Cuatro vueltas con un robot imperfecto: el error de llegada baja al aprender las escalas."""
        real_cd, real_ca = 1.02, 1.09
        esc, pose_real = pl.Escalas(), D[1].pose
        errores = []
        for k in range(16):
            s = k % 4 + 1
            destino = D[s % 4 + 1]
            creida = pose_real      # medición perfecta del tag al salir del dock
            tr = pl.planificar_tramo(creida, (destino.x, destino.y))
            cmd = pl.comandar(tr, esc)
            ej, planta, _ = ejecutar(cmd, pose_real, real_cd, real_ca)
            fin = planta.pose
            errores.append(math.hypot(fin.x - destino.x, fin.y - destino.y))
            d, g = pl.medir_tramo(creida, fin)
            esc = pl.actualizar_escalas(esc, ej.comando_efectivo(cmd), d, g).escalas
            pose_real = Pose2D(destino.x, destino.y, destino.rumbo)   # reset de pose tras el pit
        self.assertLess(errores[-1], errores[0] / 5)
        self.assertAlmostEqual(esc.ca, real_ca, delta=0.01)
        self.assertAlmostEqual(esc.cd, real_cd, delta=0.01)


class TestSeguridad(unittest.TestCase):
    def preparar(self, **kw):
        r = Reloj()
        pl_ = Planta(r, Pose2D(0, 0, 0))
        return EjecutorMovimiento(pl_, r, kw.pop('cfg', Config()), **kw), pl_, r

    def avanzar(self, ej, r, n):
        for _ in range(n):
            ej.paso(); r.dormir(0.05)

    def test_comandos_invalidos(self):
        ej, _, _ = self.preparar()
        malos = [pl.Comando(1.0, 1.0, 0.21, 0.5, 1.0, 1.0), pl.Comando(1.0, 1.0, 0.1, 0.9, 1.0, 1.0),
                 pl.Comando(float('nan'), 1.0, 0.1, 0.5, 1.0, 1.0), pl.Comando(1.0, -1.0, 0.1, 0.5, 1.0, 1.0),
                 pl.Comando(1.0, 1.0, 0.1, 0.5, 40.0, 40.0)]
        for c in malos:
            with self.assertRaises(ValueError):
                ej.iniciar(c)

    def test_no_se_inicia_dos_veces(self):
        ej, _, r = self.preparar()
        ej.iniciar(CMD); self.avanzar(ej, r, 3)
        with self.assertRaises(RuntimeError):
            ej.iniciar(CMD)

    def test_abortar_manda_ceros_y_no_reanuda(self):
        ej, planta, r = self.preparar()
        ej.iniciar(CMD); self.avanzar(ej, r, 10)
        ej.abortar('PRUEBA')
        self.avanzar(ej, r, 10)
        self.assertEqual(ej.estado, Estado.ABORTADO); self.assertEqual(ej.motivo, 'PRUEBA')
        self.assertTrue(all((v, w) == (0.0, 0.0) for _, v, w in planta.publicado[-5:]))
        self.assertLess(ej.resultado().phi_ejecutado, CMD.phi_cmd)

    def test_parada_externa_detiene(self):
        parar = {'v': False}
        ej, planta, r = self.preparar(debe_parar=lambda: parar['v'])
        ej.iniciar(CMD); self.avanzar(ej, r, 5)
        parar['v'] = True; ej.paso()
        self.assertEqual((ej.estado, ej.motivo), (Estado.DETENIDO, 'PARADA_EXTERNA'))
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))

    def test_odometria_perdida_aborta(self):
        ok = {'v': True}
        ej, _, r = self.preparar(odom_ok=lambda: ok['v'])
        ej.iniciar(CMD); self.avanzar(ej, r, 5)
        ok['v'] = False; ej.paso()
        self.assertEqual((ej.estado, ej.motivo), (Estado.ABORTADO, 'ODOM_PERDIDA'))

    def test_hueco_de_tiempo_aborta(self):
        ej, planta, r = self.preparar()
        ej.iniciar(CMD); self.avanzar(ej, r, 5)
        r.dormir(0.5); ej.paso()
        self.assertEqual((ej.estado, ej.motivo), (Estado.ABORTADO, 'HUECO_DE_TIEMPO'))
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))

    def test_primer_paso_tardio_aborta(self):
        ej, planta, r = self.preparar()
        ej.iniciar(CMD); r.dormir(0.6); ej.paso()
        self.assertEqual(ej.motivo, 'HUECO_DE_TIEMPO'); self.assertEqual(ej.resultado().L_ejecutada, 0.0)

    def test_reloj_que_retrocede_aborta(self):
        ej, _, r = self.preparar()
        ej.iniciar(CMD); self.avanzar(ej, r, 3)
        r.t -= 1.0; ej.paso()
        self.assertEqual(ej.motivo, 'RELOJ_RETROCEDE')

    def test_error_de_la_salida_aborta(self):
        class Mala:
            n = 0
            def publicar(self, v, w):
                self.n += 1
                if self.n > 3:
                    raise OSError('sin enlace')
        r = Reloj(); ej = EjecutorMovimiento(Mala(), r)
        ej.iniciar(CMD); self.avanzar(ej, r, 8)
        self.assertEqual((ej.estado, ej.motivo), (Estado.ABORTADO, 'ERROR_SALIDA'))

    def test_se_puede_reiniciar_tras_terminar(self):
        ej, planta, r = self.preparar()
        ej.iniciar(pl.comandar(pl.Tramo(0.0, 0.2)))
        ejecutar_hasta_el_final(ej, r.dormir)
        self.assertEqual(ej.estado, Estado.COMPLETO)
        ej.iniciar(pl.comandar(pl.Tramo(0.0, 0.2)))
        ejecutar_hasta_el_final(ej, r.dormir)
        self.assertEqual(ej.estado, Estado.COMPLETO)

    def test_rampa_de_aceleracion_solo_limita_acelerar(self):
        cfg = Config(a_lin_max=0.2, a_ang_max=1.0)
        base = pl.comandar(pl.Tramo(0.0, 1.0))
        ej, planta, _ = ejecutar(base, cfg=cfg)
        vs = [v for _, v, _ in planta.publicado]
        self.assertAlmostEqual(vs[0], 0.2 * 0.05, places=9)          # arranca desde el reposo
        self.assertAlmostEqual(max(vs), 0.10, places=9)
        for a_, b_ in zip(vs, vs[1:]):
            self.assertLessEqual(b_ - a_, 0.2 * 0.05 + 1e-9)          # nunca acelera más de lo permitido
        self.assertLess(ej.resultado().L_ejecutada, 1.0)              # la rampa recorta lo ejecutado...
        ef = ej.comando_efectivo(base)
        self.assertAlmostEqual(ef.L_cmd, ej.resultado().L_ejecutada)  # ...y el estimador usa lo efectivo

    def test_cierra_con_ceros_aunque_no_haya_asentamiento(self):
        ej, planta, _ = ejecutar(pl.comandar(pl.Tramo(0.0, 0.5)), cfg=Config(asentamiento_s=0.0))
        self.assertEqual(ej.estado, Estado.COMPLETO)
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))
        self.assertAlmostEqual(ej.resultado().L_ejecutada, 0.5, places=9)


class TestReversa(unittest.TestCase):
    """L_cmd < 0 = marcha atrás a |v|. Solo con Config(permitir_reversa=True); el acople es el único que la activa."""
    ATRAS = pl.Comando(0.0, -0.20, 0.10, 0.0, 0.0, 2.0)

    def test_por_defecto_se_rechaza(self):
        r = Reloj()
        ej = EjecutorMovimiento(Planta(r, Pose2D(0, 0, 0)), r, Config())
        with self.assertRaises(ValueError):
            ej.iniciar(self.ATRAS)

    def test_retrocede_la_distancia_comandada(self):
        ej, planta, _ = ejecutar(self.ATRAS, cfg=Config(permitir_reversa=True))
        self.assertEqual(ej.estado, Estado.COMPLETO)
        self.assertAlmostEqual(planta.pose.x, -0.20, places=9)
        self.assertAlmostEqual(planta.pose.y, 0.0, places=9)
        self.assertTrue(all(v <= 0 for _, v, _ in planta.publicado))
        self.assertEqual(planta.publicado[-1][1:], (0.0, 0.0))

    def test_el_comando_efectivo_es_negativo_y_exacto(self):
        ej, _, _ = ejecutar(self.ATRAS, cfg=Config(permitir_reversa=True))
        ef = ej.comando_efectivo(self.ATRAS)
        self.assertAlmostEqual(ef.L_cmd, -0.20, places=9)
        self.assertEqual(ef.v, 0.10)                        # la rapidez sigue siendo positiva

    def test_con_giro_previo_retrocede_en_el_nuevo_rumbo(self):
        cmd = pl.Comando(math.pi / 2, -0.10, 0.10, 0.5, math.pi, 1.0)
        _, planta, _ = ejecutar(cmd, cfg=Config(permitir_reversa=True))
        self.assertAlmostEqual(planta.pose.x, 0.0, places=6)
        self.assertAlmostEqual(planta.pose.y, -0.10, places=6)

    def test_los_limites_de_velocidad_siguen_valiendo(self):
        r = Reloj()
        ej = EjecutorMovimiento(Planta(r, Pose2D(0, 0, 0)), r, Config(permitir_reversa=True))
        with self.assertRaises(ValueError):
            ej.iniciar(pl.Comando(0.0, -0.1, 0.21, 0.0, 0.0, 0.5))


if __name__ == '__main__':
    unittest.main()
