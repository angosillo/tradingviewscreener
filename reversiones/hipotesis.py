"""Backtest de hipótesis del setup de reversión (casos MERL 29-sep y AAVE 1-oct-2026).

Un único detector amplio, con lo imprescindible, y las hipótesis medidas como características de cada señal
(no se exigen). Todo con lo que se sabía en cada minuto; todas las distancias en ATR(14) de 1 m.

Detector:
  1. Impulso: tramo alcista de ≥5 ATR en ≤120 min. El punto 1 es el mínimo donde empieza el tramo en un
     zigzag de 5 ATR (un retroceso de ≥5 ATR corta el tramo).
  2. Nivel (línea 3): el máximo del impulso (T1), fijado cuando una vela cierra a más de 1 ATR por debajo.
     Toque = el máximo vuelve a ±1 ATR del nivel después de haber cerrado por debajo de esa zona.
  3. Entrada: tras el 2.º toque, el primer mínimo de retroceso más alto que el del tramo anterior entre dos
     toques; se entra al cierre de la primera vela que cierra por encima del máximo de la vela de ese mínimo,
     de 5 a 60 min después de T1. Entre dos toques, al menos una vela tiene que cerrar por debajo de la zona.
  4. Cancelación: cierre a más de 0,5 ATR bajo la línea 2, cierre a más de 1 ATR sobre la línea 3 sin entrada,
     o más de 60 min desde T1. Línea 2 = el máximo más alto, por debajo de la zona del nivel, de las 6 h previas
     al punto 1 (el máximo que rompió el impulso).
Las tolerancias del patrón usan el ATR de T1; los stops y las distancias de la entrada, el ATR de la entrada.

Uso:  python3 -m reversiones.hipotesis            (MEXC, todo el universo descargado)
"""

from __future__ import annotations

import bisect
import json
import sys
from multiprocessing import Pool
from statistics import median

from . import mexc
from .backtest import RES, es_cripto, hora_madrid
from .detector import TablaMax, _zigzag_minimos, atr, ema

SALIDA = RES / "hipotesis"

# ---------------------------------------------------------------- parámetros (fijados antes de ver resultados)
IMPULSO_ATR, IMPULSO_MIN = 5.0, 120
ZIGZAG_ATR = 5.0  # un retroceso de ≥5 ATR corta el tramo alcista
TOL = 1.0  # toques a ±1 ATR del nivel; rotura = cierre a más de 1 ATR por encima
LINEA2_CANCEL = 0.5
ZONA4_MIN, ZONA4_MAX = 5, 60
VENTANA_L2 = 360  # 6 h
VENTANA_BARRIDO = 360  # el mínimo barrido está en las 6 h previas al punto 1
DIAS_REACCIONES, DIAS_NIVELES = 3, 7
SEP_REACCIONES = 3600  # reacciones separadas al menos 1 h
MAX_VELAS = 480  # cierre forzoso a las 8 h
OBJETIVOS = (3, 5, 10)
STOPS = ("S1", "S2", "S3")
SALIDAS = ("3R", "5R", "10R", "nivel")


def rsi(c, n=14):
    out = [50.0] * len(c)
    if len(c) <= n:
        return out
    sube = sum(max(c[k] - c[k - 1], 0) for k in range(1, n + 1)) / n
    baja = sum(max(c[k - 1] - c[k], 0) for k in range(1, n + 1)) / n
    for k in range(n + 1, len(c)):
        d = c[k] - c[k - 1]
        sube = (sube * (n - 1) + max(d, 0)) / n
        baja = (baja * (n - 1) + max(-d, 0)) / n
        out[k] = 100.0 if baja == 0 else 100 - 100 / (1 + sube / baja)
    return out


def agrupar(t, h, l, seg):
    """Velas de 'seg' segundos (alineadas a UTC) a partir de las de 1 m: (inicio, máximo, mínimo)."""
    T, H, L = [], [], []
    for k in range(len(t)):
        b = t[k] - t[k] % seg
        if not T or T[-1] != b:
            T.append(b), H.append(h[k]), L.append(l[k])
        else:
            H[-1], L[-1] = max(H[-1], h[k]), min(L[-1], l[k])
    return T, H, L


