"""Estación y curso falsos: núcleo, integración con la máquina de la misión y cableado del nodo (con `rclpy` sustituto).

El nodo se prueba contra un sustituto de rclpy: demuestra el cableado y la compatibilidad de JSON con `adaptador_ros`, no que la
API real de ROS 2 esté bien usada.
"""
import dataclasses
import importlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mensajes_contrato as mc
import ros_falso as rf
from carrito.granprix_carrito.maquina_pit import Estado
from ros_falso import Mensaje, Node, Ns
from simulacion.mision_simulada import Mundo
from test_adaptador_ros import odom_msg, tag_msg

E = Estado
SIM = str(RAIZ / 'carrito' / 'config' / 'marcos_sim.yaml')
ef = None
af = None


def setUpModule():
    global ef, af
    rf.instalar()
    ef = importlib.import_module('carrito.nodos.estacion_falsa')
    af = importlib.import_module('carrito.granprix_carrito.adaptador_ros')


def tearDownModule():
    rf.desinstalar('carrito.nodos.estacion_falsa', 'carrito.granprix_carrito.adaptador_ros')


def sol(estacion=1, equipo=8, dx=0.0, dy=0.0, dth=0.0, pieza='auto', **kw):
    trae = {1: None, 2: 'A', 3: 'B', 4: 'C'}[estacion] if pieza == 'auto' else pieza
    return {'v': 1, 'ts': 1.0, 'equipo': equipo, 'dock': estacion, 'pose': {'dx': dx, 'dy': dy, 'dth': dth}, 'pieza_trae': trae, **kw}


class Reloj:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def entorno(**kw):
    r = Reloj()
    return ef.EntornoFalso(ef.ConfigFalsa(**kw), r, lambda: 1.7e9 + r.t), r


def correr(e, r, s, dt=0.1):
    salida = []
    fin = r.t + s
    while r.t < fin:
        salida += e.paso()
        r.t += dt
    return salida


def de(salida, canal):
    return [c for k, c in salida if k == canal]


class TestConfig(unittest.TestCase):
    def test_validaciones(self):
        for kw in (dict(modo='raro'), dict(estacion_modo=5), dict(t_cambio_s=-1), dict(t_liberar_s=float('nan')), dict(autoiniciar_s=-2.0)):
            with self.assertRaises(ValueError, msg=kw):
                ef.ConfigFalsa(**kw)

    def test_las_piezas_por_defecto_son_las_de_mision_yaml(self):
        self.assertEqual(ef.ConfigFalsa().piezas, ((1, None, 'A'), (2, 'A', 'B'), (3, 'B', 'C'), (4, 'C', None)))


class TestCurso(unittest.TestCase):
    def test_no_da_el_turno_por_si_sola_y_lo_da_al_iniciar(self):
        e, r = entorno()
        t = de(correr(e, r, 30.0), 'turno')
        self.assertTrue(t and all(m['autorizado'] is False for m in t))
        e.iniciar()
        self.assertTrue(de(correr(e, r, 1.5), 'turno')[0]['autorizado'])

    def test_autoiniciar_y_retirar_el_turno(self):
        e, r = entorno(autoiniciar_s=5.0)
        self.assertFalse(any(m['autorizado'] for m in de(correr(e, r, 4.0), 'turno')))
        self.assertTrue(de(correr(e, r, 2.0), 'turno')[-1]['autorizado'])
        e.retirar_turno()
        self.assertFalse(de(correr(e, r, 1.5), 'turno')[-1]['autorizado'])
        self.assertFalse(any(m['autorizado'] for m in de(correr(e, r, 20.0), 'turno')))        # no se reautoriza sola

    def test_bandera_y_enlace_cambian_de_inmediato(self):
        e, r = entorno()
        correr(e, r, 1.0)
        e.bandera('roja')
        e.enlace(False)
        s = e.paso()
        self.assertEqual((de(s, 'bandera')[0]['bandera'], de(s, 'enlace')), ('roja', [False]))
        with self.assertRaises(ValueError):
            e.bandera('azul')

    def test_reenvio_periodico_como_un_topico_retenido(self):
        e, r = entorno()
        s = correr(e, r, 10.0)
        self.assertAlmostEqual(len(de(s, 'enlace')), 20, delta=2)            # 2 Hz
        self.assertAlmostEqual(len(de(s, 'turno')), 10, delta=2)             # 1 Hz
        self.assertAlmostEqual(len([m for m in de(s, 'estacion_estado') if m['estacion'] == 1]), 10, delta=2)

    def test_enlace_mudo_deja_de_publicar(self):
        e, r = entorno()
        correr(e, r, 1.0)
        e.enlace(True, mudo=True)
        self.assertEqual(de(correr(e, r, 5.0), 'enlace'), [])
        self.assertEqual(e.instantanea()['enlace'], 'mudo')
        e.enlace(True)
        self.assertTrue(de(correr(e, r, 1.0), 'enlace'))


