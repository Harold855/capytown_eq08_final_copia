#!/usr/bin/env python3
"""Estación y Race Control FALSOS: permiten probar la misión del carro sin JetCobot, sin supervisor y sin `puente_mqtt`.

    python3 carrito/nodos/estacion_falsa.py --ros-args -p t_cambio_s:=5.8 -p modo:=ok -p autoiniciar_s:=-1.0
    ros2 service call /estacion_falsa/iniciar std_srvs/srv/Trigger        # da el turno: el carro arranca

Hace de Race Control (turno, bandera, enlace) y de las cuatro estaciones (estado y resultado) con los MISMOS nombres de tópico y
JSON que usa `adaptador_ros.py`. NO mueve ningún brazo ni cambia ninguna pieza: solo responde. Sigue la especificación del supervisor
(docs/arquitectura/02 del docente): estados LIBRE -> ESPERANDO (hay turno) -> CAMBIANDO -> LISTA, y una solicitud solo se acepta con
la estación en ESPERANDO; si no, o si el equipo, la pose (4 cm y 6°), la pieza o la bandera fallan, se RECHAZA de inmediato con un
resultado ok=false y la estación sigue en ESPERANDO (el carro reintenta). Valida lo que la estación real puede saber, es decir, la pose
que el carro REPORTA (no la verdadera): mide con cinta. Por defecto NO da el turno por sí sola (falla cerrada): `~/iniciar` o `autoiniciar_s`. Núcleo en Python puro; el nodo es delgado.
Los nombres de tópicos son los provisionales del adaptador, no los del curso (aún sin publicar).
"""
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from carrito.granprix_carrito.mision import ConfigMision, cargar_mision  # noqa: E402
from carrito.granprix_carrito.planificador import TOL_ANG_DEG, TOL_POS_M  # noqa: E402

MODOS = ('ok', 'rechazar', 'no_responder', 'pieza_mala', 'offline')
HOLGURA_S = 0.05                                                              # medio periodo del temporizador (10 Hz): evita que el redondeo alargue el reenvío
INTERVALO = {'enlace': 0.5, 'turno': 1.0, 'bandera': 1.0, 'estado': 1.0}      # reenvío periódico, como un tópico retenido
PARAMETROS = {
    't_cambio_s': 5.8, 't_liberar_s': 0.5, 't_rechazo_s': 0.2, 'esperando_retardo_s': 0.0, 'modo': 'ok', 'estacion_modo': 0, 'turno_equipo': 0, 'autoiniciar_s': -1.0,
    'tanda': 'prueba', 'resultado_antes_de_estado': True, 'hz': 10.0, 'mision_yaml': '', 'registro_dir': '',
    'turno_topic': '/granprix/turno', 'bandera_topic': '/granprix/bandera', 'enlace_topic': '/granprix/enlace',
    'estacion_topic': '/granprix/estacion_estado', 'resultado_topic': '/granprix/resultado',
    'solicitud_topic': '/granprix/solicitud', 'evento_topic': '/granprix/evento', 'vuelta_topic': '/granprix/vuelta',
}


