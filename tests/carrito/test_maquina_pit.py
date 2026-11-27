"""Pruebas de estados, transiciones, temporización y seguridad de la máquina del pit, con la misión simulada
(`simulacion/mision_simulada.py`): planta continua con escalas reales ocultas y una estación que valida con la pose VERDADERA."""
import bisect
import dataclasses
import itertools
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito import maquina_pit as mp
from carrito.granprix_carrito.maquina_pit import Estado, SalidaSegura, TRANSICIONES
from carrito.granprix_carrito.mision import ConfigMision, Tiempos
from simulacion.mision_simulada import Mundo

E = Estado
CALIBRADO = dict(escalas_ini=(1.01, 1.09))
CICLO = ['ACOPLANDO', 'SOLICITANDO', 'ESPERANDO_RESULTADO', 'RECALIBRANDO', 'SALIENDO']


def hasta(m, estado, max_s=900.0, externos=None):
    fin = m.t + max_s
    while m.fsm.estado is not estado and m.t < fin:
        m.paso(externos)
    assert m.fsm.estado is estado, f'no se llegó a {estado}: {m.fsm.estado} {m.fsm.motivo}'
    return m


def avanzar(m, s, externos=None):
    fin = m.t + s
    while m.t < fin:
        m.paso(externos)


def cfg_tiempos(**kw):
    return dataclasses.replace(ConfigMision(), tiempos=dataclasses.replace(Tiempos(), **kw))


def solo_ceros(m, desde=0.0):
    return all((v, w) == (0.0, 0.0) for t, v, w in m.vel if t >= desde)


class Banderas:
    """Lo que el curso le dice al carrito; el test lo cambia en caliente."""

    def __init__(self):
        self.turno, self.bandera, self.enlace = True, 'verde', True

    def __call__(self, m):
        m.fsm.recibir_turno(self.turno)
        m.fsm.recibir_bandera(self.bandera)
        if self.enlace:
            m.fsm.recibir_enlace(True)


class TestMisionCompleta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Mundo(**CALIBRADO, semilla=0)
        cls.estado = cls.m.correr()

    def test_termina_en_fin_con_cuatro_vueltas_en_menos_de_12_minutos(self):
        m = self.m
        self.assertEqual((self.estado, m.fsm.motivo), (E.FIN, None))
        self.assertEqual([v[0] for v in m.puerto.vueltas], [1, 2, 3, 4])
        self.assertLess(m.t - 1000.0, 720.0)

    def test_secuencia_de_estados_exacta(self):
        esperado = ['MIDIENDO'] + (CICLO + ['NAVEGANDO', 'MIDIENDO']) * 15 + CICLO + ['FIN']
        self.assertEqual([s for _, s in self.m.estados], esperado)

    def test_una_solicitud_por_parada_con_la_pieza_que_trae(self):
        sol = self.m.estacion.solicitudes
        self.assertEqual([e for e, _ in sol], [1, 2, 3, 4] * 4)
        self.assertEqual([d['pieza_trae'] for _, d in sol], [None, 'A', 'B', 'C'] * 4)

    def test_nunca_se_solicita_fuera_de_tolerancia_segun_la_pose_verdadera(self):
        for e, d in self.m.estacion.solicitudes:
            dx, dy, deg = d['verdadera']
            self.assertLessEqual(dx * dx + dy * dy, 0.04 ** 2, msg=e)
            self.assertLessEqual(abs(deg), 6.0, msg=e)
            mx, my, mdeg = d['medida']['dx'], d['medida']['dy'], d['medida']['dth']
            self.assertLess(abs(mx - dx), 0.01)
            self.assertLess(abs(my - dy), 0.01)
            self.assertLess(abs(mdeg - deg), 1.0)

    def test_eventos_y_vueltas_del_contrato(self):
        m = self.m
        self.assertEqual([e for _, t, e in m.puerto.eventos if t == 'pit_ok'], [1, 2, 3, 4] * 4)
        for numero, t_ini, t_fin, est in m.puerto.vueltas:
            self.assertGreater(t_fin, t_ini)
            self.assertEqual(est, (1, 2, 3, 4))
        self.assertEqual(sum(1 for _, t, _ in m.puerto.eventos if t == 'reintento'),
                         sum(p.reintentos for p in m.mision.pits))

    def test_solo_hay_velocidad_en_navegando_y_acoplando(self):
        m, tiempos = self.m, [t for t, _ in self.m.estados]
        nombres = [s for _, s in self.m.estados]
        self.assertTrue(m.vel)
        for t, v, w in m.vel:
            i = bisect.bisect_right(tiempos, t) - 1
            estado = nombres[i] if i >= 0 else 'ESPERA'
            if estado not in ('NAVEGANDO', 'ACOPLANDO'):
                self.assertEqual((v, w), (0.0, 0.0), msg=(t - 1000.0, estado))

    def test_registro_de_pits_completo_y_pits_lentos_contados(self):
        m = self.m
        pits = m.mision.pits
        self.assertEqual(len(pits), 16)
        self.assertTrue(all(p.valido and p.t_pit_s is not None and p.cd is not None for p in pits))
        self.assertEqual(m.fsm.pits_lentos, sum(1 for p in pits if p.t_pit_s > 10.0))
        for p in pits:
            if p.correcciones == 0:
                self.assertLess(p.t_pit_s, 10.0)           # sin corrección cabe (con 5.8 s de intercambio)
            self.assertAlmostEqual(p.t_pit_s > 10.0, p.correcciones > 0, msg=p)   # y con corrección no

    def test_un_reset_de_pose_por_parada(self):
        self.assertEqual(self.m.puerto.resets, 16)

    def test_exporta_pits_csv(self):
        with tempfile.TemporaryDirectory() as d:
            self.m.mision.exportar_pits(str(Path(d) / 'p.csv'))
            self.assertEqual(len((Path(d) / 'p.csv').read_text().strip().splitlines()), 17)

    def test_fin_mantiene_ceros_y_no_se_mueve(self):
        m, n = self.m, len(self.m.vel)
        avanzar(m, 2.0)
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertGreaterEqual(len(m.vel) - n, 35)
        self.assertTrue(solo_ceros(m, m.vel[n][0]))