# ---------------------------------------------------------------- detector amplio


def detectar(c_):
    t, h, l, c, a = c_.t, c_.h, c_.l, c_.c, c_.a
    out, st = [], None
    # Zigzag de 5 ATR: el punto 1 es el mínimo donde empieza el tramo alcista en curso
    sube, ext, iext, p1 = False, l[0], 0, None
    for i in range(len(c)):
        nuevo_max = False
        if sube:
            if h[i] > ext:
                ext, iext, nuevo_max = h[i], i, True
            if l[i] <= ext - ZIGZAG_ATR * a[i]:
                sube, ext, iext = False, l[i], i
        else:
            if l[i] < ext:
                ext, iext = l[i], i
            if h[i] >= ext + ZIGZAG_ATR * a[i]:
                sube, p1, ext, iext, nuevo_max = True, iext, h[i], i, True
        if i < 200:
            continue
        if st is not None and st["fase"] == "nivel":
            r = _nivel(st, i, h, l, c)
            if r == "entrada":
                out.append(st)
                st = None
                continue
            if r is None:
                continue
            st = None  # cancelada: esta misma vela puede empezar otro impulso
        if sube and nuevo_max and i - p1 <= IMPULSO_MIN and h[i] - l[p1] >= IMPULSO_ATR * a[i]:
            if st is None or h[i] > st["H"]:  # ante un empate, el máximo es la primera vela que lo marcó
                st = {"fase": "impulso", "p1": p1, "ih": i, "H": h[i]}
        elif st is not None and h[i] > st["H"]:
            st = None  # sigue subiendo, pero ya no es un impulso de ≤120 min
        if st is not None and c[i] < st["H"] - TOL * a[st["ih"]]:
            ih, p1_ = st["ih"], st["p1"]
            aT, L = a[ih], st["H"]
            bajo_zona = [(h[k], -k) for k in range(max(0, p1_ - VENTANA_L2), p1_) if h[k] < L - TOL * aT]
            l2, i_l2 = max(bajo_zona) if bajo_zona else (l[p1_], -p1_)
            mn = min(l[ih + 1:i + 1]) if i > ih else l[i]
            st.update(fase="nivel", L=L, aT=aT, T1=ih, toques=[ih], tramos=[], fuera=True,
                      mn=mn, imn=(ih + 1 + l[ih + 1:i + 1].index(mn)) if i > ih else i,
                      linea2=l2, i_linea2=-i_l2)
    return out


def _nivel(st, i, h, l, c):
    L, aT = st["L"], st["aT"]
    if c[i] > L + TOL * aT:
        return "rompe la línea 3"
    if c[i] < st["linea2"] - LINEA2_CANCEL * aT:
        return "cierra bajo la línea 2"
    if i - st["T1"] > ZONA4_MAX:
        return "tiempo"
    # Entrada (antes que el toque: la vela que confirma puede llegar también a la zona del nivel)
    if (len(st["toques"]) >= 2 and st["imn"] is not None and l[i] >= st["mn"] and c[i] > h[st["imn"]]
            and st["mn"] > st["tramos"][-1][0] and i - st["T1"] >= ZONA4_MIN):
        st["entrada"] = i
        return "entrada"
    # Nuevo toque: vuelve a la zona después de que alguna vela posterior al toque anterior cerrara por debajo
    if h[i] >= L - TOL * aT and st["fuera"]:
        st["tramos"].append((st["mn"], st["imn"]))
        st["toques"].append(i)
        st["fuera"] = False
        st["mn"], st["imn"] = float("inf"), None
        return None
    if l[i] < st["mn"]:
        st["mn"], st["imn"] = l[i], i
    if c[i] < L - TOL * aT:
        st["fuera"] = True
    return None


# ---------------------------------------------------------------- datos y contexto de una moneda


