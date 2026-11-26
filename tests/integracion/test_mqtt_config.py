"""mqtt.yaml frente al contrato del docente (vendor/granprix): tópicos, QoS, retenidos y quién publica."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'scripts' / 'roscar_v01'))
sys.path.insert(0, str(RAIZ / 'vendor' / 'granprix' / 'pc-race'))
import mensajes_contrato as mc
from comun.yaml_estricto import ErrorYaml
from integracion.mqtt_config import cargar_mqtt

try:
    from contrato import topicos
    HAY_TOPICOS = True
except ImportError:
    HAY_TOPICOS = False

YAML = RAIZ / 'integracion' / 'configuracion' / 'mqtt.yaml'
DOC = RAIZ / 'vendor' / 'granprix' / 'docs' / 'arquitectura' / '00-contrato-mqtt.md'
QUIEN = {'Race Control': 'race_control', 'estación': 'estacion', 'carrito': 'carrito'}


def tabla_del_docente():
    """{plantilla normalizada: (publica, qos, retenido)} leída de la tabla Markdown del contrato."""
    filas = {}
    for linea in DOC.read_text(encoding='utf-8').splitlines():
        m = re.match(r'\|\s*`(granprix/[^`]+)`\s*\|\s*([^|]+?)\s*\|\s*[^|]+\|\s*(\d)\s*\|\s*(sí|no)\s*\|', linea)
        if m:
            plantilla = m.group(1).replace('<n>', '{n}').replace('NN', '{eq}')
            filas[plantilla] = (QUIEN[m.group(2)], int(m.group(3)), m.group(4) == 'sí')
    return filas


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def variante(self, viejo, nuevo):
        texto = YAML.read_text(encoding='utf-8')
        self.assertIn(viejo, texto)
        ruta = os.path.join(self.dir.name, 'mqtt.yaml')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto.replace(viejo, nuevo, 1))
        return ruta


class TestContratoDelDocente(unittest.TestCase):
    def test_la_tabla_del_docente_se_leyo(self):
        self.assertEqual(len(tabla_del_docente()), 10)

    def test_publica_qos_y_retenido_coinciden_con_la_tabla_del_docente(self):
        c = cargar_mqtt(str(YAML))
        propios = {t.plantilla: (t.publica, t.qos, t.retenido) for t in c.topicos.values()}
        self.assertEqual(propios, tabla_del_docente())

    @unittest.skipUnless(HAY_TOPICOS, 'módulo contrato del docente no importable')
    def test_los_topicos_coinciden_con_el_modulo_del_docente(self):
        c = cargar_mqtt(str(YAML))
        self.assertEqual(c.topico('estado_carrera'), topicos.topico_estado_carrera())
        self.assertEqual(c.topico('bandera'), topicos.topico_bandera())
        self.assertEqual(c.topico('turno_carrito'), topicos.topico_turno_carrito(8))
        for n in (1, 2, 3, 4):
            self.assertEqual(c.topico('turno_estacion', n), topicos.topico_turno_estacion(n))

    @unittest.skipUnless(HAY_TOPICOS, 'módulo contrato del docente no importable')
    def test_los_del_carrito_son_reconocidos_por_race_control(self):
        c = cargar_mqtt(str(YAML))
        for canal in ('telemetria', 'evento', 'vuelta'):
            r = topicos.interpretar(c.topico(canal))
            self.assertEqual((r.origen, r.numero, r.canal), ('carrito', 8, canal))
        r = topicos.interpretar(c.topico('solicitud', 3))
        self.assertEqual((r.origen, r.numero, r.canal), ('estacion', 3, 'solicitud'))

    def test_coincide_con_los_constructores_de_scripts_roscar(self):
        c = cargar_mqtt(str(YAML))
        for canal in ('telemetria', 'evento', 'vuelta'):
            self.assertEqual(c.topico(canal), mc.topico_equipo(8, canal))
        for n in (1, 2, 3, 4):
            self.assertEqual(c.topico('solicitud', n), mc.topico_solicitud(n))

    def test_valores_del_contrato(self):
        c = cargar_mqtt(str(YAML))
        self.assertEqual((c.equipo, c.host, c.puerto), (8, '192.168.50.10', 1883))
        self.assertEqual((c.telemetria_max_hz, c.offline_tras_s), (5.0, 3.0))
        self.assertEqual(c.clave_env, 'GRANPRIX_MQTT_CLAVE')

    def test_solo_el_carrito_publica_en_sus_canales(self):
        c = cargar_mqtt(str(YAML))
        propios = {n for n, t in c.topicos.items() if t.publica == 'carrito'}
        self.assertEqual(propios, {'solicitud', 'telemetria', 'evento', 'vuelta'})   # los que su usuario puede escribir


class TestUso(unittest.TestCase):
    def test_topico_con_estacion(self):
        c = cargar_mqtt(str(YAML))
        self.assertEqual(c.topico('telemetria'), 'granprix/eq08/telemetria')
        self.assertEqual(c.topico('resultado', 2), 'granprix/estacion/2/resultado')
        for nombre, est in (('solicitud', None), ('solicitud', 5), ('solicitud', 0), ('telemetria', 2)):
            with self.assertRaises(ValueError, msg=f'{nombre} {est}'):
                c.topico(nombre, est)
        with self.assertRaises(KeyError):
            c.topico('inventado')

    def test_la_clave_sale_del_entorno_y_nunca_del_archivo(self):
        c = cargar_mqtt(str(YAML))
        self.assertIsNone(c.clave({}))
        self.assertEqual(c.clave({'GRANPRIX_MQTT_CLAVE': 'x'}), 'x')


class TestRechazos(Base):
    def rechaza(self, viejo, nuevo, nombre=''):
        with self.assertRaises(ErrorYaml, msg=nombre or nuevo):
            cargar_mqtt(self.variante(viejo, nuevo))

    def test_secretos(self):
        self.rechaza('clave_env: GRANPRIX_MQTT_CLAVE', 'clave: hunter2', 'contraseña en claro')
        self.rechaza('clave_env: GRANPRIX_MQTT_CLAVE', 'clave_env: hunter2', 'una contraseña disfrazada de nombre de variable')
        self.rechaza('clave_env: GRANPRIX_MQTT_CLAVE', 'clave_env: mi clave', 'con espacio')
        self.rechaza('clave_env: GRANPRIX_MQTT_CLAVE', 'password: hunter2')
        self.rechaza('clave_env: GRANPRIX_MQTT_CLAVE', 'clave_env: GRANPRIX_MQTT_CLAVE\n  token: abc')

    def test_conexion(self):
        self.rechaza('host: 192.168.50.10', 'host: mqtt://192.168.50.10')
        self.rechaza('host: 192.168.50.10', 'host: ""')
        self.rechaza('puerto: 1883', 'puerto: 0')
        self.rechaza('puerto: 1883', 'puerto: 70000')
        self.rechaza('puerto: 1883', 'puerto: "1883"')
        self.rechaza('equipo: 8 ', 'equipo: 0 ')
        self.rechaza('equipo: 8 ', 'equipo: 100 ')

    def test_tiempos_no_pasan_del_contrato(self):
        self.rechaza('telemetria_max_hz: 5 ', 'telemetria_max_hz: 10 ')
        self.rechaza('telemetria_max_hz: 5 ', 'telemetria_max_hz: 0 ')
        self.rechaza('offline_tras_s: 3.0', 'offline_tras_s: -1')

    def test_topicos(self):
        self.rechaza('granprix/eq{eq}/evento', 'granprix/eq{equipo}/evento', 'marca desconocida')
        self.rechaza('granprix/eq{eq}/evento', 'granprix/eq+/evento', 'comodín')
        self.rechaza('granprix/eq{eq}/evento', 'otraraiz/eq{eq}/evento', 'raíz distinta')
        self.rechaza('publica: carrito,      qos: 1, retenido: false}\n  resultado',
                     'publica: carrito,      qos: 3, retenido: false}\n  resultado', 'qos 3')
        self.rechaza('publica: race_control, qos: 1, retenido: false}', 'publica: juez, qos: 1, retenido: false}')
        self.rechaza('retenido: true}', 'retenido: sí}', 'booleano como texto')
        self.rechaza('{plantilla: "granprix/carrera/bandera",          publica', '{plantilla: "granprix/carrera/bandera", extra: 1, publica',
                     'clave desconocida en un tópico')

    def test_estructura(self):
        self.rechaza('version: 1', 'version: 2')
        self.rechaza('version: 1', 'version: 1\nequipo: 9', 'equipo duplicado')
        self.rechaza('tiempos:', 'tiemps:', 'sección mal escrita')


if __name__ == '__main__':
    unittest.main()
