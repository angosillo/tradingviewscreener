"""Detector minuto a minuto del setup de reversión (casos MERL 29-sep y AAVE 1-oct).

Secuencia que busca, siempre con lo que se sabía en ese minuto (sin mirar el futuro):

  suelo  →  punto 2  →  retroceso con barrido (punto 1)  →  ruptura del 2  →  línea 3
         →  toques a la línea 3  →  aviso (2.º toque y siguientes)  →  entrada en el mínimo más alto

Todas las distancias se miden en ATR(14) de 1 minuto en el momento de la evaluación.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


# ----------------------------------------------------------------------------- parámetros


@dataclass
class Params:
    # Suelo y punto 2
    horas_suelo: int = 24  # el suelo es el mínimo de las últimas N horas
    min_velas_p2: int = 15  # el punto 2 debe quedar al menos N minutos antes de la ruptura
    min_profundidad: float = 3.0  # caída mínima del 2 al 1, en ATR
    p2_ref_bajo: float = -0.5  # el 2 puede quedarse hasta 0,5 ATR por debajo de un máximo anterior…
    p2_ref_alto: float = 4.0  # …o pasarlo hasta 4 ATR
    dias_ref_p2: int = 7  # ese máximo anterior se busca en los N días previos al suelo
    # Retroceso y barrido
    zigzag: float = 3.0  # un mínimo del retroceso cuenta cuando el precio rebota N ATR desde él…
    zigzag_frac: float = 0.40  # …o el 40 % de la caída del 2 al 1, lo que sea mayor (escala de la estructura)
    barrido_min: float = 0.8  # el punto 1 barre el primer mínimo del retroceso al menos N ATR…
    barrido_max: float = 3.5  # …y como mucho N ATR
    margen_suelo: float = 2.0  # el punto 1 debe quedar al menos N ATR por encima del suelo
    # Línea 3
    fuerza_pivote: int = 10  # un máximo de giro necesita N velas más bajas a cada lado
    l3_min: float = 1.0  # la línea 3 está al menos N ATR por encima del 2…
    l3_max: float = 10.0  # …y como mucho N ATR
    # Toques y zona 4
    toque: float = 0.15  # toca la línea 3 si el máximo llega a N ATR de ella (o la pasa con mecha)
    rotura: float = 0.5  # rompe la línea 3 si cierra más de N ATR por encima
    retirada: float = 1.0  # entre dos toques el precio debe alejarse al menos N ATR de la línea 3
    pullback_min: float = 0.7  # el mínimo de entrada debe quedar al menos N ATR por debajo de la línea 3
    # Cancelaciones
    linea2: float = 1.0  # se cancela si cierra más de N ATR por debajo del punto 2
    max_min_primer_toque: int = 120  # minutos máximos desde la ruptura del 2 hasta el primer toque
    max_min_zona4: int = 60  # minutos máximos desde el primer toque hasta la entrada


# ----------------------------------------------------------------------------- indicadores


def atr(h, l, c, n=14):
    out = [0.0] * len(c)
    if len(c) <= n:
        return out
    tr = [h[0] - l[0]] + [max(h[i], c[i - 1]) - min(l[i], c[i - 1]) for i in range(1, len(c))]
    a = sum(tr[1:n + 1]) / n
    out[n] = a
    for i in range(n + 1, len(c)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    for i in range(n):
        out[i] = out[n]
    return out


def ema(x, n):
    k, out, e = 2 / (n + 1), [0.0] * len(x), x[0]
    for i, v in enumerate(x):
        e = v * k + e * (1 - k) if i else v
        out[i] = e
    return out


class TablaMax:
    """Máximo/mínimo de cualquier rango en O(1) (tabla dispersa)."""

    def __init__(self, x, f=max):
        self.f, self.t = f, [list(x)]
        j = 1
        while (1 << j) <= len(x):
            prev, m = self.t[-1], 1 << (j - 1)
            self.t.append([f(prev[i], prev[i + m]) for i in range(len(x) - (1 << j) + 1)])
            j += 1

    def q(self, a, b):  # rango cerrado [a, b]
        if a > b:
            return None
        j = (b - a + 1).bit_length() - 1
        return self.f(self.t[j][a], self.t[j][b - (1 << j) + 1])


def pivotes_altos(h, k):
    """Índices de máximos de giro: más altos que las k velas previas y no superados en las k siguientes."""
    out = []
    for i in range(k, len(h) - k):
        izq = max(h[i - k:i])
        if h[i] > izq and h[i] >= max(h[i + 1:i + k + 1]):
            out.append(i)
    return out


# ----------------------------------------------------------------------------- estructura


@dataclass
class Estructura:
    i_suelo: int
    i_p2: int
    i_r1: int
    i_p1: int
    i_ruptura: int
    p2: float
    p1: float
    r1: float
    l3: float
    i_l3: int
    ref_p2: float
    filtro: dict
    toques: list = field(default_factory=list)  # índices de los toques
    lows_tramo: list = field(default_factory=list)  # mínimo de retroceso de cada tramo entre toques
    min_tramo: float = float("inf")
    i_min_tramo: int = -1
    retirado: bool = True  # se ha alejado de la línea 3 desde el último toque
    avisos: list = field(default_factory=list)
    entrada: dict | None = None
    fin: str | None = None
    i_fin: int | None = None


def _zigzag_minimos(h, l, a, b, umbral):
    """Mínimos confirmados entre a y b: el precio rebota 'umbral' desde el mínimo. Devuelve [(i, precio)]."""
    out, i_min, v_min = [], None, float("inf")
    for i in range(a, b + 1):
        if l[i] < v_min:
            i_min, v_min = i, l[i]
        elif h[i] - v_min >= umbral and i_min is not None:
            out.append((i_min, v_min))
            i_min, v_min = None, float("inf")
            # buscar el siguiente mínimo desde aquí
    return out


class Detector:
    def __init__(self, t, o, h, l, c, p: Params | None = None, filtro=None, exigir_filtro: bool = False):
        self.t, self.o, self.h, self.l, self.c = t, o, h, l, c
        self.p = p or Params()
        self.filtro = filtro  # función (i_suelo, i) -> dict con 'ok' y detalles, o None
        self.exigir_filtro = exigir_filtro  # si es True, una estructura que no pasa el filtro no se crea
        self.a = atr(h, l, c)
        self.maxh = TablaMax(h, max)
        self.minl = TablaMax(l, min)
        # Con índice. Ante empates, los dos dan la PRIMERA posición: el 2 es la primera vez que se marcó
        # ese máximo, no una vela posterior que solo lo iguala.
        self.maxh_i = TablaMax([(v, -j) for j, v in enumerate(h)], max)
        self.minl_i = TablaMax([(v, j) for j, v in enumerate(l)], min)
        self.piv = pivotes_altos(h, self.p.fuerza_pivote)
        self.ventana = self.p.horas_suelo * 60

    # --------------------------------------------------------------- búsqueda de estructura nueva

    def _l3(self, i, p2, a):
        """Máximo de giro confirmado más cercano por encima del 2 que siga sin romper."""
        k = self.p.fuerza_pivote
        mejor = None
        for j in self.piv:
            if j + k > i:
                break
            v = self.h[j]
            if not (p2 + self.p.l3_min * a <= v <= p2 + self.p.l3_max * a):
                continue
            if self.maxh.q(j + 1, i) > v:  # ya se rompió
                continue
            if mejor is None or v < self.h[mejor]:
                mejor = j
        return mejor

    def _ref_p2(self, i_suelo, p2, a):
        k = self.p.fuerza_pivote
        desde = max(0, i_suelo - self.p.dias_ref_p2 * 1440)
        mejor = None
        for j in self.piv:
            if j < desde or j + k > i_suelo:
                continue
            d = (p2 - self.h[j]) / a
            if self.p.p2_ref_bajo <= d <= self.p.p2_ref_alto and (mejor is None or abs(d) < abs((p2 - mejor) / a)):
                mejor = self.h[j]
        return mejor

    def _nueva(self, i):
        p, h, l, c, a = self.p, self.h, self.l, self.c, self.a[i]
        if a <= 0 or i < 60:
            return None
        ini = max(0, i - self.ventana)
        v_suelo, i_suelo = self.minl_i.q(ini, i - 1)
        p2, i_p2 = self.maxh_i.q(i_suelo, i - 1)
        i_p2 = -i_p2
        if c[i] <= p2 or c[i - 1] > p2:  # solo en la primera vela que cierra por encima del 2
            return None
        if i - i_p2 < p.min_velas_p2:
            return None
        v_p1, i_p1 = self.minl_i.q(i_p2 + 1, i)
        if (p2 - v_p1) < p.min_profundidad * a or v_p1 - v_suelo < p.margen_suelo * a:
            return None
        # Primer mínimo del retroceso (zigzag en ATR) y barrido
        umbral = max(p.zigzag * a, p.zigzag_frac * (p2 - v_p1))
        mins = _zigzag_minimos(h, l, i_p2 + 1, i_p1, umbral)
        mins = [m for m in mins if m[0] < i_p1]
        if not mins:
            return None
        i_r1, r1 = mins[0]
        barrido = (r1 - v_p1) / a
        if not (p.barrido_min <= barrido <= p.barrido_max):
            return None
        # Máximo intermedio (rebote entre el 1.er mínimo y el 1) roto antes de romper el 2
        if self.maxh.q(i_r1 + 1, i_p1) >= p2:
            return None
        ref = self._ref_p2(i_suelo, p2, a)
        if ref is None:
            return None
        j3 = self._l3(i, p2, a)
        if j3 is None:
            return None
        filtro = self.filtro(i_suelo, i) if self.filtro else {"ok": True}
        if self.exigir_filtro and not filtro["ok"]:
            return None
        return Estructura(i_suelo, i_p2, i_r1, i_p1, i, p2, v_p1, r1, h[j3], j3, ref, filtro)

    # --------------------------------------------------------------- seguimiento de la estructura

    def _avanzar(self, e: Estructura, i):
        p, h, l, c, a = self.p, self.h, self.l, self.c, self.a[i]
        l3 = e.l3
        # Cancelaciones previas
        if c[i] < e.p2 - p.linea2 * a:
            return "cierra bajo la línea 2"
        if not e.toques and i - e.i_ruptura > p.max_min_primer_toque:
            return "no llegó a la línea 3"
        if e.toques and i - e.toques[0] > p.max_min_zona4:
            return "zona 4 demasiado larga"
        # Tramo en curso: mínimo de retroceso desde el último toque
        if e.toques and l[i] < e.min_tramo:
            e.min_tramo, e.i_min_tramo = l[i], i
        # ¿Confirma un mínimo más alto? (solo desde el 2.º toque)
        if len(e.toques) >= 2 and e.i_min_tramo >= 0 and i > e.i_min_tramo:
            m, im = e.min_tramo, e.i_min_tramo
            previo = e.lows_tramo[-1]
            confirma = (l[i] > m and c[i] > c[im]) or c[i] > h[im]
            if confirma and m > previo and m <= l3 - p.pullback_min * a:
                primer_min = min(e.lows_tramo + [m])
                e.entrada = {"i": i, "precio": c[i], "minimo": m, "i_minimo": im, "atr": a,
                             "minimo_zona4": primer_min,
                             "stops": {"A_-0.3ATR": m - 0.3 * a, "B_-1ATR": m - 1.0 * a,
                                       "C_bajo_zona4": primer_min - 0.1 * a}}
                return "entrada"
        # Rotura de la línea 3 sin entrada
        if c[i] > l3 + p.rotura * a:
            return "rompió la línea 3 sin entrada"
        # Toque (la retirada debe haberse producido en velas anteriores a esta)
        if h[i] >= l3 - p.toque * a and e.retirado:
            if e.toques:
                e.lows_tramo.append(e.min_tramo)
            e.toques.append(i)
            e.retirado = False
            e.min_tramo, e.i_min_tramo = float("inf"), -1
            if len(e.toques) >= 2:
                e.avisos.append(i)
        elif l[i] <= l3 - p.retirada * a:
            e.retirado = True
        return None

    def ejecutar(self):
        """Recorre todas las velas. Devuelve la lista de estructuras (con sus avisos, entrada y final)."""
        out, activa = [], None
        for i in range(len(self.c)):
            if activa is not None:
                r = self._avanzar(activa, i)
                if r:
                    activa.fin, activa.i_fin = r, i
                    out.append(activa)
                    activa = None
            nueva = self._nueva(i)
            if nueva is not None:
                if activa is not None and activa.entrada is None:
                    # estructura anidada más pequeña: sustituye a la anterior sin entrada
                    activa.fin, activa.i_fin = "sustituida por otra más reciente", i
                    out.append(activa)
                    activa = None
                if activa is None:
                    activa = nueva
        if activa is not None:
            activa.fin = activa.fin or "abierta al final de los datos"
            out.append(activa)
        return out
