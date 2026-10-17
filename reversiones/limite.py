"""Otras formas de entrar tras el aviso, frente a la entrada al cierre de la vela que confirma.

Orden límite (sin mirar el futuro):
  - Se coloca en la vela siguiente al aviso (2.º toque) y se mueve cada minuto a la EMA20 de 1 minuto
    de la última vela cerrada.
  - Solo está activa si esa EMA20 queda por encima del mínimo de retroceso anterior (el del último tramo
    completo entre dos toques, como en el detector: si no, ya no sería un mínimo más alto) y al menos
    0,7 ATR por debajo de la línea 3.
  - Se llena si el mínimo de la vela pasa POR DEBAJO de la orden (tocarla no basta). Precio: la orden, o la
    apertura si la vela abre ya por debajo.
  - Se cancela con las mismas reglas que el patrón: cierre más de 1 ATR bajo la línea 2, cierre más de
    0,5 ATR sobre la línea 3 o 60 min desde el primer toque.
Stops: L1 = entrada − 0,5 ATR · L2 = entrada − 1 ATR · L3 = 0,1 ATR bajo ese mínimo de retroceso anterior.
Cerca del mínimo anterior (orden a mercado): en cuanto el precio baja a 0,25 o 0,5 ATR por encima del mínimo
de retroceso anterior, se compra a mercado (taker). No se compra si la vela abre ya por debajo de ese mínimo.
Stops: S1 = 0,1 ATR bajo el mínimo anterior · S3 = 0,3 ATR bajo el mínimo anterior.
Mixta: la orden y, si no se ha llenado cuando el detector confirma su entrada, la entrada al cierre.
Si en la propia vela de la entrada el precio llega al stop, cuenta como stop (criterio conservador).
El resto de la simulación es la de backtest.py (stop con precio justo/de marca, máximo 48 h, comisiones de MEXC).

Fuentes:
  mexc     los ~30 días de MEXC (reversiones/datos/)
  binance  el histórico largo de Binance (reversiones/datos_binance/), en bloques de 30 días con 30 días
           previos de historia, como los de MEXC, para que el detector vea lo mismo que vería en MEXC

Uso:  python3 -m reversiones.limite mexc
      python3 -m reversiones.limite binance
      python3 -m reversiones.limite binance --sin-barrido-min    (sin exigir barrido mínimo)
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from collections import defaultdict
from dataclasses import replace
from multiprocessing import Pool

from . import binance, mexc
from .backtest import CASOS_DISEÑO, FIJOS, OBJETIVOS, RES, es_cripto, hora_madrid, simular, wilson
from .detector import Detector, Params, ema

DIA = 86400
BLOQUE = 30 * DIA
SALIDA = RES / "limite"


def orden(d: Detector, e, nivel, estricta=True, exigir_previo=False):
    """Orden de compra que se recoloca cada minuto en nivel(i, previo, atr), desde la vela siguiente al aviso."""
    p = d.p
    t1, t2 = e.toques[0], e.toques[1]
    # mínimo de cada tramo entre dos toques, disponible desde la vela siguiente al toque que lo cierra
    tramos = [(b, min(d.l[a + 1:b + 1])) for a, b in zip(e.toques, e.toques[1:])]
    for i in range(t2 + 1, len(d.c)):
        previo = [m for b, m in tramos if b < i][-1]
        a, cp = d.a[i - 1], d.c[i - 1]
        if i - 1 > t2:
            if cp < e.p2 - p.linea2 * a:
                return None, "cierra bajo la línea 2"
            if cp > e.l3 + p.rotura * a:
                return None, "rompió la línea 3"
        if i - t1 > p.max_min_zona4:
            return None, "tiempo"
        if exigir_previo and d.o[i] <= previo:
            return None, "perdió el mínimo anterior"
        lim = nivel(i, previo, a)
        if not (previo < lim <= e.l3 - p.pullback_min * a):
            continue
        if d.l[i] < lim if estricta else d.l[i] <= lim:
            return {"i": i, "precio": min(d.o[i], lim), "atr": a, "previo": previo}, "llena"
    return None, "fin de datos"


def metodos(E20):
    """Cada forma de entrar tras el aviso: (orden, comisión de entrada, stops)."""
    return {
        # orden límite en la EMA20 (maker)
        "ema": (lambda d, e: orden(d, e, lambda i, pr, a: E20[i - 1]), "maker",
                {"L1": lambda x: x["precio"] - 0.5 * x["atr"], "L2": lambda x: x["precio"] - x["atr"],
                 "L3": lambda x: x["previo"] - 0.1 * x["atr"]}),
        # a mercado cuando el precio baja a un poco por encima del mínimo anterior (taker)
        **{f"cerca{dl}": (lambda d, e, dl=dl: orden(d, e, lambda i, pr, a: pr + dl * a, False, True), "taker",
                          {"S1": lambda x: x["previo"] - 0.1 * x["atr"], "S3": lambda x: x["previo"] - 0.3 * x["atr"]})
           for dl in (0.25, 0.5)},
    }


def simular_orden(d, justo, i, precio, stop, fees, fee_in):
    R = precio - stop
    if R <= 0:
        return None
    bajo = min(d.l[i], justo.get(d.t[i], (None, d.l[i]))[1])
    if bajo <= stop:  # stop en la misma vela de la entrada
        coste = (fees[fee_in] * precio + fees["taker"] * stop) / R
        return {"R": R, "mfe": 0.0, "stop": True, "minutos_stop": 0, "llega": {k: False for k in OBJETIVOS},
                "fijo": {k: -1.0 for k in FIJOS}, "neto": {k: -1.0 - coste for k in FIJOS}}
    return simular(d, justo, i, precio, stop, fees[fee_in], fees["maker"], fees["taker"])


def _bloques(t):
    """(inicio_carga, inicio_eval, fin_eval, fin_carga) en segundos."""
    ini, fin = t[0], t[-1]
    out, ev = [], ini + BLOQUE
    while ev < fin:
        out.append((ev - BLOQUE, ev, min(ev + BLOQUE, fin + 1), ev + BLOQUE + 3 * DIA))
        ev += BLOQUE
    return out


def procesar(args):
    fuente, simbolo, fees, cambios = args
    cargar = mexc.cargar if fuente == "mexc" else binance.cargar
    v = cargar(simbolo, "1m")
    justo = {x[0]: (x[2], x[3]) for x in cargar(simbolo, "1m_fair")}
    T = [x[0] for x in v]
    bloques = [(T[0], T[0], T[-1] + 1, T[-1] + 1)] if fuente == "mexc" else _bloques(T)
    filas, dias, moneda = [], 0.0, simbolo.replace("_USDT", "")
    for c0, e0, e1, c1 in bloques:
        a, b = bisect.bisect_left(T, c0), bisect.bisect_left(T, c1)
        trozo = v[a:b]
        if len(trozo) < 3 * 1440:
            continue
        t = [x[0] for x in trozo]
        o, h, l, c = ([x[k] for x in trozo] for k in (1, 2, 3, 4))
        d = Detector(t, o, h, l, c, replace(Params(), **cambios))
        M = metodos(ema(c, 20))
        dias += (min(e1, t[-1]) - max(e0, t[0])) / DIA
        for e in d.ejecutar():
            if not (e0 <= t[e.i_ruptura] < e1) or len(e.toques) < 2:
                continue
            fila = {"moneda": moneda, "ruptura": hora_madrid(t[e.i_ruptura]),
                    "aviso": hora_madrid(t[e.avisos[0]]), "fin_patron": e.fin, "motivo": {}}
            en = e.entrada
            if en:
                fila["cierre"] = {"entrada": hora_madrid(t[en["i"]]), "precio": en["precio"]}
                for k, st in zip("ABC", en["stops"].values()):
                    fila["cierre"][k] = simular(d, justo, en["i"], en["precio"], st, fees["taker"], fees["maker"],
                                                fees["taker"])
            for nombre, (poner, fee_in, stops) in M.items():
                x, fila["motivo"][nombre] = poner(d, e)
                if x:
                    fila[nombre] = {"entrada": hora_madrid(t[x["i"]]), "precio": x["precio"]}
                    for k, st in stops.items():
                        fila[nombre][k] = simular_orden(d, justo, x["i"], x["precio"], st(x), fees, fee_in)
            filas.append(fila)
    return simbolo, filas, dias


def resumen(sims, dias):
    sims = [s for s in sims if s]
    n = len(sims)
    if not n:
        return {"señales": 0}
    r = {"señales": n, "por_día": round(n / dias, 2),
         "IC95_llega_10R": wilson(sum(s["llega"][10] for s in sims), n)}
    for k in OBJETIVOS:
        r[f"llega_{k}R"] = round(100 * sum(s["llega"][k] for s in sims) / n, 1)
    for k in FIJOS:
        r[f"esperanza_{k}R"] = round(sum(s["neto"][k] for s in sims) / n, 2)
    return r


def mixta(f, metodo, kl, kc):
    """La orden y, si no se ha llenado cuando el detector confirma su entrada, la entrada al cierre."""
    li, ci = f.get(metodo), f.get("cierre")
    if li and (not ci or li["entrada"] <= ci["entrada"]):
        return li[kl]
    return ci[kc] if ci else None


COLUMNAS = {
    **{f"cierre {k}": (lambda f, k=k: f["cierre"][k] if "cierre" in f else None) for k in "ABC"},
    **{f"límite EMA20 {k}": (lambda f, k=k: f["ema"][k] if "ema" in f else None) for k in ("L1", "L2", "L3")},
    **{f"cerca {dl} ATR {k}": (lambda f, m=f"cerca{dl}", k=k: f[m][k] if m in f else None)
       for dl in (0.25, 0.5) for k in ("S1", "S3")},
    "mixta EMA20 L2 + cierre A": lambda f: mixta(f, "ema", "L2", "A"),
    "mixta EMA20 L3 + cierre C": lambda f: mixta(f, "ema", "L3", "C"),
    "mixta cerca 0.25 S1 + cierre A": lambda f: mixta(f, "cerca0.25", "S1", "A"),
    "mixta cerca 0.5 S1 + cierre A": lambda f: mixta(f, "cerca0.5", "S1", "A"),
}


def es_diseño(f):
    return any(f["moneda"] == m and f["ruptura"][:10] == fecha[:10] for m, fecha in CASOS_DISEÑO)


def tabla(filas, dias):
    out = {"avisos": len(filas), "entradas_al_cierre": sum("cierre" in f for f in filas)}
    for m in ("ema", "cerca0.25", "cerca0.5"):
        motivos = defaultdict(int)
        for f in filas:
            motivos[f["motivo"][m]] += 1
        out[f"órdenes {m}"] = dict(motivos)
    for nombre, grupo in (("todas", filas), ("sin MERL ni AAVE", [f for f in filas if not es_diseño(f)])):
        out[nombre] = {col: resumen([g(f) for f in grupo], dias) for col, g in COLUMNAS.items()}
    return out


def por_trimestre(filas, col):
    grupos = defaultdict(list)
    for f in filas:
        if not es_diseño(f):
            a, m = int(f["ruptura"][:4]), int(f["ruptura"][5:7])
            grupos[f"{a}-T{(m - 1) // 3 + 1}"].append(COLUMNAS[col](f))
    return {q: resumen(s, 1) for q, s in sorted(grupos.items())}


def main(fuente, cambios, sufijo):
    fees = {u["simbolo"]: u for u in json.loads((mexc.DATOS / "universo.json").read_text())}
    if fuente == "mexc":
        simbolos = [s for s in fees if es_cripto(s) and (mexc.DATOS / f"{s}_1m_fair.csv.gz").exists()]
    else:
        simbolos = [s for s, _ in json.loads((binance.DATOS / "pares.json").read_text())["pares"]
                    if (binance.DATOS / f"{s}_1m_fair.csv.gz").exists()]
    tareas = [(fuente, s, fees[s], cambios) for s in simbolos]
    filas, dias_moneda = [], {}
    with Pool(4) as pool:
        for simbolo, f, dias in pool.imap_unordered(procesar, tareas):
            filas += f
            dias_moneda[simbolo] = dias
            print(simbolo, len(f), round(dias), flush=True)
    dias = max(dias_moneda.values())
    SALIDA.mkdir(parents=True, exist_ok=True)
    res = {"fuente": fuente, "cambios": cambios, "monedas": len(tareas), "días": round(dias, 1), **tabla(filas, dias)}
    if fuente == "binance":
        res["por_trimestre"] = {col: por_trimestre(filas, col) for col in COLUMNAS}
    (SALIDA / f"tabla_{fuente}{sufijo}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    with open(SALIDA / f"señales_{fuente}{sufijo}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        cols = ["cierre A", "límite EMA20 L2", "cerca 0.25 ATR S1", "cerca 0.5 ATR S1"]
        w.writerow(["moneda", "ruptura", "aviso", "fin_patron"] + [f"{c} · {x}" for c in cols for x in ("R_max", "neto_10R")])
        for f in sorted(filas, key=lambda f: f["ruptura"]):
            fila = [f["moneda"], f["ruptura"], f["aviso"], f["fin_patron"]]
            for c in cols:
                s = COLUMNAS[c](f)
                fila += [round(s["mfe"], 2), round(s["neto"][10], 2)] if s else ["", ""]
            w.writerow(fila)


if __name__ == "__main__":
    sin_barrido = "--sin-barrido-min" in sys.argv
    main(sys.argv[1], {"barrido_min": 0.0} if sin_barrido else {}, "_sin_barrido_min" if sin_barrido else "")
