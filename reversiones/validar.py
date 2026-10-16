"""Validación del detector en los dos casos de referencia (MERL 29-sep y AAVE 1-oct-2026).

Comprueba avisos y entrada frente a lo esperado, mide los mínimos de la zona 4 frente a la EMA20 de
1 minuto y el orden de las EMAs, y revisa con el precio justo si los stops habrían saltado.

Uso:  python3 -m reversiones.validar
"""

from __future__ import annotations

from datetime import datetime, timezone

from .backtest import hora_madrid
from .datos_simbolo import preparar, precio_justo
from .detector import ema

CASOS = {
    # símbolo: (día UTC de la ruptura, avisos esperados UTC, entrada esperada UTC, objetivo, stop del usuario en MEXC)
    "MERL_USDT": ("09-29 19", ["19:41", "19:56"], "~20:00", 0.03048, 0.02884),
    # El gráfico de AAVE era el spot de Binance, ~0,06 % por encima de MEXC: 162,21 → ~162,11
    "AAVE_USDT": ("10-01 02", ["02:43"], "02:48–02:50", 166.93, 162.11),
}


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%M")


def main():
    for s, (dia, avisos_esp, entrada_esp, objetivo, stop_usuario) in CASOS.items():
        d, _ = preparar(s, con_filtro=True, exigir_filtro=True)
        e = next(x for x in d.ejecutar() if x.entrada and utc(d.t[x.i_ruptura]).startswith(dia))
        en = e.entrada
        print(f"\n{s}  (filtro: {e.filtro})")
        print(f"  2 {e.p2} · 1 {e.p1} · línea 3 {e.l3} (máximo de giro del {hora_madrid(d.t[e.i_l3])} Madrid)")
        print(f"  avisos UTC {[utc(d.t[i])[6:] for i in e.avisos]}  (esperados {avisos_esp})")
        print(f"  entrada UTC {utc(d.t[en['i']])[6:]} a {en['precio']} sobre el mínimo {en['minimo']}  (esperada {entrada_esp})")
        E = {n: ema(d.c, n) for n in (20, 50, 100, 200)}
        mins = sorted({k for k in range(e.toques[0], en["i"] + 1)
                       if d.l[k] <= min(d.l[k - 1], d.l[k + 1]) and d.h[k] < e.l3} | {en["i_minimo"]})
        for k in mins:
            orden = E[20][k] > E[50][k] > E[100][k] > E[200][k]
            marca = "  ← mínimo de entrada" if k == en["i_minimo"] else ""
            print(f"    mínimo {utc(d.t[k])[6:]} {d.l[k]}: {(d.l[k] - E[20][k]) / d.a[k]:+.2f} ATR de la EMA20 · "
                  f"EMAs ordenadas al alza: {'sí' if orden else 'no'}{marca}")
        justo = precio_justo(s)
        stops = dict(en["stops"], usuario=stop_usuario)
        for nombre, st in stops.items():
            salto = None
            for k in range(en["i"] + 1, len(d.t)):
                if justo.get(d.t[k], (0, d.l[k]))[1] <= st:
                    salto = utc(d.t[k])
                    break
                if d.h[k] >= objetivo:
                    break
            print(f"    stop {nombre:10s} {st:.6g}: {'salta ' + salto if salto else 'no salta antes del objetivo'}")


if __name__ == "__main__":
    main()