class Moneda:
    def __init__(self, simbolo, u):
        v = mexc.cargar(simbolo, "1m")
        self.simbolo, self.u = simbolo, u
        self.t = [x[0] for x in v]
        self.o, self.h, self.l, self.c, self.v = ([x[k] for x in v] for k in (1, 2, 3, 4, 5))
        justo = {x[0]: x[3] for x in mexc.cargar(simbolo, "1m_fair")}
        self.fl = [justo.get(t, l) for t, l in zip(self.t, self.l)]  # mínimo del precio justo (o del último)
        self.a = atr(self.h, self.l, self.c)
        self.e = {n: ema(self.c, n) for n in (20, 50, 100, 200)}
        self.rsi = rsi(self.c)
        self.maxh = TablaMax(self.h, max)
        self.minl = TablaMax(self.l, min)
        self.minl_i = TablaMax([(x, j) for j, x in enumerate(self.l)], min)
        # 15 m: fractales de 1 vela
        T, H, L = agrupar(self.t, self.h, self.l, 900)
        self.f_alto = [(T[k], H[k]) for k in range(1, len(T) - 1) if H[k] > H[k - 1] and H[k] > H[k + 1]]
        self.f_bajo = [(T[k], L[k]) for k in range(1, len(T) - 1) if L[k] < L[k - 1] and L[k] < L[k + 1]]
        # 4 h y diario (velas de MEXC, con la historia previa descargada)
        self.g = {}
        for tipo, seg in (("4h", 14400), ("1d", 86400)):
            w = mexc.cargar(simbolo, tipo)
            cierres = [x[4] for x in w]
            self.g[tipo] = ([x[0] + seg for x in w], ema(cierres, 20), ema(cierres, 50))

    def idx(self, ts):
        """Índice de la vela de 1 m que empieza en ts o después."""
        return bisect.bisect_left(self.t, ts)

    def fractales(self, lista, desde, hasta):
        """Fractales de 15 m confirmados (cerrada la vela siguiente) entre desde y hasta (segundos)."""
        return [(t, p) for t, p in lista if desde <= t and t + 1800 <= hasta]

    def ema_g(self, tipo, ts):
        cierre, e20, e50 = self.g[tipo]
        k = bisect.bisect_right(cierre, ts) - 1
        return (e20[k], e50[k]) if k >= 50 or (tipo == "1d" and k >= 20) else (None, None)


# ---------------------------------------------------------------- características de cada señal


def contar_reacciones(puntos, centro, tol):
    """Puntos dentro de ±tol del centro, separados al menos 1 h entre sí."""
    n, ultimo = 0, None
    for t, p in sorted(puntos):
        if abs(p - centro) <= tol and (ultimo is None or t - ultimo >= SEP_REACCIONES):
            n, ultimo = n + 1, t
    return n


