"""Radar en tiempo real: vigila los perpetuos de MEXC minuto a minuto y avisa por Telegram.

No opera: solo avisa para que mires el gráfico tú. Usa la API pública de MEXC (sin claves).

Mensajes:
  🔔 AVISO     2.º toque de la línea 3 (y cada toque siguiente)
  ✅ ENTRADA   el detector confirma el mínimo más alto (con stop y objetivo 10R orientativos)
  ❌ CANCELADO el patrón de un aviso ya enviado se cae
  Un resumen diario a las 09:00 de Madrid, para saber que sigue vivo.
Cada mensaje incluye si BTC está en tendencia alcista en 4 h (el filtro que mejor separó las señales en el
histórico de Binance: unas +0,4R por operación con BTC alcista frente a −0,26R sin él).

Configuración (variables de entorno o archivo .env en la raíz del repo):
  TELEGRAM_TOKEN      token del bot de Telegram (obligatorio salvo con --prueba)
  TELEGRAM_CHAT_ID    chat al que se envían los avisos (obligatorio salvo con --prueba)
  MONEDAS=150         perpetuos con más volumen que se vigilan (luego se quitan los que no son cripto)
  DIAS_HISTORIA=30    días de velas de 1 m que se cargan al arrancar (como en el backtest)
  BARRIDO_MIN=0       barrido mínimo en ATR (0 = sin exigirlo, la variante con más señales)
  SOLO_BTC_ALCISTA=0  1 = solo avisa cuando BTC está en tendencia alcista en 4 h

Uso:
  python3 -m reversiones.vivo              en marcha (pensado para systemd)
  python3 -m reversiones.vivo --prueba     sin Telegram: escribe los mensajes en pantalla
  python3 -m reversiones.vivo --telegram   envía un mensaje de prueba y sale
"""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from array import array
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .backtest import MADRID, es_cripto
from .detector import Detector, Params, ema, pivotes_altos
from .mexc import BASE, _get, universo

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = Path(__file__).resolve().parent / "resultados" / "alertas.jsonl"


def cargar_env():
    ruta = RAIZ / ".env"
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            if "=" in linea and not linea.strip().startswith("#"):
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ahora():
    return int(time.time())


