import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from comun import yaml_estricto as ye


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def cargar(self, texto):
        ruta = os.path.join(self.dir.name, 'x.yaml')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        return ye.cargar_mapeo(ruta)


class TestCarga(Base):
    def test_lee_un_mapa_valido(self):
        d = self.cargar('a: 1\nb: {c: 2.5}\nlista: [1, 2]\n')
        self.assertEqual(d, {'a': 1, 'b': {'c': 2.5}, 'lista': [1, 2]})

    def test_rechaza_claves_duplicadas(self):
        with self.assertRaisesRegex(ye.ErrorYaml, 'duplicada'):
            self.cargar('v_max: 0.2\nv_max: 5.0\n')
        with self.assertRaisesRegex(ye.ErrorYaml, 'duplicada'):
            self.cargar('seccion:\n  a: 1\n  a: 2\n')

    def test_rechaza_claves_que_no_son_texto(self):
        for texto in ('yes: 1\n', 'no: 1\n', 'on: 1\n', '1: a\n'):
            with self.assertRaisesRegex(ye.ErrorYaml, 'no es texto', msg=texto):
                self.cargar(texto)

    def test_rechaza_lo_que_no_es_un_mapa(self):
        for texto in ('- 1\n- 2\n', 'texto suelto\n', '', '42\n'):
            with self.assertRaises(ye.ErrorYaml, msg=repr(texto)):
                self.cargar(texto)

    def test_rechaza_yaml_invalido_y_archivo_ausente(self):
        with self.assertRaises(ye.ErrorYaml):
            self.cargar('a: [1, 2\n')
        with self.assertRaises(ye.ErrorYaml):
            self.cargar('a:\n\t- 1\n')   # tabulador
        with self.assertRaises(ye.ErrorYaml):
            ye.cargar_mapeo(os.path.join(self.dir.name, 'no_existe.yaml'))

    def test_no_ejecuta_etiquetas_de_python(self):
        with self.assertRaises(ye.ErrorYaml):
            self.cargar('a: !!python/object/apply:os.system ["echo hola"]\n')

    def test_json_tambien_es_valido(self):
        self.assertEqual(self.cargar('{"a": 1, "b": [1, 2]}'), {'a': 1, 'b': [1, 2]})


class TestSecretos(Base):
    def test_rechaza_claves_con_aspecto_de_secreto(self):
        for texto in ('clave: abc\n', 'broker:\n  password: x\n', 'api_token: t\n', 'mi_secret: z\n',
                      'contrasena: q\n', 'lista:\n  - {passwd: x}\n'):
            with self.assertRaisesRegex(ye.ErrorYaml, 'secreto', msg=texto):
                self.cargar(texto)

    def test_admite_el_nombre_de_la_variable_de_entorno(self):
        self.assertEqual(self.cargar('clave_env: GRANPRIX_MQTT_CLAVE\n')['clave_env'], 'GRANPRIX_MQTT_CLAVE')

    def test_un_secreto_vacio_no_es_un_secreto(self):
        self.assertIsNone(self.cargar('clave: null\n')['clave'])


class TestValidadores(unittest.TestCase):
    def test_exigir_claves(self):
        ye.exigir_claves({'a': 1}, 'x', ('a',), ('b',))
        with self.assertRaisesRegex(ye.ErrorYaml, 'faltan'):
            ye.exigir_claves({}, 'x', ('a',))
        with self.assertRaisesRegex(ye.ErrorYaml, 'desconocidas'):
            ye.exigir_claves({'a': 1, 'v_maxx': 2}, 'x', ('a',))

    def test_numero(self):
        self.assertEqual(ye.numero({'a': 3}, 'a', 'x'), 3.0)
        self.assertIsInstance(ye.numero({'a': 3}, 'a', 'x'), float)
        malos = [{'a': True}, {'a': '1.0'}, {'a': float('nan')}, {'a': float('inf')}, {'a': None}, {}, {'a': [1]}]
        for d in malos:
            with self.assertRaises(ye.ErrorYaml, msg=str(d)):
                ye.numero(d, 'a', 'x')
        with self.assertRaises(ye.ErrorYaml):
            ye.numero({'a': 0.0}, 'a', 'x', 0, exclusivo_min=True)
        with self.assertRaises(ye.ErrorYaml):
            ye.numero({'a': 0.3}, 'a', 'x', maximo=0.2)
        self.assertIsNone(ye.numero({'a': None}, 'a', 'x', permitir_none=True))

    def test_numero_avisa_de_la_notacion_1e3(self):
        with self.assertRaisesRegex(ye.ErrorYaml, '1.0e\\+3'):
            ye.numero({'a': '1e3'}, 'a', 'x')

    def test_entero_booleano_texto(self):
        self.assertEqual(ye.entero({'a': 5}, 'a', 'x', 1, 10), 5)
        for d in ({'a': 5.0}, {'a': True}, {'a': '5'}, {'a': 11}):
            with self.assertRaises(ye.ErrorYaml, msg=str(d)):
                ye.entero(d, 'a', 'x', 1, 10)
        self.assertTrue(ye.booleano({'a': True}, 'a', 'x'))
        for d in ({'a': 1}, {'a': 'true'}, {}):
            with self.assertRaises(ye.ErrorYaml):
                ye.booleano(d, 'a', 'x')
        self.assertEqual(ye.texto({'a': 'hola'}, 'a', 'x'), 'hola')
        for d in ({'a': ''}, {'a': '  '}, {'a': 3}, {'a': None}):
            with self.assertRaises(ye.ErrorYaml):
                ye.texto(d, 'a', 'x')

    def test_volcar_y_releer(self):
        d = {'version': 1, 'a': {'b': 1.5, 'c': None, 'd': True}, 'lista': [1, 2]}
        texto = ye.volcar(d, 'línea uno\nlínea dos')
        self.assertTrue(texto.startswith('# línea uno\n# línea dos\n'))
        with tempfile.TemporaryDirectory() as dd:
            ruta = os.path.join(dd, 'x.yaml')
            with open(ruta, 'w', encoding='utf-8') as f:
                f.write(texto)
            self.assertEqual(ye.cargar_mapeo(ruta), d)


if __name__ == '__main__':
    unittest.main()
