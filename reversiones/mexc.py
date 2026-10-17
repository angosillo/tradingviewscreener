"""Descarga de datos de la API pública de futuros de MEXC (perpetuos USDT-M).

Guarda en reversiones/datos/ (no se sube a git):
  <SIMBOLO>_1m.csv.gz        velas de 1 minuto del último precio
  <SIMBOLO>_1m_fair.csv.gz   velas de 1 minuto del precio justo (con el que salta la liquidación)
  <SIMBOLO>_4h.csv.gz / _1d.csv.gz   velas para el filtro de contexto
  universo.json              símbolos elegidos y su comisión taker/maker

Uso:
  python3 -m reversiones.mexc universo 50          # elige los 50 perpetuos cripto con más volumen
  python3 -m reversiones.mexc descargar 30         # descarga los últimos 30 días del universo
"""

from __future__ import annotations

import csv
import gzip
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://contract.mexc.com/api/v1/contract"
DATOS = Path(__file__).resolve().parent / "datos"
INTERVALOS = {"1m": ("Min1", 60), "4h": ("Hour4", 4 * 3600), "1d": ("Day1", 86400)}

# Perpetuos que no son cripto: acciones, materias primas, índices y ETFs tokenizados
NO_CRIPTO = ("STOCK", "XAU", "SILVER", "OIL", "SPY", "SPX", "NAS", "NICKEL", "COPPER", "GAS",
             "TESLA", "NVIDIA", "APPLE", "AMAZON", "META", "GOOGL", "MSFT", "SOXL", "KORU", "SNXX",
             "EUR", "GBP", "JPY", "PLAT", "PALL", "XPT", "EWY", "DRAM", "MUU", "ZINC")


def _get(url: str) -> dict:
    for intento in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            r = json.load(urllib.request.urlopen(req, timeout=30))
            if r.get("success"):
                return r["data"]
        except Exception:
            pass
        time.sleep(1.5 * (intento + 1))
    raise RuntimeError(f"MEXC no respondió: {url}")


def universo(n: int, incluir: tuple[str, ...] = ("MERL_USDT", "AAVE_USDT")) -> list[dict]:
    tick = [t for t in _get(f"{BASE}/ticker") if t["symbol"].endswith("_USDT")]
    tick = [t for t in tick if not any(k in t["symbol"] for k in NO_CRIPTO)]
    tick.sort(key=lambda t: -float(t.get("amount24") or 0))
    simbolos = [t["symbol"] for t in tick[:n]]
    simbolos += [s for s in incluir if s not in simbolos]
    salida = []
    for s in simbolos:
        d = _get(f"{BASE}/detail?symbol={s}")
        salida.append({"simbolo": s, "taker": float(d.get("takerFeeRate") or 0),
                       "maker": float(d.get("makerFeeRate") or 0), "tick": float(d.get("priceUnit") or 0)})
    DATOS.mkdir(parents=True, exist_ok=True)
    (DATOS / "universo.json").write_text(json.dumps(salida, indent=1))
    return salida


def klines(simbolo: str, intervalo: str, inicio: datetime, fin: datetime, justo: bool = False) -> list[tuple]:
    nombre, seg = INTERVALOS[intervalo]
    ruta = "kline/fair_price" if justo else "kline"
    filas, t, t_fin = {}, int(inicio.timestamp()), int(fin.timestamp())
    paso = 1500 * seg
    while t < t_fin:
        d = _get(f"{BASE}/{ruta}/{simbolo}?interval={nombre}&start={t}&end={min(t_fin, t + paso)}")
        for i, ts in enumerate(d.get("time", [])):
            vol = d["vol"][i] if "vol" in d else 0
            filas[ts] = (ts, d["open"][i], d["high"][i], d["low"][i], d["close"][i], vol)
        t += paso
    return [filas[k] for k in sorted(filas) if int(inicio.timestamp()) <= k <= t_fin]


def guardar(ruta: Path, filas: list[tuple]) -> None:
    with gzip.open(ruta, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "o", "h", "l", "c", "v"])
        w.writerows(filas)


def cargar(simbolo: str, tipo: str) -> list[tuple]:
    """tipo: '1m', '1m_fair', '4h' o '1d'. Devuelve tuplas (t, o, h, l, c, v) con floats."""
    with gzip.open(DATOS / f"{simbolo}_{tipo}.csv.gz", "rt") as f:
        r = csv.reader(f)
        next(r)
        return [(int(x[0]), *map(float, x[1:])) for x in r]


def descargar(simbolo: str, dias: int, fin: datetime) -> str:
    inicio = fin - timedelta(days=dias)
    tareas = [("1m", inicio, False), ("1m_fair", inicio, True),
              ("4h", fin - timedelta(days=dias + 40), False), ("1d", fin - timedelta(days=dias + 120), False)]
    for tipo, desde, justo in tareas:
        ruta = DATOS / f"{simbolo}_{tipo}.csv.gz"
        if ruta.exists():
            continue
        guardar(ruta, klines(simbolo, tipo.replace("_fair", ""), desde, fin, justo))
    return simbolo


if __name__ == "__main__":
    if sys.argv[1] == "universo":
        for u in universo(int(sys.argv[2])):
            print(u)
    elif sys.argv[1] == "descargar":
        dias = int(sys.argv[2])
        fin = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        simbolos = [u["simbolo"] for u in json.loads((DATOS / "universo.json").read_text())]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for s in pool.map(lambda s: descargar(s, dias, fin), simbolos):
                print("ok", s, flush=True)
