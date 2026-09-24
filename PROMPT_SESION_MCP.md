# Contexto: análisis del setup de ONDO con el MCP de TradingView

Hola. Vengo de otra sesión y te paso el contexto para continuar. Explícamelo todo como un profesor de informática: claro, paso a paso y en español.

## Qué quiero conseguir

Opero criptomonedas en el exchange **MEXC**. El **24 de septiembre de 2026**, en **ONDO** (`MEXC:ONDOUSDT`), apareció un setup que me dio una entrada muy buena y muy acotada. Quiero:

1. **Ver con datos reales de TradingView qué ocurrió exactamente** en ese momento: precio, RSI y volumen.
2. **Definir el setup como reglas objetivas**, para que se pueda detectar automáticamente.
3. **Encontrar ese mismo setup en otras monedas** (de MEXC), idealmente **mientras se está formando**, antes de que se complete.
4. Más adelante, decidir si montamos un screener propio, alertas o un script.

## Cómo es el setup (descrito por mí)

- Aparece **después de que la moneda haya explotado**: un repunte fuerte con mucho volumen.
- El precio sube hasta un **nivel superior (techo)**, baja, vuelve a tocar **el mismo techo**, vuelve a bajar pero **un poco por encima del mínimo anterior**, y así varias veces. Es decir: **máximos iguales y mínimos crecientes**, con el precio cada vez más comprimido.
- Mientras se dibuja la figura, mi indicador (**RSI con divergencias**) forma **máximos cada vez más bajos**: se va comprimiendo.
- También quiero saber **qué hizo el volumen** durante la figura.

## Lo que ya encontramos en la sesión anterior (sin el MCP)

Usamos la API pública de MEXC con velas de **15 minutos** y el RSI(14) calculado a mano. **Horas en UTC; en España son 2 horas más.**

- **Explosión:** 24-sep-2026 a las **12:00 UTC**. Una vela de +8 % (0,428 → 0,463) con un volumen unas 40 veces mayor que el de las anteriores. Después sube hasta ~0,51.
- **Figura candidata:** entre las **15:15 y las 17:45 UTC**.
  - **Techo** en ~0,520–0,529, tocado muchas veces.
  - **Mínimos crecientes:** 0,5083 → 0,5100 → 0,5141 → 0,5149.
  - **Picos de RSI descendentes:** 87,4 (14:15) → 79,4 (15:30) → 76,1 (16:15) → 75,3 (17:00) → 72,8 (17:30). Es una divergencia bajista.
  - **Volumen:** se va secando, de ~200.000 USDT por vela a 30.000–50.000.
- **Desenlace:** a las **18:00 UTC** el volumen vuelve a subir (~120.000 USDT) y el precio **rompe hacia abajo** hasta ~0,498.

⚠️ Todavía no he confirmado que ese sea exactamente mi momento ni la temporalidad que yo miraba.

## Lo que sabemos del MCP de TradingView

- **URL del servidor:** `https://mcp.tradingview.com/mcp`. Requiere plan Essential o superior. Límite de ~100 llamadas por minuto.
- **Herramientas útiles:**
  - `get_ohlcv`: velas de 1m a 1M, hasta 5.000.
  - `run_screener`: con `market: "crypto"` y filtros `{campo: [min, max]}`.
  - `get_screener_columns`: catálogo de columnas disponibles.
  - `get_technicals_rating`: RSI y otros indicadores de una moneda.
  - `get_symbol_data_batch`: datos de hasta 50 monedas a la vez.
  - `search_symbols`: resolver tickers.
  - **Alertas:** puede crear alertas en mi cuenta.
- **Limitación importante:** el screener de TradingView compara **valores de un instante** (RSI actual, % de cambio, volumen). No detecta **secuencias** como "3 toques al mismo techo con mínimos crecientes". Por eso el plan es:
  1. **Filtro rápido** con el screener: monedas que acaban de explotar (por ejemplo +15 % en 24 h y volumen relativo alto).
  2. **Análisis de las velas** de esos candidatos para comprobar la figura.
- **Otro hallazgo:** en el screener de pares CEX, la capitalización de mercado sale vacía para MEXC. Se obtiene cruzando por moneda base con el screener de monedas (mercado `coin`, columna `market_cap_calc`).

## Lo que te pido en esta sesión

1. **Comprueba que tienes conectado el MCP de TradingView** (herramientas de TradingView disponibles). Si no, dímelo y no sigas.
2. Con `get_ohlcv` sobre `MEXC:ONDOUSDT`, descarga velas de **5m y 15m** que cubran el **24-sep-2026 entre las 10:00 y las 20:00 UTC**. Pide suficientes barras para llegar a esa fecha. Si hay datos de 1h, úsalos también como contexto.
3. **Reconstruye el momento:** la explosión, la figura (techo, mínimos crecientes), los picos de RSI(14) y el comportamiento del volumen. Compáralo con lo que encontramos antes y dime si coincide o si hay diferencias.
4. **Muéstramelo visualmente** si puedes: una gráfica con el precio, las líneas del techo y de los mínimos, el RSI con sus máximos descendentes y el volumen.
5. **Propón reglas objetivas del setup**, con números. Por ejemplo:
   - subida mínima previa;
   - número de toques al techo y tolerancia en %;
   - mínimos crecientes;
   - picos de RSI descendentes;
   - caída del volumen.
6. **Pruébalo en vivo:** usa `run_screener` para buscar ahora mismo monedas de MEXC que acaben de explotar y revisa si alguna está formando la figura.

## Preguntas que aún tengo pendientes (hazme estas preguntas antes de sacar conclusiones)

- La **hora exacta** de mi entrada y la **temporalidad** que miraba (5m, 15m, 1h…).
- Si la entrada fue en **corto** (en el techo) o en **largo** (esperando la ruptura hacia arriba).
- Si mi indicador es el **RSI estándar de 14** o un indicador de "RSI Divergence" de la comunidad con otros ajustes.

Aviso: un solo caso no demuestra nada. Antes de fiarnos del setup quiero comprobarlo en el **histórico** de varias monedas (cuántas veces funcionó y cuántas no).
