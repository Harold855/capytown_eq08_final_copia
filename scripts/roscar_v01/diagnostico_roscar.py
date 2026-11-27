#!/usr/bin/env python3
"""Diagnóstico de SOLO LECTURA del ROSCar, con veredicto OK / AVISO / FALLA.

Complementa a preflight.sh (que vuelca información sin juzgarla). No publica en ningún tópico, no
cambia parámetros y no llama servicios: solo escucha. Revisa lo que pide la sección 1.1 de la
división: entorno ROS, nodos, /cmd_vel, odometría (publicadores y frecuencia), IMU, LiDAR, batería,
calibración activa de odom_corrector, cámara, disco y hora.

Uso (en el Pi5, dentro del contenedor con ROS 2 cargado y el bringup en marcha):
    python3 scripts/roscar_v01/diagnostico_roscar.py
    python3 scripts/roscar_v01/diagnostico_roscar.py --ventana 8 --r-esperado 0.03145 --b-eff-esperado 0.2138
    python3 scripts/roscar_v01/diagnostico_roscar.py --simular ok      # sin robot: prueba el script
    python3 scripts/roscar_v01/diagnostico_roscar.py --simular mal
Código de salida: 1 si hay alguna FALLA.
"""
import argparse
import glob
import json
import platform
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

DOMINIO_GRANPRIX = '8'
R0, B0 = 0.0325, 0.24  # valores que asume el firmware (r0, b0); no se tocan
# Conjuntos de parámetros vistos en RC-0 y RC-1, para saber de dónde viene la calibración activa.
CALIBRACIONES_CONOCIDAS = [
    (0.03145, 0.2138, 'ROSCar 4 calibrado en RC-1 (solo vale para ese robot)', 'INFO'),
    (0.0311, 0.2259, 'valores iniciales del docente en RC-0', 'AVISO'),
    (0.031256, 0.2450, 'copia instalada de capytown_esan, editada por otro grupo (no usar)', 'AVISO'),
    (0.0316, 0.2332, 'calibración de otro grupo encontrada en el robot en RC-1 (no usar)', 'AVISO'),
    (0.0230, 0.1350, 'prueba de sensibilidad de RC-0 / YAML equivocado: NO es una calibración', 'FALLA'),
]
TOPICOS_ESCUCHA = ['/odom', '/odom_raw', '/imu', '/battery', '/battery_state', '/scan']


# --------------------------------------------------------------------------- lógica pura
def parsear_param(texto):
    """Extrae el número de la salida de `ros2 param get`. Devuelve None si no hay."""
    m = re.search(r'value is:\s*(-?[0-9.]+(?:e-?\d+)?)', texto or '')
    return float(m.group(1)) if m else None


def estadisticas(tiempos, ventana):
    """Frecuencia y periodo máximo a partir de instantes de llegada (s)."""
    n = len(tiempos)
    if n < 2:
        return {'n': n, 'hz': 0.0 if n == 0 else None, 'periodo_max_s': None}
    t = sorted(tiempos)
    return {'n': n, 'hz': (n - 1) / (t[-1] - t[0]) if t[-1] > t[0] else None,
            'periodo_max_s': max(b - a for a, b in zip(t, t[1:]))}


def factores(r, b_eff):
    """k_lin y k_ang que aplica odom_corrector (los reporta su log de arranque)."""
    return r / R0, (r / R0) * (B0 / b_eff)


