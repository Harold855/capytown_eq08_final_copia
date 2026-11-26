import csv
import io
import json
import math
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from evidencia import registro_experimental as re_
from evidencia.registro_experimental import ErrorRegistro, RegistroExperimental, verificar_ruta


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.t = [1700000000.0]
        self.reg = RegistroExperimental(os.path.join(self.dir, 'r', 'registro.jsonl'), lambda: self.t[0])

    def agregar(self, **kw):
        base = dict(tipo='recta', robot='eq08-roscar', operador='ana', estado='ok', parametros={'distancia_m': 0.5},
                    resultados={'distancia_fisica_m': 0.49})
        base.update(kw)
        return self.reg.agregar(**base)

    def archivo(self, nombre='datos.csv', texto='a,b\n1,2\n'):
        ruta = os.path.join(self.dir, nombre)
        Path(ruta).write_text(texto)
        return ruta

    def editar(self, fn):
        lineas = Path(self.reg.ruta).read_text().split('\n')[:-1]
        nuevas = fn(lineas)
        Path(self.reg.ruta).write_text('\n'.join(nuevas) + ('\n' if nuevas else ''))


class TestAgregar(Base):
    def test_ids_secuenciales_y_cadena_de_hashes(self):
        a, b, c = self.agregar(), self.agregar(tipo='giro'), self.agregar(estado='fallo', notas='se atoró')
        self.assertEqual([a['id'], b['id'], c['id']], ['E0001', 'E0002', 'E0003'])
        self.assertEqual((a['prev'], b['prev'], c['prev']), (re_.CERO, a['sha'], b['sha']))
        self.assertEqual(len(self.reg.leer()), 3)
        self.assertEqual(self.reg.verificar(), [])

    def test_la_fecha_es_utc_iso(self):
        self.assertEqual(self.agregar()['fecha'], '2023-11-14T22:13:20+00:00')

    def test_las_pruebas_fallidas_se_guardan(self):
        r = self.agregar(estado='abortado', notas='bateria baja')
        self.assertEqual(self.reg.leer()[0]['estado'], 'abortado')
        self.assertEqual(r['notas'], 'bateria baja')

    def test_validaciones(self):
        for kw in (dict(tipo='otra'), dict(estado='bien'), dict(robot=' '), dict(operador=''), dict(parametros={'x': float('nan')}),
                   dict(resultados={'x': float('inf')}), dict(parametros={'x': object()}), dict(archivos=['/no/existe.csv']),
                   dict(corrige='E0099')):
            with self.assertRaises(ErrorRegistro, msg=kw):
                self.agregar(**kw)
        self.assertEqual(self.reg.leer(), [])                          # una prueba rechazada no deja nada escrito

    def test_corrige_apunta_a_un_registro_existente(self):
        a = self.agregar()
        b = self.agregar(corrige=a['id'], notas='la cinta estaba mal leída')
        self.assertEqual(b['corrige'], 'E0001')
        self.assertEqual(self.reg.verificar(), [])

    def test_valores_anidados_y_listas(self):
        r = self.agregar(parametros={'ruta': [1, 2.5, 'a'], 'cfg': {'v': 0.1, 'ok': True, 'x': None}})
        self.assertEqual(r['parametros']['cfg']['v'], 0.1)

    def test_el_archivo_nunca_tiene_nan(self):
        self.agregar()
        self.assertNotIn('NaN', Path(self.reg.ruta).read_text())


class TestIntegridad(Base):
    def llenar(self, n=4):
        for i in range(n):
            self.agregar(parametros={'i': i})

    def test_editar_un_valor_se_detecta(self):
        self.llenar()
        self.editar(lambda l: [x.replace('"distancia_fisica_m":0.49', '"distancia_fisica_m":0.50') for x in l])
        (p,) = self.reg.verificar()
        self.assertIn('línea 1', p)
        self.assertIn('editada', p)

    def test_borrar_una_linea_se_detecta(self):
        self.llenar()
        self.editar(lambda l: l[:1] + l[2:])
        (p,) = self.reg.verificar()
        self.assertIn('línea 2', p)
        self.assertIn('numeración', p)

    def test_reordenar_se_detecta(self):
        self.llenar()
        self.editar(lambda l: [l[1], l[0], l[2], l[3]])
        self.assertIn('línea 1', self.reg.verificar()[0])

    def test_borrar_la_ultima_no_se_puede_detectar_sin_copia_externa(self):
        """Límite conocido: la cadena protege el pasado, no el final. Por eso `exportar` y subir el CSV al repositorio."""
        self.llenar()
        self.editar(lambda l: l[:-1])
        self.assertEqual(self.reg.verificar(), [])
        self.assertEqual(len(self.reg.leer()), 3)

    def test_recalcular_un_hash_a_mano_rompe_la_siguiente(self):
        self.llenar()
        regs = self.reg.leer()
        regs[0]['notas'] = 'cambiada'
        regs[0]['sha'] = re_._sha(re_._canon({k: v for k, v in regs[0].items() if k != 'sha'}))
        self.editar(lambda l: [re_._canon(regs[0])] + l[1:])
        self.assertIn('línea 2', self.reg.verificar()[0])

    def test_json_invalido_y_claves_de_mas(self):
        self.llenar(2)
        self.editar(lambda l: l + ['{no es json'])
        self.assertIn('línea 3', self.reg.verificar()[0])
        self.editar(lambda l: l[:2] + [json.dumps({'x': 1})])
        self.assertIn('claves', self.reg.verificar()[0])

    def test_un_corte_a_mitad_de_linea_se_avisa_y_no_deja_seguir(self):
        self.llenar(2)
        with open(self.reg.ruta, 'a') as f:
            f.write('{"n":3,"id":"E00')
        self.assertIn('incompleta', self.reg.verificar()[0])
        with self.assertRaises(ErrorRegistro):
            self.agregar()

    def test_no_se_puede_seguir_sobre_un_registro_roto(self):
        self.llenar()
        self.editar(lambda l: [x.replace('ana', 'eva') for x in l])
        with self.assertRaises(ErrorRegistro):
            self.agregar()

    def test_archivos_adjuntos(self):
        ruta = self.archivo()
        self.agregar(archivos=['datos.csv'], base=self.dir)
        self.assertEqual(self.reg.verificar(self.dir), [])
        Path(ruta).write_text('a,b\n1,3\n')
        (p,) = self.reg.verificar(self.dir)
        self.assertIn('cambió después de registrarse', p)
        os.remove(ruta)
        self.assertIn('falta el archivo', self.reg.verificar(self.dir)[0])

    def test_el_hash_del_adjunto_es_sha256(self):
        import hashlib
        ruta = self.archivo(texto='hola')
        r = self.agregar(archivos=[ruta])
        self.assertEqual(r['archivos'][0]['sha256'], hashlib.sha256(b'hola').hexdigest())
        self.assertEqual(r['archivos'][0]['bytes'], 4)

    def test_corrige_un_registro_posterior_se_detecta(self):
        self.llenar(2)
        regs = self.reg.leer()
        regs[0]['corrige'] = 'E0002'
        # reconstruir una cadena válida con una referencia hacia adelante
        prev, lineas = re_.CERO, []
        for r in regs:
            r = dict(r, prev=prev)
            r['sha'] = re_._sha(re_._canon({k: v for k, v in r.items() if k != 'sha'}))
            prev = r['sha']
            lineas.append(re_._canon(r))
        self.editar(lambda l: lineas)
        self.assertIn('no es anterior', self.reg.verificar()[0])

    def test_registro_inexistente_esta_vacio_y_es_integro(self):
        self.assertEqual((self.reg.leer(), self.reg.verificar()), ([], []))
        self.assertEqual(verificar_ruta(os.path.join(self.dir, 'nada.jsonl')), [])