@dataclass(frozen=True)
class ConfigFalsa:
    equipo: int = 8
    piezas: tuple = ConfigMision().piezas                 # (estación, trae, deja)
    t_cambio_s: float = 5.8                               # lo que tardaría el intercambio real (supuesto)
    t_liberar_s: float = 0.5                              # de LISTA a LIBRE
    t_rechazo_s: float = 0.2                              # lo que tarda el supervisor en rechazar una solicitud
    esperando_retardo_s: float = 0.0                      # retraso entre tener el turno y pasar a ESPERANDO (el carro puede llegar antes)
    tol_pos_m: float = TOL_POS_M
    tol_ang_deg: float = TOL_ANG_DEG
    modo: str = 'ok'
    estacion_modo: object = None                          # None = el modo vale para todas
    turno_equipo: object = None                           # None = el turno es del equipo del carro
    autoiniciar_s: object = None                          # None = no da el turno sola
    tanda: str = 'prueba'
    resultado_antes_de_estado: bool = True

    def __post_init__(self):
        if self.modo not in MODOS:
            raise ValueError(f'modo debe ser uno de {MODOS}')
        if self.estacion_modo not in (None, 1, 2, 3, 4):
            raise ValueError('estacion_modo debe ser None o 1 a 4')
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
                   for v in (self.t_cambio_s, self.t_liberar_s, self.t_rechazo_s, self.esperando_retardo_s)):
            raise ValueError('los tiempos deben ser finitos y no negativos')
        if self.autoiniciar_s is not None and not (math.isfinite(self.autoiniciar_s) and self.autoiniciar_s >= 0):
            raise ValueError('autoiniciar_s debe ser None o >= 0')


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def parsear_solicitud(msg, estacion):
    """(equipo, dx, dy, dth_deg, pieza_trae) o el motivo de descarte (texto). Una solicitud mal formada no recibe respuesta."""
    if not isinstance(msg, dict):
        return 'DESCARTADO_NO_ES_OBJETO'
    if isinstance(msg.get('equipo'), bool) or not isinstance(msg.get('equipo'), int):
        return 'DESCARTADO_EQUIPO'
    if msg.get('dock') != estacion or isinstance(msg.get('dock'), bool):
        return 'DESCARTADO_DOCK'
    pose = msg.get('pose')
    if not isinstance(pose, dict) or not all(_num(pose.get(k)) for k in ('dx', 'dy', 'dth')):
        return 'DESCARTADO_POSE'
    pieza = msg.get('pieza_trae')
    if pieza is not None and not isinstance(pieza, str):
        return 'DESCARTADO_PIEZA'
    return msg['equipo'], pose['dx'], pose['dy'], pose['dth'], pieza


