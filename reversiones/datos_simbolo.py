"""Carga los datos de un símbolo y construye el detector con o sin filtro de contexto."""

from __future__ import annotations

from .detector import Detector, Params
from .filtro import Filtro, FiltroParams
from .mexc import cargar


def preparar(simbolo: str, params: Params | None = None, con_filtro: bool = True,
             fparams: FiltroParams | None = None, exigir_filtro: bool = False):
    v = cargar(simbolo, "1m")
    t = [x[0] for x in v]
    o, h, l, c = ([x[k] for x in v] for k in (1, 2, 3, 4))
    filtro = Filtro(t, l, cargar(simbolo, "4h"), cargar(simbolo, "1d"), fparams) if con_filtro else None
    return Detector(t, o, h, l, c, params, filtro, exigir_filtro), v


def precio_justo(simbolo: str) -> dict:
    """{timestamp: (máximo, mínimo)} del precio justo de 1 minuto."""
    return {x[0]: (x[2], x[3]) for x in cargar(simbolo, "1m_fair")}