class TestTransiciones(unittest.TestCase):
    def test_solo_las_transiciones_declaradas(self):
        m = Mundo()
        for a, b in itertools.product(Estado, Estado):
            m.fsm.estado = a
            if b is E.FALLA or b in TRANSICIONES[a]:
                m.fsm._ir(b)
            else:
                with self.assertRaises(RuntimeError, msg=(a, b)):
                    m.fsm._ir(b)

    def test_falla_es_alcanzable_desde_cualquier_estado_y_solo_sale_por_reiniciar(self):
        for e in Estado:
            self.assertTrue(e is E.FALLA or e in TRANSICIONES)
        self.assertEqual(TRANSICIONES[E.FALLA], {E.ESPERA})
        self.assertEqual(TRANSICIONES[E.FIN], {E.ESPERA})

    def test_los_diez_estados_de_la_especificacion(self):
        self.assertEqual([e.value for e in Estado], ['ESPERA', 'NAVEGANDO', 'MIDIENDO', 'ACOPLANDO', 'SOLICITANDO',
                                                     'ESPERANDO_RESULTADO', 'RECALIBRANDO', 'SALIENDO', 'FIN', 'FALLA'])


class TestAutorizacion(unittest.TestCase):
    def test_sin_turno_no_arranca_ni_publica_nada(self):
        for turno in (None, False):
            m = Mundo(**CALIBRADO)
            b = Banderas()
            b.turno = turno
            if turno is None:
                b.__call__ = None
            avanzar(m, 30.0, (lambda mm: (mm.fsm.recibir_enlace(True), mm.fsm.recibir_bandera('verde')) if turno is None else b(mm)))
            self.assertEqual((m.fsm.estado, m.vel, m.estacion.solicitudes), (E.ESPERA, [], []))

    def test_sin_enlace_no_arranca(self):
        m = Mundo(**CALIBRADO)
        b = Banderas()
        b.enlace = False
        avanzar(m, 30.0, b)
        self.assertEqual((m.fsm.estado, m.vel), (E.ESPERA, []))

    def test_bandera_roja_no_arranca(self):
        m = Mundo(**CALIBRADO)
        b = Banderas()
        b.bandera = 'roja'
        avanzar(m, 10.0, b)
        self.assertEqual(m.fsm.estado, E.ESPERA)
        b.bandera = 'verde'
        avanzar(m, 1.0, b)
        self.assertNotEqual(m.fsm.estado, E.ESPERA)

    def test_turno_retirado_en_marcha_frena_de_inmediato(self):
        m, b = Mundo(**CALIBRADO), Banderas()
        hasta(m, E.NAVEGANDO, externos=b)
        avanzar(m, 5.0, b)
        self.assertNotEqual((m.planta._v, m.planta._w), (0.0, 0.0))               # ya está avanzando
        b.turno = False
        m.fsm.recibir_turno(False)
        m.paso(b)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'SIN_AUTORIZACION'))
        self.assertEqual((m.planta._v, m.planta._w), (0.0, 0.0))
        self.assertTrue(solo_ceros(m, m.estados[-1][0]))

    def test_bandera_roja_detiene_en_cada_estado_activo(self):
        for objetivo in (E.MIDIENDO, E.ACOPLANDO, E.SOLICITANDO, E.ESPERANDO_RESULTADO, E.RECALIBRANDO, E.SALIENDO, E.NAVEGANDO):
            m, b = Mundo(**CALIBRADO), Banderas()
            hasta(m, objetivo, externos=b)
            m.fsm.recibir_bandera('roja')
            b.bandera = 'roja'
            m.paso(b)
            self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'BANDERA_ROJA'), msg=objetivo)
            self.assertEqual(m.planta._v, 0.0)

    def test_enlace_perdido_detiene_tras_enlace_max(self):
        m, b = Mundo(**CALIBRADO), Banderas()
        hasta(m, E.NAVEGANDO, externos=b)
        avanzar(m, 5.0, b)
        b.enlace = False
        t0 = m.t
        while m.fsm.estado is E.NAVEGANDO and m.t - t0 < 10:
            m.paso(b)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'ENLACE_PERDIDO'))
        self.assertAlmostEqual(m.t - t0, 2.0, delta=0.6)
        self.assertEqual(m.planta._v, 0.0)

    def test_estacion_offline_detiene(self):
        m, b = Mundo(**CALIBRADO), Banderas()
        hasta(m, E.NAVEGANDO, externos=b)
        m.fsm.recibir_estacion(m.mision.estacion, 'OFFLINE')
        m.paso(b)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'ESTACION_OFFLINE'))

    def test_tanda_agotada(self):
        m = Mundo(cfg_mision=cfg_tiempos(tanda_max_s=60.0), **CALIBRADO)
        m.correr(200.0)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'TANDA_AGOTADA'))
        self.assertAlmostEqual(m.t - 1000.0, 60.0, delta=1.0)


