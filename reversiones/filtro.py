"""Filtro de contexto en 4 h y diario: ¿el suelo es el final de un retroceso dentro de una tendencia alcista?

Solo usa velas de 4 h y diarias ya cerradas antes del minuto que se evalúa.

Condiciones (parámetros en FiltroParams):
  1. Impulso previo: en los N días anteriores al suelo hay un máximo H que está al menos un X % por
     encima del mínimo L de los N días anteriores a ese máximo.
  2. Retroceso: el suelo ha devuelto entre el A % y el B % de ese impulso.
  3. El suelo está cerca de la EMA20 de 4 h o de la EMA20 diaria.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from .detector import ema


@dataclass
class FiltroParams:
    dias_impulso: int = 10  # ventana para buscar el máximo del impulso antes del suelo (y su mínimo)
    impulso_min: float = 0.15  # subida mínima del impulso (15 %)
    retroceso_min: float = 0.38  # el suelo devuelve al menos el 38 % del impulso…
    retroceso_max: float = 0.85  # …y como mucho el 85 %
    dist_ema: float = 0.015  # el suelo está a menos de un 1,5 % de la EMA20 de 4 h o de la diaria


class Filtro:
    def __init__(self, t1m, l1m, velas_4h, velas_1d, p: FiltroParams | None = None):
        self.t1m, self.l1m, self.p = t1m, l1m, p or FiltroParams()
        self.v4, self.vd = velas_4h, velas_1d
        self.t4 = [v[0] for v in velas_4h]
        self.td = [v[0] for v in velas_1d]
        self.e4 = ema([v[4] for v in velas_4h], 20)
        self.ed = ema([v[4] for v in velas_1d], 20)

    @staticmethod
    def _ultima_cerrada(tiempos, t, dur):
        """Índice de la última vela cerrada antes del instante t (vela de duración 'dur' segundos)."""
        return bisect.bisect_right(tiempos, t - dur) - 1

    def __call__(self, i_suelo, i):
        p = self.p
        t_suelo, suelo = self.t1m[i_suelo], self.l1m[i_suelo]
        j4 = self._ultima_cerrada(self.t4, t_suelo, 4 * 3600)
        jd = self._ultima_cerrada(self.td, t_suelo, 86400)
        if j4 < 25 or jd < 20:
            return {"ok": False, "motivo": "pocos datos de 4 h o diarios"}
        # 1. Impulso: máximo H en los N días previos al suelo; mínimo L en los N días previos a H
        desde = bisect.bisect_left(self.t4, t_suelo - p.dias_impulso * 86400)
        k_h = max(range(desde, j4 + 1), key=lambda k: self.v4[k][2])
        H = self.v4[k_h][2]
        desde_l = bisect.bisect_left(self.t4, self.t4[k_h] - p.dias_impulso * 86400)
        L = min(self.v4[k][3] for k in range(desde_l, k_h + 1))
        impulso = H / L - 1
        retroceso = (H - suelo) / (H - L) if H > L else 0
        # 3. Cercanía a la EMA20 de 4 h o diaria (la de la última vela cerrada)
        d4 = abs(suelo / self.e4[j4] - 1)
        dd = abs(suelo / self.ed[jd] - 1)
        ok = (impulso >= p.impulso_min and p.retroceso_min <= retroceso <= p.retroceso_max
              and min(d4, dd) <= p.dist_ema)
        return {"ok": ok, "impulso": round(impulso, 3), "retroceso": round(retroceso, 3),
                "dist_ema20_4h": round(d4, 4), "dist_ema20_1d": round(dd, 4)}