def evaluar(d):
    """Devuelve [(nivel, mensaje)] con nivel INFO, OK, AVISO o FALLA. Función pura."""
    r = []
    add = lambda n, m: r.append((n, m))
    env = d.get('env', {})
    dom = env.get('ROS_DOMAIN_ID')
    add('OK' if dom == DOMINIO_GRANPRIX else 'AVISO',
        f'ROS_DOMAIN_ID={dom or "sin definir"}' + ('' if dom == DOMINIO_GRANPRIX else f' (el GranPrix usa {DOMINIO_GRANPRIX} para eq08)'))
    add('OK' if env.get('ROS_LOCALHOST_ONLY') == '1' else 'AVISO',
        f'ROS_LOCALHOST_ONLY={env.get("ROS_LOCALHOST_ONLY") or "sin definir"} (el GranPrix usa 1)')

    nodos = d.get('nodos', [])
    add('OK' if '/YB_Car_Node' in nodos else 'FALLA',
        'placa conectada (/YB_Car_Node)' if '/YB_Car_Node' in nodos else
        f'no aparece /YB_Car_Node en el dominio {dom}: agente micro-ROS o placa sin conexión, o dominio distinto')
    n_corr = nodos.count('/odom_corrector')
    if n_corr == 1:
        add('OK', 'un solo /odom_corrector')
    elif n_corr == 0:
        add('AVISO', '/odom_corrector no corre: /odom puede no existir o ser el crudo del firmware')
    else:
        add('FALLA', f'hay {n_corr} /odom_corrector: dos correctores publicando /odom (ocurrió en RC-1)')
    otros = [n for n in nodos if n.lstrip('/').startswith(('teleop', 'secuencia', 'cuadrado', 'calibrate'))]
    if otros:
        add('AVISO', 'nodos de movimiento abiertos: ' + ', '.join(otros))

    top = d.get('topicos', {})
    cmd = top.get('/cmd_vel', [])
    if 'geometry_msgs/msg/Twist' not in cmd:
        add('FALLA', f'/cmd_vel con tipo Twist no detectado (tipos: {cmd or "ninguno"})')
    if d.get('suscriptores_cmd_vel', 0) < 1:
        add('FALLA', 'nadie escucha /cmd_vel: el robot no se movería')
    else:
        add('OK', f'/cmd_vel tiene {d["suscriptores_cmd_vel"]} suscriptor(es) (driver de la placa)')
    pubs = d.get('publicadores_cmd_vel', [])
    add('OK' if not pubs else 'AVISO',
        'nadie publica en /cmd_vel' if not pubs else 'ya hay publicadores en /cmd_vel: ' + ', '.join(pubs))

    if 'nav_msgs/msg/Odometry' not in top.get('/odom', []):
        add('FALLA', '/odom (nav_msgs/Odometry) no existe')
    npo = d.get('publicadores_odom', 0)
    add('OK' if npo == 1 else 'FALLA', f'/odom tiene {npo} publicador(es)' + ('' if npo == 1 else ' (debe ser 1)'))

    fr = d.get('frecuencias', {})
    for t, minimo, nivel_sin_datos in (('/odom', 5.0, 'FALLA'), ('/imu', 5.0, 'AVISO'), ('/scan', 2.0, 'AVISO')):
        f = fr.get(t)
        if t == '/scan' and t not in top:
            add('INFO', 'sin /scan (LiDAR no es obligatorio)')
            continue
        if not f or not f['n']:
            add(nivel_sin_datos, f'{t}: no llegaron mensajes en la ventana de medición')
        elif f['hz'] is None:
            add('AVISO', f'{t}: llegó un solo mensaje; no se puede medir la frecuencia')
        else:
            add('OK' if f['hz'] >= minimo else 'AVISO',
                f'{t}: {f["hz"]:.1f} Hz (periodo máximo {f["periodo_max_s"]*1000:.0f} ms)'
                + ('' if f['hz'] >= minimo else f' — por debajo de {minimo:g} Hz'))
    ult = d.get('ultimo', {}).get('/odom')
    if ult and (abs(ult.get('vx', 0)) > 0.01 or abs(ult.get('wz', 0)) > 0.02):
        add('AVISO', f'la odometría reporta movimiento (vx={ult.get("vx")}, wz={ult.get("wz")}): esperar a que se detenga')

    bat = [t for t in ('/battery', '/battery_state') if t in top]
    if not bat:
        add('AVISO', 'no hay tópico de batería (/battery ni /battery_state)')
    else:
        for t in bat:
            add('INFO', f'{t}: tipo {top[t][0] if top[t] else "?"}, último valor {d.get("ultimo", {}).get(t, "sin lectura")}')
        if '/battery_state' not in top:
            add('AVISO', 'el bag oficial pide /battery_state y el robot publica /battery: hará falta un adaptador')
    if '/servo_s1' in top or '/servo_s2' in top:
        add('INFO', 'hay /servo_s1 y /servo_s2: si mueven la cámara, fijarlos en cada arranque (la calibración extrínseca depende de ello)')

    p = d.get('params', {})
    rr, bb = p.get('wheel_radius'), p.get('wheel_separation')
    if rr is None or bb is None:
        add('AVISO', 'no se pudieron leer wheel_radius y wheel_separation de /odom_corrector')
    else:
        kl, ka = factores(rr, bb)
        add('INFO', f'calibración activa: r={rr}, b_eff={bb} → k_lin={kl:.4f}, k_ang={ka:.4f} '
                    f'(firmware: r0={p.get("firmware_wheel_radius", R0)}, b0={p.get("firmware_wheel_separation", B0)})')
        for cr, cb, etiqueta, nivel in CALIBRACIONES_CONOCIDAS:
            if abs(rr - cr) < 1e-6 and abs(bb - cb) < 1e-6:
                add(nivel, 'esos valores coinciden con: ' + etiqueta)
                break
        else:
            add('INFO', 'valores de calibración desconocidos (no coinciden con ninguno de RC-0 ni RC-1)')
        esp = d.get('esperado', {})
        for nombre, real, valor in (('r', rr, esp.get('r')), ('b_eff', bb, esp.get('b_eff'))):
            if valor is not None and abs(real - valor) > 1e-6:
                add('FALLA', f'{nombre} activo ({real}) distinto del esperado ({valor})')

    dev = d.get('dispositivos', {})
    add('OK' if dev.get('video') else 'AVISO',
        'cámaras: ' + ', '.join(dev['video']) if dev.get('video') else 'no hay /dev/video*: la cámara es obligatoria para el pit')
    if d.get('disco_libre_mb') is not None:
        add('OK' if d['disco_libre_mb'] >= 1000 else 'AVISO', f'disco libre: {d["disco_libre_mb"]:.0f} MB' +
            ('' if d['disco_libre_mb'] >= 1000 else ' (grabar bags y videos necesita más)'))
    fecha = d.get('fecha', '')
    if fecha and int(fecha[:4]) < 2026:
        add('AVISO', f'la hora del sistema parece mal ({fecha}): el Pi5 no guarda la hora; corregirla antes de grabar')
    else:
        add('INFO', f'hora del sistema: {fecha} (verificar contra la hora real)')
    return r