class TestEstacion(unittest.TestCase):
    def intercambio(self, **kw):
        e, r = entorno(**kw)
        e.iniciar()
        return e, r

    def test_intercambio_normal_estados_y_resultado(self):
        e, r = self.intercambio()
        self.assertIsNone(e.solicitud(2, sol(2)))
        self.assertEqual(e.estados[2], 'CAMBIANDO')
        s = correr(e, r, 5.0)
        self.assertEqual([m['ok'] for m in de(s, 'resultado')], [])
        self.assertEqual(e.estados[2], 'CAMBIANDO')
        s = correr(e, r, 1.0)
        (res,) = de(s, 'resultado')
        self.assertEqual((res['ok'], res['estacion'], res['equipo'], res['pieza_dejo'], res['t_cambio']), (True, 2, 8, 'B', 5.8))
        self.assertEqual(e.estados[2], 'LISTA')
        correr(e, r, 1.0)
        self.assertEqual(e.estados[2], 'LIBRE')
        self.assertEqual(e.n['resultados'], 1)

    def test_el_resultado_llega_antes_o_despues_del_estado_segun_la_configuracion(self):
        for antes in (True, False):
            e, r = self.intercambio(resultado_antes_de_estado=antes, t_cambio_s=1.0)
            e.solicitud(1, sol(1))
            orden = [k for k, c in correr(e, r, 2.0) if k == 'resultado' or (k == 'estacion_estado' and c['estacion'] == 1 and c['estado'] == 'LISTA')]
            self.assertEqual(orden, ['resultado', 'estacion_estado'] if antes else ['estacion_estado', 'resultado'])

    def test_pieza_que_deja_cada_estacion(self):
        for est, deja in ((1, 'A'), (2, 'B'), (3, 'C'), (4, None)):
            e, r = self.intercambio(t_cambio_s=0.2)
            e.solicitud(est, sol(est))
            (res,) = de(correr(e, r, 1.0), 'resultado')
            self.assertEqual((res['ok'], res['pieza_dejo']), (True, deja), msg=est)

    def test_tolerancia_de_pose_incluidos_los_bordes(self):
        casos = ((0.04, 0.0, 0.0, True), (0.0301, 0.0301, 0.0, False), (0.041, 0.0, 0.0, False), (0.0, 0.0, 6.0, True), (0.0, 0.0, -6.01, False),
                 (-0.03, 0.02, 3.0, True))
        for dx, dy, dth, ok in casos:
            e, r = self.intercambio(t_cambio_s=0.1)
            e.solicitud(1, sol(1, dx=dx, dy=dy, dth=dth))
            (res,) = de(correr(e, r, 1.0), 'resultado')
            self.assertEqual(res['ok'], ok, msg=(dx, dy, dth))
            self.assertEqual(res['motivo'], None if ok else 'FUERA_DE_TOLERANCIA')

    def test_pieza_o_equipo_equivocados_son_resultado_no_ok(self):
        for kw, motivo in ((dict(pieza='C'), 'PIEZA_INESPERADA'), (dict(pieza=None, estacion=2), 'PIEZA_INESPERADA'), (dict(equipo=7), 'SIN_TURNO')):
            e, r = self.intercambio(t_cambio_s=0.1)
            est = kw.pop('estacion', 2)
            e.solicitud(est, sol(est, **kw))
            (res,) = de(correr(e, r, 1.0), 'resultado')
            self.assertEqual((res['ok'], res['motivo']), (False, motivo))
            self.assertEqual(e.estados[est], 'LIBRE')                        # un rechazo no deja la estación en LISTA

    def test_un_rechazo_libera_la_estacion_y_un_exito_la_deja_lista(self):
        for pose, esperado in ((0.0, 'LISTA'), (0.1, 'LIBRE')):
            e, r = self.intercambio(t_cambio_s=0.1, t_liberar_s=5.0)
            e.solicitud(1, sol(1, dx=pose))
            correr(e, r, 0.5)                                                    # ya respondió y aún no liberó
            self.assertEqual(e.estados[1], esperado, msg=pose)

    def test_turno_de_otro_equipo(self):
        e, r = self.intercambio(turno_equipo=3, t_cambio_s=0.1)
        e.solicitud(1, sol(1))
        self.assertEqual(de(correr(e, r, 1.0), 'resultado')[0]['motivo'], 'SIN_TURNO')

    def test_mensajes_mal_formados_se_descartan_sin_responder(self):
        malos = [None, [], 'x', {}, sol(equipo=True), sol(equipo='8'), sol(dock=2), {**sol(), 'dock': True}, {**sol(), 'pose': [1]},
                 {**sol(), 'pose': {'dx': float('nan'), 'dy': 0, 'dth': 0}}, {**sol(), 'pose': {'dx': 0, 'dy': 0}},
                 {**sol(), 'pose': {'dx': True, 'dy': 0, 'dth': 0}}, {**sol(), 'pieza_trae': 3}]
        e, r = self.intercambio(t_cambio_s=0.1)
        for m in malos:
            self.assertTrue(e.solicitud(1, m).startswith('DESCARTADO'), msg=m)
        for est in (0, 5, None, [1], True, 'x'):
            self.assertEqual(e.solicitud(est, sol()), 'DESCARTADO_ESTACION')
        self.assertEqual(de(correr(e, r, 2.0), 'resultado'), [])
        self.assertEqual((e.n['solicitudes'], e.estados[1]), (0, 'LIBRE'))

    def test_una_segunda_solicitud_mientras_cambia_se_ignora(self):
        e, r = self.intercambio(t_cambio_s=1.0)
        e.solicitud(1, sol(1))
        self.assertEqual(e.solicitud(1, sol(1)), 'OCUPADA')
        self.assertEqual(len(de(correr(e, r, 3.0), 'resultado')), 1)
        self.assertIsNone(e.solicitud(1, sol(1)))                              # libre otra vez: acepta

    def test_estaciones_independientes(self):
        e, r = self.intercambio(t_cambio_s=1.0)
        e.solicitud(1, sol(1))
        e.solicitud(3, sol(3))
        self.assertEqual(sorted(m['estacion'] for m in de(correr(e, r, 2.0), 'resultado')), [1, 3])


