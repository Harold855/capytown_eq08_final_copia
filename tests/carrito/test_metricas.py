"""Eventos de la misión, cronómetro y métricas. Las cifras se comprueban contra la misión simulada y contra casos armados a mano."""
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from carrito.granprix_carrito import cronometro as cr
from carrito.granprix_carrito.tablero_extension import metricas as me
from carrito.granprix_carrito.eventos_mision import Evento, RegistroEventos, leer_eventos
from simulacion.mision_simulada import Mundo

CALIBRADO = dict(escalas_ini=(1.01, 1.09))


def ev(ts, tipo, estado=None, vuelta=None, estacion=None, motivo=None, **datos):
    return Evento(float(ts), tipo, estado, vuelta, estacion, motivo, datos)


def pit(ts, vuelta, est, t_pit=8.0, valido=True, pos_pre=0.02, pos_post=0.01, ang_pre=1.0, ang_post=0.5, cd=1.0, ca=1.0, corr=0, reint=0):
    return Evento(float(ts), 'pit', 'SALIENDO', vuelta, est, None,
                  dict(vuelta=vuelta, estacion=est, t_pit_s=t_pit, valido=valido, err_pos_pre_m=pos_pre, err_pos_post_m=pos_post,
                       err_ang_pre_deg=ang_pre, err_ang_post_deg=ang_post, cd=cd, ca=ca, correcciones=corr, reintentos=reint,
                       pieza_recibida='A'))


