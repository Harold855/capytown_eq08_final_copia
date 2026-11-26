#!/usr/bin/env python3
"""Registro de las pruebas de laboratorio: una línea JSON por prueba, solo se añade, y cada línea lleva el hash de la anterior.

    python3 evidencia/registro_experimental.py agregar --tipo recta --robot eq08-roscar --operador ana --estado ok \\
        --parametro distancia_m=0.5 --resultado distancia_fisica_m=0.49 --archivo experimentos/dia01_roscar/movimientos_odom.csv
    python3 evidencia/registro_experimental.py listar | verificar | exportar --salida registro.csv

Las pruebas fallidas se registran igual (`--estado fallo`); una corrección es un registro nuevo con `--corrige ID`, nunca una
edición. Los archivos adjuntos guardan su SHA-256: si cambian después, `verificar` lo dice. La cadena de hashes detecta que se
edite, borre o reordene una línea, no que alguien con acceso al archivo lo reescriba entero. Complementa a la bitácora escrita
(`docs/bitacora_laboratorio.md`), no la sustituye.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, List, Optional, Sequence

RUTA_DEFECTO = os.path.join('experimentos', 'registro', 'registro_experimental.jsonl')
TIPOS = ('recta', 'giro', 'cuadrado', 'acople', 'calibracion_camara', 'medicion_tag', 'pit', 'mision', 'jetcobot', 'evidencia', 'otro')
ESTADOS = ('ok', 'fallo', 'parcial', 'abortado')
CLAVES = ('n', 'id', 'fecha', 'tipo', 'robot', 'operador', 'estado', 'parametros', 'resultados', 'notas', 'archivos', 'corrige', 'prev', 'sha')
CERO = '0' * 64


class ErrorRegistro(ValueError):
    pass


def _canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


def sha_archivo(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def _valor(x: Any, donde: str) -> Any:
    if isinstance(x, float) and not math.isfinite(x):
        raise ErrorRegistro(f'{donde}: valor no finito')
    if isinstance(x, dict):
        return {str(k): _valor(v, f'{donde}.{k}') for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_valor(v, donde) for v in x]
    if x is None or isinstance(x, (bool, int, float, str)):
        return x
    raise ErrorRegistro(f'{donde}: tipo no admitido ({type(x).__name__})')


class RegistroExperimental:
    def __init__(self, ruta: str = RUTA_DEFECTO, reloj: Callable[[], float] = time.time) -> None:
        self.ruta, self._reloj = ruta, reloj

    def leer(self) -> List[dict]:
        """Registros en orden. Lanza ErrorRegistro con la primera línea rota (edición, borrado, reordenamiento o corte)."""
        if not os.path.exists(self.ruta):
            return []
        with open(self.ruta, encoding='utf-8') as f:
            texto = f.read()
        if texto and not texto.endswith('\n'):
            raise ErrorRegistro(f'{self.ruta}: la última línea está incompleta (corte a mitad de escritura): revísala antes de seguir')
        out, prev = [], CERO
        for i, linea in enumerate(texto.split('\n')[:-1], 1):
            try:
                r = json.loads(linea)
            except ValueError as e:
                raise ErrorRegistro(f'línea {i}: JSON inválido ({e})') from e
            if not isinstance(r, dict) or set(r) != set(CLAVES):
                raise ErrorRegistro(f'línea {i}: no tiene exactamente las claves del registro')
            if r['n'] != i or r['id'] != f'E{i:04d}':
                raise ErrorRegistro(f'línea {i}: numeración rota (¿se borró o reordenó una línea?)')
            if r['prev'] != prev:
                raise ErrorRegistro(f'línea {i}: la cadena de hashes no coincide (¿se editó o borró la línea anterior?)')
            if r['sha'] != _sha(_canon({k: v for k, v in r.items() if k != 'sha'})):
                raise ErrorRegistro(f'línea {i}: el contenido no coincide con su hash (editada)')
            out.append(r)
            prev = r['sha']
        return out

    def agregar(self, tipo: str, robot: str, operador: str, estado: str, parametros: Optional[dict] = None,
                resultados: Optional[dict] = None, notas: str = '', archivos: Iterable[str] = (), corrige: Optional[str] = None,
                base: Optional[str] = None) -> dict:
        if tipo not in TIPOS:
            raise ErrorRegistro(f'tipo debe ser uno de {TIPOS}')
        if estado not in ESTADOS:
            raise ErrorRegistro(f'estado debe ser uno de {ESTADOS}')
        for nombre, v in (('robot', robot), ('operador', operador)):
            if not isinstance(v, str) or not v.strip():
                raise ErrorRegistro(f'{nombre} es obligatorio')
        previos = self.leer()
        if corrige is not None and corrige not in {r['id'] for r in previos}:
            raise ErrorRegistro(f'corrige: no existe el registro {corrige!r}')
        adjuntos = []
        for a in archivos:
            ruta = os.path.join(base, a) if base and not os.path.isabs(a) else a
            if not os.path.isfile(ruta):
                raise ErrorRegistro(f'archivo adjunto inexistente: {a}')
            adjuntos.append({'ruta': a, 'sha256': sha_archivo(ruta), 'bytes': os.path.getsize(ruta)})
        n = len(previos) + 1
        r = {'n': n, 'id': f'E{n:04d}', 'fecha': datetime.fromtimestamp(self._reloj(), timezone.utc).isoformat(timespec='seconds'),
             'tipo': tipo, 'robot': robot.strip(), 'operador': operador.strip(), 'estado': estado,
             'parametros': _valor(parametros or {}, 'parametros'), 'resultados': _valor(resultados or {}, 'resultados'),
             'notas': str(notas), 'archivos': adjuntos, 'corrige': corrige, 'prev': previos[-1]['sha'] if previos else CERO}
        r['sha'] = _sha(_canon(r))
        os.makedirs(os.path.dirname(os.path.abspath(self.ruta)), exist_ok=True)
        with open(self.ruta, 'a', encoding='utf-8') as f:
            f.write(_canon(r) + '\n')
            f.flush()
            os.fsync(f.fileno())
        return r

    def verificar(self, base: Optional[str] = None) -> List[str]:
        """Lista de problemas (vacía = íntegro): cadena de hashes y archivos adjuntos (existen y no cambiaron)."""
        try:
            registros = self.leer()
        except ErrorRegistro as e:
            return [str(e)]
        problemas = []
        ids = set()
        for r in registros:
            if r['corrige'] is not None and r['corrige'] not in ids:
                problemas.append(f'{r["id"]}: corrige un registro que no es anterior ({r["corrige"]})')
            ids.add(r['id'])
            for a in r['archivos']:
                ruta = os.path.join(base, a['ruta']) if base and not os.path.isabs(a['ruta']) else a['ruta']
                if not os.path.isfile(ruta):
                    problemas.append(f'{r["id"]}: falta el archivo adjunto {a["ruta"]}')
                elif sha_archivo(ruta) != a['sha256']:
                    problemas.append(f'{r["id"]}: el archivo {a["ruta"]} cambió después de registrarse')
        return problemas

    def exportar_csv(self, salida: str) -> int:
        regs = self.leer()
        with open(salida, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['id', 'fecha', 'tipo', 'robot', 'operador', 'estado', 'parametros', 'resultados', 'archivos', 'corrige', 'notas'])
            for r in regs:
                w.writerow([r['id'], r['fecha'], r['tipo'], r['robot'], r['operador'], r['estado'], _canon(r['parametros']),
                            _canon(r['resultados']), ';'.join(a['ruta'] for a in r['archivos']), r['corrige'] or '', r['notas']])
        return len(regs)


def verificar_ruta(ruta: str, base: Optional[str] = None) -> List[str]:
    return RegistroExperimental(ruta).verificar(base)


def _par(texto: str) -> tuple:
    if '=' not in texto:
        raise argparse.ArgumentTypeError(f'se esperaba clave=valor, no {texto!r}')
    k, v = texto.split('=', 1)
    if v.lower() in ('true', 'false'):
        return k, v.lower() == 'true'
    try:
        x = float(v)
        return k, x if math.isfinite(x) else v
    except ValueError:
        return k, v


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--ruta', default=RUTA_DEFECTO)
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('agregar')
    a.add_argument('--tipo', required=True, choices=TIPOS)
    a.add_argument('--robot', required=True)
    a.add_argument('--operador', required=True)
    a.add_argument('--estado', required=True, choices=ESTADOS)
    a.add_argument('--parametro', action='append', type=_par, default=[])
    a.add_argument('--resultado', action='append', type=_par, default=[])
    a.add_argument('--archivo', action='append', default=[])
    a.add_argument('--notas', default='')
    a.add_argument('--corrige')
    sub.add_parser('listar')
    sub.add_parser('verificar')
    e = sub.add_parser('exportar')
    e.add_argument('--salida', required=True)
    args = p.parse_args(argv)
    reg = RegistroExperimental(args.ruta)
    try:
        if args.cmd == 'agregar':
            r = reg.agregar(args.tipo, args.robot, args.operador, args.estado, dict(args.parametro), dict(args.resultado), args.notas,
                            args.archivo, args.corrige)
            print(f'{r["id"]} registrado ({r["tipo"]}, {r["estado"]})')
        elif args.cmd == 'listar':
            for r in reg.leer():
                print(f'{r["id"]}  {r["fecha"]}  {r["tipo"]:<18} {r["estado"]:<9} {r["robot"]}  {r["notas"][:50]}')
        elif args.cmd == 'verificar':
            problemas = reg.verificar()
            print('\n'.join(problemas) if problemas else f'registro íntegro ({len(reg.leer())} pruebas)')
            return 1 if problemas else 0
        else:
            print(f'{reg.exportar_csv(args.salida)} registros exportados a {args.salida}')
    except (ErrorRegistro, OSError) as ex:
        print(f'ERROR: {ex}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