class TestModosDeFalla(unittest.TestCase):
    def test_rechazar(self):
        e, r = entorno(modo='rechazar', t_cambio_s=0.1)
        e.solicitud(1, sol(1))
        (res,) = de(correr(e, r, 1.0), 'resultado')
        self.assertEqual((res['ok'], res['motivo']), (False, 'RECHAZO_FORZADO'))

    def test_no_responder_deja_la_estacion_cambiando_para_siempre(self):
        e, r = entorno(modo='no_responder', t_cambio_s=0.1)
        e.solicitud(1, sol(1))
        self.assertEqual(de(correr(e, r, 200.0), 'resultado'), [])
        self.assertEqual(e.estados[1], 'CAMBIANDO')

    def test_pieza_mala_responde_ok_con_otra_pieza(self):
        e, r = entorno(modo='pieza_mala', t_cambio_s=0.1)
        e.solicitud(2, sol(2))
        (res,) = de(correr(e, r, 1.0), 'resultado')
        self.assertEqual((res['ok'], res['pieza_dejo']), (True, 'Z'))

    def test_offline_publica_offline_e_ignora_solicitudes(self):
        e, r = entorno(modo='offline', estacion_modo=3)
        s = correr(e, r, 2.0)
        self.assertEqual({m['estado'] for m in de(s, 'estacion_estado') if m['estacion'] == 3}, {'OFFLINE'})
        self.assertEqual({m['estado'] for m in de(s, 'estacion_estado') if m['estacion'] == 2}, {'LIBRE'})
        self.assertEqual(e.solicitud(3, sol(3)), 'ESTACION_OFFLINE')

    def test_estacion_modo_limita_la_falla_a_una_estacion(self):
        e, r = entorno(modo='rechazar', estacion_modo=2, t_cambio_s=0.1)
        e.solicitud(1, sol(1))
        e.solicitud(2, sol(2))
        res = {m['estacion']: m['ok'] for m in de(correr(e, r, 1.0), 'resultado')}
        self.assertEqual(res, {1: True, 2: False})

    def test_fallar_proximo_vale_una_sola_vez(self):
        e, r = entorno(t_cambio_s=0.1)
        e.fallar_proximo('rechazar')
        e.solicitud(1, sol(1))
        correr(e, r, 1.0)
        e.solicitud(1, sol(1))
        oks = [m['ok'] for m in de(correr(e, r, 1.0), 'resultado')]
        self.assertEqual(oks, [True])
        with self.assertRaises(ValueError):
            e.fallar_proximo('offline')

    def test_contadores_de_eventos_y_vueltas(self):
        e, r = entorno()
        for m in ({'tipo': 'pit_ok'}, {'tipo': 'pit_ok'}, {'tipo': 'reintento'}, {'tipo': 'intervencion'}, 'x', None):
            e.evento(m)
        for m in ({'numero': 1}, {'numero': 2}, {'numero': 'x'}, {}):
            e.vuelta(m)
        i = e.instantanea()
        self.assertEqual((i['pit_ok'], i['reintento'], i['vueltas'], i['vueltas_vistas']), (2, 1, 2, [1, 2]))
        json.dumps(i, allow_nan=False)