class TestIntercambio(unittest.TestCase):
    def test_la_salida_segura_filtra_la_velocidad(self):
        enviados, permitido = [], [True]

        class Raw:
            def publicar(self, v, w):
                enviados.append((v, w))
        s = SalidaSegura(Raw(), lambda: permitido[0])
        s.publicar(0.1, 0.3)
        permitido[0] = False
        s.publicar(0.1, 0.3)
        self.assertEqual(enviados, [(0.1, 0.3), (0.0, 0.0)])

    def test_puede_mover_solo_en_navegando_y_acoplando_y_sin_intercambio(self):
        m = Mundo(**CALIBRADO)
        Banderas()(m)
        s = m.fsm.seg
        m.fsm.entorno.t_inicio = m.t
        for e in Estado:
            self.assertEqual(s.puede_mover(e), e in (E.NAVEGANDO, E.ACOPLANDO), msg=e)
        m.fsm.entorno.intercambio = True
        self.assertFalse(s.puede_mover(E.NAVEGANDO))
        m.fsm.entorno.intercambio = False
        m.fsm.recibir_estacion(3, 'CAMBIANDO')
        self.assertFalse(s.puede_mover(E.ACOPLANDO))

    def test_el_carrito_espera_quieto_hasta_el_resultado(self):
        m = Mundo(**CALIBRADO, t_cambio=9.0)
        hasta(m, E.ESPERANDO_RESULTADO)
        t0 = m.t
        avanzar(m, 8.0)
        self.assertEqual(m.fsm.estado, E.ESPERANDO_RESULTADO)
        self.assertTrue(m.fsm.entorno.intercambio)
        self.assertTrue(solo_ceros(m, t0))
        hasta(m, E.SALIENDO)
        self.assertFalse(m.fsm.entorno.intercambio)

    def test_no_sale_mientras_alguna_estacion_siga_cambiando(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.SALIENDO)
        m.fsm.recibir_estacion(1, 'CAMBIANDO')
        t0 = m.t
        avanzar(m, 2.0)
        self.assertEqual(m.fsm.estado, E.SALIENDO)
        self.assertTrue(solo_ceros(m, t0))
        m.fsm.recibir_estacion(1, 'LISTA')
        avanzar(m, 0.2)
        self.assertEqual(m.fsm.estado, E.NAVEGANDO)

    def test_si_el_intercambio_no_termina_falla_por_plazo(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.SALIENDO)
        m.fsm.recibir_estacion(1, 'CAMBIANDO')
        avanzar(m, 4.0)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'TIMEOUT_SALIENDO'))
        self.assertEqual(m.planta._v, 0.0)

    def test_un_intercambio_que_arranca_en_plena_marcha_detiene_el_tramo(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        avanzar(m, 5.0)
        m.fsm.recibir_estacion(2, 'CAMBIANDO')
        m.paso()
        self.assertEqual(m.fsm.estado, E.FALLA)
        self.assertEqual(m.planta._v, 0.0)


class TestResultado(unittest.TestCase):
    def test_resultado_no_ok_es_falla_y_no_avanza_la_mision(self):
        m = Mundo(**CALIBRADO)
        m.estacion.respuesta = lambda est, ok, deja: (False, None) if est == 2 else (ok, deja)
        m.correr()
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'RESULTADO_NO_OK'))
        self.assertEqual(m.mision.estacion, 2)
        self.assertEqual(len(m.estacion.solicitudes), 2)
        self.assertFalse(m.mision.pits[-1].valido)
        self.assertEqual(m.mision.pits[-1].motivo, 'RESULTADO_NO_OK')
        self.assertTrue(solo_ceros(m, m.t - 1.0))

    def test_pieza_inesperada_no_detiene_la_mision_pero_la_marca(self):
        m = Mundo(**CALIBRADO)
        m.estacion.respuesta = lambda est, ok, deja: (True, 'Z') if est == 2 and len(m.estacion.solicitudes) == 2 else (ok, deja)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertEqual(m.mision.pits_invalidos, 1)
        self.assertEqual(m.mision.vueltas[0].estaciones, (1, 3, 4))
        self.assertTrue(any('PIEZA_INESPERADA' in t for _, _, t in m.puerto.avisos))
        self.assertEqual(sum(1 for _, t, _ in m.puerto.eventos if t == 'pit_ok'), 15)

    def test_resultados_fuera_de_lugar_se_ignoran(self):
        m = Mundo(**CALIBRADO, t_cambio=9.0)
        self.assertFalse(m.fsm.recibir_resultado(1, True, 'A'))                  # nadie lo esperaba
        hasta(m, E.ESPERANDO_RESULTADO)
        self.assertFalse(m.fsm.recibir_resultado(3, True, 'C'))                  # de otra estación
        self.assertEqual(m.fsm.ignorados, 2)
        self.assertEqual(m.fsm.estado, E.ESPERANDO_RESULTADO)
        self.assertTrue(m.fsm.recibir_resultado(1, True, 'A'))
        self.assertFalse(m.fsm.recibir_resultado(1, False, None))                # duplicado
        hasta(m, E.SALIENDO)
        self.assertTrue(m.mision.pits[0].valido)


