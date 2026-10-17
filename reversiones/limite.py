"""Entrada con orden límite en la EMA20 tras el aviso, frente a la entrada al cierre de la vela que confirma.

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
Mixta: la orden límite y, si no se ha llenado cuando el detector confirma su entrada, la entrada al cierre.
Si en la propia vela de la entrada el precio llega al stop, cuenta como stop (criterio conservador).
El resto de la simulación es la de backtest.py (stop con precio justo/de marca, máximo 48 h, comisiones de MEXC).

Fuentes:
  mexc     los ~30 días de MEXC (reversiones/datos/)
  binance  el histórico largo de Binance (reversiones/datos_binance/), en bloques de 30 días con 30 días
           previos de historia, como los de MEXC, para que el detector vea lo mismo que vería en MEXC

Uso:  python3 -m reversiones.limite mexc
      python3 -m reversiones.limite binance
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from collections import defaultdict
from multiprocessing import Pool

from . import binance, mexc
from .backtest import CASOS_DISEÑO, FIJOS, OBJETIVOS, RES, es_cripto, hora_madrid, simular, wilson
from .detector import Detector, Params, ema

DIA = 86400
BLOQUE = 30 * DIA
SALIDA = RES / "limite"


def orden_limite(d: Detector, e, E20):
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
        lim = E20[i - 1]
        if not (previo < lim <= e.l3 - p.pullback_min * a):
            continue
        if d.l[i] < lim:
            precio = min(d.o[i], lim)
            return {"i": i, "precio": precio, "atr": a, "previo": previo,
                    "stops": {"L1": precio - 0.5 * a, "L2": precio - 1.0 * a, "L3": previo - 0.1 * a}}, "llena"
    return None, "fin de datos"


def simular_limite(d, justo, i, precio, stop, fees):
    R = precio - stop
    if R <= 0:
        return None
    bajo = min(d.l[i], justo.get(d.t[i], (None, d.l[i]))[1])
    if bajo <= stop:  # stop en la misma vela de la entrada
        coste = (fees["maker"] * precio + fees["taker"] * stop) / R
        return {"R": R, "mfe": 0.0, "stop": True, "minutos_stop": 0, "llega": {k: False for k in OBJETIVOS},
                "fijo": {k: -1.0 for k in FIJOS}, "neto": {k: -1.0 - coste for k in FIJOS}}
    return simular(d, justo, i, precio, stop, fees["maker"], fees["maker"], fees["taker"])


def _bloques(t):
    """(inicio_carga, inicio_eval, fin_eval, fin_carga) en segundos."""
    ini, fin = t[0], t[-1]
    out, ev = [], ini + BLOQUE
    while ev < fin:
        out.append((ev - BLOQUE, ev, min(ev + BLOQUE, fin + 1), ev + BLOQUE + 3 * DIA))
        ev += BLOQUE
    return out


def procesar(args):
    fuente, simbolo, fees = args
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
        d = Detector(t, o, h, l, c, Params())
        E20 = ema(c, 20)
        dias += (min(e1, t[-1]) - max(e0, t[0])) / DIA
        for e in d.ejecutar():
            if not (e0 <= t[e.i_ruptura] < e1) or len(e.toques) < 2:
                continue
            fila = {"moneda": moneda, "ruptura": hora_madrid(t[e.i_ruptura]),
                    "aviso": hora_madrid(t[e.avisos[0]]), "fin_patron": e.fin}
            en = e.entrada
            if en:
                fila["cierre"] = {"entrada": hora_madrid(t[en["i"]]), "precio": en["precio"]}
                for k, st in zip("ABC", en["stops"].values()):
                    fila["cierre"][k] = simular(d, justo, en["i"], en["precio"], st, fees["taker"], fees["maker"],
                                                fees["taker"])
            lim, motivo = orden_limite(d, e, E20)
            fila["limite_motivo"] = motivo
            if lim:
                fila["limite"] = {"entrada": hora_madrid(t[lim["i"]]), "precio": lim["precio"]}
                for k, st in lim["stops"].items():
                    fila["limite"][k] = simular_limite(d, justo, lim["i"], lim["precio"], st, fees)
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


def mixta(f, kl, kc):
    """Orden límite; si no se llena antes de la entrada del detector, la entrada al cierre."""
    li, ci = f.get("limite"), f.get("cierre")
    if li and (not ci or li["entrada"] <= ci["entrada"]):
        return li[kl]
    return ci[kc] if ci else None


def es_diseño(f):
    return any(f["moneda"] == m and f["ruptura"][:10] == fecha[:10] for m, fecha in CASOS_DISEÑO)


def tabla(filas, dias):
    out = {"avisos": len(filas),
           "entradas_al_cierre": sum("cierre" in f for f in filas),
           "ordenes_llenas": sum("limite" in f for f in filas)}
    motivos = defaultdict(int)
    for f in filas:
        if "limite" not in f:
            motivos[f["limite_motivo"]] += 1
    out["motivos_sin_llenar"] = dict(motivos)
    for nombre, grupo in (("todas", filas), ("sin MERL ni AAVE", [f for f in filas if not es_diseño(f)])):
        bloque = {}
        for k in "ABC":
            bloque[f"cierre {k}"] = resumen([f["cierre"][k] for f in grupo if "cierre" in f], dias)
        for k in ("L1", "L2", "L3"):
            bloque[f"límite {k}"] = resumen([f["limite"][k] for f in grupo if "limite" in f], dias)
        for kl, kc in (("L2", "A"), ("L3", "C")):
            bloque[f"mixta {kl}+{kc}"] = resumen([mixta(f, kl, kc) for f in grupo], dias)
        out[nombre] = bloque
    return out


def por_trimestre(filas, metodo, k):
    grupos = defaultdict(list)
    for f in filas:
        if metodo in f and not es_diseño(f):
            a, m = int(f["ruptura"][:4]), int(f["ruptura"][5:7])
            grupos[f"{a}-T{(m - 1) // 3 + 1}"].append(f[metodo][k])
        elif metodo == "mixta" and not es_diseño(f):
            a, m = int(f["ruptura"][:4]), int(f["ruptura"][5:7])
            grupos[f"{a}-T{(m - 1) // 3 + 1}"].append(mixta(f, *k.split("+")))
    return {q: resumen(s, 1) for q, s in sorted(grupos.items())}


def main(fuente):
    if fuente == "mexc":
        universo = json.loads((mexc.DATOS / "universo.json").read_text())
        tareas = [(fuente, u["simbolo"], u) for u in universo
                  if es_cripto(u["simbolo"]) and (mexc.DATOS / f"{u['simbolo']}_1m_fair.csv.gz").exists()]
    else:
        fees = {u["simbolo"]: u for u in json.loads((mexc.DATOS / "universo.json").read_text())}
        tareas = [(fuente, s, fees[s]) for s, _ in json.loads((binance.DATOS / "pares.json").read_text())["pares"]
                  if (binance.DATOS / f"{s}_1m_fair.csv.gz").exists()]
    filas, dias_moneda = [], {}
    with Pool(4) as pool:
        for simbolo, f, dias in pool.imap_unordered(procesar, tareas):
            filas += f
            dias_moneda[simbolo] = dias
            print(simbolo, len(f), round(dias), flush=True)
    dias = max(dias_moneda.values())
    SALIDA.mkdir(parents=True, exist_ok=True)
    res = {"fuente": fuente, "monedas": len(tareas), "días": round(dias, 1), **tabla(filas, dias)}
    if fuente == "binance":
        res["por_trimestre"] = {m: por_trimestre(filas, *m.split()) for m in ("cierre A", "cierre C", "limite L2", "limite L3", "mixta L2+A")}
    (SALIDA / f"tabla_{fuente}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    with open(SALIDA / f"señales_{fuente}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        cab = ["moneda", "ruptura", "aviso", "fin_patron", "entrada_cierre", "R_max_cierre_A", "neto10_cierre_A",
               "limite", "entrada_limite", "R_max_L2", "neto10_L2", "R_max_L3", "neto10_L3"]
        w.writerow(cab)
        for f in sorted(filas, key=lambda f: f["ruptura"]):
            ci, li = f.get("cierre"), f.get("limite")
            fila = [f["moneda"], f["ruptura"], f["aviso"], f["fin_patron"]]
            s = ci and ci["A"]
            fila += [ci["entrada"] if ci else "", round(s["mfe"], 2) if s else "", round(s["neto"][10], 2) if s else ""]
            fila += [f["limite_motivo"], li["entrada"] if li else ""]
            for k in ("L2", "L3"):
                s = li and li[k]
                fila += [round(s["mfe"], 2) if s else "", round(s["neto"][10], 2) if s else ""]
            w.writerow(fila)
    print(json.dumps({k: v for k, v in res.items() if k != "por_trimestre"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
