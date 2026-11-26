import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'estacion' / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_equipo.brazo_simulado import BrazoSimulado
from app_equipo.compensacion_pose import GeometriaEstacion
from app_equipo.configuracion import cargar_estacion
from app_equipo.estrategia import EstrategiaCambio
from app_equipo.posiciones import ErrorConfiguracion, cargar
from app_equipo.puerto import PoseDock
from test_estacion import poses_ejemplo

CONFIG = RAIZ / 'estacion' / 'config' / 'estacion.yaml'
PLANTILLA = RAIZ / 'estacion' / 'config' / 'poses.plantilla.yaml'


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def escribir(self, nombre, texto):
        ruta = os.path.join(self.dir.name, nombre)
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        return ruta

    def variante(self, viejo, nuevo):
        texto = CONFIG.read_text(encoding='utf-8')
        self.assertIn(viejo, texto)
        return self.escribir('estacion.yaml', texto.replace(viejo, nuevo, 1))


class TestEstacionYaml(Base):
    def test_coincide_con_los_valores_del_codigo(self):
        c = cargar_estacion(str(CONFIG))
        self.assertEqual(c.geometria, GeometriaEstacion())
        self.assertEqual((c.tol_pos_m, c.tol_ang_deg, c.tiempo_max_s), (0.04, 6.0, 8.0))

    def test_construye_una_estrategia_que_funciona(self):
        c = cargar_estacion(str(CONFIG))
        args = c.argumentos_estrategia()
        args['tiempo_max_s'] = 60.0   # las duraciones del brazo simulado son placeholders (E2 tarda 15.4 s)
        brazo = BrazoSimulado()
        e = EstrategiaCambio(2, brazo, poses_ejemplo(2), reloj=brazo.reloj, **args)
        r = e.cambiar(PoseDock(0.0, 0.0, 0.0), 'A')
        self.assertTrue(r.ok, r)

    def test_con_el_tope_del_yaml_el_brazo_simulado_tarda_de_mas(self):
        """Documenta el hallazgo: con tiempos placeholder y 8 s de tope, E2 no cabe. Hay que medir el brazo real."""
        args = cargar_estacion(str(CONFIG)).argumentos_estrategia()
        brazo = BrazoSimulado()
        r = EstrategiaCambio(2, brazo, poses_ejemplo(2), reloj=brazo.reloj, **args).cambiar(PoseDock(0, 0, 0), 'A')
        self.assertFalse(r.ok)

    def test_no_se_puede_ser_mas_laxo_que_el_reto(self):
        casos = {'tol_pos_m: 0.04': 'tol_pos_m: 0.05', 'tol_ang_deg: 6.0': 'tol_ang_deg: 7.0',
                 'tiempo_max_s: 8.0': 'tiempo_max_s: 12.0'}
        for viejo, nuevo in casos.items():
            with self.assertRaises(ErrorConfiguracion, msg=nuevo):
                cargar_estacion(self.variante(viejo, nuevo))

    def test_si_puede_ser_mas_estricto(self):
        c = cargar_estacion(self.variante('tol_pos_m: 0.04', 'tol_pos_m: 0.03'))
        self.assertEqual(c.tol_pos_m, 0.03)

    def test_valores_absurdos(self):
        casos = [('tol_pos_m: 0.04', 'tol_pos_m: 0'), ('tiempo_max_s: 8.0', 'tiempo_max_s: -1'),
                 ('y_m: -0.11', 'y_m: -11'),                       # metros escritos como centímetros
                 ('alcance_max_m: 0.22', 'alcance_max_m: 0.10'),    # máximo menor que el mínimo
                 ('alcance_min_m: 0.14', 'alcance_min_m: 0'),
                 ('th_deg: 0.0', 'th_deg: 720'),
                 ('x_m: 0.0', 'x_m: "0.0"')]
        for viejo, nuevo in casos:
            with self.assertRaises(ErrorConfiguracion, msg=nuevo):
                cargar_estacion(self.variante(viejo, nuevo))

    def test_claves_desconocidas_duplicadas_y_versiones(self):
        for viejo, nuevo in (('tol_pos_m:', 'tol_pos:'), ('version: 1', 'version: 1\nversion: 1'),
                             ('version: 1', 'version: 2'), ('alcance_min_m: 0.14', '')):
            with self.assertRaises(ErrorConfiguracion, msg=nuevo):
                cargar_estacion(self.variante(viejo, nuevo))

    def test_archivo_ausente(self):
        with self.assertRaises(ErrorConfiguracion):
            cargar_estacion(os.path.join(self.dir.name, 'no_existe.yaml'))


class TestPosesYaml(Base):
    def test_la_plantilla_falla_cerrada_y_dice_que_falta(self):
        with self.assertRaisesRegex(ErrorConfiguracion, 'faltan poses por enseñar'):
            cargar(str(PLANTILLA))

    def test_poses_en_yaml_y_en_json_dan_lo_mismo(self):
        import dataclasses
        import json
        crudo = dataclasses.asdict(poses_ejemplo(2))
        datos = {'rol': 2, 'poses': {k: v for k, v in crudo.items() if k != 'rol' and v is not None}}
        como_json = self.escribir('p.json', json.dumps(datos))
        como_yaml = self.escribir('p.yaml', json.dumps(datos))   # JSON es YAML válido
        otro = self.escribir('p2.yml', 'rol: 2\nposes:\n' + ''.join(
            f'  {k}: {json.dumps(v)}\n' for k, v in datos['poses'].items()))
        self.assertEqual(cargar(como_json), cargar(como_yaml))
        self.assertEqual(cargar(como_json), cargar(otro))

    def test_clave_duplicada_en_poses_falla(self):
        with self.assertRaisesRegex(ErrorConfiguracion, 'duplicada'):
            cargar(self.escribir('d.yaml', 'rol: 2\nrol: 3\nposes: {}\n'))

    def test_metros_en_vez_de_milimetros_sigue_rechazado(self):
        import json
        import dataclasses
        crudo = dataclasses.asdict(poses_ejemplo(1))
        poses = {k: v for k, v in crudo.items() if k != 'rol' and v is not None}
        poses['cuna_aprox'] = [0.2, 0.0, 0.15, -180.0, 0.0, 0.0]
        with self.assertRaises(ErrorConfiguracion):
            cargar(self.escribir('m.yaml', json.dumps({'rol': 1, 'poses': poses})))

    def test_json_roto_o_ausente_es_error_de_configuracion(self):
        with self.assertRaises(ErrorConfiguracion):
            cargar(self.escribir('roto.json', '{no es json'))
        with self.assertRaises(ErrorConfiguracion):
            cargar(os.path.join(self.dir.name, 'no_existe.json'))


if __name__ == '__main__':
    unittest.main()
