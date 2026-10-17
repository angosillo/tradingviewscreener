"""Histórico largo de 1 minuto de los perpetuos USDT-M de Binance (archivo público data.binance.vision).

MEXC solo guarda unos 30 días de velas de 1 minuto. Binance publica años de velas de 1 minuto y también
las del precio de marca (el equivalente al precio justo de MEXC, con el que salta la liquidación).
Se usa solo para medir el patrón con muchas más señales; las comisiones siguen siendo las de MEXC.

Guarda en reversiones/datos_binance/ (no se sube a git), con el mismo formato que mexc.py:
  <SIMBOLO>_1m.csv.gz        velas de 1 minuto del último precio
  <SIMBOLO>_1m_fair.csv.gz   velas de 1 minuto del precio de marca

<SIMBOLO> es el nombre de MEXC (p. ej. PEPE_USDT), aunque en Binance sea 1000PEPEUSDT.

Uso:
  python3 -m reversiones.binance descargar 2025-10 2026-09 2026-10-16
      meses completos de 2025-10 a 2026-09 y días sueltos de octubre de 2026 hasta el 16
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from .backtest import es_cripto
from .mexc import DATOS as DATOS_MEXC

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
WEB = "https://data.binance.vision/data/futures/um"
DATOS = Path(__file__).resolve().parent / "datos_binance"
SERIES = {"1m": "klines", "1m_fair": "markPriceKlines"}
# Monedas que en Binance tienen otro nombre
ALIAS = {"PUMPFUN": "PUMP", "FILECOIN": "FIL", "ZKSYNC": "ZK", "TRUMPOFFICIAL": "TRUMP", "MONAD": "MON"}


def _get(url: str) -> bytes | None:
    for intento in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 * (intento + 1))
    raise RuntimeError(f"Binance no respondió: {url}")


def simbolos_binance() -> set[str]:
    """Todos los perpetuos USDT-M con histórico en el archivo."""
    out, marca = set(), ""
    while True:
        xml = _get(f"{S3}?prefix=data/futures/um/monthly/klines/&delimiter=/&marker={marca}").decode()
        nuevos = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^/<]+)/</Prefix>", xml)
        out.update(nuevos)
        if "<IsTruncated>true</IsTruncated>" not in xml:
            return out
        marca = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml).group(1)


def equivalente(simbolo_mexc: str, disponibles: set[str]) -> str | None:
    base = simbolo_mexc.replace("_USDT", "")
    base = ALIAS.get(base, base)
    for cand in (base, "1000" + base, "1000000" + base, "1M" + base):
        if cand + "USDT" in disponibles:
            return cand + "USDT"
    return None


def _filas(zbytes: bytes) -> list[tuple]:
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        texto = z.read(z.namelist()[0]).decode()
    out = []
    for x in csv.reader(io.StringIO(texto)):
        if not x or not x[0].isdigit():  # cabecera (los archivos recientes la traen)
            continue
        t = int(x[0])
        t = t // 1_000_000 if t > 10 ** 14 else t // 1000  # microsegundos o milisegundos → segundos
        out.append((t, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])))
    return out


def descargar(simbolo_mexc: str, simbolo_bn: str, meses: list[str], dias: list[str]) -> str:
    for tipo, serie in SERIES.items():
        ruta = DATOS / f"{simbolo_mexc}_{tipo}.csv.gz"
        if ruta.exists():
            continue
        filas = {}
        urls = [f"{WEB}/monthly/{serie}/{simbolo_bn}/1m/{simbolo_bn}-1m-{m}.zip" for m in meses]
        urls += [f"{WEB}/daily/{serie}/{simbolo_bn}/1m/{simbolo_bn}-1m-{d}.zip" for d in dias]
        for u in urls:
            z = _get(u)
            if z:
                filas.update((f[0], f) for f in _filas(z))
        if not filas:
            return f"{simbolo_mexc}: sin datos"
        tmp = ruta.with_suffix(".tmp")
        with gzip.open(tmp, "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["t", "o", "h", "l", "c", "v"])
            w.writerows(filas[k] for k in sorted(filas))
        tmp.rename(ruta)
    return simbolo_mexc


def cargar(simbolo: str, tipo: str) -> list[tuple]:
    with gzip.open(DATOS / f"{simbolo}_{tipo}.csv.gz", "rt") as f:
        r = csv.reader(f)
        next(r)
        return [(int(x[0]), *map(float, x[1:])) for x in r]


def _meses(desde: str, hasta: str) -> list[str]:
    a, m = map(int, desde.split("-"))
    out = []
    while f"{a:04d}-{m:02d}" <= hasta:
        out.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return out


def main(desde: str, hasta: str, ultimo_dia: str):
    DATOS.mkdir(exist_ok=True)
    meses = _meses(desde, hasta)
    a, m = map(int, hasta.split("-"))
    d = date(a + (m == 12), m % 12 + 1, 1)
    dias = []
    while d.isoformat() <= ultimo_dia:
        dias.append(d.isoformat())
        d += timedelta(days=1)
    disponibles = simbolos_binance()
    universo = json.loads((DATOS_MEXC / "universo.json").read_text())
    pares, faltan = [], []
    for u in universo:
        if not es_cripto(u["simbolo"]):
            continue
        bn = equivalente(u["simbolo"], disponibles)
        (pares.append((u["simbolo"], bn)) if bn else faltan.append(u["simbolo"]))
    (DATOS / "pares.json").write_text(json.dumps({"pares": pares, "sin_binance": faltan, "meses": meses,
                                                 "dias": dias}, indent=1))
    print(f"{len(pares)} monedas en Binance; sin equivalente: {faltan}", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        for r in pool.map(lambda p: descargar(p[0], p[1], meses, dias), pares):
            print("ok", r, flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "descargar":
        main(sys.argv[2], sys.argv[3], sys.argv[4])