class EntornoFalso:
    def __init__(self, cfg=ConfigFalsa(), reloj=time.monotonic, reloj_ts=time.time):
        self.cfg, self._reloj, self._ts = cfg, reloj, reloj_ts
        self._t0 = reloj()
        self.turno, self.bandera_actual, self.enlace_ok, self.enlace_mudo = False, 'verde', True, False
        self._turno_retirado, self._t_turno = False, None
        self.estados = {n: 'LIBRE' for n in (1, 2, 3, 4)}
        self._libre_desde = {n: self._t0 for n in self.estados}
        for n in self.estados:
            if cfg.modo == 'offline' and cfg.estacion_modo in (None, n):
                self.estados[n] = 'OFFLINE'
        self._pend, self._ult, self._proximo = {}, {}, None
        self.n = {'solicitudes': 0, 'descartadas': 0, 'ocupada': 0, 'rechazos': 0, 'resultados': 0, 'pit_ok': 0, 'reintento': 0, 'vueltas': 0}
        self.vueltas, self.ultima_solicitud, self.ultimo_motivo = [], None, None

    # ---------------------------------------------------------------- Race Control falso
    def iniciar(self):
        self.turno, self._turno_retirado, self._t_turno = True, False, self._reloj()

    def retirar_turno(self):
        self.turno, self._turno_retirado = False, True

    def bandera(self, valor):
        if valor not in ('verde', 'roja'):
            raise ValueError("bandera debe ser 'verde' o 'roja'")
        self.bandera_actual = valor

    def enlace(self, ok, mudo=False):
        """ok=False publica enlace caído; mudo=True deja de publicar (el carro lo nota por la falta de latidos)."""
        self.enlace_ok, self.enlace_mudo = bool(ok), bool(mudo)

    def fallar_proximo(self, modo='rechazar'):
        if modo not in ('rechazar', 'no_responder', 'pieza_mala'):
            raise ValueError('modo no válido para una sola vez')
        self._proximo = modo

    # ---------------------------------------------------------------- entradas del carro
    def solicitud(self, estacion, msg):
        """Procesa una solicitud. Devuelve el motivo si se descartó o rechazó, o None si se aceptó para cambiar."""
        n = self.n
        valida = isinstance(estacion, int) and not isinstance(estacion, bool) and estacion in self.estados
        v = parsear_solicitud(msg, estacion) if valida else 'DESCARTADO_ESTACION'
        if isinstance(v, str):
            n['descartadas'] += 1
            return self._motivo(v)
        if self.estados[estacion] == 'OFFLINE':
            n['descartadas'] += 1
            return self._motivo('ESTACION_OFFLINE')
        if estacion in self._pend:
            n['ocupada'] += 1
            return self._motivo('OCUPADA')
        equipo, dx, dy, dth, pieza = v
        n['solicitudes'] += 1
        modo, self._proximo = self._proximo or (self.cfg.modo if self.cfg.estacion_modo in (None, estacion) else 'ok'), None
        ok, deja, motivo = self._decidir(modo, estacion, equipo, dx, dy, dth, pieza)
        self.ultima_solicitud = {'estacion': estacion, 'equipo': equipo, 'dx': dx, 'dy': dy, 'dth': dth, 'pieza_trae': pieza, 'modo': modo,
                                 'ok': ok, 'motivo': motivo, 'estado_al_recibir': self.estados[estacion]}
        t = self._reloj()
        if ok:                                            # se acepta: la estación pasa a CAMBIANDO
            self.estados[estacion] = 'CAMBIANDO'
            self._pend[estacion] = {'t_fin': t + self.cfg.t_cambio_s, 'fase': 'cambiando', 'ok': True, 'deja': deja, 'motivo': None,
                                    'equipo': equipo, 'responde': modo != 'no_responder'}
        else:                                             # se rechaza de inmediato; la estación no cambia de estado
            self._pend[estacion] = {'t_fin': t + self.cfg.t_rechazo_s, 'fase': 'rechazando', 'ok': False, 'deja': None, 'motivo': motivo,
                                    'equipo': equipo, 'responde': True}
        return self._motivo(motivo)

    def _motivo(self, m):
        self.ultimo_motivo = m
        return m

    def _decidir(self, modo, estacion, equipo, dx, dy, dth, pieza):
        """Mismo orden que el supervisor: estado, turno, pose, bandera (y la pieza, que valida la estrategia)."""
        c = self.cfg
        if modo == 'rechazar':
            return False, None, 'RECHAZO_FORZADO'
        if self.estados[estacion] != 'ESPERANDO':
            return False, None, 'NO_ESPERANDO'
        if equipo != (c.turno_equipo if c.turno_equipo is not None else c.equipo):
            return False, None, 'SIN_TURNO'
        if math.hypot(dx, dy) > c.tol_pos_m + 1e-9 or abs(dth) > c.tol_ang_deg + 1e-9:
            return False, None, 'FUERA_DE_TOLERANCIA'
        if self.bandera_actual == 'roja':
            return False, None, 'BANDERA_ROJA'
        _, trae, deja = next(p for p in c.piezas if p[0] == estacion)
        if pieza != trae:
            return False, None, 'PIEZA_INESPERADA'
        if modo == 'no_responder':
            return True, None, None
        return True, ('Z' if modo == 'pieza_mala' else deja), None

    def evento(self, msg):
        if isinstance(msg, dict) and msg.get('tipo') in ('pit_ok', 'reintento'):
            self.n[msg['tipo']] += 1

    def vuelta(self, msg):
        if isinstance(msg, dict) and _num(msg.get('numero')):
            self.n['vueltas'] += 1
            self.vueltas.append(int(msg['numero']))

    # ---------------------------------------------------------------- salidas
    def _emitir(self, out, clave, valor, canal, payload):
        t, previo = self._reloj(), self._ult.get(clave)
        if previo is None or previo[0] != valor or t - previo[1] >= INTERVALO[clave.rstrip('0123456789')] - HOLGURA_S:
            self._ult[clave] = (valor, t)
            out.append((canal, payload))

    def _base(self):
        return {'v': 1, 'ts': self._ts()}

    def _estado_msg(self, estacion):
        return ('estacion_estado', {**self._base(), 'estacion': estacion, 'estado': self.estados[estacion]})

    def paso(self):
        """Lo que hay que publicar ahora: lista de (canal, carga). Canales: turno, bandera, enlace, estacion_estado, resultado."""
        t, out = self._reloj(), []
        a = self.cfg.autoiniciar_s
        if a is not None and not self.turno and not self._turno_retirado and t - self._t0 >= a:
            self.turno, self._t_turno = True, t
        for n, ex in list(self._pend.items()):
            if ex['fase'] == 'rechazando' and t >= ex['t_fin']:
                out.append(('resultado', {**self._base(), 'estacion': n, 'equipo': ex['equipo'], 'ok': False, 'pieza_dejo': None,
                                          't_cambio': None, 'motivo': ex['motivo']}))
                self.n['rechazos'] += 1
                del self._pend[n]
                continue
            if ex['fase'] == 'cambiando' and t >= ex['t_fin'] and ex['responde']:
                resultado = ('resultado', {**self._base(), 'estacion': n, 'equipo': ex['equipo'], 'ok': ex['ok'], 'pieza_dejo': ex['deja'],
                                           't_cambio': self.cfg.t_cambio_s, 'motivo': ex['motivo']})
                self.estados[n] = 'LISTA'
                self._ult.pop(f'estado{n}', None)
                nuevo = self._estado_msg(n)
                out.extend([resultado, nuevo] if self.cfg.resultado_antes_de_estado else [nuevo, resultado])
                self._ult[f'estado{n}'] = (self.estados[n], t)
                self.n['resultados'] += 1
                ex['fase'], ex['t_libre'] = 'lista', t + self.cfg.t_liberar_s
            if ex['fase'] == 'lista' and t >= ex['t_libre']:
                self.estados[n], self._libre_desde[n] = 'LIBRE', t
                del self._pend[n]
        for n, estado in self.estados.items():            # LIBRE <-> ESPERANDO según haya turno (y tras el retardo)
            if n in self._pend or estado not in ('LIBRE', 'ESPERANDO'):
                continue
            if self.turno and estado == 'LIBRE' and self._t_turno is not None \
                    and t - max(self._libre_desde[n], self._t_turno) >= self.cfg.esperando_retardo_s - 1e-9:
                self.estados[n] = 'ESPERANDO'
            elif not self.turno and estado == 'ESPERANDO':
                self.estados[n], self._libre_desde[n] = 'LIBRE', t
        if not self.enlace_mudo:
            self._emitir(out, 'enlace', self.enlace_ok, 'enlace', self.enlace_ok)
        self._emitir(out, 'turno', self.turno, 'turno', {**self._base(), 'autorizado': self.turno, 'tanda': self.cfg.tanda})
        self._emitir(out, 'bandera', self.bandera_actual, 'bandera', {**self._base(), 'bandera': self.bandera_actual})
        for n in self.estados:
            clave = f'estado{n}'
            previo = self._ult.get(clave)
            if previo is None or previo[0] != self.estados[n] or t - previo[1] >= INTERVALO['estado'] - HOLGURA_S:
                self._ult[clave] = (self.estados[n], t)
                out.append(self._estado_msg(n))
        return out

    def instantanea(self):
        return {'turno': self.turno, 'bandera': self.bandera_actual, 'enlace': 'mudo' if self.enlace_mudo else self.enlace_ok,
                'estaciones': dict(self.estados), 'modo': self.cfg.modo, **self.n, 'vueltas_vistas': list(self.vueltas),
                'ultima_solicitud': self.ultima_solicitud, 'ultimo_motivo': self.ultimo_motivo}