# --------------------------------------------------------------------------- recolección
def recolectar(ventana, esperado):
    """Escucha el grafo ROS 2 sin publicar. Requiere rclpy (Pi5 / contenedor con ROS 2 cargado)."""
    import os
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rosidl_runtime_py.utilities import get_message
    rclpy.init()
    nodo = rclpy.create_node('diagnostico_roscar')
    propio = nodo.get_name()
    try:
        fin = time.monotonic() + 2.0  # descubrimiento
        while time.monotonic() < fin:
            rclpy.spin_once(nodo, timeout_sec=0.1)
        nodos = sorted(f'{ns.rstrip("/")}/{n}' for n, ns in nodo.get_node_names_and_namespaces() if n != propio)
        topicos = {t: list(tipos) for t, tipos in nodo.get_topic_names_and_types()}
        pubs_cmd = [f'{i.node_namespace.rstrip("/")}/{i.node_name}' for i in nodo.get_publishers_info_by_topic('/cmd_vel')]
        llegadas, ultimo, subs = {}, {}, []

        def resumen(topico, msg):
            if hasattr(msg, 'twist') and hasattr(msg.twist, 'twist'):
                return {'vx': msg.twist.twist.linear.x, 'wz': msg.twist.twist.angular.z}
            if hasattr(msg, 'voltage'):
                return msg.voltage
            return getattr(msg, 'data', None)

        for t in TOPICOS_ESCUCHA:
            if t in topicos and topicos[t]:
                llegadas[t] = []
                def cb(msg, t=t):
                    llegadas[t].append(time.monotonic())
                    if t != '/scan' and t != '/imu':
                        ultimo[t] = resumen(t, msg)
                subs.append(nodo.create_subscription(get_message(topicos[t][0]), t, cb, qos_profile_sensor_data))
        fin = time.monotonic() + ventana
        while time.monotonic() < fin:
            rclpy.spin_once(nodo, timeout_sec=0.05)
        datos = {
            'env': {k: os.environ.get(k) for k in ('ROS_DOMAIN_ID', 'ROS_LOCALHOST_ONLY', 'ROS_DISTRO')},
            'nodos': nodos, 'topicos': topicos,
            'suscriptores_cmd_vel': nodo.count_subscribers('/cmd_vel'),
            'publicadores_cmd_vel': pubs_cmd,
            'publicadores_odom': nodo.count_publishers('/odom'),
            'frecuencias': {t: estadisticas(v, ventana) for t, v in llegadas.items()},
            'ultimo': ultimo,
        }
    finally:
        nodo.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    params = {}
    for p in ('wheel_radius', 'wheel_separation', 'firmware_wheel_radius', 'firmware_wheel_separation'):
        try:
            salida = subprocess.run(['ros2', 'param', 'get', '/odom_corrector', p], capture_output=True, text=True, timeout=6)
            v = parsear_param(salida.stdout)
        except (subprocess.TimeoutExpired, OSError):
            v = None
        if v is not None:
            params[p] = v
    datos['params'] = params
    datos['esperado'] = esperado
    datos.update(_sistema())
    return datos