class Puente:
    """Une el entorno falso con `MaquinaPit` como lo harían el adaptador y los tópicos, sin ROS."""

    def __init__(self, mundo, e):
        self.m, self.e = mundo, e
        poner = mundo.puerto
        evento, vuelta = poner.evento, poner.vuelta
        poner.evento = lambda tipo, est: (evento(tipo, est), e.evento({'tipo': tipo, 'estacion': est}))
        poner.vuelta = lambda n, a, b, est: (vuelta(n, a, b, est), e.vuelta({'numero': n}))
        mundo.estacion = self

    def solicitud(self, estacion, pose, pieza_trae):
        self.e.solicitud(estacion, json.loads(mc.a_json(mc.solicitud(self.m.cfg_mision.equipo, estacion, pose.dx, pose.dy, pose.dth, pieza_trae))))

    def avanzar(self):
        f = self.m.fsm
        for canal, c in self.e.paso():
            if canal == 'turno':
                f.recibir_turno(c['autorizado'])
            elif canal == 'bandera':
                f.recibir_bandera(c['bandera'])
            elif canal == 'enlace':
                f.recibir_enlace(c)
            elif canal == 'estacion_estado':
                f.recibir_estacion(c['estacion'], c['estado'])
            elif canal == 'resultado' and c['equipo'] == self.m.cfg_mision.equipo:
                f.recibir_resultado(c['estacion'], c['ok'], c['pieza_dejo'])


def mundo(iniciar=True, **kw):
    m = Mundo(escalas_ini=(1.01, 1.09), **kw['mundo'] if 'mundo' in kw else {})
    e = ef.EntornoFalso(ef.ConfigFalsa(**{k: v for k, v in kw.items() if k != 'mundo'}), lambda: m.t, lambda: 1.7e9 + m.t)
    Puente(m, e)
    if iniciar:
        e.iniciar()
    return m, e


def correr_mision(m, max_s=900.0):
    fin = m.t + max_s
    while m.t < fin and m.fsm.estado not in (E.FIN, E.FALLA):
        m.paso(lambda mm: None)
    return m.fsm.estado


def hasta(m, estado):
    while m.fsm.estado is not estado and m.t < 3000:
        m.paso(lambda mm: None)
    assert m.fsm.estado is estado