class TestExportarYCli(Base):
    def test_exportar_csv(self):
        self.agregar(parametros={'v': 0.1}, notas='con, coma')
        self.agregar(tipo='acople', archivos=[self.archivo()])
        salida = os.path.join(self.dir, 'r.csv')
        self.assertEqual(self.reg.exportar_csv(salida), 2)
        with open(salida, newline='') as f:
            filas = list(csv.DictReader(f))
        self.assertEqual((filas[0]['id'], filas[0]['notas'], json.loads(filas[0]['parametros'])), ('E0001', 'con, coma', {'v': 0.1}))
        self.assertTrue(filas[1]['archivos'].endswith('datos.csv'))

    def correr(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = re_.main(['--ruta', self.reg.ruta, *args])
            except SystemExit as e:
                rc = e.code
        return rc, out.getvalue(), err.getvalue()

    def test_flujo_completo_por_linea_de_comandos(self):
        ruta = self.archivo()
        rc, out, _ = self.correr('agregar', '--tipo', 'recta', '--robot', 'eq08-roscar', '--operador', 'ana', '--estado', 'ok',
                                 '--parametro', 'distancia_m=0.5', '--parametro', 'superficie=carton', '--parametro', 'seca=true',
                                 '--resultado', 'dist_fisica_m=0.49', '--archivo', ruta, '--notas', 'primera')
        self.assertEqual((rc, out.strip()), (0, 'E0001 registrado (recta, ok)'))
        r = self.reg.leer()[0]
        self.assertEqual(r['parametros'], {'distancia_m': 0.5, 'superficie': 'carton', 'seca': True})
        rc, out, _ = self.correr('verificar')
        self.assertEqual((rc, 'íntegro' in out), (0, True))
        self.assertIn('E0001', self.correr('listar')[1])
        salida = os.path.join(self.dir, 'x.csv')
        self.assertEqual(self.correr('exportar', '--salida', salida)[0], 0)
        Path(ruta).write_text('cambiado')
        rc, out, _ = self.correr('verificar')
        self.assertEqual(rc, 1)
        self.assertIn('cambió después de registrarse', out)

    def test_errores_de_la_linea_de_comandos(self):
        rc, _, err = self.correr('agregar', '--tipo', 'recta', '--robot', 'r', '--operador', 'o', '--estado', 'ok', '--archivo', '/no/existe')
        self.assertEqual(rc, 1)
        self.assertIn('inexistente', err)
        self.assertEqual(self.correr('agregar', '--tipo', 'zzz', '--robot', 'r', '--operador', 'o', '--estado', 'ok')[0], 2)
        self.assertEqual(self.correr('agregar', '--tipo', 'recta', '--robot', 'r', '--operador', 'o', '--estado', 'ok', '--parametro', 'sinigual')[0], 2)

    def test_verificar_por_linea_de_comandos_detecta_la_edicion(self):
        self.agregar()
        self.editar(lambda l: [x.replace('ana', 'eva') for x in l])
        rc, out, _ = self.correr('verificar')
        self.assertEqual(rc, 1)
        self.assertIn('editada', out)

    def test_parseo_de_valores(self):
        self.assertEqual(re_._par('a=1.5'), ('a', 1.5))
        self.assertEqual(re_._par('a=true'), ('a', True))
        self.assertEqual(re_._par('a=nan'), ('a', 'nan'))                    # nunca un NaN numérico
        self.assertEqual(re_._par('a=x=y'), ('a', 'x=y'))


if __name__ == '__main__':
    unittest.main()
