import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'estacion' / 'src'))
from app_equipo.brazo_simulado import BrazoSimulado
from app_equipo.compensacion_pose import GeometriaEstacion, compensar
from app_equipo.estrategia import EstrategiaCambio
from app_equipo.posiciones import ErrorConfiguracion, desde_dict, requeridas
from app_equipo.puerto import PoseDock
from app_equipo.roles import ROLES

NOMINAL = PoseDock(0.0, 0.0, 0.0)


def poses_ejemplo(rol):
    """Poses de PRUEBA (no son coordenadas reales del laboratorio)."""
    def p(x, y, z): return [x, y, z, -180.0, 0.0, 0.0]
    todas = {
        'cuna_aprox': p(200, 0, 150), 'cuna_agarre': p(200, 0, 120), 'cuna_dejar': p(200, 0, 120),
        'pose_libre': p(100, 0, 250),
        'recepcion_aprox': [p(100, 150 + 10 * i, 150) for i in range(4)],
        'recepcion_dejar': [p(100, 150 + 10 * i, 125) for i in range(4)],
        'almacen_aprox': [p(150, -150 + 10 * i, 150) for i in range(4)],
        'almacen_agarre': [p(150, -150 + 10 * i, 125) for i in range(4)],
    }
    return desde_dict({'rol': rol, 'poses': {c: todas[c] for c in requeridas(rol)}})


def estrategia(rol, **kw):
    brazo = kw.pop('brazo', None) or BrazoSimulado()
    return EstrategiaCambio(rol, brazo, kw.pop('poses', poses_ejemplo(rol)), reloj=brazo.reloj, **kw), brazo


class TestCompensacion(unittest.TestCase):
    def test_nominal_a_18_cm_del_eje(self):
        c = compensar(NOMINAL)
        self.assertAlmostEqual(c.distancia_al_eje_m, 0.18)
        self.assertTrue(c.alcanzable)
        self.assertAlmostEqual(c.delta_en_brazo[0], 0); self.assertAlmostEqual(c.delta_en_brazo[1], 0)

    def test_extremos_de_4_cm_hacia_y_desde_el_brazo(self):
        self.assertAlmostEqual(compensar(PoseDock(0, -0.04, 0)).distancia_al_eje_m, 0.14)
        self.assertAlmostEqual(compensar(PoseDock(0, 0.04, 0)).distancia_al_eje_m, 0.22)
        self.assertTrue(compensar(PoseDock(0, -0.04, 0)).alcanzable)
        self.assertFalse(compensar(PoseDock(0, 0.06, 0)).alcanzable)

    def test_el_offset_lateral_rota_con_dth(self):
        c = compensar(PoseDock(0, 0, 6.0))
        self.assertAlmostEqual(c.delta_en_brazo[0], 0.11 * math.sin(math.radians(6)), places=6)


class TestConfiguracion(unittest.TestCase):
    def test_faltan_poses(self):
        with self.assertRaises(ErrorConfiguracion):
            desde_dict({'rol': 2, 'poses': {'cuna_aprox': None}})

    def test_metros_en_vez_de_milimetros(self):
        with self.assertRaises(ErrorConfiguracion):
            desde_dict({'rol': 4, 'poses': {'cuna_aprox': [0.2, 0, 0.15, 0, 0, 0], 'pose_libre': [100, 0, 250, 0, 0, 0],
                                            'cuna_agarre': [200, 0, 120, 0, 0, 0],
                                            'recepcion_aprox': [[1, 1, 1, 0, 0, 0]] * 4, 'recepcion_dejar': [[1, 1, 1, 0, 0, 0]] * 4}})

    def test_bandeja_de_4(self):
        datos = {'rol': 4, 'poses': {c: [200, 0, 120, 0, 0, 0] for c in ('cuna_aprox', 'cuna_agarre', 'pose_libre')}}
        datos['poses']['recepcion_aprox'] = [[100, 100, 100, 0, 0, 0]] * 3
        datos['poses']['recepcion_dejar'] = [[100, 100, 100, 0, 0, 0]] * 4
        with self.assertRaises(ErrorConfiguracion):
            desde_dict(datos)

    def test_rol_invalido(self):
        with self.assertRaises(ErrorConfiguracion):
            desde_dict({'rol': 7, 'poses': {}})