def caracteristicas(m: Moneda, st):
    t, h, l, c, a = m.t, m.h, m.l, m.c, m.a
    i, im, mn = st["entrada"], st["imn"], st["mn"]
    tick = m.u.get("tick") or 0
    te = t[i] + 60  # cierre de la vela de entrada
    ai = a[i]
    entrada = c[i] + tick
    primer = st["tramos"][0][0]  # primer mínimo de la zona 4 (entre T1 y T2)
    stops = {"S1": (primer + mn) / 2, "S2": mn - 0.3 * ai, "S3": primer - 0.3 * ai}
    f = {"moneda": m.simbolo.replace("_USDT", ""), "ts": t[i], "entrada_madrid": hora_madrid(t[i] + 60),
         "t1_madrid": hora_madrid(t[st["T1"]]), "p1_madrid": hora_madrid(t[st["p1"]]),
         "minimo_madrid": hora_madrid(t[im]), "i": i, "im": im,
         "entrada": entrada, "minimo": mn, "primer_minimo_z4": primer, "linea3": st["L"], "linea2": st["linea2"],
         "punto1": l[st["p1"]], "atr": ai, "toques": len(st["toques"]),
         "impulso_atr": (st["L"] - l[st["p1"]]) / a[st["T1"]], "impulso_min": st["T1"] - st["p1"]}
    for k, s in stops.items():
        f[f"stop_{k}"] = s
    R1 = entrada - stops["S1"]
    # H1 espacio libre: primer máximo de 15 m sin romper por encima de la línea 3 + tolerancia
    techo = st["L"] + TOL * st["aT"]
    libres = []
    for tf, p in m.fractales(m.f_alto, 0, te):
        if p > techo:
            k0 = m.idx(tf + 900)
            if k0 > i or m.maxh.q(k0, i) < p:
                libres.append(p)
    esp = min(libres) - entrada if libres else None
    f["espacio_R"] = esp / R1 if esp is not None and R1 > 0 else None
    f["espacio_ATR"] = esp / ai if esp is not None else None
    # H2 fuerza de la línea 3: máximos de 15 m a ±tolerancia en los 3 días previos al punto 1
    previos = m.fractales(m.f_alto, t[st["p1"]] - DIAS_REACCIONES * 86400, t[st["p1"]])
    f["reacciones_l3"] = contar_reacciones(previos, st["L"], TOL * st["aT"])
    # H3 barrido del punto 1: el primer mínimo del retroceso desde la línea 2 (zigzag de max(3 ATR, 40 % de la
    # caída de la línea 2 al punto 1), como el «primer mínimo» de MERL y AAVE), dentro de las 6 h previas
    p1, i2 = st["p1"], st["i_linea2"]
    umbral = max(3 * a[p1], 0.4 * (st["linea2"] - l[p1]))
    mins = [x for x in _zigzag_minimos(h, l, max(i2 + 1, p1 - VENTANA_BARRIDO), p1, umbral) if x[0] < p1]
    f["barrido_atr"] = (mins[0][1] - l[p1]) / a[p1] if mins else None
    f["barrido_madrid"] = hora_madrid(t[mins[0][0]]) if mins else None
    # H4 contexto 4 h / diario
    e20_4, e50_4 = m.ema_g("4h", te)
    e20_1d, _ = m.ema_g("1d", te)
    bajo24 = m.minl.q(max(0, i - 1440), i)
    f["tendencia_4h"] = None if e20_4 is None else e20_4 > e50_4
    cerca = [abs(bajo24 - e) / e <= 0.005 for e in (e20_4, e20_1d) if e]
    f["suelo_cerca_ema"] = any(cerca) if cerca else None
    # H5 EMAs de 1 m
    f["min_cerca_ema20"] = abs(mn - m.e[20][im]) <= 0.3 * a[im]
    f["emas_ordenadas"] = m.e[20][i] > m.e[50][i] > m.e[100][i] > m.e[200][i]
    # Secundarias
    f["retrocesos_sobre_l2"] = min([x[0] for x in st["tramos"]] + [mn]) > st["linea2"]
    r = [m.rsi[k] for k in st["toques"]]
    f["rsi_picos_bajan"] = all(r[k] < r[k - 1] for k in range(1, len(r)))
    base_vol = m.v[max(0, st["T1"] - 1440):st["T1"]]
    med = median(base_vol) if base_vol else 0
    f["pico_volumen_z4"] = med > 0 and max(m.v[st["T1"]:i + 1]) >= 3 * med
    # Niveles para el objetivo: fractales de 15 m (máximos y mínimos) de los 7 días previos
    puntos = m.fractales(m.f_alto + m.f_bajo, te - DIAS_NIVELES * 86400, te)
    f["_puntos"] = puntos
    f["_stops"] = stops
    return f


def objetivo_nivel(f, R):
    """Siguiente nivel de 15 m con ≥2 reacciones a ≥3R de la entrada (si no hay, 10R)."""
    minimo = f["entrada"] + 3 * R
    for _, p in sorted(f["_puntos"], key=lambda x: x[1]):
        if p >= minimo and contar_reacciones(f["_puntos"], p, TOL * f["atr"]) >= 2:
            return p, True
    return f["entrada"] + 10 * R, False


# ---------------------------------------------------------------- simulación


