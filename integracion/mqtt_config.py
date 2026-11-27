"""Carga y validación de `integracion/configuracion/mqtt.yaml`. Compatible con Python 3.8.

Falla cerrado (ErrorYaml). No guarda ni acepta contraseñas: solo el nombre de la variable de entorno.
`ConfigMqtt.topico(nombre, estacion=None)` arma el tópico concreto del equipo.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, Optional

from comun import yaml_estricto as ye

VERSION = 1
PUBLICADORES = ('race_control', 'estacion', 'carrito')
_MARCAS = re.compile(r'\{([a-z]+)\}')
DIRECTORIO_DEFECTO = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'configuracion')


@dataclass(frozen=True)
class Topico:
    plantilla: str
    publica: str
    qos: int
    retenido: bool


@dataclass(frozen=True)
class ConfigMqtt:
    equipo: int
    host: str
    puerto: int
    usuario: str
    clave_env: str
    telemetria_max_hz: float
    offline_tras_s: float
    topicos: Dict[str, Topico]

    def topico(self, nombre: str, estacion: Optional[int] = None) -> str:
        t = self.topicos[nombre]
        usa_n = '{n}' in t.plantilla
        if usa_n and estacion not in (1, 2, 3, 4):
            raise ValueError(f'el tópico {nombre} necesita estacion de 1 a 4')
        if not usa_n and estacion is not None:
            raise ValueError(f'el tópico {nombre} no lleva estación')
        return t.plantilla.format(eq=f'{self.equipo:02d}', n=estacion)

    def clave(self, entorno: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Contraseña tomada de la variable de entorno indicada (None si no está definida)."""
        return (os.environ if entorno is None else entorno).get(self.clave_env)


def cargar_mqtt(ruta: str = os.path.join(DIRECTORIO_DEFECTO, 'mqtt.yaml')) -> ConfigMqtt:
    d = ye.cargar_mapeo(ruta)
    ye.exigir_claves(d, 'mqtt', ('version', 'equipo', 'broker', 'tiempos', 'topicos'))
    if d['version'] != VERSION or isinstance(d['version'], bool):
        raise ye.ErrorYaml('mqtt: versión desconocida')
    equipo = ye.entero(d, 'equipo', 'mqtt', 1, 99)

    b = ye.seccion(d, 'broker', 'mqtt')
    ye.exigir_claves(b, 'mqtt.broker', ('host', 'puerto', 'usuario', 'clave_env'))
    host = ye.texto(b, 'host', 'mqtt.broker')
    if '://' in host or '/' in host or ' ' in host:  # type: ignore[operator]
        raise ye.ErrorYaml('mqtt.broker.host: solo el nombre o la IP, sin esquema ni ruta')
    clave_env = ye.texto(b, 'clave_env', 'mqtt.broker')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', clave_env):  # type: ignore[arg-type]
        raise ye.ErrorYaml('mqtt.broker.clave_env: debe ser el NOMBRE de una variable de entorno (MAYÚSCULAS), '
                           'no la contraseña')

    t = ye.seccion(d, 'tiempos', 'mqtt')
    ye.exigir_claves(t, 'mqtt.tiempos', ('telemetria_max_hz', 'offline_tras_s'))

    topicos: Dict[str, Topico] = {}
    tabla = ye.seccion(d, 'topicos', 'mqtt')
    if not tabla:
        raise ye.ErrorYaml('mqtt.topicos: no puede estar vacío')
    for nombre, fila in tabla.items():
        donde = f'mqtt.topicos.{nombre}'
        if not isinstance(fila, dict):
            raise ye.ErrorYaml(f'{donde}: debe ser un bloque de claves')
        ye.exigir_claves(fila, donde, ('plantilla', 'publica', 'qos', 'retenido'))
        plantilla = ye.texto(fila, 'plantilla', donde)
        marcas = set(_MARCAS.findall(plantilla))  # type: ignore[arg-type]
        if not marcas <= {'eq', 'n'}:
            raise ye.ErrorYaml(f'{donde}.plantilla: solo se admiten {{eq}} y {{n}}')
        if not plantilla.startswith('granprix/') or '+' in plantilla or '#' in plantilla:  # type: ignore[union-attr]
            raise ye.ErrorYaml(f'{donde}.plantilla: debe empezar por granprix/ y no llevar comodines')
        publica = ye.texto(fila, 'publica', donde)
        if publica not in PUBLICADORES:
            raise ye.ErrorYaml(f'{donde}.publica: debe ser uno de {", ".join(PUBLICADORES)}')
        topicos[nombre] = Topico(plantilla, publica, ye.entero(fila, 'qos', donde, 0, 2),  # type: ignore[arg-type]
                                 ye.booleano(fila, 'retenido', donde))
    return ConfigMqtt(
        equipo=equipo, host=host, puerto=ye.entero(b, 'puerto', 'mqtt.broker', 1, 65535),  # type: ignore[arg-type]
        usuario=ye.texto(b, 'usuario', 'mqtt.broker'), clave_env=clave_env,  # type: ignore[arg-type]
        telemetria_max_hz=ye.numero(t, 'telemetria_max_hz', 'mqtt.tiempos', 0, 5.0, exclusivo_min=True),  # type: ignore[arg-type]
        offline_tras_s=ye.numero(t, 'offline_tras_s', 'mqtt.tiempos', 0, exclusivo_min=True),  # type: ignore[arg-type]
        topicos=topicos)
