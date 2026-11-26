"""Barrido de alpha del estimador de escalas con el modelo del simulador oficial (simulacion/modelo_granprix.py).

Es SIMULACIÓN: el robot ideal del modelo gira `1+sa/100` y avanza `1+sd/100` veces lo comandado, con el ruido
del HTML (tag 0.5 cm por coordenada y 0.4° de rumbo, 0.5 % de ruido de distancia, 0.4° de ruido de giro).
Los valores por defecto (giro +9 %, distancia +1 %) son un ejemplo en el rango que midió RC-1, no una
medición del carrito de este reto. Uso:  python3 simulacion/barrido_alpha.py [semillas] [vueltas]
"""
from __future__ import annotations

import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulacion.modelo_granprix import PARAMS_DEFECTO, simular  # noqa: E402

ALPHAS = (0.10, 0.20, 0.35, 0.50, 0.70)


def pits_hasta(serie, real, tol):
    """Índice (1-based) del primer pit a partir del cual la serie queda dentro de `tol` del valor real."""
    for i in range(len(serie)):
        if all(abs(x - real) <= tol for x in serie[i:]):
            return i + 1
    return len(serie) + 1


def correr(sd=1.0, sa=9.0, semillas=200, vueltas=4, tol=0.015):
    cd_real, ca_real = 1 + sd / 100, 1 + sa / 100
    filas = []
    for alpha in ALPHAS:
        p = dict(PARAMS_DEFECTO, sd=sd, sa=sa, alpha=alpha)
        err_final, err_cd, err_ca, ok, pits_cd, pits_ca = [], [], [], [], [], []
        for s in range(1, semillas + 1):
            r = simular(p, 'recal', vueltas, s)
            ult = r[-4:]
            err_final.append(statistics.mean(x['err'] for x in ult))
            err_cd.append(statistics.mean(abs(x['cd'] - cd_real) for x in ult))
            err_ca.append(statistics.mean(abs(x['ca'] - ca_real) for x in ult))
            ok.append(sum(x['ok'] for x in ult) / 4)
            pits_cd.append(pits_hasta([x['cd'] for x in r], cd_real, tol))
            pits_ca.append(pits_hasta([x['ca'] for x in r], ca_real, tol))
        filas.append((alpha, statistics.mean(err_final), statistics.mean(err_cd), statistics.mean(err_ca),
                      statistics.mean(ok), statistics.median(pits_cd), statistics.median(pits_ca)))
    return cd_real, ca_real, filas


def main() -> None:
    semillas = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    vueltas = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    cd, ca, filas = correr(semillas=semillas, vueltas=vueltas)
    print(f'robot simulado: cd={cd:.3f} ca={ca:.3f}; {semillas} semillas x {vueltas} vueltas; '
          'métricas sobre la ÚLTIMA vuelta; pits = mediana hasta quedar a ±1.5 % del real')
    print(f"{'alpha':>6} {'error llegada (cm)':>19} {'|cd-real|':>10} {'|ca-real|':>10} {'llegadas ok':>12} "
          f"{'pits cd':>8} {'pits ca':>8}")
    for a, e, ecd, eca, ok, pcd, pca in filas:
        print(f'{a:>6.2f} {e:>19.2f} {ecd:>10.4f} {eca:>10.4f} {ok:>11.0%} {pcd:>8.0f} {pca:>8.0f}')


if __name__ == '__main__':
    main()
