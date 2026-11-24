"""Funciones puras del GranPrix, unidades SI: metros y radianes."""
import math

DOCKS = {1:(.4,.4,-math.pi/2), 2:(2.4,.4,0.), 3:(2.4,2.4,math.pi/2), 4:(.4,2.4,math.pi)}

def wrap(a):
    if not math.isfinite(a): raise ValueError('Ángulo no finito')
    return math.atan2(math.sin(a), math.cos(a))

def planificar(x,y,theta,xd,yd):
    if not all(math.isfinite(v) for v in (x,y,theta,xd,yd)): raise ValueError('Pose no finita')
    dx,dy=xd-x,yd-y
    L=math.hypot(dx,dy)
    return (wrap(math.atan2(dy,dx)-theta) if L>1e-9 else 0., L)

def compensar(phi,L,cd=1.,ca=1.):
    if not all(math.isfinite(v) for v in (phi,L,cd,ca)) or min(cd,ca)<=0 or L<0:
        raise ValueError('Comando o escala inválidos')
    return phi/ca,L/cd

def actualizar_escala(anterior,medido,comandado,alpha=.35,*,min_comando=1e-3,limites=(.5,1.5)):
    """Rechaza muestras degeneradas y escalas incompatibles. Límites provisionales de laboratorio."""
    if not all(math.isfinite(v) for v in (anterior,medido,comandado,alpha,min_comando,*limites)):
        raise ValueError('Dato no finito')
    if not 0<alpha<=1 or min_comando<=0 or not 0<limites[0]<limites[1] or not limites[0]<=anterior<=limites[1]:
        raise ValueError('Configuración inválida')
    if abs(comandado)<min_comando: return anterior,False
    medida=medido/comandado
    if not limites[0]<=medida<=limites[1]: return anterior,False
    return anterior+alpha*(medida-anterior),True

if __name__=='__main__':
    phi,L=planificar(*DOCKS[1],*DOCKS[2][:2])
    print(f'E1 -> E2: giro {math.degrees(phi):.2f} grados; distancia {L:.3f} m')
    p,l=compensar(phi,L,.98,1.09)
    print(f'Ejemplo compensado (escalas ficticias): {math.degrees(p):.2f} grados, {l:.3f} m')
