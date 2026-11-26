import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from carrito.granprix_carrito import planificador as pl
from carrito.granprix_carrito.calibracion import EstimadorEscalas
from carrito.granprix_carrito.configuracion import DIRECTORIO_DEFECTO, cargar_carrito, cargar_movimiento
from carrito.granprix_carrito.ejecutor import Config, Estado, EjecutorMovimiento
from comun.yaml_estricto import ErrorYaml
from geometria_dock.transformaciones import Pose2D
from test_ejecutor import Planta, Reloj

MOV = RAIZ / 'carrito' / 'config' / 'movimiento.yaml'
CAL = RAIZ / 'carrito' / 'config' / 'calibracion.yaml'


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def con_cambio(self, archivo, viejo, nuevo, nombre):
        """Copia los YAML del repo a una carpeta temporal cambiando UNA cosa en `archivo`."""
        for f in ('movimiento.yaml', 'calibracion.yaml'):
            texto = (RAIZ / 'carrito' / 'config' / f).read_text(encoding='utf-8')
            if f == archivo:
                self.assertIn(viejo, texto, nombre)
                texto = texto.replace(viejo, nuevo, 1)
            with open(os.path.join(self.dir.name, f), 'w', encoding='utf-8') as fh:
                fh.write(texto)
        return self.dir.name


class TestArchivosDelRepo(unittest.TestCase):
    def test_movimiento_coincide_con_los_valores_del_codigo(self):
        """Si alguien cambia un valor por defecto del código o del YAML sin el otro, esto lo avisa."""
        m = cargar_movimiento(str(MOV))
        self.assertEqual((m.v_ref, m.w_ref, m.v_max, m.w_max), (pl.V_REF, pl.W_REF, pl.V_MAX, pl.W_MAX))
        self.assertEqual(m.ejecutor, Config())

    def test_calibracion_semilla(self):
        e = EstimadorEscalas.cargar(str(CAL), robot_esperado='eq08-roscar')
        self.assertEqual(e.escalas, pl.Escalas(1.0, 1.0))      # sin caracterizar: no hay escalas inventadas
        self.assertEqual((e.alpha, e.perfil), (0.35, (pl.V_REF, pl.W_REF)))

    def test_carrito_completo_y_coherente(self):
        mov, est = cargar_carrito(DIRECTORIO_DEFECTO, 'eq08-roscar')
        self.assertEqual(est.perfil, (mov.v_ref, mov.w_ref))

    def test_la_config_cargada_sirve_para_ejecutar_un_tramo(self):
        mov, est = cargar_carrito(robot_esperado='eq08-roscar')
        reloj = Reloj()
        planta = Planta(reloj, Pose2D(0, 0, 0))
        cmd = pl.comandar(pl.Tramo(1.0, 0.5), est.escalas, mov.v_ref, mov.w_ref, mov.v_max, mov.w_max)
        ej = EjecutorMovimiento(planta, reloj, mov.ejecutor)
        ej.iniciar(cmd)
        while ej.paso() not in (Estado.COMPLETO, Estado.ABORTADO):
            reloj.dormir(mov.ejecutor.periodo_s)
        self.assertEqual(ej.estado, Estado.COMPLETO)

    def test_el_robot_esperado_debe_coincidir(self):
        with self.assertRaises(ValueError):
            cargar_carrito(DIRECTORIO_DEFECTO, 'otro-robot')


class TestMovimientoNoAflojaElReto(Base):
    def rechaza(self, viejo, nuevo, nombre, fragmento=None):
        d = self.con_cambio('movimiento.yaml', viejo, nuevo, nombre)
        with self.assertRaises(ErrorYaml, msg=nombre) as cm:
            cargar_movimiento(os.path.join(d, 'movimiento.yaml'))
        if fragmento:
            self.assertIn(fragmento, str(cm.exception))

    def test_limites_del_reto(self):
        self.rechaza('v_max: 0.20', 'v_max: 0.25', 'v_max sobre el límite', 'v_max')
        self.rechaza('w_max: 0.80', 'w_max: 0.90', 'w_max sobre el límite', 'w_max')

    def test_referencias_coherentes(self):
        self.rechaza('v_ref: 0.10', 'v_ref: 0.30', 'v_ref > v_max')
        self.rechaza('w_ref: 0.50', 'w_ref: 0.0', 'w_ref cero')
        self.rechaza('v_ref: 0.10', 'v_ref: -0.1', 'v_ref negativa')

    def test_ejecutor(self):
        self.rechaza('periodo_s: 0.05 ', 'periodo_s: 0.5 ', 'periodo demasiado largo')
        self.rechaza('max_hueco_s: 0.25', 'max_hueco_s: 0.06', 'hueco menor que 2 periodos', 'doble')
        self.rechaza('pausa_s: 0.30 ', 'pausa_s: -1.0 ', 'pausa negativa')
        self.rechaza('t_max_tramo_s: 60.0', 't_max_tramo_s: 500.0', 'tramo larguísimo')
        self.rechaza('a_lin_max: null', 'a_lin_max: -0.2', 'rampa negativa')
        self.rechaza('a_ang_max: null', 'a_ang_max: 0', 'rampa cero')
        self.rechaza('ajustar_ultimo_paso: true', 'ajustar_ultimo_paso: "si"', 'booleano como texto')
        self.rechaza('ceros_al_abortar: 5', 'ceros_al_abortar: 0', 'sin ceros al abortar')
        self.rechaza('pausa_s: 0.30 ', 'pausa_s: 1e-1 ', 'notacion 1e-1 que YAML lee como texto', '1.0e')

    def test_claves_desconocidas_y_duplicadas(self):
        self.rechaza('pausa_s: 0.30', 'pausa_ss: 0.30', 'error de dedo en el nombre', 'pausa_s')
        self.rechaza('version: 1', 'version: 1\nvelocidades: {}', 'bloque duplicado', 'duplicada')
        self.rechaza('version: 1', 'version: 3', 'versión desconocida')

    def test_acepta_rampa_valida(self):
        d = self.con_cambio('movimiento.yaml', 'a_lin_max: null', 'a_lin_max: 0.4', 'rampa')
        m = cargar_movimiento(os.path.join(d, 'movimiento.yaml'))
        self.assertEqual(m.ejecutor.a_lin_max, 0.4)
        self.assertIsNone(m.ejecutor.a_ang_max)


class TestCoherenciaMovimientoCalibracion(Base):
    def test_perfil_distinto_de_las_velocidades_falla(self):
        d = self.con_cambio('calibracion.yaml', 'w_ref: 0.50', 'w_ref: 0.40', 'perfil')
        with self.assertRaisesRegex(ErrorYaml, 'w_ref'):
            cargar_carrito(d, 'eq08-roscar')
        d = self.con_cambio('calibracion.yaml', 'v_ref: 0.10', 'v_ref: 0.15', 'perfil v')
        with self.assertRaisesRegex(ErrorYaml, 'v_ref'):
            cargar_carrito(d, 'eq08-roscar')

    def test_perfil_nulo_se_acepta(self):
        d = self.con_cambio('calibracion.yaml', 'w_ref: 0.50', 'w_ref: null', 'perfil nulo')
        _, est = cargar_carrito(d, 'eq08-roscar')
        self.assertEqual(est.perfil, (0.10, None))


if __name__ == '__main__':
    unittest.main()
