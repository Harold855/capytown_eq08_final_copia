"""Sustituto mínimo de rclpy y de los mensajes para probar el cableado de los nodos sin ROS.

Demuestra lo que el autor cree que hace la API; NO demuestra que la API real esté bien usada.
"""
import sys
import types


class Ns:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def vector(*campos):
    return Ns(**{c: 0.0 for c in campos})


class TransformStamped:
    def __init__(self):
        self.header = Ns(stamp=None, frame_id='')
        self.child_frame_id = ''
        self.transform = Ns(translation=vector('x', 'y', 'z'), rotation=vector('x', 'y', 'z', 'w'))


class PoseStamped:
    def __init__(self):
        self.header = Ns(stamp=None, frame_id='')
        self.pose = Ns(position=vector('x', 'y', 'z'), orientation=vector('x', 'y', 'z', 'w'))


class Mensaje:
    def __init__(self, data=None):
        self.data = data


class Registro:
    def __init__(self):
        self.info, self.advertencias, self.errores = [], [], []


class Logger:
    def __init__(self, reg):
        self.reg = reg

    def info(self, t):
        self.reg.info.append(t)

    def warning(self, t):
        self.reg.advertencias.append(t)

    def error(self, t):
        self.reg.errores.append(t)


class Publicador:
    def __init__(self):
        self.enviados = []
        self.suscriptores = 1

    def publish(self, m):
        self.enviados.append(m)

    def get_subscription_count(self):
        return self.suscriptores


class Futuro:
    def __init__(self):
        self.listo, self.valor = False, None

    def done(self):
        return self.listo

    def result(self):
        return self.valor


class Cliente:
    def __init__(self):
        self.disponible, self.llamadas = True, []

    def service_is_ready(self):
        return self.disponible

    def call_async(self, peticion):
        f = Futuro()
        self.llamadas.append(f)
        return f


class Twist:
    def __init__(self):
        self.linear, self.angular = vector('x', 'y', 'z'), vector('x', 'y', 'z')


class Reloj:
    def __init__(self, nodo):
        self.nodo = nodo

    def now(self):
        ns = self.nodo.ns
        return Ns(nanoseconds=ns, to_msg=lambda: Ns(sec=ns // 10 ** 9, nanosec=ns % 10 ** 9))


class Node:
    sobrescribe = {}

    def __init__(self, nombre):
        self.nombre, self._params, self.subs, self.servicios, self.timers, self.pubs = nombre, {}, [], [], [], []
        self.ns, self.reg = 0, Registro()

    def declare_parameter(self, n, d):
        self._params[n] = Ns(value=Node.sobrescribe.get(n, d))

    def get_parameter(self, n):
        return self._params[n]

    def create_subscription(self, tipo, topico, cb, qos):
        self.subs.append((tipo, topico, cb))

    def create_service(self, tipo, nombre, cb):
        self.servicios.append((tipo, nombre, cb))

    def create_timer(self, periodo, cb):
        self.timers.append((periodo, cb))

    def create_client(self, tipo, nombre):
        c = Cliente()
        self.clientes = getattr(self, 'clientes', []) + [(tipo, nombre, c)]
        return c

    def create_publisher(self, tipo, topico, qos):
        p = Publicador()
        self.pubs.append((tipo, topico, p))
        return p

    def get_clock(self):
        return Reloj(self)

    def get_logger(self):
        return Logger(self.reg)

    def get_name(self):
        return self.nombre

    def get_namespace(self):
        return '/'

    def get_publishers_info_by_topic(self, topico):
        return []

    def destroy_node(self):
        pass

    def publicador(self, topico):
        return next(p for _, t, p in self.pubs if t == topico)

    def callback(self, topico):
        return next(cb for _, t, cb in self.subs if t == topico)


class Difusor:
    def __init__(self, nodo):
        self.enviados = []

    def sendTransform(self, t):
        self.enviados.append(t)


NOMBRES = ('rclpy', 'rclpy.node', 'rclpy.qos', 'rclpy.signals', 'geometry_msgs', 'geometry_msgs.msg', 'nav_msgs', 'nav_msgs.msg', 'std_msgs',
           'std_msgs.msg', 'std_srvs', 'std_srvs.srv', 'sensor_msgs', 'sensor_msgs.msg', 'tf2_ros')


def instalar():
    def modulo(nombre, **atributos):
        m = types.ModuleType(nombre)
        m.__dict__.update(atributos)
        sys.modules[nombre] = m
    modulo('rclpy', init=lambda args=None, **kw: None, spin=lambda n: None, spin_once=lambda n, timeout_sec=0: None,
           ok=lambda: True, shutdown=lambda: None)
    modulo('rclpy.signals', SignalHandlerOptions=Ns(NO=0))
    modulo('rclpy.node', Node=Node)
    modulo('rclpy.qos', qos_profile_sensor_data='SENSOR')
    modulo('geometry_msgs')
    modulo('geometry_msgs.msg', PoseStamped=PoseStamped, TransformStamped=TransformStamped, Twist=Twist)
    modulo('nav_msgs')
    modulo('nav_msgs.msg', Odometry=type('Odometry', (), {}))
    modulo('sensor_msgs')
    modulo('sensor_msgs.msg', Image=type('Image', (), {}))
    modulo('std_msgs')
    modulo('std_msgs.msg', Int32=type('Int32', (Mensaje,), {}), String=type('String', (Mensaje,), {}),
           Bool=type('Bool', (Mensaje,), {}))
    modulo('std_srvs')
    modulo('std_srvs.srv', Trigger=type('Trigger', (), {'Request': type('Request', (), {})}))
    modulo('tf2_ros', TransformBroadcaster=Difusor)


def desinstalar(*modulos_nodo):
    for m in NOMBRES + tuple(modulos_nodo):
        sys.modules.pop(m, None)
    Node.sobrescribe = {}