class TestEventos(unittest.TestCase):
    def test_ida_y_vuelta_por_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, 'sub', 'e.jsonl')
            r = RegistroEventos(lambda: 1700.5, ruta)
            r.registrar('estado', 'MIDIENDO', 1, 2, datos={'de': 'NAVEGANDO', 'x': (1, 2), 'inf': float('inf'), 'nan': float('nan')})
            r.registrar('aviso', datos={'texto': 'hola'})
            r.cerrar()
            leidos = leer_eventos(ruta)
        self.assertEqual([e.tipo for e in leidos], ['estado', 'aviso'])
        self.assertEqual((leidos[0].estado, leidos[0].vuelta, leidos[0].estacion, leidos[0].ts), ('MIDIENDO', 1, 2, 1700.5))
        self.assertEqual(leidos[0].datos, {'de': 'NAVEGANDO', 'x': [1, 2], 'inf': None, 'nan': None})      # nada de NaN en el archivo

    def test_tipo_desconocido(self):
        with self.assertRaises(ValueError):
            RegistroEventos().registrar('inventado')

    def test_corte_a_mitad_de_linea_descarta_solo_la_ultima(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, 'e.jsonl')
            r = RegistroEventos(lambda: 5.0, ruta)
            r.registrar('inicio')
            r.registrar('fin')
            r.cerrar()
            with open(ruta, 'a') as f:
                f.write('{"ts":6.0,"tipo":"aviso","dat')
            self.assertEqual([e.tipo for e in leer_eventos(ruta)], ['inicio', 'fin'])

    def test_una_linea_mala_en_medio_es_error_con_su_numero(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = os.path.join(d, 'e.jsonl')
            Path(ruta).write_text('{"ts":1,"tipo":"inicio","datos":{}}\nbasura\n{"ts":2,"tipo":"fin","datos":{}}\n')
            with self.assertRaisesRegex(ValueError, 'línea 2'):
                leer_eventos(ruta)

    def test_eventos_invalidos(self):
        for d in ({'tipo': 'fin'}, {'ts': 'x', 'tipo': 'fin'}, {'ts': True, 'tipo': 'fin'}, {'ts': float('nan'), 'tipo': 'fin'},
                  {'ts': 1, 'tipo': 'otro'}, {'ts': 1, 'tipo': 'fin', 'datos': [1]}, []):
            with self.assertRaises(ValueError, msg=d):
                Evento.desde_dict(d)

    def test_un_disco_que_falla_no_detiene_ni_pierde_la_memoria(self):
        with tempfile.TemporaryDirectory() as d:
            r = RegistroEventos(lambda: 1.0, d)                      # una carpeta no se puede abrir como archivo
            self.assertIsNotNone(r.error_escritura)
            r.registrar('inicio')
            self.assertEqual(len(r.eventos), 1)
            r2 = RegistroEventos(lambda: 1.0, os.path.join(d, 'e.jsonl'))
            r2._f.close()                                            # el archivo se rompe en pleno uso
            r2.registrar('inicio')
            r2.registrar('fin')
            self.assertIsNotNone(r2.error_escritura)
            self.assertEqual(len(r2.eventos), 2)

    def test_solo_los_eventos_importantes_fuerzan_fsync(self):
        with tempfile.TemporaryDirectory() as d, mock.patch('os.fsync') as fs:
            r = RegistroEventos(lambda: 1.0, os.path.join(d, 'e.jsonl'))
            for t in ('inicio', 'estado', 'aviso', 'pit'):
                r.registrar(t)
            self.assertEqual(fs.call_count, 0)
            for t in ('falla', 'vuelta', 'fin'):
                r.registrar(t)
            self.assertEqual(fs.call_count, 3)
            r.cerrar()

    def test_la_memoria_tiene_tope(self):
        r = RegistroEventos(lambda: 1.0, maximo=5)
        for _ in range(9):
            r.registrar('aviso')
        self.assertEqual(len(r.eventos), 5)


class TestMisionRegistrada(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.ruta = os.path.join(cls.dir.name, 'eventos.jsonl')
        cls.m = Mundo(**CALIBRADO, eventos=RegistroEventos(lambda: 1.7e9 + 0.0, cls.ruta))
        cls.m.fsm.eventos._reloj = lambda: cls.m.fsm.reloj_ts()
        cls.m.correr()
        cls.m.fsm.eventos.cerrar()
        cls.ev = leer_eventos(cls.ruta)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_el_archivo_trae_lo_mismo_que_la_memoria(self):
        self.assertEqual(len(self.ev), len(self.m.fsm.eventos.eventos))

    def test_empieza_con_inicio_y_termina_con_fin_en_orden_de_tiempo(self):
        self.assertEqual([e.tipo for e in self.ev if e.tipo in ('inicio', 'fin')], ['inicio', 'fin'])
        primero_estado = next(i for i, e in enumerate(self.ev) if e.tipo == 'estado')
        self.assertLess(next(i for i, e in enumerate(self.ev) if e.tipo == 'inicio'), primero_estado)
        ts = [e.ts for e in self.ev]
        self.assertEqual(ts, sorted(ts))

    def test_la_cadena_de_estados_es_coherente(self):
        est = [e for e in self.ev if e.tipo == 'estado']
        self.assertEqual(est[0].datos['de'], 'ESPERA')
        for a, b in zip(est, est[1:]):
            self.assertEqual(b.datos['de'], a.estado)

    def test_un_evento_de_cada_cosa_por_parada(self):
        cuenta = lambda t: sum(1 for e in self.ev if e.tipo == t)  # noqa: E731
        self.assertEqual((cuenta('pit'), cuenta('pit_cerrado'), cuenta('solicitud'), cuenta('resultado'), cuenta('acople'),
                          cuenta('reset'), cuenta('vuelta')), (16, 16, 16, 16, 16, 16, 4))

    def test_las_entradas_solo_se_registran_al_cambiar(self):
        turnos = [e for e in self.ev if e.tipo == 'entrada' and e.datos['campo'] == 'turno']
        self.assertEqual(len(turnos), 1)                                  # el turno se reenvía cada 0.5 s: un solo cambio
        self.assertEqual((turnos[0].datos['antes'], turnos[0].datos['ahora']), (None, True))

    def test_el_evento_pit_lleva_la_fila_completa(self):
        p = next(e for e in self.ev if e.tipo == 'pit')
        for k in ('vuelta', 'estacion', 't_pit_s', 'err_pos_pre_m', 'err_pos_post_m', 'cd', 'ca', 'valido', 'correcciones', 'reintentos'):
            self.assertIn(k, p.datos)
        self.assertEqual((p.vuelta, p.estacion), (p.datos['vuelta'], p.datos['estacion']))

    def test_una_falla_queda_registrada_con_su_motivo(self):
        m = Mundo(**CALIBRADO)
        m.estacion.respuesta = lambda est, ok, deja: (False, None) if est == 2 else (ok, deja)
        m.correr()
        f = [e for e in m.fsm.eventos.eventos if e.tipo == 'falla']
        self.assertEqual([(e.motivo, e.estacion) for e in f], [('RESULTADO_NO_OK', 2)])

    def test_registrar_nunca_detiene_la_mision(self):
        class Roto(RegistroEventos):
            def registrar(self, *a, **k):
                raise RuntimeError('disco lleno')
        m = Mundo(**CALIBRADO, eventos=Roto())
        m.correr()
        self.assertEqual((m.fsm.estado.value, m.fsm.motivo), ('FIN', None))


class TestCronometro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Mundo(**CALIBRADO)
        cls.m.correr()
        cls.ev = cls.m.fsm.eventos.eventos
        cls.v = cr.vueltas_desde_eventos(cls.ev)

    def test_cuatro_vueltas_y_los_sectores_suman_la_vuelta(self):
        self.assertEqual([v.numero for v in self.v], [1, 2, 3, 4])
        for v in self.v:
            self.assertTrue(all(s is not None and s > 0 for s in v.sectores))
            self.assertAlmostEqual(sum(v.sectores), v.duracion, places=6)
            self.assertTrue(v.valida)

    def test_las_vueltas_coinciden_con_las_publicadas_al_curso(self):
        for v, (n, ini, fin, _) in zip(self.v, self.m.puerto.vueltas):
            self.assertEqual((v.numero, v.t_inicio, v.t_fin), (n, ini, fin))

    def test_los_pits_coinciden_con_el_registro_de_la_mision(self):
        esperado = {(p.vuelta, p.estacion): p.t_pit_s for p in self.m.mision.pits}
        for v in self.v:
            for est, t in enumerate(v.pits, 1):
                self.assertEqual(t, esperado[(v.numero, est)])

    def test_un_sector_es_el_tramo_mas_el_pit_de_salida(self):
        tramos = {(v, e): d for v, e, d in cr.tramos_desde_eventos(self.ev)}
        pits = {(p.vuelta, p.estacion): p.t_pit_s for p in self.m.mision.pits}
        v1 = self.v[0]
        self.assertAlmostEqual(v1.sectores[0], pits[(1, 1)] + tramos[(1, 2)], delta=0.1)

    def test_tramos(self):
        t = cr.tramos_desde_eventos(self.ev)
        self.assertEqual(len(t), 15)                                       # 16 pits, 15 tramos entre ellos
        self.assertEqual([e for _, e, _ in t[:4]], [2, 3, 4, 1])
        self.assertTrue(all(20.0 < d < 40.0 for _, _, d in t))              # 2 m a 0.1 m/s + giro 90°

    def test_datos_que_faltan_quedan_en_none(self):
        e = [ev(10, 'estado', 'MIDIENDO', 1, 1), ev(20, 'estado', 'MIDIENDO', 1, 3), ev(40, 'estado', 'MIDIENDO', 1, 4),
             pit(41, 1, 1, valido=True), pit(42, 1, 4, valido=False), ev(50, 'vuelta', vuelta=1, numero=1, t_inicio=10.0, t_fin=50.0)]
        (v,) = cr.vueltas_desde_eventos(e)
        self.assertEqual(v.sectores, (None, None, 20.0, 10.0))
        self.assertEqual(v.pits, (8.0, None, None, 8.0))
        self.assertFalse(v.valida)

    def test_resumen_ultima_mejor_delta(self):
        vs = [cr.VueltaTiempo(i + 1, 0, d, d, (None,) * 4, (None,) * 4, True) for i, d in enumerate((120.0, 110.0, 115.0))]
        r = cr.resumen_vueltas(vs)
        self.assertEqual((r['ultima'], r['mejor'], r['delta']), (115.0, 110.0, 5.0))
        self.assertAlmostEqual(r['media'], 115.0)
        self.assertEqual(cr.resumen_vueltas([]), {'ultima': None, 'mejor': None, 'delta': None, 'media': None})


class TestFormulas(unittest.TestCase):
    def test_puntos_de_la_rubrica_en_los_bordes(self):
        self.assertEqual([me._pts_tanda(n) for n in range(6)], [0, 0, 1, 3, 4, 4])
        self.assertEqual([me._pts_pieza(f) for f in (1.0, 0.9, 0.899, 0.75, 0.749, 0.5, 0.499, 0.0)], [3, 3, 2, 2, 1, 1, 0, 0])
        self.assertEqual([me._pts_autonomia(n) for n in (0, 1, 2, 3, 5, 6, None)], [3, 2, 2, 1, 1, 0, None])

    def test_percentil(self):
        self.assertEqual(me.percentil(list(range(1, 21))), 19)
        self.assertEqual(me.percentil([5.0]), 5.0)
        self.assertIsNone(me.percentil([]))

    def test_convergio(self):
        self.assertTrue(me.convergio([1.5, 1.2, 1.0, 1.001, 1.002, 1.003]))
        self.assertFalse(me.convergio([1.0, 1.0, 1.0]))                    # pocas
        self.assertFalse(me.convergio([1.0, 1.0, 1.0, 1.02]))              # dispersión de 0.02


class TestMetricas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Mundo(**CALIBRADO)
        cls.m.correr()
        cls.d = me.calcular(cls.m.fsm.eventos.eventos)

    def test_mision_completa(self):
        d = self.d
        self.assertEqual(d['estado']['estado'], 'FIN')
        self.assertEqual({k: d['mision'][k] for k in ('vueltas_cerradas', 'vueltas_validas', 'pits', 'pits_validos', 'terminada')},
                         {'vueltas_cerradas': 4, 'vueltas_validas': 4, 'pits': 16, 'pits_validos': 16, 'terminada': True})
        self.assertEqual(d['rubrica_estimada']['tanda_pts'], 4)
        self.assertEqual(d['rubrica_estimada']['pieza_pts'], 3)
        self.assertIsNone(d['rubrica_estimada']['autonomia_pts'])        # no se inventa lo que no se sabe

    def test_pits_coinciden_con_el_registro_de_la_mision(self):
        p, pits = self.d['pits'], self.m.mision.pits
        self.assertAlmostEqual(p['t_medio_s'], sum(x.t_pit_s for x in pits) / 16)
        self.assertEqual(p['lentos'], self.m.fsm.pits_lentos)
        self.assertEqual(p['con_correccion'], sum(1 for x in pits if x.correcciones))
        self.assertEqual(p['reintentos'], sum(x.reintentos for x in pits))
        self.assertAlmostEqual(p['err_pos_pre_cm']['media'], sum(x.err_pos_pre_m for x in pits) / 16 * 100)

    def test_reduccion_coincide_con_la_del_calibrador(self):
        ev = self.m.fsm.calibrador.evaluacion()
        r = self.d['pits']['reduccion']
        self.assertEqual((r['n'], r['mejoran'], r['cumple']), (ev.n, ev.n_mejoran, ev.cumple))

    def test_escalas_y_estaciones(self):
        e = self.d['escalas']
        self.assertEqual(len(e['serie']), 16)
        self.assertAlmostEqual(e['ca_final'], self.m.fsm.calibrador.estimador.escalas.ca, places=9)
        self.assertEqual([s['estacion'] for s in self.d['estaciones']], [1, 2, 3, 4])
        self.assertEqual(self.d['estado']['ca'], e['ca_final'])

    def test_una_misión_que_falla(self):
        m = Mundo(**CALIBRADO)
        m.estacion.respuesta = lambda est, ok, deja: (False, None) if est == 3 else (ok, deja)
        m.correr()
        d = me.calcular(m.fsm.eventos.eventos)
        self.assertEqual((d['estado']['estado'], d['estado']['motivo']), ('FALLA', 'RESULTADO_NO_OK'))
        self.assertEqual((d['mision']['vueltas_cerradas'], d['rubrica_estimada']['tanda_pts'], d['mision']['terminada']), (0, 0, False))
        self.assertEqual(d['mision']['fallas'][0]['estacion'], 3)

    def test_sin_datos_no_inventa_nada(self):
        d = me.calcular([])
        self.assertEqual(d['estado']['estado'], 'SIN_DATOS')
        self.assertIsNone(d['pits']['t_medio_s'])
        self.assertIsNone(d['pits']['reduccion'])
        self.assertFalse(d['escalas']['convergio'])
        json.dumps(d, allow_nan=False)

    def test_pits_armados_a_mano(self):
        e = [ev(0, 'inicio'), pit(1, 1, 1, t_pit=5.0, pos_pre=0.10, pos_post=0.01), pit(2, 1, 2, t_pit=12.0, pos_pre=0.01, pos_post=0.02, corr=1),
             pit(3, 1, 3, t_pit=9.0, valido=False)]
        d = me.calcular(e, intervenciones=2)
        self.assertEqual((d['pits']['lentos'], d['pits']['t_max_s'], d['pits']['con_correccion']), (1, 12.0, 1))
        self.assertEqual((d['mision']['pits_validos'], d['rubrica_estimada']['autonomia_pts']), (2, 2))
        self.assertEqual(d['pits']['reduccion']['n'], 3)

    def test_valores_no_numericos_se_ignoran(self):
        malo = pit(1, 1, 1)
        malo.datos.update(t_pit_s='x', err_pos_pre_m=None, cd=float('nan'))
        d = me.calcular([malo])
        self.assertIsNone(d['pits']['t_medio_s'])
        self.assertIsNone(d['estado']['cd'])

    def test_todo_es_serializable_sin_nan(self):
        json.dumps(self.d, allow_nan=False)

    def test_eventos_recientes_acotados(self):
        self.assertLessEqual(len(self.d['eventos_recientes']), 30)


class TestCli(unittest.TestCase):
    def correr(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = me.main(list(args))
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_escribe_el_json_de_forma_atomica(self):
        with tempfile.TemporaryDirectory() as d:
            r = RegistroEventos(lambda: 1.0, os.path.join(d, 'eventos.jsonl'))
            r.registrar('inicio')
            r.cerrar()
            salida = os.path.join(d, 'datos.json')
            self.assertEqual(self.correr(d, '--salida', salida)[0], 0)
            with open(salida) as f:
                self.assertEqual(json.load(f)['estado']['estado'], 'SIN_DATOS')
            self.assertEqual(sorted(os.listdir(d)), ['datos.json', 'eventos.jsonl'])     # sin .tmp sobrante

    def test_imprime_por_defecto(self):
        with tempfile.TemporaryDirectory() as d:
            RegistroEventos(lambda: 1.0, os.path.join(d, 'eventos.jsonl')).cerrar()
            rc, out, _ = self.correr(d)
            self.assertEqual((rc, json.loads(out)['version']), (0, 1))

    def test_errores(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _, err = self.correr(d)
            self.assertEqual(rc, 1)
            self.assertIn('ERROR', err)
            self.assertEqual(self.correr(d, '--cada', '-1')[0], 2)


class TestDatosSimuladosYPanel(unittest.TestCase):
    """`tablero/datos_simulados.py` produce lo que lee `tablero/panel.js`; si cambia uno sin el otro, esto falla."""

    @classmethod
    def setUpClass(cls):
        from tablero import datos_simulados as ds
        cls.ds = ds
        cls.js = (RAIZ / 'tablero' / 'panel.js').read_text(encoding='utf-8')

    def generar(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            datos = self.ds.generar(d, **kw)
            with open(os.path.join(d, 'datos.json')) as f1, open(os.path.join(d, 'datos.js')) as f2:
                return datos, sorted(os.listdir(d)), json.load(f1), f2.read()

    def test_archivos_y_formato(self):
        datos, archivos, json_, js = self.generar()
        self.assertEqual(archivos, ['datos.js', 'datos.json', 'eventos.jsonl', 'pits.csv'])
        self.assertTrue(js.startswith('window.DATOS = {') and js.rstrip().endswith('};'))
        self.assertEqual(json.loads(js[len('window.DATOS = '):].rstrip().rstrip(';')), json_)
        self.assertEqual(json_['fuente'], 'simulado')

    def test_las_claves_que_usa_el_panel_existen(self):
        import re
        datos, *_ = self.generar(defectos_evidencia=['bag_vacio'])
        top = set(re.findall(r'\bd\.(\w+)', self.js)) - {'banderas_x'}
        self.assertLessEqual(top, set(datos) | {'DATOS'}, top - set(datos))
        m = datos['metricas']
        self.assertLessEqual(set(re.findall(r'\bm\.(\w+)(?!\w*\()', self.js)), set(m))
        for bloque in ('estado', 'mision', 'cronometraje', 'pits', 'escalas', 'rubrica_estimada'):
            usados = set(re.findall(r'\bm\.' + bloque + r'\.(\w+)', self.js))
            self.assertLessEqual(usados, set(m[bloque]), (bloque, usados - set(m[bloque])))
        for k in ('limite_s', 'reduccion', 'err_pos_pre_cm', 'err_pos_post_cm', 't_medio_s', 't_max_s', 'lentos', 'con_correccion', 'reintentos'):
            self.assertIn(k, m['pits'])
        for k in ('numero', 'duracion', 'sectores', 'valida'):
            self.assertIn(k, m['cronometraje']['vueltas'][0])
        for k in ('estacion', 't_pit_s', 'err_pos_pre_cm', 'err_pos_post_cm', 'valido'):
            self.assertIn(k, m['estaciones'][0])
        for k in ('v', 'w', 'bateria', 'latencia_ms', 'video'):
            self.assertIn(k, datos['telemetria'])
        for k in ('ok', 'fallas', 'avisos', 'hallazgos'):
            self.assertIn(k, datos['evidencia'])

    def test_escenarios(self):
        normal, *_ = self.generar()
        self.assertEqual((normal['metricas']['estado']['estado'], normal['metricas']['mision']['vueltas_validas']), ('FIN', 4))
        falla, *_ = self.generar(escenario='falla')
        self.assertEqual((falla['metricas']['estado']['estado'], falla['metricas']['estado']['motivo']), ('FALLA', 'RESULTADO_NO_OK'))
        curso, *_ = self.generar(hasta_s=200.0)
        self.assertNotIn(curso['metricas']['estado']['estado'], ('FIN', 'FALLA', 'SIN_DATOS'))
        self.assertFalse(curso['metricas']['mision']['terminada'])
        apr, *_ = self.generar(escenario='aprendiendo')
        self.assertEqual(apr['metricas']['estado']['estado'], 'FIN')
        with self.assertRaises(ValueError):
            self.ds.crear_mundo('inventado', 0)

    def test_todo_lo_que_no_se_simula_es_none(self):
        datos, *_ = self.generar()
        self.assertTrue(all(datos['telemetria'][k] is None for k in ('bateria', 'latencia_ms', 'video')))
        self.assertIsNone(datos['evidencia'])
        self.assertEqual(datos['intervenciones'], {'contador': 0, 'bitacora': []})

    def test_evidencia_simulada_con_defectos(self):
        sin, *_ = self.generar(defectos_evidencia=[])
        con, *_ = self.generar(defectos_evidencia=['bag_vacio'])
        self.assertTrue(sin['evidencia']['ok'])
        self.assertFalse(con['evidencia']['ok'])

    def test_modo_vivo_reescribe_los_datos_hasta_terminar(self):
        with tempfile.TemporaryDirectory() as d, mock.patch('time.sleep') as dormir:
            self.ds.vivo(d, 'normal', velocidad=100.0, semilla=0, cada=0.5)
            self.assertGreater(dormir.call_count, 5)                                    # varias actualizaciones, no una sola
            with open(os.path.join(d, 'datos.json')) as f:
                self.assertEqual(json.load(f)['metricas']['estado']['estado'], 'FIN')
            self.assertFalse([f for f in os.listdir(d) if f.endswith('.tmp')])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with redirect_stdout(out):
                rc = self.ds.main(['--salida', d, '--hasta-s', '100'])
            self.assertEqual(rc, 0)
            self.assertIn('estado', out.getvalue())
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.ds.main(['--salida', d, '--hasta-s', '-1'])


if __name__ == '__main__':
    unittest.main()