def _sistema():
    return {'dispositivos': {'video': sorted(glob.glob('/dev/video*')),
                             'serial': sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))},
            'disco_libre_mb': shutil.disk_usage('.').free / 1e6,
            'fecha': datetime.now().isoformat(timespec='seconds')}


def simulado(escenario, esperado):
    ok = {
        'env': {'ROS_DOMAIN_ID': '8', 'ROS_LOCALHOST_ONLY': '1', 'ROS_DISTRO': 'humble'},
        'nodos': ['/YB_Car_Node', '/odom_corrector'],
        'topicos': {'/cmd_vel': ['geometry_msgs/msg/Twist'], '/odom': ['nav_msgs/msg/Odometry'],
                    '/odom_raw': ['nav_msgs/msg/Odometry'], '/imu': ['sensor_msgs/msg/Imu'],
                    '/scan': ['sensor_msgs/msg/LaserScan'], '/battery': ['std_msgs/msg/UInt16']},
        'suscriptores_cmd_vel': 1, 'publicadores_cmd_vel': [], 'publicadores_odom': 1,
        'frecuencias': {'/odom': {'n': 56, 'hz': 11.1, 'periodo_max_s': 0.15}, '/imu': {'n': 120, 'hz': 24.0, 'periodo_max_s': 0.08},
                        '/scan': {'n': 9, 'hz': 9.8, 'periodo_max_s': 0.2}},
        'ultimo': {'/odom': {'vx': 0.0, 'wz': 0.0}, '/battery': 82},
        'params': {'wheel_radius': 0.03145, 'wheel_separation': 0.2138, 'firmware_wheel_radius': 0.0325,
                   'firmware_wheel_separation': 0.24},
        'esperado': esperado,
    }
    if escenario == 'mal':
        ok['env'] = {'ROS_DOMAIN_ID': '20', 'ROS_LOCALHOST_ONLY': None, 'ROS_DISTRO': 'humble'}
        ok['nodos'] = ['/odom_corrector', '/odom_corrector', '/teleop_key']
        ok['suscriptores_cmd_vel'] = 0
        ok['publicadores_cmd_vel'] = ['/teleop_key']
        ok['publicadores_odom'] = 2
        ok['frecuencias']['/odom'] = {'n': 0, 'hz': 0.0, 'periodo_max_s': None}
        ok['params'] = {'wheel_radius': 0.023, 'wheel_separation': 0.135}
    ok.update(_sistema())
    return ok


# --------------------------------------------------------------------------- salida
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ventana', type=float, default=5.0, help='segundos escuchando los tópicos (2 a 30)')
    p.add_argument('--r-esperado', type=float, dest='r', help='wheel_radius que debería estar activo')
    p.add_argument('--b-eff-esperado', type=float, dest='b', help='wheel_separation que debería estar activo')
    p.add_argument('--simular', choices=['ok', 'mal'], help='sin robot: datos de ejemplo')
    p.add_argument('--salida', type=Path, default=None)
    a = p.parse_args(argv)
    if not 2.0 <= a.ventana <= 30.0:
        p.error('--ventana debe estar entre 2 y 30')
    esperado = {'r': a.r, 'b_eff': a.b}
    if a.simular:
        datos = simulado(a.simular, esperado)
    else:
        try:
            datos = recolectar(a.ventana, esperado)
        except ImportError as e:
            print(f'ERROR: falta {e.name}. Ejecutar dentro del contenedor con ROS 2 cargado '
                  '(source /opt/ros/humble/setup.bash).', file=__import__('sys').stderr)
            return 2
    checks = evaluar(datos)
    ahora = datetime.now()
    lineas = [f'=== Diagnóstico ROSCar (solo lectura) {ahora.isoformat(timespec="seconds")} ===',
              f'host={platform.node()} python={platform.python_version()} ventana={a.ventana:g}s'
              + (f' SIMULADO({a.simular})' if a.simular else '')]
    lineas += [f'{n:6s} {m}' for n, m in checks]
    fallas = sum(n == 'FALLA' for n, _ in checks)
    avisos = sum(n == 'AVISO' for n, _ in checks)
    lineas.append(f'=== {fallas} falla(s), {avisos} aviso(s) ===')
    texto = '\n'.join(lineas)
    print(texto)
    salida = a.salida or Path('experimentos/dia01_roscar') / f'diagnostico_roscar_{ahora:%Y%m%d_%H%M%S}.txt'
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto + '\n' + json.dumps({'datos': datos, 'checks': checks}, default=str) + '\n')
    print(f'Guardado en {salida}')
    return 1 if fallas else 0


if __name__ == '__main__':
    raise SystemExit(main())