class TestAcopleYMedicion(unittest.TestCase):
    def test_sin_tag_al_llegar_falla_por_plazo_sin_solicitar(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        m.tag_activo = False
        m.correr(100.0)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'TIMEOUT_MIDIENDO'))
        self.assertEqual(len(m.estacion.solicitudes), 1)                          # solo la del E1
        self.assertTrue(solo_ceros(m, m.estados[-1][0]))                          # desde la falla, solo ceros

    def test_un_acople_que_no_llega_a_tolerancia_falla_y_no_solicita(self):
        m = Mundo(cfg_acople=dataclasses.replace(Mundo().cfg_acople, error_max_m=0.04), ca=1.04, escalas_ini=(1.0, 1.0))
        m.correr()
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'ACOPLE_FUERA_DE_ALCANCE'))
        self.assertEqual(len(m.estacion.solicitudes), 1)

    def test_aprende_las_escalas_y_llega_cada_vez_mejor(self):
        m = Mundo(ca=1.04, escalas_ini=(1.0, 1.0), semilla=3)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertAlmostEqual(m.fsm.calibrador.estimador.escalas.ca, 1.04, delta=0.02)
        pits = m.mision.pits
        self.assertGreater(sum(p.err_pos_pre_m for p in pits[1:5]) / 4, 2 * sum(p.err_pos_pre_m for p in pits[-8:]) / 8)
        self.assertTrue(all(p.valido for p in pits))


    def test_cada_reintento_del_acople_se_reporta_en_su_estacion(self):
        base = Mundo().cfg_acople
        m = Mundo(**CALIBRADO, cfg_acople=dataclasses.replace(base, ganancia_pos=0.7, ganancia_ang=0.7, presupuesto_s=None), semilla=0)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        esperados = [p.estacion for p in m.mision.pits for _ in range(p.reintentos)]
        self.assertGreater(len(esperados), 0)
        self.assertEqual([e for _, t, e in m.puerto.eventos if t == 'reintento'], esperados)
        self.assertTrue(all(p.reintentos <= 2 for p in m.mision.pits))               # el reto permite 2

    def test_con_ganancia_baja_el_presupuesto_de_tiempo_del_acople_aborta_la_mision(self):
        base = Mundo().cfg_acople
        m = Mundo(**CALIBRADO, cfg_acople=dataclasses.replace(base, ganancia_pos=0.7, ganancia_ang=0.7))
        m.correr()
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'ACOPLE_SIN_TIEMPO'))
        self.assertEqual(len(m.estacion.solicitudes), sum(1 for p in m.mision.pits if p.valido))      # el pit fallido no solicitó