class TestConLaMaquinaDeLaMision(unittest.TestCase):
    def test_cuatro_vueltas_con_el_curso_y_la_estacion_falsos(self):
        m, e = mundo()
        self.assertEqual(correr_mision(m), E.FIN)
        i = e.instantanea()
        self.assertEqual((i['solicitudes'], i['resultados'], i['pit_ok'], i['vueltas'], i['vueltas_vistas']), (16, 16, 16, 4, [1, 2, 3, 4]))
        self.assertEqual(i['descartadas'] + i['ocupada'], 0)
        self.assertTrue(all(p.valido for p in m.mision.pits))

    def test_la_estacion_falsa_solo_ve_la_pose_que_el_carro_reporta(self):
        m, e = mundo()
        correr_mision(m)
        self.assertEqual(e.ultima_solicitud['estacion'], 4)
        self.assertLessEqual(math.hypot(e.ultima_solicitud['dx'], e.ultima_solicitud['dy']), 0.04)

    def test_resultado_antes_o_despues_del_estado_la_mision_completa(self):
        for antes in (True, False):
            m, e = mundo(resultado_antes_de_estado=antes)
            self.assertEqual(correr_mision(m), E.FIN, msg=antes)

    def test_intercambios_de_cualquier_duracion(self):
        for t in (0.0, 2.0, 12.0):
            m, e = mundo(t_cambio_s=t)
            self.assertEqual(correr_mision(m), E.FIN, msg=t)
        self.assertEqual(m.fsm.pits_lentos, 16)

    def test_sin_el_turno_el_carro_no_arranca_y_con_autoiniciar_si(self):
        m, e = mundo(iniciar=False)
        for _ in range(600):
            m.paso(lambda mm: None)
        self.assertEqual((m.fsm.estado, m.vel), (E.ESPERA, []))
        m2, e2 = mundo(iniciar=False, autoiniciar_s=2.0)
        for _ in range(200):
            m2.paso(lambda mm: None)
        self.assertNotEqual(m2.fsm.estado, E.ESPERA)

    def test_modos_de_falla_y_la_respuesta_segura_del_carro(self):
        casos = {'rechazar': ('RESULTADO_NO_OK', dict(modo='rechazar', estacion_modo=2)),
                 'no_responder': ('TIMEOUT_ESPERANDO_RESULTADO', dict(modo='no_responder', estacion_modo=2)),
                 'offline': ('ESTACION_OFFLINE', dict(modo='offline', estacion_modo=3)),
                 'otro_equipo': ('RESULTADO_NO_OK', dict(turno_equipo=5))}
        for nombre, (motivo, kw) in casos.items():
            m, e = mundo(**kw)
            self.assertEqual(correr_mision(m), E.FALLA, msg=nombre)
            self.assertEqual(m.fsm.motivo, motivo, msg=nombre)
            self.assertEqual(m.planta._v, 0.0)

    def test_pieza_mala_marca_los_pits_invalidos_y_sigue(self):
        m, e = mundo(modo='pieza_mala', estacion_modo=2)
        self.assertEqual(correr_mision(m), E.FIN)
        self.assertEqual(m.mision.pits_invalidos, 4)

    def test_ordenes_del_curso_en_plena_marcha(self):
        casos = {'turno': (lambda e: e.retirar_turno(), 'SIN_AUTORIZACION'), 'roja': (lambda e: e.bandera('roja'), 'BANDERA_ROJA'),
                 'enlace_caido': (lambda e: e.enlace(False), 'ENLACE_PERDIDO'), 'enlace_mudo': (lambda e: e.enlace(True, mudo=True), 'ENLACE_PERDIDO')}
        for nombre, (orden, motivo) in casos.items():
            m, e = mundo()
            hasta(m, E.NAVEGANDO)
            for _ in range(100):
                m.paso(lambda mm: None)
            orden(e)
            for _ in range(200):
                m.paso(lambda mm: None)
            self.assertEqual((m.fsm.estado, m.fsm.motivo), (E.FALLA, motivo), msg=nombre)
            self.assertEqual((m.planta._v, m.planta._w), (0.0, 0.0), msg=nombre)

    def test_un_enlace_que_vuelve_antes_del_plazo_no_aborta(self):
        m, e = mundo()
        hasta(m, E.NAVEGANDO)
        e.enlace(True, mudo=True)
        for _ in range(20):                                                   # 1 s de silencio < 2 s de enlace_max_s
            m.paso(lambda mm: None)
        e.enlace(True)
        for _ in range(100):
            m.paso(lambda mm: None)
        self.assertEqual(m.fsm.estado, E.NAVEGANDO)