class TestEstrategia(unittest.TestCase):
    def test_e1_carga_a(self):
        e, b = estrategia(1)
        r = e.cambiar(NOMINAL, None)
        self.assertTrue(r.ok); self.assertEqual(r.pieza_dejo, 'A'); self.assertIsNone(r.error)
        self.assertEqual(b.nombres().count('cerrar_pinza'), 1)
        self.assertEqual(b.llamadas[-1][1], (100, 0, 250, -180, 0, 0))  # termina en pose libre

    def test_e2_retira_a_y_coloca_b(self):
        e, b = estrategia(2, tiempo_max_s=60.0)
        r = e.cambiar(NOMINAL, 'A')
        self.assertTrue(r.ok); self.assertEqual(r.pieza_dejo, 'B')
        n = b.nombres()
        self.assertEqual(n.count('cerrar_pinza'), 2)
        # retira de la cuna (primer movimiento a la cuna) antes de tomar del almacén
        primero_cuna = next(i for i, (nom, a) in enumerate(b.llamadas) if nom == 'mover_coords' and a[0] == 200)
        primero_almacen = next(i for i, (nom, a) in enumerate(b.llamadas) if nom == 'mover_coords' and a[0] == 150)
        self.assertLess(primero_cuna, primero_almacen)

    def test_e4_solo_retira(self):
        e, _ = estrategia(4)
        r = e.cambiar(NOMINAL, 'C')
        self.assertTrue(r.ok); self.assertIsNone(r.pieza_dejo)

    def test_pasos_por_rol_con_duraciones_de_ejemplo(self):
        """Con 1.0 s por movimiento y 0.4 s por pinza (PLACEHOLDERS): E2 y E3 duplican el trabajo de E1."""
        t = {}
        for rol, pieza in ((1, None), (2, 'A'), (3, 'B'), (4, 'C')):
            e, b = estrategia(rol, tiempo_max_s=60.0)
            self.assertTrue(e.cambiar(NOMINAL, pieza).ok)
            t[rol] = b.reloj.t
        self.assertAlmostEqual(t[1], 8.2); self.assertAlmostEqual(t[4], 8.2)
        self.assertAlmostEqual(t[2], 15.4); self.assertAlmostEqual(t[3], 15.4)

    def test_pieza_inesperada_no_mueve(self):
        e, b = estrategia(2)
        r = e.cambiar(NOMINAL, 'B')
        self.assertFalse(r.ok); self.assertEqual(r.error, 'PIEZA_INESPERADA'); self.assertEqual(b.llamadas, [])

    def test_fuera_de_tolerancia(self):
        e, b = estrategia(2)
        self.assertEqual(e.cambiar(PoseDock(0.05, 0, 0), 'A').error, 'FUERA_DE_TOLERANCIA')
        self.assertEqual(e.cambiar(PoseDock(0, 0, 7.0), 'A').error, 'FUERA_DE_TOLERANCIA')
        self.assertEqual(b.llamadas, [])

    def test_sin_configuracion_falla_cerrado(self):
        e, b = estrategia(2, poses=None)
        r = e.cambiar(NOMINAL, 'A')
        self.assertEqual(r.error, 'NO_CONFIGURADO'); self.assertEqual(b.llamadas, [])

    def test_poses_de_otro_rol(self):
        e, b = estrategia(2, poses=poses_ejemplo(3))
        self.assertEqual(e.cambiar(NOMINAL, 'A').error, 'NO_CONFIGURADO')

    def test_compensacion_solo_sobre_la_cuna(self):
        e, b = estrategia(1)
        e.cambiar(PoseDock(0.02, 0.01, 0.0), None)
        moves = [a for n, a in b.llamadas if n == 'mover_coords']
        cuna = [m for m in moves if abs(m[0] - 200.0) < 30]
        almacen = [m for m in moves if m[0] == 150.0]
        self.assertTrue(all(abs(m[0] - 220.0) < 1e-6 and abs(m[1] - 10.0) < 1e-6 for m in cuna))
        self.assertTrue(almacen and all(m[1] < 0 for m in almacen))
        self.assertEqual(almacen[0][0], 150.0)  # el almacén no se desplaza

    def test_agarre_en_vacio(self):
        e, b = estrategia(1, brazo=BrazoSimulado(agarre='vacia'))
        r = e.cambiar(NOMINAL, None)
        self.assertFalse(r.ok); self.assertTrue(r.error.startswith('AGARRE_EN_VACIO'))
        self.assertEqual(e.indice, 0)  # no consume la ranura

    def test_movimiento_fallido_no_sigue(self):
        e, b = estrategia(2, brazo=BrazoSimulado(fallar_en=2))
        r = e.cambiar(NOMINAL, 'A')
        self.assertFalse(r.ok); self.assertIn('MOVIMIENTO_FALLIDO', r.error)
        self.assertEqual(len(b.llamadas), 3)  # se detiene en la llamada fallida

    def test_excepcion_se_captura(self):
        e, _ = estrategia(2, brazo=BrazoSimulado(lanzar_en=1))
        r = e.cambiar(NOMINAL, 'A')
        self.assertFalse(r.ok); self.assertTrue(r.error.startswith('EXCEPCION'))

    def test_limite_de_tiempo(self):
        e, _ = estrategia(2, brazo=BrazoSimulado(dur_mover=3.0), tiempo_max_s=8.0)
        r = e.cambiar(NOMINAL, 'A')
        self.assertFalse(r.ok); self.assertTrue(r.error.startswith('TIEMPO_EXCEDIDO'))

    def test_tiempo_registrado_con_duraciones_simuladas(self):
        e, b = estrategia(1, brazo=BrazoSimulado(dur_mover=0.5, dur_pinza=0.2))
        r = e.cambiar(NOMINAL, None)
        self.assertAlmostEqual(r.t_cambio, b.reloj.t)
        self.assertGreater(r.t_cambio, 0)

    def test_bandeja_se_agota_a_la_quinta(self):
        e, _ = estrategia(1)
        for _ in range(4):
            self.assertTrue(e.cambiar(NOMINAL, None).ok)
        self.assertEqual(e.cambiar(NOMINAL, None).error, 'BANDEJA_AGOTADA')

    def test_usa_una_ranura_distinta_por_pit(self):
        e, b = estrategia(4)
        e.cambiar(NOMINAL, 'C'); e.cambiar(NOMINAL, 'C')
        dejar = [a for n, a in b.llamadas if n == 'mover_coords' and a[2] == 125]
        self.assertEqual(sorted({d[1] for d in dejar}), [150.0, 160.0])

    def test_fuera_de_alcance(self):
        geo = GeometriaEstacion(alcance_min_m=0.14, alcance_max_m=0.17)
        e, b = estrategia(1, geo=geo)
        self.assertEqual(e.cambiar(NOMINAL, None).error, 'FUERA_DE_ALCANCE')
        self.assertEqual(b.llamadas, [])

    def test_roles_coinciden_con_el_reto(self):
        self.assertEqual([(r.retira, r.coloca) for r in ROLES.values()],
                         [(None, 'A'), ('A', 'B'), ('B', 'C'), ('C', None)])


if __name__ == '__main__':
    unittest.main()
