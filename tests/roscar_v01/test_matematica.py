import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'/'roscar_v01'))
import random
from matematica import DOCKS, wrap, planificar, compensar, actualizar_escala, giro_medido

class TestMatematica(unittest.TestCase):
    def test_cuatro_tramos(self):
        for s in range(1,5):
            phi,L=planificar(*DOCKS[s],*DOCKS[s%4+1][:2])
            self.assertAlmostEqual(phi,math.pi/2)
            self.assertAlmostEqual(L,2.)
    def test_wrap(self): self.assertAlmostEqual(wrap(3*math.pi/2),-math.pi/2)
    def test_mismo_punto(self): self.assertEqual(planificar(0,0,1,0,0),(0.,0.))
    def test_compensar(self): self.assertAlmostEqual(compensar(1,2,.98,1.09)[1],2/.98)
    def test_invalida(self):
        with self.assertRaises(ValueError): compensar(1,2,0,1)
    def test_filtro(self):
        v,ok=actualizar_escala(1.,2.08,2.)
        self.assertTrue(ok); self.assertAlmostEqual(v,1.014)
    def test_giro_negativo(self):
        v,ok=actualizar_escala(1.,-1.1,-1.)
        self.assertTrue(ok); self.assertAlmostEqual(v,1.035)
    def test_muestra_degenerada(self): self.assertEqual(actualizar_escala(1,0,0),(1,False))
    def test_atipica(self): self.assertEqual(actualizar_escala(1,9,1),(1,False))
    def test_nan(self):
        with self.assertRaises(ValueError): planificar(float('nan'),0,0,1,1)

    def test_giro_medido_cruza_pi(self):
        self.assertAlmostEqual(giro_medido(math.radians(170),math.radians(-170)),math.radians(20))

    def test_converge_con_comando_compensado(self):
        random.seed(3); cd=1.; real_sd=1.01
        for _ in range(12):
            enviado=compensar(0.,2.,cd,1.)[1]
            cd,_=actualizar_escala(cd,enviado*real_sd*(1+random.gauss(0,.005)),enviado)
        self.assertAlmostEqual(cd,real_sd,delta=.01)

    def test_con_valor_nominal_converge_sesgado(self):
        """Error típico: pasar el giro nominal en lugar del comandado. Converge a ~raiz(escala real)."""
        random.seed(3); ca=1.; real=1.09
        for _ in range(40):
            enviado=compensar(1.,2.,1.,ca)[0]
            ca,_=actualizar_escala(ca,enviado*real,1.)
        self.assertAlmostEqual(ca,math.sqrt(real),delta=.005)
        self.assertGreater(real-ca,.04)

if __name__=='__main__': unittest.main()