class TestReset(unittest.TestCase):
    def test_reintenta_si_odom_no_ha_llegado(self):
        m = Mundo(**CALIBRADO, reset_tras_intentos=2)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertEqual(m.puerto.resets, 16)                                     # los dos rechazos se reintentaron
        self.assertFalse(any('rechazado' in t for _, _, t in m.puerto.avisos))

    def test_un_reset_rechazado_no_detiene_la_mision(self):
        m = Mundo(**CALIBRADO, reset_tras_intentos=999)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertEqual(m.puerto.resets, 0)
        self.assertEqual(sum('rechazado' in t for _, _, t in m.puerto.avisos), 16)

    def test_sin_servicio_de_reset_se_sigue(self):
        m = Mundo(**CALIBRADO)
        m.puerto.pedir_reset = lambda: False
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertTrue(any('no disponible' in t for _, _, t in m.puerto.avisos))


class TestTemporizacion(unittest.TestCase):
    def test_cada_estado_vence_en_su_plazo(self):
        m = Mundo(**CALIBRADO)
        t = m.fsm.mision.cfg.tiempos
        tabla = {E.MIDIENDO: t.midiendo_s, E.ACOPLANDO: t.acoplando_s, E.SOLICITANDO: t.solicitando_s,
                 E.ESPERANDO_RESULTADO: t.esperando_resultado_s, E.RECALIBRANDO: t.recalibrando_s, E.SALIENDO: t.saliendo_s}
        for estado, limite in tabla.items():
            m.fsm.estado, m.fsm.t_estado = estado, 500.0
            self.assertIsNone(m.fsm._plazo(500.0 + limite - 0.01), msg=estado)
            self.assertEqual(m.fsm._plazo(500.0 + limite + 0.01), f'TIMEOUT_{estado.value}')
        for estado in (E.ESPERA, E.FIN, E.FALLA):
            m.fsm.estado = estado
            self.assertIsNone(m.fsm._plazo(1e9))

    def test_el_plazo_de_navegacion_depende_del_tramo(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        c, ej, ti = m.fsm._cmd, m.fsm.mov.ejecutor, m.fsm.mision.cfg.tiempos
        self.assertAlmostEqual(m.fsm._lim_nav, c.t_total + ej.pausa_s + ej.asentamiento_s + ti.navegando_margen_s, places=9)
        self.assertGreater(m.fsm._lim_nav, 20.0)

    def test_sin_resultado_falla_a_los_15_s_y_queda_quieto(self):
        m = Mundo(**CALIBRADO, t_cambio=1000.0)
        hasta(m, E.ESPERANDO_RESULTADO)
        t0 = m.t
        m.correr(60.0)
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'TIMEOUT_ESPERANDO_RESULTADO'))
        self.assertAlmostEqual(m.t - t0, 15.0, delta=0.2)
        self.assertTrue(solo_ceros(m, t0))
        self.assertTrue(m.fsm.entorno.intercambio)           # no se sabe si el brazo sigue: nunca se da por terminado

    def test_el_pit_lento_se_cuenta_pero_no_aborta(self):
        m = Mundo(**CALIBRADO, t_cambio=12.0)
        m.correr()
        self.assertEqual(m.fsm.estado, E.FIN)
        self.assertEqual(m.fsm.pits_lentos, 16)


