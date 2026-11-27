"""Planificador matemático del carrito (sección 1.2 de la división; 1.4 para el acople).

Funciones puras, sin ROS, en unidades SI (metros, radianes, segundos) y marcos del mapa o del dock.
Implementa lo que pide el HTML:
  planificar:  phi = wrap(atan2(dy, dx) - theta),  L = hypot(dx, dy)
  compensar:   phi_cmd = phi / ca,  L_cmd = L / cd
  duración:    t_giro = |phi_cmd| / w,  t_avance = L_cmd / v
  estimar:     escala_nueva = escala + alpha * (medido / comandado - escala)

`comandado` es SIEMPRE lo que se envió al robot (phi_cmd y L_cmd, ya compensados), no lo nominal; con
lo nominal el estimador converge a un valor sesgado. Las protecciones de `actualizar_escalas` (límites
de la escala, paso máximo, comandos mínimos) son PROVISIONALES: el HTML pide un paso limitado pero no
fija números. Con `proteger=False` reproduce exactamente la fórmula del simulador oficial.

No ejecuta nada: el ejecutor (1.2.4 a 1.2.7) toma un `Comando` y lo publica por la entrada autorizada
de `twist_mux`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from geometria_dock.transformaciones import Pose2D, wrap

from .docks import ORDEN, Dock, siguiente

V_REF, W_REF = 0.10, 0.50    # referencia de RC-1 / HTML
V_MAX, W_MAX = 0.20, 0.80    # límites del reto
TOL_POS_M, TOL_ANG_DEG = 0.04, 6.0
EPS_DIST = 1e-9

# Protecciones provisionales del estimador
LIMITES_ESCALA = (0.5, 1.5)
PASO_MAX_ESCALA = 0.05
MIN_L_ESTIMAR_M = 0.10
MIN_PHI_ESTIMAR = math.radians(20.0)
MAX_PHI_ESTIMAR = math.radians(150.0)  # cerca de ±pi el ángulo medido es ambiguo


def _finitos(*v: float) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in v)


@dataclass(frozen=True)
class Escalas:
    """Relación real movimiento/comando. 1.0 = el robot hace lo que se le ordena."""
    cd: float = 1.0
    ca: float = 1.0

    def __post_init__(self) -> None:
        if not _finitos(self.cd, self.ca) or self.cd <= 0 or self.ca <= 0:
            raise ValueError('las escalas deben ser positivas y finitas')


@dataclass(frozen=True)
class Tramo:
    phi: float  # giro geométrico, rad (+ antihorario)
    L: float    # distancia, m


@dataclass(frozen=True)
class Comando:
    phi_cmd: float
    L_cmd: float
    v: float
    w: float        # con signo: el de phi_cmd
    t_giro: float
    t_avance: float

    @property
    def t_total(self) -> float:
        return self.t_giro + self.t_avance


def planificar_tramo(pose: Pose2D, destino: Tuple[float, float]) -> Tramo:
    """Giro y distancia desde la pose creída hasta el destino. Con destino coincidente, giro cero."""
    if not _finitos(*destino):
        raise ValueError('destino no finito')
    dx, dy = destino[0] - pose.x, destino[1] - pose.y
    L = math.hypot(dx, dy)
    phi = wrap(math.atan2(dy, dx) - pose.th) if L > EPS_DIST else 0.0
    return Tramo(phi, L)


def comandar(tramo: Tramo, escalas: Escalas = Escalas(), v: float = V_REF, w: float = W_REF,
             v_max: float = V_MAX, w_max: float = W_MAX) -> Comando:
    """Comando compensado y sus duraciones. Rechaza velocidades fuera de los límites del reto."""
    if not _finitos(v, w) or not 0 < v <= v_max:
        raise ValueError(f'v debe estar en (0, {v_max}] m/s')
    if not 0 < w <= w_max:
        raise ValueError(f'w debe estar en (0, {w_max}] rad/s')
    phi_cmd, L_cmd = tramo.phi / escalas.ca, tramo.L / escalas.cd
    return Comando(phi_cmd, L_cmd, v, math.copysign(w, phi_cmd) if phi_cmd else 0.0,
                   abs(phi_cmd) / w, L_cmd / v)


def pose_prevista(pose: Pose2D, tramo: Tramo) -> Pose2D:
    """Pose a la que llegaría el carrito si ejecutara el tramo sin errores."""
    th = wrap(pose.th + tramo.phi)
    return Pose2D(pose.x + tramo.L * math.cos(th), pose.y + tramo.L * math.sin(th), th)


def medir_tramo(inicio: Pose2D, fin: Pose2D) -> Tuple[float, float]:
    """(distancia, giro con signo) entre dos poses medidas. Medir ANTES de cualquier acople."""
    return math.hypot(fin.x - inicio.x, fin.y - inicio.y), wrap(fin.th - inicio.th)


# ------------------------------------------------------------------ estimador de escalas
@dataclass(frozen=True)
class ResultadoEscalas:
    escalas: Escalas
    uso_cd: bool
    uso_ca: bool
    motivo_cd: Optional[str] = None
    motivo_ca: Optional[str] = None


def _paso(actual: float, ratio: float, alpha: float, proteger: bool) -> float:
    nuevo = actual + alpha * (ratio - actual)
    if proteger:
        nuevo = actual + max(-PASO_MAX_ESCALA, min(PASO_MAX_ESCALA, nuevo - actual))
        nuevo = max(LIMITES_ESCALA[0], min(LIMITES_ESCALA[1], nuevo))
    return nuevo


def actualizar_escalas(esc: Escalas, cmd: Comando, dist_medida: float, giro_medido: float,
                       alpha: float = 0.35, *, proteger: bool = True) -> ResultadoEscalas:
    """Filtro exponencial de las escalas con lo medido en el tramo anterior."""
    if not _finitos(dist_medida, giro_medido, alpha) or not 0 < alpha <= 1:
        raise ValueError('datos inválidos para actualizar las escalas')
    cd, ca, uso_cd, uso_ca, m_cd, m_ca = esc.cd, esc.ca, False, False, None, None

    if cmd.L_cmd == 0:
        m_cd = 'sin_distancia_comandada'
    elif proteger and cmd.L_cmd < MIN_L_ESTIMAR_M:
        m_cd = 'distancia_comandada_pequena'
    else:
        ratio = dist_medida / cmd.L_cmd
        if proteger and not LIMITES_ESCALA[0] <= ratio <= LIMITES_ESCALA[1]:
            m_cd = 'razon_fuera_de_limites'
        else:
            cd, uso_cd = _paso(cd, ratio, alpha, proteger), True

    if cmd.phi_cmd == 0:
        m_ca = 'sin_giro_comandado'
    elif proteger and not MIN_PHI_ESTIMAR <= abs(cmd.phi_cmd) <= MAX_PHI_ESTIMAR:
        m_ca = 'giro_comandado_fuera_de_rango'
    else:
        ratio = giro_medido / cmd.phi_cmd
        if proteger and not LIMITES_ESCALA[0] <= ratio <= LIMITES_ESCALA[1]:
            m_ca = 'razon_fuera_de_limites'
        else:
            ca, uso_ca = _paso(ca, ratio, alpha, proteger), True
    return ResultadoEscalas(Escalas(cd, ca), uso_cd, uso_ca, m_cd, m_ca)


# ------------------------------------------------------------------ vuelta y presupuesto
def planificar_vuelta(docks: Dict[int, Dock], escalas: Escalas = Escalas(), v: float = V_REF,
                      w: float = W_REF) -> List[Comando]:
    """Los 4 comandos de una vuelta con llegadas ideales, empezando en E1 con su rumbo nominal."""
    pose, out, est = docks[1].pose, [], 1
    for _ in ORDEN:
        destino = docks[siguiente(est)]
        tramo = planificar_tramo(pose, (destino.x, destino.y))
        out.append(comandar(tramo, escalas, v, w))
        pose, est = pose_prevista(pose, tramo), siguiente(est)
    return out


def tiempo_vuelta(comandos: List[Comando], t_pit: float) -> float:
    """Tiempo ideal de una vuelta: movimientos más un pit por parada (sin reintentos ni aceleración)."""
    return sum(c.t_total for c in comandos) + t_pit * len(comandos)


# ------------------------------------------------------------------ acople
@dataclass(frozen=True)
class Primitiva:
    tipo: str      # 'giro' (rad) o 'avance' (m; negativo = reversa)
    valor: float


def error_acople(dx: float, dy: float, dth_deg: float) -> Tuple[float, float]:
    """(error de posición en m, error angular en grados) respecto a la cruz del dock."""
    return math.hypot(dx, dy), abs(math.degrees(wrap(math.radians(dth_deg))))


def acople_valido(dx: float, dy: float, dth_deg: float, tol_pos: float = TOL_POS_M,
                  tol_ang_deg: float = TOL_ANG_DEG) -> bool:
    """Ambas condiciones a la vez: posición <= 4 cm y ángulo <= 6°."""
    pos, ang = error_acople(dx, dy, dth_deg)
    eps = 1e-9  # los bordes (4 cm, 6°) son válidos; evita el ruido de punto flotante
    return pos <= tol_pos + eps and ang <= tol_ang_deg + eps


def planificar_acople(dx: float, dy: float, dth_deg: float, *, permitir_reversa: bool = False,
                      min_dist: float = 0.01, min_giro: float = math.radians(0.5)) -> List[Primitiva]:
    """Corrección con giros y avances (tracción diferencial: sin movimiento lateral directo).

    Trabaja en el marco del dock, cuyo objetivo es (0, 0, 0): girar hacia la cruz, avanzar y girar al
    rumbo nominal. Con `permitir_reversa` elige adelante o atrás según el menor tiempo (la reversa
    está desactivada por defecto: el carrito no ve ni detecta obstáculos hacia atrás).
    """
    if not _finitos(dx, dy, dth_deg):
        raise ValueError('pose no finita')
    th, dist = math.radians(dth_deg), math.hypot(dx, dy)
    prims: List[Primitiva] = []
    if dist < min_dist:
        phi = wrap(-th)
        return [Primitiva('giro', phi)] if abs(phi) >= min_giro else []
    rumbo = math.atan2(-dy, -dx)
    opciones = [(wrap(rumbo - th), dist, rumbo)]
    if permitir_reversa:
        opciones.append((wrap(rumbo + math.pi - th), -dist, rumbo + math.pi))

    def costo(o: Tuple[float, float, float]) -> float:
        phi1, avance, rumbo_final = o
        return (abs(phi1) + abs(wrap(-rumbo_final))) / W_REF + abs(avance) / V_REF

    phi1, avance, _ = min(opciones, key=costo)
    aplicado = 0.0
    if abs(phi1) >= min_giro:
        prims.append(Primitiva('giro', phi1))
        aplicado = phi1
    prims.append(Primitiva('avance', avance))
    phi2 = wrap(-(th + aplicado))  # rumbo tras el avance = rumbo inicial + giro aplicado; objetivo: 0
    return prims + ([Primitiva('giro', phi2)] if abs(phi2) >= min_giro else [])


def aplicar_primitivas(pose: Pose2D, prims: List[Primitiva]) -> Pose2D:
    """Resultado ideal (sin ruido) de ejecutar las primitivas. Para pruebas."""
    x, y, th = pose.x, pose.y, pose.th
    for p in prims:
        if p.tipo == 'giro':
            th = wrap(th + p.valor)
        elif p.tipo == 'avance':
            x, y = x + p.valor * math.cos(th), y + p.valor * math.sin(th)
        else:
            raise ValueError(f'primitiva desconocida: {p.tipo}')
    return Pose2D(x, y, th)
