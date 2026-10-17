# Detector de reversiones (1 minuto, perpetuos de MEXC)

Busca el setup de los casos **MERL (29-sep-2026)** y **AAVE (1-oct-2026)**: final de un retroceso dentro de una tendencia alcista, con barrido de liquidez y entrada en un mínimo más alto bajo una resistencia. El sistema de noticias (tipo ONDO) va aparte.

Cada condición se evalúa **solo con lo que se sabía en ese minuto**.

## Secuencia

1. **Filtro de contexto (4 h / diario)**: impulso previo, retroceso y suelo cerca de la EMA20 de 4 h o diaria.
2. **Suelo**: mínimo de las últimas 24 h.
3. **Punto 2**: máximo desde el suelo, a la altura de un máximo anterior.
4. **Retroceso y barrido (punto 1)**: el primer mínimo del retroceso queda barrido, sin perder el suelo.
5. **Ruptura**: cierra por encima del 2 tras romper el máximo intermedio.
6. **Línea 3**: el máximo de giro más cercano por encima del 2 que siga sin romper, de cualquier antigüedad.
7. **Toques**: aviso en el 2.º toque y en cada uno de los siguientes.
8. **Entrada**: primer mínimo de retroceso, desde el 2.º toque, por encima del mínimo de retroceso anterior. Se entra al cierre de la vela que lo confirma.
9. **Cancelación**:
   - cierra claramente por debajo de la línea 2;
   - rompe la línea 3 sin haber dado entrada;
   - pasan más de 60 min desde el primer toque.

Si aparece una estructura más reciente antes de la entrada, sustituye a la anterior. Así se queda con la pequeña en los casos anidados, como AAVE.

## Parámetros (`detector.py` → `Params`, `filtro.py` → `FiltroParams`)

Todas las distancias van en ATR(14) de 1 minuto.

| Parámetro | Valor | Qué hace |
|---|---|---|
| `horas_suelo` | 24 | El suelo es el mínimo de las últimas 24 h |
| `min_velas_p2` | 15 | El 2 queda al menos 15 min antes de la ruptura |
| `min_profundidad` | 3 | Caída mínima del 2 al 1 |
| `p2_ref_bajo` / `p2_ref_alto` | −0,5 / +4 | El 2 está entre 0,5 ATR por debajo y 4 por encima de un máximo anterior… |
| `dias_ref_p2` | 7 | …buscado en los 7 días previos al suelo |
| `zigzag` / `zigzag_frac` | 3 / 40 % | Un mínimo del retroceso cuenta si el precio rebota 3 ATR o el 40 % de la caída del 2 al 1, lo que sea mayor |
| `barrido_min` / `barrido_max` | 0,8 / 3,5 | El 1 barre ese primer mínimo entre 0,8 y 3,5 ATR |
| `margen_suelo` | 2 | El 1 queda al menos 2 ATR por encima del suelo |
| `fuerza_pivote` | 10 | Un máximo de giro necesita 10 velas más bajas a cada lado |
| `l3_min` / `l3_max` | 1 / 10 | La línea 3 está entre 1 y 10 ATR por encima del 2 |
| `toque` | 0,15 | Toca la línea 3 si el máximo llega a 0,15 ATR de ella (o la pasa con mecha) |
| `rotura` | 0,5 | Rompe la línea 3 si cierra más de 0,5 ATR por encima |
| `retirada` | 1 | Entre dos toques, el precio se aleja al menos 1 ATR de la línea 3 |
| `pullback_min` | 0,7 | El mínimo de entrada queda al menos 0,7 ATR por debajo de la línea 3 |
| `linea2` | 1 | Cancela si cierra más de 1 ATR por debajo del 2 |
| `max_min_primer_toque` | 120 | Minutos máximos desde la ruptura del 2 hasta el primer toque |
| `max_min_zona4` | 60 | Minutos máximos desde el primer toque hasta la entrada |
| `dias_impulso` | 10 | Ventana del impulso previo (filtro) |
| `impulso_min` | 15 % | Subida mínima del impulso (filtro) |
| `retroceso_min` / `retroceso_max` | 38 % / 85 % | Parte del impulso devuelta en el suelo (filtro) |
| `dist_ema` | 1,5 % | El suelo está a menos de un 1,5 % de la EMA20 de 4 h o diaria (filtro) |

## Uso

```bash
python3 -m reversiones.mexc universo 150    # elige los perpetuos con más volumen (luego se excluyen los no cripto)
python3 -m reversiones.mexc descargar 30    # últimos 30 días (MEXC no guarda más en 1 minuto)
python3 -m reversiones.validar              # comprueba MERL y AAVE
python3 -m reversiones.backtest             # prueba en el histórico → resultados/
python3 -m reversiones.analisis             # embudo y ablación → resultados/analisis.json
```

Los datos se guardan en `datos/` (no se suben a git).
