"""Prueba del detector en el histórico de 1 minuto de los perpetuos descargados.

Para cada señal (estructura con entrada):
  - Entrada real: al cierre de la vela que confirma el mínimo más alto (sin mirar el futuro).
  - Entrada ideal (solo referencia): en el propio mínimo, con orden límite.
  - Tres stops: A = mínimo − 0,3 ATR · B = mínimo − 1 ATR · C = bajo el primer mínimo de la zona 4.
  - El stop salta con el PRECIO JUSTO de MEXC (como la liquidación); los objetivos, con el último precio.
  - Si en la misma vela se tocan stop y objetivo, cuenta el stop (criterio conservador).
  - Máximo 48 h por operación (límite del estilo banderín); después se cierra a mercado.
  - Comisiones de cada moneda según la API de MEXC: entrada real y stop = taker; objetivo y entrada ideal = maker.

Uso:  python3 -m reversiones.backtest
Salida en reversiones/resultados/.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .datos_simbolo import preparar, precio_justo
from .mexc import DATOS, NO_CRIPTO

RES = Path(__file__).resolve().parent / "resultados"
MADRID = ZoneInfo("Europe/Madrid")
OBJETIVOS = (1, 3, 5, 10)
FIJOS = (5, 10)
MAX_VELAS = 48 * 60
EXCLUIR = ("ZINC",)


def hora_madrid(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(MADRID).strftime("%Y-%m-%d %H:%M")


def simular(d, justo, i0, entrada, stop, fee_in, fee_tp, fee_sl):
    """Recorre las velas desde i0+1. Devuelve R alcanzado antes del stop y el resultado con objetivos fijos."""
    R = entrada - stop
    if R <= 0:
        return None
    t, h, c = d.t, d.h, d.c
    mfe, salto, i_stop = 0.0, False, None
    fin = min(len(t) - 1, i0 + MAX_VELAS)
    fijos = {k: None for k in FIJOS}
    for i in range(i0 + 1, fin + 1):
        bajo = justo.get(t[i], (None, d.l[i]))[1]
        if bajo <= stop:
            salto, i_stop = True, i
            for k in FIJOS:
                if fijos[k] is None:
                    fijos[k] = ("stop", -1.0, stop)
            break
        r_alto = (h[i] - entrada) / R
        mfe = max(mfe, r_alto)
        for k in FIJOS:
            if fijos[k] is None and r_alto >= k:
                fijos[k] = ("objetivo", float(k), entrada + k * R)
        if all(v is not None for v in fijos.values()):
            break
    for k in FIJOS:
        if fijos[k] is None:  # ni stop ni objetivo en 48 h (o fin de datos): cierre a mercado
            fijos[k] = ("tiempo", (c[fin] - entrada) / R, c[fin])
    neto = {}
    for k, (tipo, r_bruto, salida) in fijos.items():
        fee_out = fee_tp if tipo == "objetivo" else fee_sl
        neto[k] = r_bruto - (fee_in * entrada + fee_out * salida) / R
    return {"R": R, "mfe": mfe, "stop": salto, "minutos_stop": (i_stop - i0) if i_stop else None,
            "llega": {k: mfe >= k for k in OBJETIVOS}, "fijo": {k: v[1] for k, v in fijos.items()},
            "fijo_tipo": {k: v[0] for k, v in fijos.items()}, "neto": neto}


def señales(simbolo, exigir_filtro, fees):
    d, _ = preparar(simbolo, con_filtro=True, exigir_filtro=exigir_filtro)
    justo = precio_justo(simbolo)
    out = []
    for e in d.ejecutar():
        if not e.entrada:
            continue
        en = e.entrada
        fila = {"moneda": simbolo.replace("_USDT", ""), "filtro_ok": e.filtro.get("ok"),
                "avisos_madrid": " | ".join(hora_madrid(d.t[i]) for i in e.avisos),
                "entrada_madrid": hora_madrid(d.t[en["i"]]), "minimo_madrid": hora_madrid(d.t[en["i_minimo"]]),
                "entrada": en["precio"], "minimo": en["minimo"], "atr": en["atr"],
                "p2": e.p2, "p1": e.p1, "l3": e.l3, "toques": len(e.toques)}
        for nombre, stop in en["stops"].items():
            clave = nombre[0]  # A, B o C
            fila[f"stop_{clave}"] = stop
            real = simular(d, justo, en["i"], en["precio"], stop, fees["taker"], fees["maker"], fees["taker"])
            ideal = simular(d, justo, en["i_minimo"], en["minimo"], stop, fees["maker"], fees["maker"], fees["taker"])
            fila[f"res_{clave}"] = real
            fila[f"ideal_{clave}"] = ideal
        out.append(fila)
    return out, (d.t[-1] - d.t[0]) / 86400


CASOS_DISEÑO = {("MERL", "2026-09-29 22:01"), ("AAVE", "2026-10-01 04:49")}


def wilson(k, n, z=1.96):
    """Intervalo de confianza del 95 % para una proporción (método de Wilson)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return (round(100 * (c - m)), round(100 * (c + m)))