class TestFallos(unittest.TestCase):
    def test_odometria_perdida_en_marcha(self):
        corte = []
        m = Mundo(**CALIBRADO, odom_ok=lambda: not corte)
        hasta(m, E.NAVEGANDO)
        avanzar(m, 5.0)
        corte.append(1)
        m.paso()
        m.paso()
        self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, 'MOVIMIENTO_ODOM_PERDIDA'))
        self.assertEqual(m.planta._v, 0.0)

    def test_un_error_interno_termina_en_falla_con_cero(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        avanzar(m, 5.0)

        def roto():
            raise KeyError('x')
        m.fsm.ej.paso = roto
        m.paso()
        self.assertEqual(m.fsm.estado, E.FALLA)
        self.assertTrue(m.fsm.motivo.startswith('ERROR_INTERNO'))
        self.assertEqual(m.planta._v, 0.0)
        self.assertEqual(m.vel[-1][1:], (0.0, 0.0))

    def test_parar_a_mano_frena_al_instante(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        avanzar(m, 5.0)
        m.fsm.parar()
        self.assertEqual((m.fsm.estado, m.fsm.motivo, m.planta._v), (E.FALLA, 'PARADA_MANUAL', 0.0))

    def test_falla_mantiene_ceros_y_no_se_recupera_sola(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        m.fsm.parar()
        n = len(m.vel)
        avanzar(m, 5.0)
        self.assertEqual(m.fsm.estado, E.FALLA)
        self.assertGreaterEqual(len(m.vel) - n, 90)
        self.assertTrue(solo_ceros(m, m.vel[n][0]))

    def test_reiniciar_solo_desde_espera_fin_o_falla(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.NAVEGANDO)
        self.assertFalse(m.fsm.reiniciar())
        self.assertEqual(m.fsm.estado, E.NAVEGANDO)
        m.fsm.parar()
        self.assertTrue(m.fsm.reiniciar())
        self.assertEqual((m.fsm.estado, m.fsm.motivo, m.mision.estacion, m.mision.pits), (E.ESPERA, None, 1, []))

    def test_tras_reiniciar_se_puede_repetir_la_mision_conservando_las_escalas(self):
        m = Mundo(ca=1.04, escalas_ini=(1.0, 1.0), semilla=3)
        hasta(m, E.NAVEGANDO)
        avanzar(m, 5.0)
        m.fsm.parar()
        m.fsm.reiniciar()
        m.planta.colocar_en_dock(0.0, 0.0, 0.0, 1)
        m.correr()
        self.assertEqual((m.fsm.estado, m.fsm.motivo, len(m.mision.pits)), (E.FIN, None, 16))

    def test_instantanea(self):
        m = Mundo(**CALIBRADO)
        hasta(m, E.ESPERANDO_RESULTADO)
        s = m.fsm.instantanea()
        self.assertEqual((s['estado'], s['vuelta'], s['estacion'], s['pits']), ('ESPERANDO_RESULTADO', 1, 1, 1))
        self.assertEqual((s['cd'], s['ca']), (1.01, 1.09))


if __name__ == '__main__':
    unittest.main()
