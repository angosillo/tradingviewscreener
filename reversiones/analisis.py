"""Embudo del detector y ablación: qué condiciones aportan y cuáles sobran.

- Embudo: cuántas estructuras llegan a cada paso (ruptura del 2 → 1.er toque → aviso → entrada) y por qué acaban.
- Ablación: se relaja UNA condición cada vez y se compara número de señales y resultado (stop B, entrada al cierre).

Uso:  python3 -m reversiones.analisis
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace

from .backtest import RES, es_cripto, simular
from .datos_simbolo import preparar, precio_justo
from .detector import Params
from .mexc import DATOS

VARIANTES = {
    "base": {},
    "sin referencia del 2": {"p2_ref_bajo": -1e9, "p2_ref_alto": 1e9},
    "barrido 0,3–8 ATR": {"barrido_min": 0.3, "barrido_max": 8.0},
    "sin barrido mínimo": {"barrido_min": 0.0},
    "toque a 0,5 ATR": {"toque": 0.5},
    "línea 3 hasta 20 ATR": {"l3_max": 20.0},
    "zona 4 sin límite de tiempo": {"max_min_zona4": 10 ** 9},
    "sin retroceso mínimo de entrada": {"pullback_min": 0.0},
    "zigzag 25 %": {"zigzag_frac": 0.25},
}


def universo():
    u = json.loads((DATOS / "universo.json").read_text())
    return [x for x in u if (DATOS / f"{x['simbolo']}_1m_fair.csv.gz").exists() and es_cripto(x["simbolo"])]


def correr(params: Params, exigir_filtro: bool, monedas, justos):
    fin, n_est, toque, aviso, sims = Counter(), 0, 0, 0, []
    for u in monedas:
        d, _ = preparar(u["simbolo"], params, con_filtro=True, exigir_filtro=exigir_filtro)
        for e in d.ejecutar():
            n_est += 1
            toque += bool(e.toques)
            aviso += bool(e.avisos)
            fin[e.fin] += 1
            if e.entrada:
                en = e.entrada
                for clave, stop in (("A", en["stops"]["A_-0.3ATR"]), ("B", en["stops"]["B_-1ATR"])):
                    s = simular(d, justos[u["simbolo"]], en["i"], en["precio"], stop, u["taker"], u["maker"], u["taker"])
                    if s:
                        sims.append((clave, s))
    out = {"estructuras": n_est, "con_toque": toque, "con_aviso": aviso, "finales": dict(fin)}
    for clave in "AB":
        ss = [s for k, s in sims if k == clave]
        n = len(ss)
        out[clave] = {"señales": n} if not n else {
            "señales": n, "llega_1R": round(100 * sum(s["llega"][1] for s in ss) / n),
            "llega_5R": round(100 * sum(s["llega"][5] for s in ss) / n),
            "esp_5R": round(sum(s["neto"][5] for s in ss) / n, 2), "esp_10R": round(sum(s["neto"][10] for s in ss) / n, 2)}
    return out


def main(solo_sin_filtro: bool = False):
    monedas = universo()
    justos = {u["simbolo"]: precio_justo(u["simbolo"]) for u in monedas}
    res = {"monedas": len(monedas), "variantes": {}}
    for nombre, cambios in VARIANTES.items():
        p = replace(Params(), **cambios)
        res["variantes"][nombre] = {"sin filtro": correr(p, False, monedas, justos)}
        if not solo_sin_filtro:
            res["variantes"][nombre]["con filtro"] = correr(p, True, monedas, justos)
        print(nombre, json.dumps(res["variantes"][nombre], ensure_ascii=False), flush=True)
    RES.mkdir(exist_ok=True)
    (RES / "analisis.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    import sys
    main(solo_sin_filtro="--sin-filtro" in sys.argv)