def resumen(filas, dias, clave, modo="res"):
    sims = [f[f"{modo}_{clave}"] for f in filas if f[f"{modo}_{clave}"]]
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


def main():
    RES.mkdir(exist_ok=True)
    universo = json.loads((DATOS / "universo.json").read_text())
    disponibles = [u for u in universo
                   if (DATOS / f"{u['simbolo']}_1m_fair.csv.gz").exists()
                   and not any(x in u["simbolo"] for x in EXCLUIR + NO_CRIPTO)]
    resultados = {}
    for exigir in (False, True):
        todas, dias = [], 0
        for u in disponibles:
            filas, dias_s = señales(u["simbolo"], exigir, u)
            todas += filas
            dias = max(dias, dias_s)
        resultados["con filtro" if exigir else "sin filtro"] = (todas, dias)
    # Tabla
    tabla = []
    for nombre, (filas, dias) in resultados.items():
        for clave, desc in (("A", "−0,3 ATR"), ("B", "−1 ATR"), ("C", "bajo zona 4")):
            for modo in ("res", "ideal"):
                fila = {"filtro": nombre, "stop": f"{clave} ({desc})", "entrada": "cierre" if modo == "res" else "ideal"}
                fila.update(resumen(filas, dias, clave, modo))
                tabla.append(fila)
            # Fuera de muestra: sin los dos casos con los que se diseñó el detector
            fuera = [f for f in filas if (f["moneda"], f["entrada_madrid"]) not in CASOS_DISEÑO]
            fila = {"filtro": nombre + " · sin MERL ni AAVE", "stop": f"{clave} ({desc})", "entrada": "cierre"}
            fila.update(resumen(fuera, dias, clave, "res"))
            tabla.append(fila)
    (RES / "tabla.json").write_text(json.dumps({"monedas": len(disponibles), "dias": round(dias, 1),
                                                "tabla": tabla}, indent=1, ensure_ascii=False))
    # CSV de señales (corrida sin filtro, con la columna filtro_ok)
    filas = resultados["sin filtro"][0]
    campos = ["moneda", "filtro_ok", "avisos_madrid", "minimo_madrid", "entrada_madrid", "entrada", "minimo",
              "atr", "p2", "p1", "l3", "toques"]
    with open(RES / "señales.csv", "w", newline="") as f:
        w = csv.writer(f)
        cab = campos[:]
        for k in "ABC":
            cab += [f"stop_{k}", f"R_max_{k}", f"salta_stop_{k}", f"min_hasta_stop_{k}", f"neto_5R_{k}", f"neto_10R_{k}"]
        w.writerow(cab)
        for x in filas:
            fila = [x[c] for c in campos]
            for k in "ABC":
                s = x[f"res_{k}"]
                fila += [x[f"stop_{k}"], round(s["mfe"], 2) if s else "", s["stop"] if s else "",
                         s["minutos_stop"] if s else "", round(s["neto"][5], 2) if s else "",
                         round(s["neto"][10], 2) if s else ""]
            w.writerow(fila)
    # 10 buenas y 10 malas (stop A, entrada al cierre)
    validas = [x for x in filas if x["res_A"]]
    buenas = sorted(validas, key=lambda x: -x["res_A"]["mfe"])[:10]
    malas = sorted([x for x in validas if x["res_A"]["stop"]],
                   key=lambda x: (x["res_A"]["mfe"], x["res_A"]["minutos_stop"]))[:10]
    with open(RES / "revisar.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tipo", "moneda", "avisos_madrid", "entrada_madrid", "entrada", "stop_A", "l3", "R_max_A", "min_hasta_stop_A"])
        for tipo, grupo in (("buena", buenas), ("mala", malas)):
            for x in grupo:
                w.writerow([tipo, x["moneda"], x["avisos_madrid"], x["entrada_madrid"], x["entrada"],
                            x["stop_A"], x["l3"], round(x["res_A"]["mfe"], 2), x["res_A"]["minutos_stop"]])
    return tabla


if __name__ == "__main__":
    for fila in main():
        print(fila)