class TestNodo(unittest.TestCase):
    def crear(self, **parametros):
        Node.sobrescribe = parametros
        self.addCleanup(lambda: setattr(Node, 'sobrescribe', {}))
        self.t = [1000.0]
        for nombre in ('monotonic', 'time'):
            p = mock.patch(f'time.{nombre}', lambda: self.t[0] if nombre == 'monotonic' else 1.7e9 + self.t[0])
            p.start()
            self.addCleanup(p.stop)
        self.nodo = ef._clase_nodo()()
        return self.nodo

    def avanzar(self, n, s):
        fin = self.t[0] + s
        while self.t[0] < fin:
            n.timers[0][1]()
            self.t[0] += 0.1

    def enviados(self, n, topico):
        return n.publicador(topico).enviados

    def servicio(self, n, nombre):
        cb = next(c for _, nom, c in n.servicios if nom == f'~/{nombre}')
        return cb(None, Ns(success=None, message=None))

    def test_interfaces(self):
        n = self.crear()
        self.assertEqual({t for _, t, _ in n.subs}, {'/granprix/solicitud', '/granprix/evento', '/granprix/vuelta'})
        self.assertTrue({'/granprix/turno', '/granprix/bandera', '/granprix/enlace', '/granprix/estacion_estado', '/granprix/resultado'}
                        <= {t for _, t, _ in n.pubs})
        self.assertEqual({nom for _, nom, _ in n.servicios}, {f'~/{a}' for a in ef.ACCIONES})
        self.assertEqual(sorted(round(p, 2) for p, _ in n.timers), [0.1, 1.0])

    def test_parametros(self):
        n = self.crear(modo='rechazar', estacion_modo=2, t_cambio_s=3.0, autoiniciar_s=4.0, turno_equipo=5, resultado_antes_de_estado=False)
        c = n.entorno.cfg
        self.assertEqual((c.modo, c.estacion_modo, c.t_cambio_s, c.autoiniciar_s, c.turno_equipo, c.resultado_antes_de_estado),
                         ('rechazar', 2, 3.0, 4.0, 5, False))
        n = self.crear()
        c = n.entorno.cfg
        self.assertEqual((c.modo, c.estacion_modo, c.autoiniciar_s, c.turno_equipo, c.equipo), ('ok', None, None, None, 8))
        with self.assertRaises(ValueError):
            self.crear(modo='raro')

    def test_sin_orden_no_da_el_turno_y_publica_el_resto(self):
        n = self.crear()
        self.avanzar(n, 3.0)
        turno = json.loads(self.enviados(n, '/granprix/turno')[-1].data)
        self.assertEqual((turno['autorizado'], turno['v']), (False, 1))
        self.assertEqual(self.enviados(n, '/granprix/enlace')[-1].data, True)
        self.assertEqual(json.loads(self.enviados(n, '/granprix/bandera')[-1].data)['bandera'], 'verde')
        self.assertEqual({json.loads(m.data)['estacion'] for m in self.enviados(n, '/granprix/estacion_estado')}, {1, 2, 3, 4})

    def test_servicios_del_curso(self):
        n = self.crear()
        r = self.servicio(n, 'iniciar')
        self.assertTrue(r.success)
        self.avanzar(n, 1.5)
        self.assertTrue(json.loads(self.enviados(n, '/granprix/turno')[-1].data)['autorizado'])
        self.servicio(n, 'roja')
        self.avanzar(n, 0.3)
        self.assertEqual(json.loads(self.enviados(n, '/granprix/bandera')[-1].data)['bandera'], 'roja')
        self.servicio(n, 'cortar_enlace')
        self.avanzar(n, 0.7)
        self.assertEqual(self.enviados(n, '/granprix/enlace')[-1].data, False)
        self.servicio(n, 'silenciar_enlace')
        antes = len(self.enviados(n, '/granprix/enlace'))
        self.avanzar(n, 3.0)
        self.assertEqual(len(self.enviados(n, '/granprix/enlace')), antes)
        self.servicio(n, 'restaurar_enlace')
        self.avanzar(n, 1.0)
        self.assertEqual(self.enviados(n, '/granprix/enlace')[-1].data, True)
        self.servicio(n, 'retirar_turno')
        self.avanzar(n, 1.5)
        self.assertFalse(json.loads(self.enviados(n, '/granprix/turno')[-1].data)['autorizado'])
        self.assertEqual(json.loads(r.message)['modo'], 'ok')

    def test_solicitud_y_resultado_por_los_topicos(self):
        n = self.crear(t_cambio_s=2.0)
        n.callback('/granprix/solicitud')(Mensaje(json.dumps(sol(2))))
        self.avanzar(n, 1.0)
        estados = [json.loads(m.data) for m in self.enviados(n, '/granprix/estacion_estado')]
        self.assertEqual([x['estado'] for x in estados if x['estacion'] == 2][-1], 'CAMBIANDO')
        self.assertEqual(self.enviados(n, '/granprix/resultado'), [])
        self.avanzar(n, 2.0)
        (res,) = [json.loads(m.data) for m in self.enviados(n, '/granprix/resultado')]
        self.assertEqual((res['estacion'], res['equipo'], res['ok'], res['pieza_dejo'], res['t_cambio']), (2, 8, True, 'B', 2.0))

    def test_mensajes_que_no_son_json_se_cuentan_y_no_rompen(self):
        n = self.crear()
        for topico in ('/granprix/solicitud', '/granprix/evento', '/granprix/vuelta'):
            for basura in ('no es json', '[1,2]', None):
                n.callback(topico)(Mensaje(basura))
        n.callback('/granprix/solicitud')(Mensaje(json.dumps({**sol(1), 'dock': [1]})))
        self.assertEqual(n.entorno.n['descartadas'], 10)
        self.avanzar(n, 1.0)
        self.assertEqual(n.entorno.n['solicitudes'], 0)

    def test_registro_de_mensajes_y_estado(self):
        with tempfile.TemporaryDirectory() as d:
            n = self.crear(t_cambio_s=0.5, registro_dir=d)
            n.callback('/granprix/solicitud')(Mensaje(json.dumps(sol(1))))
            n.callback('/granprix/evento')(Mensaje(json.dumps({'tipo': 'pit_ok', 'estacion': 1})))
            self.avanzar(n, 2.0)
            n._publicar_estado()
            with open(os.path.join(d, 'mensajes_falsos.jsonl')) as f:
                lineas = [json.loads(x) for x in f]
            self.assertEqual({(x['sentido'], x['canal']) for x in lineas}, {('rx', 'solicitud'), ('rx', 'evento'), ('tx', 'resultado'), ('tx', 'turno'), ('tx', 'bandera')})
            est = json.loads(self.enviados(n, '/estacion_falsa/estado')[-1].data) if False else json.loads(n.estado_pub.enviados[-1].data)
            self.assertEqual((est['solicitudes'], est['resultados'], est['pit_ok']), (1, 1, 1))
            n._log.close()