def madrid(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(MADRID).strftime("%H:%M")


def fmt(x):
    """Precio con unas 5 cifras significativas y coma decimal: 0,029050 · 1,2345 · 162,43."""
    dec = max(2, 4 - math.floor(math.log10(abs(x)))) if x else 2
    return f"{x:.{dec}f}".replace(".", ",")


# ----------------------------------------------------------------------------- detector incremental


class Rango:
    """Máximo/mínimo de un rango sobre una serie que crece (sustituye a TablaMax, que es estática)."""

    def __init__(self, x, f, con_indice=False):
        self.x, self.f, self.idx = x, f, con_indice

    def q(self, a, b):
        if a > b:
            return None
        trozo = self.x[a:b + 1]
        v = self.f(trozo)
        if not self.idx:
            return v
        j = a + trozo.index(v)  # primera posición, como en el detector
        return (v, -j) if self.f is max else (v, j)


class DetectorVivo(Detector):
    """El mismo detector, pero alimentado vela a vela. Las reglas son las de detector.py."""

    def __init__(self, velas, p: Params):
        self.t = array("q", (int(v[0]) for v in velas))
        self.o, self.h, self.l, self.c = (array("d", (v[k] for v in velas)) for k in (1, 2, 3, 4))
        self.p, self.filtro, self.exigir_filtro = p, None, False
        self.ventana = p.horas_suelo * 60
        self.a = array("d")
        self._tr = array("d")
        for i in range(len(self.c)):
            self._atr(i)
        self.maxh, self.minl = Rango(self.h, max), Rango(self.l, min)
        self.maxh_i, self.minl_i = Rango(self.h, max, True), Rango(self.l, min, True)
        self.piv = pivotes_altos(self.h, p.fuerza_pivote)
        self.activa = None
        # Reconstruye el estado con las últimas 6 h (un patrón vive como mucho unas 3 h)
        for i in range(max(60, len(self.c) - 360), len(self.c)):
            self.paso(i)

    def _atr(self, i, n=14):
        h, l, c = self.h, self.l, self.c
        self._tr.append(h[i] - l[i] if i == 0 else max(h[i], c[i - 1]) - min(l[i], c[i - 1]))
        if i < n:
            self.a.append(0.0)
        elif i == n:
            a = sum(self._tr[1:n + 1]) / n
            for k in range(n):
                self.a[k] = a
            self.a.append(a)
        else:
            self.a.append((self.a[-1] * (n - 1) + self._tr[i]) / n)

    def añadir(self, vela):
        """Añade una vela cerrada y la procesa. Devuelve los eventos de esa vela."""
        t, o, h, l, c = vela[:5]
        self.t.append(int(t)), self.o.append(o), self.h.append(h), self.l.append(l), self.c.append(c)
        i = len(self.c) - 1
        self._atr(i)
        k, m = self.p.fuerza_pivote, i - self.p.fuerza_pivote
        if m >= k and self.h[m] > max(self.h[m - k:m]) and self.h[m] >= max(self.h[m + 1:m + k + 1]):
            self.piv.append(m)
        return self.paso(i)

    def paso(self, i):
        """Lo mismo que hace Detector.ejecutar() en la vela i."""
        eventos, e = [], self.activa
        if e is not None:
            n_avisos = len(e.avisos)
            r = self._avanzar(e, i)
            if len(e.avisos) > n_avisos:
                eventos.append(("aviso", e))
            if r:
                e.fin, e.i_fin = r, i
                eventos.append(("entrada" if r == "entrada" else "fin", e))
                self.activa = None
        nueva = self._nueva(i)
        if nueva is not None:
            if self.activa is not None and self.activa.entrada is None:
                self.activa.fin, self.activa.i_fin = "sustituida por otra más reciente", i
                eventos.append(("fin", self.activa))
                self.activa = None
            if self.activa is None:
                self.activa = nueva
        return eventos


# ----------------------------------------------------------------------------- MEXC y BTC


_ritmo = threading.Lock()
_ultima = [0.0]


def _get_lento(url):
    """Como mucho unas 8 peticiones por segundo (el límite público de MEXC es 20 cada 2 s)."""
    with _ritmo:
        espera = _ultima[0] + 0.12 - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        _ultima[0] = time.monotonic()
    return _get(url)


def velas_mexc(simbolo, desde, hasta):
    """Velas de 1 m CERRADAS entre desde y hasta (segundos)."""
    out, t = {}, desde
    while t < hasta:
        d = _get_lento(f"{BASE}/kline/{simbolo}?interval=Min1&start={t}&end={min(hasta, t + 1500 * 60)}")
        for k, ts in enumerate(d.get("time", [])):
            if ts + 60 <= ahora():
                out[ts] = (ts, d["open"][k], d["high"][k], d["low"][k], d["close"][k])
        t += 1500 * 60
    return [out[k] for k in sorted(out) if desde <= k <= hasta]


def btc_alcista_4h(precio_btc):
    """BTC por encima de su EMA20 de 4 h y esa EMA20 subiendo (más alta que hace 2 velas). Solo velas cerradas."""
    fin = ahora()
    d = _get(f"{BASE}/kline/BTC_USDT?interval=Hour4&start={fin - 120 * 4 * 3600}&end={fin}")
    cierres = [c for ts, c in zip(d["time"], d["close"]) if ts + 4 * 3600 <= fin]
    if len(cierres) < 25:
        return None
    e = ema(cierres, 20)
    return precio_btc > e[-1] and e[-1] > e[-3]


# ----------------------------------------------------------------------------- Telegram


class Telegram:
    def __init__(self, prueba=False):
        self.prueba = prueba
        self.token, self.chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not prueba and not (self.token and self.chat):
            sys.exit("Faltan TELEGRAM_TOKEN y TELEGRAM_CHAT_ID (en .env o en el entorno)")

    def enviar(self, texto):
        if self.prueba:
            print(texto, "\n", flush=True)
            return
        datos = urllib.parse.urlencode({"chat_id": self.chat, "text": texto, "parse_mode": "HTML",
                                        "disable_web_page_preview": "true"}).encode()
        for intento in range(3):
            try:
                urllib.request.urlopen(f"https://api.telegram.org/bot{self.token}/sendMessage", datos, timeout=20)
                return
            except Exception as ex:
                print("Telegram falló:", ex, flush=True)
                time.sleep(3)


def btc_txt(estado):
    return {True: "BTC 4h: alcista ✅", False: "BTC 4h: no alcista ⚠️", None: "BTC 4h: sin datos"}[estado]


def mensaje(tipo, moneda, d, e, btc):
    i = len(d.c) - 1
    enlace = f'<a href="https://www.mexc.com/futures/{moneda}_USDT">MEXC {moneda}</a>'
    if tipo == "aviso":
        n = len(e.toques)
        previo = e.lows_tramo[-1] if e.lows_tramo else None
        return (f"🔔 <b>{moneda}</b> · AVISO ({n}.º toque de la línea 3) · {madrid(d.t[i] + 60)}\n"
                f"Línea 3: {fmt(e.l3)} · línea 2: {fmt(e.p2)}\n"
                + (f"Mínimo anterior: {fmt(previo)} (si lo pierde, no vale)\n" if previo else "")
                + f"Espera un mínimo más alto y la vela que lo confirme.\n{btc_txt(btc)}\n{enlace}")
    if tipo == "entrada":
        en = e.entrada
        stop = en["stops"]["A_-0.3ATR"]
        R = en["precio"] - stop
        pct = f"{100 * R / en['precio']:.2f}".replace(".", ",")
        return (f"✅ <b>{moneda}</b> · ENTRADA confirmada · {madrid(d.t[en['i']] + 60)}\n"
                f"Precio: {fmt(en['precio'])} · mínimo más alto: {fmt(en['minimo'])}\n"
                f"Stop orientativo: {fmt(stop)} (1R = {pct} %)\n"
                f"Objetivo 10R: {fmt(en['precio'] + 10 * R)}\n{btc_txt(btc)}\n{enlace}")
    return f"❌ <b>{moneda}</b> · patrón cancelado ({e.fin}) · {madrid(d.t[i] + 60)}"


# ----------------------------------------------------------------------------- bucle principal


def main(prueba=False):
    cargar_env()
    tg = Telegram(prueba)
    p = replace(Params(), barrido_min=float(os.environ.get("BARRIDO_MIN", "0")))
    solo_btc = os.environ.get("SOLO_BTC_ALCISTA", "0") == "1"
    dias = int(os.environ.get("DIAS_HISTORIA", "30"))
    simbolos = [u["simbolo"] for u in universo(int(os.environ.get("MONEDAS", "150")), incluir=("BTC_USDT",))
                if es_cripto(u["simbolo"])]
    print(f"Cargando {dias} días de {len(simbolos)} monedas…", flush=True)
    fin = ahora() - ahora() % 60
    detectores = {}

    def iniciar(s):
        v = velas_mexc(s, fin - dias * 86400, fin)
        return s, (DetectorVivo(v, p) if len(v) > 1500 else None)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for s, d in pool.map(iniciar, simbolos):
            if d:
                detectores[s] = d
    tg.enviar(f"📡 Radar de reversiones en marcha: {len(detectores)} monedas de MEXC"
              f"{' · solo con BTC alcista en 4 h' if solo_btc else ''}.")
    avisados, btc, btc_t, resumen_dia, hoy = set(), None, 0, None, {"avisos": 0, "entradas": 0}

    def actualizar(s):
        d = detectores[s]
        try:
            nuevas = velas_mexc(s, d.t[-1] + 60, ahora())
        except Exception as ex:
            print(s, "error:", ex, flush=True)
            return s, []
        eventos = []
        for v in nuevas:
            eventos += d.añadir(v)
        return s, eventos

    while True:
        time.sleep(max(1, 60 - ahora() % 60 + 3))  # 3 s después de cerrar cada vela
        with ThreadPoolExecutor(max_workers=4) as pool:
            resultados = list(pool.map(actualizar, list(detectores)))
        if ahora() - btc_t > 300 and "BTC_USDT" in detectores:
            try:
                btc, btc_t = btc_alcista_4h(detectores["BTC_USDT"].c[-1]), ahora()
            except Exception as ex:
                print("BTC 4h error:", ex, flush=True)
        for s, eventos in resultados:
            moneda, d = s.replace("_USDT", ""), detectores[s]
            for tipo, e in eventos:
                clave = (s, e.i_ruptura)
                if tipo == "fin" and clave not in avisados:
                    continue  # solo se avisa de cancelaciones de patrones ya avisados
                if solo_btc and btc is not True and tipo != "fin":
                    continue
                if tipo == "aviso":
                    avisados.add(clave)
                    hoy["avisos"] += 1
                if tipo == "entrada":
                    hoy["entradas"] += 1
                tg.enviar(mensaje(tipo, moneda, d, e, btc))
                REGISTRO.parent.mkdir(exist_ok=True)
                with open(REGISTRO, "a") as f:
                    f.write(json.dumps({"ts": d.t[-1], "moneda": moneda, "tipo": tipo, "btc_4h": btc,
                                        "l3": e.l3, "p2": e.p2, "fin": e.fin,
                                        "entrada": e.entrada and {k: e.entrada[k] for k in ("precio", "minimo")},
                                        "stop": e.entrada and e.entrada["stops"]["A_-0.3ATR"]}) + "\n")
        local = datetime.now(MADRID)
        if local.hour == 9 and resumen_dia != local.date():
            resumen_dia = local.date()
            tg.enviar(f"📡 Radar activo · {len(detectores)} monedas · últimas 24 h: {hoy['avisos']} avisos, "
                      f"{hoy['entradas']} entradas · {btc_txt(btc)}")
            hoy = {"avisos": 0, "entradas": 0}


if __name__ == "__main__":
    if "--telegram" in sys.argv:
        cargar_env()
        Telegram().enviar("✅ Prueba del radar de reversiones: Telegram funciona.")
    else:
        main(prueba="--prueba" in sys.argv)