# -------------------------------------------------------------------- nodo ROS 2
ACCIONES = {'iniciar': lambda e: e.iniciar(), 'retirar_turno': lambda e: e.retirar_turno(), 'roja': lambda e: e.bandera('roja'),
            'verde': lambda e: e.bandera('verde'), 'cortar_enlace': lambda e: e.enlace(False),
            'silenciar_enlace': lambda e: e.enlace(True, mudo=True), 'restaurar_enlace': lambda e: e.enlace(True),
            'fallar_proximo': lambda e: e.fallar_proximo('rechazar'), 'no_responder_proximo': lambda e: e.fallar_proximo('no_responder')}


def _clase_nodo():
    from rclpy.node import Node
    from std_msgs.msg import Bool, String
    from std_srvs.srv import Trigger

    class EstacionFalsa(Node):
        def __init__(self):
            super().__init__('estacion_falsa')
            for nombre, defecto in PARAMETROS.items():
                self.declare_parameter(nombre, defecto)
            p = {nombre: self.get_parameter(nombre).value for nombre in PARAMETROS}
            self.p = p
            mision = cargar_mision(p['mision_yaml'] or None)
            cfg = ConfigFalsa(mision.equipo, mision.piezas, float(p['t_cambio_s']), float(p['t_liberar_s']), t_rechazo_s=float(p['t_rechazo_s']),
                              esperando_retardo_s=float(p['esperando_retardo_s']), modo=p['modo'],
                              estacion_modo=int(p['estacion_modo']) or None, turno_equipo=int(p['turno_equipo']) or None,
                              autoiniciar_s=None if p['autoiniciar_s'] < 0 else float(p['autoiniciar_s']), tanda=p['tanda'],
                              resultado_antes_de_estado=bool(p['resultado_antes_de_estado']))
            self.entorno = EntornoFalso(cfg, time.monotonic, time.time)
            self.pub = {'turno': self.create_publisher(String, p['turno_topic'], 10), 'bandera': self.create_publisher(String, p['bandera_topic'], 10),
                        'enlace': self.create_publisher(Bool, p['enlace_topic'], 10),
                        'estacion_estado': self.create_publisher(String, p['estacion_topic'], 10),
                        'resultado': self.create_publisher(String, p['resultado_topic'], 10)}
            self.estado_pub = self.create_publisher(String, '~/estado', 10)
            self._ruido, self._log = 0, None
            if p['registro_dir']:
                os.makedirs(p['registro_dir'], exist_ok=True)
                self._log = open(os.path.join(p['registro_dir'], 'mensajes_falsos.jsonl'), 'a', encoding='utf-8')
            for canal, cb in (('solicitud', self._solicitud), ('evento', self._evento), ('vuelta', self._vuelta)):
                self.create_subscription(String, p[f'{canal}_topic'], cb, 10)
            for nombre in ACCIONES:
                self.create_service(Trigger, f'~/{nombre}', lambda req, res, n=nombre: self._accion(n, res))
            self.create_timer(1.0 / p['hz'], self._tick)
            self.create_timer(1.0, self._publicar_estado)
            self.get_logger().info(f'estación falsa lista (modo {cfg.modo}, t_cambio {cfg.t_cambio_s} s). SIN turno hasta ~/iniciar')

        def _anotar(self, sentido, canal, carga):
            if self._log is not None:
                self._log.write(json.dumps({'ts': time.time(), 'sentido': sentido, 'canal': canal, 'carga': carga}, ensure_ascii=False) + '\n')
                self._log.flush()

        def _json(self, msg):
            try:
                d = json.loads(msg.data)
            except (TypeError, ValueError):
                d = None
            if not isinstance(d, dict):
                self.entorno.n['descartadas'] += 1
                self._ruido += 1
                if self._ruido % 20 == 1:
                    self.get_logger().warning(f'mensaje que no es un objeto JSON descartado (ocurrencia {self._ruido})')
                return None
            return d

        def _solicitud(self, msg):
            d = self._json(msg)
            if d is None:
                return
            self._anotar('rx', 'solicitud', d)
            motivo = self.entorno.solicitud(d.get('dock'), d)
            self.get_logger().info(f'solicitud E{d.get("dock")}: {"aceptada" if motivo is None else motivo}')

        def _evento(self, msg):
            d = self._json(msg)
            if d is not None:
                self._anotar('rx', 'evento', d)
                self.entorno.evento(d)

        def _vuelta(self, msg):
            d = self._json(msg)
            if d is not None:
                self._anotar('rx', 'vuelta', d)
                self.entorno.vuelta(d)

        def _accion(self, nombre, respuesta):
            ACCIONES[nombre](self.entorno)
            self.get_logger().info(f'orden: {nombre}')
            respuesta.success, respuesta.message = True, json.dumps(self.entorno.instantanea())
            return respuesta

        def _tick(self):
            for canal, carga in self.entorno.paso():
                self.pub[canal].publish(Bool(data=carga) if canal == 'enlace' else String(data=json.dumps(carga)))
                if canal in ('resultado', 'turno', 'bandera'):
                    self._anotar('tx', canal, carga)

        def _publicar_estado(self):
            self.estado_pub.publish(String(data=json.dumps(self.entorno.instantanea())))

    return EstacionFalsa


def main(args=None):
    import rclpy
    rclpy.init(args=args)
    nodo = _clase_nodo()()
    try:
        rclpy.spin(nodo)
    except KeyboardInterrupt:
        pass
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
