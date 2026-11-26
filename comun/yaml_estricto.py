"""Lectura estricta de archivos YAML de configuración. Falla cerrado ante cualquier cosa dudosa.

Por qué no basta `yaml.safe_load`:
- acepta claves duplicadas sin avisar y gana la última (en una configuración de seguridad es peligroso);
- `1e3` se lee como texto (YAML 1.1 exige `1.0e+3`) y `yes/no/on/off` como booleanos;
- no sabe nada de qué claves se esperan: un error de dedo en el nombre se ignora en silencio.

Aquí se rechazan las claves duplicadas, las claves que no sean texto, las claves desconocidas o faltantes
(`exigir_claves`) y cualquier clave que parezca una contraseña o un token (los secretos van por variable
de entorno, nunca en el repositorio). Los lectores de números rechazan booleanos y valores no finitos.

PyYAML se importa al usarse: si falta, el error lo dice claro (en la Jetson no está verificado que exista).
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, Iterable, Optional

PALABRAS_SECRETO = ('clave', 'password', 'contrasena', 'contraseña', 'passwd', 'token', 'secret')


class ErrorYaml(ValueError):
    pass


def _importar_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise ErrorYaml('falta PyYAML: instalar con `pip install pyyaml` o `apt install python3-yaml`') from e
    return yaml


def _cargador():
    yaml = _importar_yaml()

    class Cargador(yaml.SafeLoader):  # type: ignore[misc, name-defined]
        pass

    def mapeo(loader, nodo, deep=False):
        loader.flatten_mapping(nodo)
        vistas = set()
        for clave_nodo, _ in nodo.value:
            clave = loader.construct_object(clave_nodo, deep=True)
            if not isinstance(clave, str):
                raise ErrorYaml(f'línea {clave_nodo.start_mark.line + 1}: la clave {clave!r} no es texto '
                                '(¿"yes", "no", "on", "off" o un número sin comillas?)')
            if clave in vistas:
                raise ErrorYaml(f'línea {clave_nodo.start_mark.line + 1}: clave duplicada {clave!r}')
            vistas.add(clave)
        return yaml.SafeLoader.construct_mapping(loader, nodo, deep)

    Cargador.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapeo)
    return Cargador


def _buscar_secretos(dato: Any, ruta: str = '') -> None:
    if isinstance(dato, dict):
        for k, v in dato.items():
            bajo = k.lower()
            if any(p in bajo for p in PALABRAS_SECRETO) and not bajo.endswith('_env') and v is not None:
                raise ErrorYaml(f"'{ruta}{k}' parece un secreto: no se guardan contraseñas ni tokens en YAML; "
                                "use una variable de entorno y guarde solo su nombre en una clave '..._env'")
            _buscar_secretos(v, f'{ruta}{k}.')
    elif isinstance(dato, list):
        for i, v in enumerate(dato):
            _buscar_secretos(v, f'{ruta}[{i}].')


def cargar_mapeo(ruta: str) -> Dict[str, Any]:
    """Lee un YAML cuyo nivel superior es un mapa. Lanza ErrorYaml ante cualquier problema."""
    cargador = _cargador()
    yaml = _importar_yaml()
    try:
        with open(ruta, encoding='utf-8') as f:
            dato = yaml.load(f, Loader=cargador)  # noqa: S506 - el cargador deriva de SafeLoader
    except OSError as e:
        raise ErrorYaml(f'no se pudo leer {os.path.basename(ruta)}: {e.strerror or e}') from e
    except yaml.YAMLError as e:
        raise ErrorYaml(f'YAML inválido en {os.path.basename(ruta)}: {e}') from e
    if not isinstance(dato, dict):
        raise ErrorYaml(f'{os.path.basename(ruta)}: el nivel superior debe ser un mapa de claves')
    _buscar_secretos(dato)
    return dato


def volcar(dato: Dict[str, Any], encabezado: str = '') -> str:
    yaml = _importar_yaml()
    cuerpo = yaml.safe_dump(dato, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return (''.join(f'# {linea}\n' for linea in encabezado.splitlines()) + cuerpo) if encabezado else cuerpo


# ------------------------------------------------------------------ validación de claves y valores
def exigir_claves(d: Dict[str, Any], donde: str, requeridas: Iterable[str] = (),
                  opcionales: Iterable[str] = ()) -> None:
    requeridas, opcionales = tuple(requeridas), tuple(opcionales)
    faltan = [k for k in requeridas if k not in d]
    sobran = [k for k in d if k not in requeridas and k not in opcionales]
    if faltan:
        raise ErrorYaml(f'{donde}: faltan las claves {", ".join(faltan)}')
    if sobran:
        raise ErrorYaml(f'{donde}: claves desconocidas {", ".join(sobran)} '
                        f'(válidas: {", ".join(requeridas + opcionales)})')


def seccion(d: Dict[str, Any], clave: str, donde: str) -> Dict[str, Any]:
    v = d.get(clave)
    if not isinstance(v, dict):
        raise ErrorYaml(f'{donde}.{clave}: debe ser un bloque de claves')
    return v


def numero(d: Dict[str, Any], clave: str, donde: str, minimo: Optional[float] = None,
           maximo: Optional[float] = None, exclusivo_min: bool = False, permitir_none: bool = False
           ) -> Optional[float]:
    v = d.get(clave)
    nombre = f'{donde}.{clave}'
    if v is None:
        if permitir_none:
            return None
        raise ErrorYaml(f'{nombre}: falta el valor (null no permitido)')
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        pista = ' (YAML lee 1e3 como texto: escriba 1000.0 o 1.0e+3)' if isinstance(v, str) else ''
        raise ErrorYaml(f'{nombre}: debe ser un número, no {v!r}{pista}')
    if not math.isfinite(v):
        raise ErrorYaml(f'{nombre}: debe ser finito')
    if minimo is not None and (v <= minimo if exclusivo_min else v < minimo):
        raise ErrorYaml(f'{nombre}: {v} debe ser {">" if exclusivo_min else ">="} {minimo}')
    if maximo is not None and v > maximo:
        raise ErrorYaml(f'{nombre}: {v} debe ser <= {maximo}')
    return float(v)


def entero(d: Dict[str, Any], clave: str, donde: str, minimo: Optional[int] = None,
           maximo: Optional[int] = None) -> int:
    v = d.get(clave)
    nombre = f'{donde}.{clave}'
    if isinstance(v, bool) or not isinstance(v, int):
        raise ErrorYaml(f'{nombre}: debe ser un entero, no {v!r}')
    if (minimo is not None and v < minimo) or (maximo is not None and v > maximo):
        raise ErrorYaml(f'{nombre}: {v} fuera del rango [{minimo}, {maximo}]')
    return v


def booleano(d: Dict[str, Any], clave: str, donde: str) -> bool:
    v = d.get(clave)
    if not isinstance(v, bool):
        raise ErrorYaml(f'{donde}.{clave}: debe ser true o false, no {v!r}')
    return v


def texto(d: Dict[str, Any], clave: str, donde: str, permitir_none: bool = False) -> Optional[str]:
    v = d.get(clave)
    if v is None and permitir_none:
        return None
    if not isinstance(v, str) or not v.strip():
        raise ErrorYaml(f'{donde}.{clave}: debe ser un texto no vacío, no {v!r}')
    return v