class TestCompatibleConElAdaptador(unittest.TestCase):
    """El adaptador real (con rclpy sustituto) y la estación falsa conversando por los tópicos: primer pit completo."""

    def test_primer_pit_de_punta_a_punta(self):
        Node.sobrescribe = {'marcos_yaml': SIM}
        self.addCleanup(lambda: setattr(Node, 'sobrescribe', {}))
        t = [1000.0]
        for nombre in ('monotonic', 'time'):
            p = mock.patch(f'time.{nombre}', lambda nombre=nombre: t[0] if nombre == 'monotonic' else 1.7e9 + t[0])
            p.start()
            self.addCleanup(p.stop)
        auto = af._clase_nodo()()
        Node.sobrescribe = {'t_cambio_s': 3.0}
        falsa = ef._clase_nodo()()
        vistos = {}

        def cruzar(origen, destino):
            for _, topico, pub in origen.pubs:
                ya = vistos.get((id(origen), topico), 0)
                for m in pub.enviados[ya:]:
                    cb = next((c for _, tp, c in destino.subs if tp == topico), None)
                    if cb:
                        cb(m)
                vistos[(id(origen), topico)] = len(pub.enviados)

        def paso():
            if round(t[0] * 20) % 2 == 0:
                auto.callback('/odom')(odom_msg())
                auto.callback('/tag/pose')(tag_msg(0.0, 0.0, 0.0))
            for f in auto.reset.llamadas:
                if not f.listo:
                    f.listo, f.valor = True, Ns(success=True, message=json.dumps({'motivo': None}))
            falsa.timers[0][1]()
            cruzar(falsa, auto)
            auto._tick()
            cruzar(auto, falsa)
            t[0] += 0.05

        for _ in range(40):
            paso()
        self.assertEqual(auto.fsm.estado, E.ESPERA)                           # sin turno no arranca
        falsa.entorno.iniciar()
        for _ in range(400):
            paso()
            if auto.fsm.estado is E.NAVEGANDO:
                break
        self.assertEqual((auto.fsm.estado, auto.fsm.motivo), (E.NAVEGANDO, None))
        i = falsa.entorno.instantanea()
        self.assertEqual((i['solicitudes'], i['resultados'], i['pit_ok'], i['descartadas']), (1, 1, 1, 0))
        self.assertTrue(auto.fsm.mision.pits[0].valido)
        self.assertEqual(auto.fsm.mision.pits[0].pieza_recibida, 'A')


if __name__ == '__main__':
    unittest.main()
