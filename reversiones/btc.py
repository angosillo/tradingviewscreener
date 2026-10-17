"""¿Funciona mejor el setup cuando Bitcoin está en modo alcista?

Para cada aviso del histórico de Binance (señales_binance*.csv) se mira el estado de BTC en ese minuto, solo con
velas ya cerradas, y se comparan los resultados de las señales con BTC alcista y sin él.

Definiciones de «BTC alcista» (fijadas antes de mirar los resultados):
  tendencia 1h    BTC por encima de su EMA20 de 1 h y esa EMA20 más alta que hace 3 h
  tendencia 4h    BTC por encima de su EMA20 de 4 h y esa EMA20 más alta que hace 8 h (2 velas)
  momentum 1h     BTC sube en la última hora
  barrido 4h      en las últimas 24 h, una vela de 4 h perdió el mínimo del rango de los 5 días anteriores
                  y BTC ya ha vuelto por encima del máximo de esa vela del barrido
  barrido 1h      lo mismo en 1 h: rango de las 48 h anteriores, barrido en las últimas 12 h

Uso:  python3 -m reversiones.btc                     (señales_binance.csv)
      python3 -m reversiones.btc _sin_barrido_min    (señales_binance_sin_barrido_min.csv)
"""

from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import datetime

from . import binance
from .backtest import MADRID, RES, wilson
from .detector import ema

SALIDA = RES / "limite"


def agrupar(v, seg):
    """Velas de 1 m → velas de 'seg' segundos alineadas a UTC: listas t (cierre), o, h, l, c."""
    out = {"t": [], "o": [], "h": [], "l": [], "c": []}
    actual = None
    for t, o, h, l, c, _ in v:
        k = t - t % seg
        if k != actual:
            out["t"].append(k + seg)
            out["o"].append(o), out["h"].append(h), out["l"].append(l), out["c"].append(c)
            actual = k
        else:
            out["h"][-1] = max(out["h"][-1], h)
            out["l"][-1] = min(out["l"][-1], l)
            out["c"][-1] = c
    return out


class EstadoBTC:
    def __init__(self):
        v = binance.cargar("BTC_USDT", "1m")
        self.t1 = [x[0] for x in v]
        self.c1 = [x[4] for x in v]
        self.h1 = agrupar(v, 3600)
        self.h4 = agrupar(v, 4 * 3600)
        for g in (self.h1, self.h4):
            g["e20"] = ema(g["c"], 20)

    def _cerradas(self, g, ts):
        """Número de velas de g ya cerradas en ts."""
        return bisect.bisect_right(g["t"], ts)

    def _barrido(self, g, n, rango, recientes):
        if n < rango + recientes:
            return False
        r_lo = min(g["l"][n - recientes - rango:n - recientes])
        ult = range(n - recientes, n)
        j = min(ult, key=lambda k: g["l"][k])
        return g["l"][j] < r_lo and self.precio > g["h"][j] and self.precio > r_lo

    def estado(self, ts):
        """ts = cierre de la vela del aviso (segundos UTC)."""
        i = bisect.bisect_right(self.t1, ts - 60) - 1  # última vela de 1 m cerrada
        self.precio = self.c1[i]
        n1, n4 = self._cerradas(self.h1, ts), self._cerradas(self.h4, ts)
        e1, e4 = self.h1["e20"], self.h4["e20"]
        return {
            "tendencia 1h": n1 > 23 and self.precio > e1[n1 - 1] and e1[n1 - 1] > e1[n1 - 4],
            "tendencia 4h": n4 > 22 and self.precio > e4[n4 - 1] and e4[n4 - 1] > e4[n4 - 3],
            "momentum 1h": i >= 60 and self.precio > self.c1[i - 60],
            "barrido 4h": self._barrido(self.h4, n4, 30, 6),
            "barrido 1h": self._barrido(self.h1, n1, 48, 12),
        }


def stats(filas):
    n = len(filas)
    if not n:
        return {"señales": 0}
    k10 = sum(f["rmax"] >= 10 for f in filas)
    m = sum(f["neto"] for f in filas) / n
    ee = (sum((f["neto"] - m) ** 2 for f in filas) / max(n - 1, 1) / n) ** 0.5  # error típico de la media
    return {"señales": n, "llega_10R": round(100 * k10 / n, 1), "IC95_llega_10R": wilson(k10, n),
            "esperanza_10R": round(m, 2), "IC95_esperanza": (round(m - 1.96 * ee, 2), round(m + 1.96 * ee, 2))}


def main(sufijo=""):
    btc = EstadoBTC()
    filas = []
    for x in csv.DictReader(open(SALIDA / f"señales_binance{sufijo}.csv")):
        if not x["cierre A · neto_10R"] or x["moneda"] == "BTC":
            continue
        ts = int(datetime.strptime(x["aviso"], "%Y-%m-%d %H:%M").replace(tzinfo=MADRID).timestamp()) + 60
        filas.append({"rmax": float(x["cierre A · R_max"]), "neto": float(x["cierre A · neto_10R"]),
                      **btc.estado(ts)})
    res = {"señales": len(filas), "todas": stats(filas)}
    for k in ("tendencia 1h", "tendencia 4h", "momentum 1h", "barrido 4h", "barrido 1h"):
        res[k] = {"BTC alcista": stats([f for f in filas if f[k]]), "no": stats([f for f in filas if not f[k]])}
    (SALIDA / f"btc_binance{sufijo}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
