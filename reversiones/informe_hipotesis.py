"""Tablas del backtest de hipótesis (lee resultados/hipotesis/señales.json, escrito por hipotesis.py).

- Una sola operación abierta por moneda a la vez, en cada combinación de stop y salida.
- Primeros 2/3 del periodo = exploración; último tercio = confirmación (no se ajusta nada con él).
- Intervalos de confianza del 95 % por bootstrap (2000 remuestreos, semilla fija).
- Combinación (regla fijada antes de mirar): en exploración y con S1 + objetivo por nivel, de cada hipótesis
  se toma el grupo con mejor R medio que tenga ≥30 señales y supere a la base en ≥0,2R; se exigen todos a la vez
  y, si quedan menos de 30 señales, se quitan los de menor mejora hasta llegar a 30. Luego se mira en confirmación.

Uso:  python3 -m reversiones.informe_hipotesis
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict

from .hipotesis import SALIDA, SALIDAS, STOPS

BOOT, SEMILLA, MIN_N = 2000, 7, 30
ORDEN = ["<5R", "5–10R", ">10R", "<5 ATR", "5–15 ATR", ">15 ATR", "0", "1", "≥2", "sin mínimo previo", "no barre",
         "0–1 ATR", "1–2,5 ATR", ">2,5 ATR", "sí", "resto", "no", "2", "≥3", "llega", "no llega"]


def cargar():
    d = json.loads((SALIDA / "señales.json").read_text())
    t0 = min(r[0] for r in d["rango"].values())
    t1 = max(r[1] for r in d["rango"].values())
    corte = t0 + (t1 - t0) * 2 / 3
    for f in d["señales"]:
        f["periodo"] = "exploración" if f["ts"] < corte else "confirmación"
    return d, t0, t1, corte


def tomar(señales, stop, salida):
    """Operaciones de una variante, con una sola abierta por moneda a la vez."""
    clave = f"{stop}_{salida}_neto"
    out, libre = [], {}
    for f in sorted(señales, key=lambda f: (f["moneda"], f["ts"])):
        if clave not in f or f[clave] is None:
            continue
        if f["i"] <= libre.get(f["moneda"], -1):
            continue
        libre[f["moneda"]] = f[f"{stop}_{salida}_salida"]
        out.append(f)
    return sorted(out, key=lambda f: f["ts"])


def boot_ic(v):
    if len(v) < 2:
        return (None, None)
    rnd = random.Random(SEMILLA)
    n = len(v)
    medias = sorted(sum(rnd.choices(v, k=n)) / n for _ in range(BOOT))
    return (medias[int(0.025 * BOOT)], medias[int(0.975 * BOOT) - 1])


def base(ops, clave, dias):
    v = [f[clave] for f in ops]
    if not v:
        return {"n": 0}
    gan, per = sum(x for x in v if x > 0), -sum(x for x in v if x < 0)
    eq = pico = dd = 0.0
    racha = peor = 0
    for x in v:
        eq += x
        pico = max(pico, eq)
        dd = max(dd, pico - eq)
        racha = racha + 1 if x < 0 else 0
        peor = max(peor, racha)
    return {"n": len(v), "por_dia": len(v) / dias, "ganadoras": 100 * sum(x > 0 for x in v) / len(v),
            "R_medio": sum(v) / len(v), "PF": gan / per if per else None, "max_dd_R": dd, "peor_racha": peor}


def grupo(ops, clave, stop):
    v = [f[clave] for f in ops]
    if not v:
        return {"n": 0}
    lo, hi = boot_ic(v)
    return {"n": len(v), "R_medio": sum(v) / len(v), "IC": (lo, hi),
            "llega_5R": 100 * sum(f[f"{stop}_mfe"] >= 5 for f in ops) / len(v),
            "llega_10R": 100 * sum(f[f"{stop}_mfe"] >= 10 for f in ops) / len(v)}


def _bins(x, cortes, nombres, nulo):
    if x is None:
        return nulo
    for c, n in zip(cortes, nombres):
        if x < c:
            return n
    return nombres[-1]


def _sino(x):
    return None if x is None else ("sí" if x else "no")


HIPOTESIS = {
    "H1 espacio libre (R, con S1)": lambda f: _bins(f["espacio_R"], (5, 10), ("<5R", "5–10R", ">10R"), ">10R"),
    "H1 espacio libre (ATR)": lambda f: _bins(f["espacio_ATR"], (5, 15), ("<5 ATR", "5–15 ATR", ">15 ATR"), ">15 ATR"),
    "H2 reacciones previas en la línea 3": lambda f: {0: "0", 1: "1"}.get(f["reacciones_l3"], "≥2"),
    "H3 barrido del punto 1": lambda f: _bins(f["barrido_atr"], (0, 1, 2.5), ("no barre", "0–1 ATR", "1–2,5 ATR", ">2,5 ATR"),
                                             "sin mínimo previo"),
    "H4 tendencia 4 h y suelo junto a la EMA20": lambda f: (None if f["tendencia_4h"] is None or f["suelo_cerca_ema"] is None
                                                           else "sí" if f["tendencia_4h"] and f["suelo_cerca_ema"] else "resto"),
    "H4a tendencia 4 h (EMA20 > EMA50)": lambda f: _sino(f["tendencia_4h"]),
    "H4b suelo de 24 h a ≤0,5 % de la EMA20 4 h o 1 d": lambda f: _sino(f["suelo_cerca_ema"]),
    "H5a mínimo de entrada a ≤0,3 ATR de la EMA20": lambda f: _sino(f["min_cerca_ema20"]),
    "H5b EMAs 20/50/100/200 ordenadas al alza": lambda f: _sino(f["emas_ordenadas"]),
    "S toques al entrar": lambda f: "2" if f["toques"] == 2 else "≥3",
    "S retrocesos por encima de la línea 2": lambda f: _sino(f["retrocesos_sobre_l2"]),
    "S RSI con picos descendentes en los toques": lambda f: _sino(f["rsi_picos_bajan"]),
    "S pico de volumen en la zona 4": lambda f: _sino(f["pico_volumen_z4"]),
    "Apalancamiento: liquidación en el stop S1": lambda f: (None if f.get("S1_apal_necesario") is None or not f.get("max_lev")
                                                            else "llega" if f["S1_apal_necesario"] <= f["max_lev"] else "no llega"),
}


def tabla_hipotesis(ops, stop, salida):
    clave = f"{stop}_{salida}_neto"
    out = {}
    for nombre, fn in HIPOTESIS.items():
        g = defaultdict(lambda: {"exploración": [], "confirmación": []})
        for f in ops:
            k = fn(f)
            if k is not None:
                g[k][f["periodo"]].append(f)
        out[nombre] = {k: {p: grupo(v, clave, stop) for p, v in per.items()}
                       for k, per in sorted(g.items(), key=lambda x: ORDEN.index(x[0]) if x[0] in ORDEN else 99)}
    return out


def combinacion(ops, stop, salida):
    clave = f"{stop}_{salida}_neto"
    exp = [f for f in ops if f["periodo"] == "exploración"]
    conf = [f for f in ops if f["periodo"] == "confirmación"]
    b_exp = sum(f[clave] for f in exp) / len(exp)
    elegidas = []
    for nombre, fn in HIPOTESIS.items():
        if nombre.startswith("Apalancamiento") or nombre.startswith("H4 "):
            continue  # H4 ya está en H4a y H4b; el apalancamiento no es una condición del setup
        grupos = defaultdict(list)
        for f in exp:
            k = fn(f)
            if k is not None:
                grupos[k].append(f[clave])
        cand = [(sum(v) / len(v), k) for k, v in grupos.items() if len(v) >= MIN_N]
        if cand:
            m, k = max(cand)
            if m - b_exp >= 0.2:
                elegidas.append((m - b_exp, nombre, k))
    elegidas.sort(reverse=True)

    def filtra(lista, conds):
        return [f for f in lista if all(HIPOTESIS[n](f) == k for _, n, k in conds)]

    while elegidas and len(filtra(exp, elegidas)) < MIN_N:
        elegidas.pop()
    return {"condiciones": [(n, k, round(d, 2)) for d, n, k in elegidas],
            "exploración": grupo(filtra(exp, elegidas), clave, stop) if elegidas else None,
            "confirmación": grupo(filtra(conf, elegidas), clave, stop) if elegidas else None,
            "base_exploración": grupo(exp, clave, stop), "base_confirmación": grupo(conf, clave, stop)}


def por_moneda(ops, clave):
    tot = defaultdict(float)
    for f in ops:
        tot[f["moneda"]] += f[clave]
    orden = sorted(tot.items(), key=lambda x: -x[1])
    n = len(ops)
    sin = lambda k: (sum(f[clave] for f in ops if f["moneda"] not in dict(orden[:k])) /
                     max(1, sum(f["moneda"] not in dict(orden[:k]) for f in ops)))
    return {"monedas": len(tot), "R_medio": sum(tot.values()) / n, "top": [(m, round(r, 1)) for m, r in orden[:5]],
            "sin_la_mejor": sin(1), "sin_las_2_mejores": sin(2), "peores": [(m, round(r, 1)) for m, r in orden[-3:]]}


def main():
    d, t0, t1, corte = cargar()
    señales = d["señales"]
    dias = {"exploración": (corte - t0) / 86400, "confirmación": (t1 - corte) / 86400}
    res = {"periodo": [t0, corte, t1], "señales_detectadas": len(señales), "monedas": d["monedas"], "base": {},
           "hipótesis": {}, "combinación": {}, "monedas_dependencia": {}}
    variantes = {}
    for s in STOPS:
        for sal in SALIDAS:
            ops = tomar(señales, s, sal)
            variantes[(s, sal)] = ops
            res["base"][f"{s} + {sal}"] = {p: base([f for f in ops if f["periodo"] == p], f"{s}_{sal}_neto", dias[p])
                                           for p in dias}
            ideal = [f for f in ops if f.get(f"{s}_{sal}_ideal") is not None]
            res["base"][f"{s} + {sal}"]["ideal (referencia)"] = {
                p: base([f for f in ideal if f["periodo"] == p], f"{s}_{sal}_ideal", dias[p]) for p in dias}
    for sal in ("nivel", "10R"):
        ops = variantes[("S1", sal)]
        res["hipótesis"][f"S1 + {sal}"] = tabla_hipotesis(ops, "S1", sal)
        res["combinación"][f"S1 + {sal}"] = combinacion(variantes[("S1", "nivel")], "S1", "nivel") if sal == "nivel" else None
        res["monedas_dependencia"][f"S1 + {sal}"] = por_moneda(ops, f"S1_{sal}_neto")
    # la combinación elegida con S1 + nivel, vista también con S1 + 10R en confirmación
    conds = res["combinación"]["S1 + nivel"]["condiciones"]
    conf10 = [f for f in variantes[("S1", "10R")] if f["periodo"] == "confirmación"
              and all(HIPOTESIS[n](f) == k for n, k, _ in conds)]
    res["combinación"]["S1 + 10R"] = {"condiciones": conds, "confirmación": grupo(conf10, "S1_10R_neto", "S1") if conds else None,
                                      "base_confirmación": grupo([f for f in variantes[("S1", "10R")]
                                                                  if f["periodo"] == "confirmación"], "S1_10R_neto", "S1")}
    (SALIDA / "tablas.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    escribir_informe(res)
    # CSV con todas las señales
    tomadas = {k: {(f["moneda"], f["ts"]) for f in v} for k, v in variantes.items()}
    campos = [k for k in señales[0] if k not in ("i", "im", "ts")]
    for f in señales:
        for s in STOPS:
            for sal in SALIDAS:
                f[f"tomada_{s}_{sal}"] = (f["moneda"], f["ts"]) in tomadas[(s, sal)]
    extra = [f"tomada_{s}_{sal}" for s in STOPS for sal in SALIDAS]
    todos = sorted({k for f in señales for k in f} - {"i", "im", "ts"} - set(campos) - set(extra))
    cab = ["periodo"] + [c for c in campos if c != "periodo"] + todos + extra
    with open(SALIDA / "señales.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, cab, extrasaction="ignore")
        w.writeheader()
        for f in sorted(señales, key=lambda f: f["ts"]):
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in f.items()})
    # 10 mejores, 10 peores y 10 al azar (S1 + objetivo por nivel)
    ops = variantes[("S1", "nivel")]
    orden = sorted(ops, key=lambda f: -f["S1_nivel_neto"])
    azar = random.Random(SEMILLA).sample(ops, min(10, len(ops)))
    cols = ["moneda", "periodo", "p1_madrid", "t1_madrid", "minimo_madrid", "entrada_madrid", "entrada", "stop_S1",
            "S1_objetivo_nivel", "linea2", "linea3", "toques", "S1_nivel_tipo", "S1_nivel_neto", "S1_mfe"]
    with open(SALIDA / "revisar.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["grupo"] + cols)
        for nombre, lista in (("mejor", orden[:10]), ("peor", orden[-10:]), ("azar", azar)):
            for f in lista:
                w.writerow([nombre] + [round(f[c], 6) if isinstance(f[c], float) else f[c] for c in cols])
    print("ok", len(señales), "señales")



# ---------------------------------------------------------------- informe en Markdown


def _r(x, d=2):
    return "—" if x is None else f"{x:+.{d}f}".replace(".", ",")


def _ic(g):
    if not g or not g.get("n"):
        return "—"
    lo, hi = g["IC"]
    marca = " *" if g["n"] < MIN_N else ""
    return f"{_r(g['R_medio'])} [{_r(lo)}; {_r(hi)}]{marca}"


def _pct(x):
    return "—" if x is None else f"{x:.0f} %"


def escribir_informe(res):
    from datetime import datetime, timezone
    f = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%d-%m %H:%M")
    t0, corte, t1 = res["periodo"]
    L = [f"# Hipótesis del setup de reversión", "",
         f"MEXC, {res['monedas']} perpetuos cripto, 1 m. Exploración {f(t0)} → {f(corte)} UTC; "
         f"confirmación {f(corte)} → {f(t1)} UTC. {res['señales_detectadas']} señales detectadas.", "",
         "## Base por stop y salida", "",
         "| Variante | Periodo | Señales (por día) | Ganadoras | R medio neto | Factor de beneficio | Máx. caída (R) | Peor racha |",
         "|---|---|---|---|---|---|---|---|"]
    for var, per in res["base"].items():
        for p in ("exploración", "confirmación"):
            b = per[p]
            if not b.get("n"):
                continue
            pf = "—" if b["PF"] is None else f"{b['PF']:.2f}".replace(".", ",")
            L.append(f"| {var} | {p} | {b['n']} ({b['por_dia']:.0f}) | {b['ganadoras']:.0f} % | {_r(b['R_medio'])} | {pf} | "
                     f"{b['max_dd_R']:.0f} | {b['peor_racha']} |")
        ide = per["ideal (referencia)"]
        L.append(f"| {var} · entrada ideal | exp. / conf. | — | — | {_r(ide['exploración'].get('R_medio'))} / "
                 f"{_r(ide['confirmación'].get('R_medio'))} | — | — | — |")
    L += ["", "## Hipótesis", "", "R medio neto por operación [IC 95 % bootstrap]. * = menos de 30 señales.", ""]
    hip_n, hip_10 = res["hipótesis"]["S1 + nivel"], res["hipótesis"]["S1 + 10R"]
    for nombre in hip_n:
        L += [f"### {nombre}", "",
              "| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | "
              "S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |",
              "|---|---|---|---|---|---|---|"]
        for g, per in hip_n[nombre].items():
            e, c = per.get("exploración", {}), per.get("confirmación", {})
            e10 = hip_10[nombre].get(g, {}).get("exploración", {})
            c10 = hip_10[nombre].get(g, {}).get("confirmación", {})
            L.append(f"| {g} | {e.get('n', 0)} / {c.get('n', 0)} | {_ic(e)} | {_ic(c)} | {_ic(e10)} | {_ic(c10)} | "
                     f"{_pct(e.get('llega_5R'))} / {_pct(e.get('llega_10R'))} |")
        L.append("")
    cb = res["combinación"]["S1 + nivel"]
    L += ["## Combinación elegida en exploración (S1 + nivel)", "",
          "Condiciones: " + ("; ".join(f"{n} = {k} (+{str(d).replace('.', ',')}R)" for n, k, d in cb["condiciones"])
                             or "ninguna supera a la base en ≥0,2R con ≥30 señales"), ""]
    if cb["condiciones"]:
        c10 = res["combinación"]["S1 + 10R"]
        L += ["| | Exploración | Confirmación |", "|---|---|---|",
              f"| Base | {cb['base_exploración']['n']} · {_ic(cb['base_exploración'])} | "
              f"{cb['base_confirmación']['n']} · {_ic(cb['base_confirmación'])} |",
              f"| Combinación | {cb['exploración']['n']} · {_ic(cb['exploración'])} | "
              f"{cb['confirmación']['n']} · {_ic(cb['confirmación'])} |",
              f"| Combinación con S1 + 10R | — | {c10['confirmación']['n']} · {_ic(c10['confirmación'])} "
              f"(base {_ic(c10['base_confirmación'])}) |", ""]
    L += ["## Dependencia de pocas monedas (todo el periodo)", ""]
    for var, d in res["monedas_dependencia"].items():
        L.append(f"- {var}: {d['monedas']} monedas, R medio {_r(d['R_medio'])}; sin la mejor {_r(d['sin_la_mejor'])}; "
                 f"sin las 2 mejores {_r(d['sin_las_2_mejores'])}. Mejores: "
                 + ", ".join(f"{m} {_r(r, 0)}R" for m, r in d["top"]) + ".")
    (SALIDA / "informe.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