def simular(m: Moneda, i0, entrada, stop, objetivo, fee_in):
    R = entrada - stop
    if R <= 0:
        return None
    h, c, fl = m.h, m.c, m.fl
    fin = min(len(c) - 1, i0 + MAX_VELAS)
    mfe, tipo, salida, k_sal = 0.0, None, None, fin
    for k in range(i0 + 1, fin + 1):
        if fl[k] <= stop:  # el stop salta con el precio justo; si coincide con el objetivo, cuenta el stop
            tipo, salida, k_sal = "stop", stop, k
            break
        mfe = max(mfe, (h[k] - entrada) / R)
        if objetivo is not None and h[k] >= objetivo:
            tipo, salida, k_sal = "objetivo", objetivo, k
            break
    if tipo is None:
        tipo, salida = "tiempo", c[fin]
    fee_out = m.u["maker"] if tipo == "objetivo" else m.u["taker"]
    bruto = (salida - entrada) / R
    neto = bruto - (fee_in * entrada + fee_out * salida) / R
    return {"tipo": tipo, "neto": neto, "k_salida": k_sal, "mfe": mfe, "completa": i0 + MAX_VELAS < len(c)}


def procesar(args):
    simbolo, u = args
    try:
        m = Moneda(simbolo, u)
    except FileNotFoundError:
        return simbolo, [], None
    filas = []
    for st in detectar(m):
        f = caracteristicas(m, st)
        i, im = f["i"], f["im"]
        for s in STOPS:
            stop = f["_stops"][s]
            R = f["entrada"] - stop
            if R <= 0:
                continue
            # excursión máxima a favor y alcance de 5R/10R (sin objetivo, hasta el stop o 8 h)
            libre = simular(m, i, f["entrada"], stop, None, u["taker"])
            f[f"{s}_R"] = R
            f[f"{s}_mfe"] = libre["mfe"]
            obj_n, hay = objetivo_nivel(f, R)
            f[f"{s}_objetivo_nivel"] = obj_n
            f[f"{s}_nivel_encontrado"] = hay
            f[f"{s}_apal_necesario"] = 1 / (R / f["entrada"] + u["mmr"]) if u.get("mmr") is not None else None
            for sal in SALIDAS:
                obj = obj_n if sal == "nivel" else f["entrada"] + int(sal[:-1]) * R
                r = simular(m, i, f["entrada"], stop, obj, u["taker"])
                f[f"{s}_{sal}_neto"], f[f"{s}_{sal}_salida"] = r["neto"], r["k_salida"]
                f[f"{s}_{sal}_tipo"] = r["tipo"]
                # entrada ideal en el propio mínimo (solo referencia): orden límite, comisión maker
                mn = f["minimo"]
                if mn > stop:
                    obj_i = obj if sal == "nivel" else mn + int(sal[:-1]) * (mn - stop)
                    f[f"{s}_{sal}_ideal"] = simular(m, im, mn, stop, obj_i, u["maker"])["neto"]
            f["completa"] = libre["completa"]
        f["max_lev"] = u.get("max_lev")
        del f["_puntos"], f["_stops"]
        filas.append(f)
    return simbolo, filas, (m.t[0], m.t[-1])


def main():
    universo = json.loads((mexc.DATOS / "universo.json").read_text())
    tareas = [(u["simbolo"], u) for u in universo
              if es_cripto(u["simbolo"]) and (mexc.DATOS / f"{u['simbolo']}_1m_fair.csv.gz").exists()
              and (mexc.DATOS / f"{u['simbolo']}_1d.csv.gz").exists()]
    filas, rango = [], {}
    with Pool(4) as pool:
        for s, f, r in pool.imap_unordered(procesar, tareas):
            if r:
                filas += f
                rango[s] = r
            print(s, len(f), flush=True)
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "señales.json").write_text(json.dumps({"monedas": len(rango), "rango": rango, "señales": filas},
                                                    ensure_ascii=False))
    print("señales:", len(filas))


if __name__ == "__main__":
    main()
