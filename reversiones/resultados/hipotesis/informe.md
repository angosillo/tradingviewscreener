# Hipótesis del setup de reversión

MEXC, 234 perpetuos cripto, 1 m. Exploración 16-09 23:38 → 07-10 00:18 UTC; confirmación 07-10 00:18 → 17-10 00:38 UTC. 41560 señales detectadas.

## Base por stop y salida

| Variante | Periodo | Señales (por día) | Ganadoras | R medio neto | Factor de beneficio | Máx. caída (R) | Peor racha |
|---|---|---|---|---|---|---|---|
| S1 + 3R | exploración | 23817 (1189) | 26 % | -0,10 | 0,88 | 2430 | 66 |
| S1 + 3R | confirmación | 11414 (1140) | 25 % | -0,14 | 0,84 | 1620 | 57 |
| S1 + 3R · entrada ideal | exp. / conf. | — | — | +2,11 / +2,15 | — | — | — |
| S1 + 5R | exploración | 22514 (1124) | 19 % | -0,02 | 0,98 | 1206 | 84 |
| S1 + 5R | confirmación | 10785 (1077) | 18 % | -0,08 | 0,91 | 1050 | 92 |
| S1 + 5R · entrada ideal | exp. / conf. | — | — | +2,71 / +2,73 | — | — | — |
| S1 + 10R | exploración | 20719 (1035) | 12 % | +0,08 | 1,07 | 941 | 181 |
| S1 + 10R | confirmación | 9947 (993) | 12 % | -0,05 | 0,95 | 1245 | 125 |
| S1 + 10R · entrada ideal | exp. / conf. | — | — | +3,32 / +3,17 | — | — | — |
| S1 + nivel | exploración | 22530 (1125) | 21 % | -0,03 | 0,97 | 1506 | 81 |
| S1 + nivel | confirmación | 10950 (1093) | 21 % | -0,08 | 0,91 | 1062 | 92 |
| S1 + nivel · entrada ideal | exp. / conf. | — | — | +4,27 / +4,00 | — | — | — |
| S2 + 3R | exploración | 24375 (1217) | 26 % | -0,09 | 0,89 | 2348 | 67 |
| S2 + 3R | confirmación | 11764 (1175) | 26 % | -0,12 | 0,86 | 1387 | 84 |
| S2 + 3R · entrada ideal | exp. / conf. | — | — | +2,72 / +2,77 | — | — | — |
| S2 + 5R | exploración | 23119 (1154) | 19 % | -0,02 | 0,98 | 1161 | 95 |
| S2 + 5R | confirmación | 11122 (1111) | 18 % | -0,06 | 0,93 | 1109 | 97 |
| S2 + 5R · entrada ideal | exp. / conf. | — | — | +3,73 / +3,76 | — | — | — |
| S2 + 10R | exploración | 21195 (1058) | 12 % | +0,08 | 1,08 | 1091 | 143 |
| S2 + 10R | confirmación | 10200 (1019) | 12 % | -0,04 | 0,96 | 1187 | 146 |
| S2 + 10R · entrada ideal | exp. / conf. | — | — | +3,98 / +4,03 | — | — | — |
| S2 + nivel | exploración | 23069 (1152) | 21 % | -0,02 | 0,97 | 1452 | 80 |
| S2 + nivel | confirmación | 11260 (1124) | 22 % | -0,05 | 0,94 | 1086 | 89 |
| S2 + nivel · entrada ideal | exp. / conf. | — | — | +5,08 / +4,96 | — | — | — |
| S3 + 3R | exploración | 21810 (1089) | 27 % | -0,02 | 0,98 | 1022 | 68 |
| S3 + 3R | confirmación | 10470 (1046) | 26 % | -0,08 | 0,90 | 862 | 73 |
| S3 + 3R · entrada ideal | exp. / conf. | — | — | +1,37 / +1,30 | — | — | — |
| S3 + 5R | exploración | 20229 (1010) | 20 % | +0,06 | 1,07 | 752 | 91 |
| S3 + 5R | confirmación | 9727 (971) | 19 % | -0,05 | 0,94 | 998 | 85 |
| S3 + 5R · entrada ideal | exp. / conf. | — | — | +1,55 / +1,45 | — | — | — |
| S3 + 10R | exploración | 18436 (921) | 15 % | +0,16 | 1,17 | 634 | 140 |
| S3 + 10R | confirmación | 8915 (890) | 15 % | -0,01 | 0,99 | 1158 | 115 |
| S3 + 10R · entrada ideal | exp. / conf. | — | — | +1,85 / +1,57 | — | — | — |
| S3 + nivel | exploración | 20427 (1020) | 23 % | +0,06 | 1,07 | 604 | 75 |
| S3 + nivel | confirmación | 10028 (1001) | 23 % | -0,04 | 0,95 | 904 | 85 |
| S3 + nivel · entrada ideal | exp. / conf. | — | — | +2,12 / +1,76 | — | — | — |

## Hipótesis

R medio neto por operación [IC 95 % bootstrap]. * = menos de 30 señales.

### H1 espacio libre (R, con S1)

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| <5R | 14321 / 7386 | -0,04 [-0,08; +0,00] | -0,10 [-0,15; -0,05] | +0,08 [+0,03; +0,14] | -0,10 [-0,17; -0,02] | 18 % / 10 % |
| 5–10R | 3953 / 2143 | -0,07 [-0,14; +0,00] | -0,06 [-0,16; +0,04] | +0,02 [-0,08; +0,12] | +0,02 [-0,13; +0,17] | 19 % / 10 % |
| >10R | 4256 / 1421 | +0,05 [-0,04; +0,14] | +0,04 [-0,11; +0,20] | +0,10 [-0,00; +0,20] | +0,08 [-0,11; +0,27] | 19 % / 10 % |

### H1 espacio libre (ATR)

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| <5 ATR | 9821 / 4933 | -0,01 [-0,05; +0,04] | -0,07 [-0,13; +0,00] | +0,12 [+0,05; +0,19] | -0,06 [-0,15; +0,03] | 18 % / 10 % |
| 5–15 ATR | 8205 / 4446 | -0,11 [-0,16; -0,06] | -0,13 [-0,19; -0,07] | -0,00 [-0,07; +0,07] | -0,09 [-0,19; +0,01] | 18 % / 9 % |
| >15 ATR | 4504 / 1571 | +0,07 [-0,01; +0,15] | +0,04 [-0,10; +0,18] | +0,13 [+0,02; +0,23] | +0,09 [-0,08; +0,26] | 19 % / 10 % |

### H2 reacciones previas en la línea 3

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| 0 | 8510 / 4781 | +0,04 [-0,02; +0,10] | -0,03 [-0,11; +0,04] | +0,14 [+0,06; +0,21] | +0,04 [-0,05; +0,14] | 19 % / 10 % |
| 1 | 5659 / 2569 | -0,04 [-0,11; +0,02] | -0,03 [-0,12; +0,06] | +0,10 [+0,01; +0,19] | -0,03 [-0,16; +0,10] | 19 % / 10 % |
| ≥2 | 8361 / 3600 | -0,09 [-0,13; -0,04] | -0,17 [-0,23; -0,10] | -0,01 [-0,08; +0,07] | -0,20 [-0,30; -0,10] | 17 % / 9 % |

### H3 barrido del punto 1

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sin mínimo previo | 6709 / 3619 | -0,06 [-0,11; -0,00] | -0,05 [-0,12; +0,02] | +0,04 [-0,04; +0,13] | +0,01 [-0,10; +0,12] | 18 % / 9 % |
| no barre | 4091 / 1778 | +0,07 [-0,01; +0,15] | -0,14 [-0,25; -0,03] | +0,23 [+0,11; +0,35] | -0,16 [-0,31; -0,00] | 20 % / 12 % |
| 0–1 ATR | 1683 / 766 | -0,06 [-0,17; +0,05] | -0,07 [-0,23; +0,08] | -0,03 [-0,19; +0,14] | -0,13 [-0,35; +0,12] | 17 % / 9 % |
| 1–2,5 ATR | 2727 / 1273 | -0,06 [-0,16; +0,03] | -0,09 [-0,21; +0,04] | +0,01 [-0,11; +0,15] | -0,10 [-0,27; +0,08] | 17 % / 9 % |
| >2,5 ATR | 7320 / 3514 | -0,03 [-0,09; +0,02] | -0,06 [-0,14; +0,03] | +0,07 [-0,01; +0,15] | -0,03 [-0,14; +0,08] | 18 % / 10 % |

### H4 tendencia 4 h y suelo junto a la EMA20

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 2538 / 405 | -0,03 [-0,12; +0,08] | -0,06 [-0,29; +0,18] | +0,07 [-0,07; +0,21] | -0,05 [-0,37; +0,30] | 19 % / 10 % |
| resto | 19907 / 10515 | -0,03 [-0,06; +0,00] | -0,08 [-0,12; -0,03] | +0,08 [+0,03; +0,13] | -0,05 [-0,11; +0,01] | 18 % / 10 % |

### H4a tendencia 4 h (EMA20 > EMA50)

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 16859 / 3317 | -0,04 [-0,08; -0,01] | -0,02 [-0,10; +0,06] | +0,06 [+0,00; +0,11] | -0,01 [-0,13; +0,11] | 18 % / 10 % |
| no | 5586 / 7603 | +0,02 [-0,05; +0,09] | -0,10 [-0,15; -0,05] | +0,12 [+0,03; +0,22] | -0,07 [-0,14; +0,00] | 18 % / 10 % |

### H4b suelo de 24 h a ≤0,5 % de la EMA20 4 h o 1 d

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 3034 / 547 | -0,02 [-0,11; +0,08] | -0,11 [-0,30; +0,08] | +0,08 [-0,05; +0,21] | -0,03 [-0,30; +0,26] | 19 % / 10 % |
| no | 19411 / 10373 | -0,03 [-0,06; +0,01] | -0,08 [-0,12; -0,03] | +0,08 [+0,03; +0,13] | -0,05 [-0,12; +0,01] | 18 % / 10 % |

### H5a mínimo de entrada a ≤0,3 ATR de la EMA20

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 3477 / 1704 | -0,02 [-0,10; +0,06] | -0,22 [-0,33; -0,10] | +0,05 [-0,06; +0,17] | -0,29 [-0,42; -0,15] | 18 % / 9 % |
| no | 19053 / 9246 | -0,03 [-0,06; +0,01] | -0,05 [-0,10; -0,00] | +0,08 [+0,03; +0,13] | -0,01 [-0,08; +0,06] | 18 % / 10 % |

### H5b EMAs 20/50/100/200 ordenadas al alza

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 12529 / 5179 | -0,02 [-0,06; +0,03] | -0,02 [-0,09; +0,05] | +0,08 [+0,02; +0,15] | +0,01 [-0,08; +0,11] | 18 % / 10 % |
| no | 10001 / 5771 | -0,05 [-0,09; -0,00] | -0,13 [-0,19; -0,07] | +0,07 [-0,00; +0,14] | -0,10 [-0,18; -0,02] | 18 % / 10 % |

### S toques al entrar

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| 2 | 14243 / 7084 | -0,02 [-0,07; +0,02] | -0,04 [-0,09; +0,02] | +0,08 [+0,03; +0,15] | -0,03 [-0,10; +0,05] | 18 % / 10 % |
| ≥3 | 8287 / 3866 | -0,04 [-0,09; +0,02] | -0,15 [-0,22; -0,08] | +0,06 [-0,01; +0,14] | -0,10 [-0,19; +0,00] | 18 % / 10 % |

### S retrocesos por encima de la línea 2

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 6630 / 3136 | -0,02 [-0,08; +0,04] | +0,03 [-0,06; +0,12] | +0,06 [-0,03; +0,15] | +0,14 [+0,02; +0,27] | 18 % / 9 % |
| no | 15900 / 7814 | -0,03 [-0,07; +0,01] | -0,12 [-0,17; -0,07] | +0,08 [+0,02; +0,14] | -0,12 [-0,19; -0,05] | 18 % / 10 % |

### S RSI con picos descendentes en los toques

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 13371 / 6528 | -0,01 [-0,05; +0,04] | -0,04 [-0,10; +0,02] | +0,10 [+0,04; +0,16] | -0,03 [-0,11; +0,06] | 19 % / 10 % |
| no | 9159 / 4422 | -0,06 [-0,11; -0,01] | -0,13 [-0,20; -0,06] | +0,04 [-0,04; +0,11] | -0,09 [-0,18; +0,01] | 18 % / 9 % |

### S pico de volumen en la zona 4

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| sí | 15801 / 7759 | +0,01 [-0,03; +0,05] | -0,07 [-0,12; -0,02] | +0,11 [+0,06; +0,17] | -0,04 [-0,12; +0,03] | 18 % / 10 % |
| no | 6729 / 3191 | -0,12 [-0,18; -0,06] | -0,10 [-0,19; -0,01] | -0,02 [-0,10; +0,07] | -0,07 [-0,18; +0,05] | 18 % / 10 % |

### Apalancamiento: liquidación en el stop S1

| Grupo | Señales exp. / conf. | S1 + nivel · exploración | S1 + nivel · confirmación | S1 + 10R · exploración | S1 + 10R · confirmación | Llega a 5R / 10R (exp.) |
|---|---|---|---|---|---|---|
| llega | 6067 / 2988 | +0,10 [+0,04; +0,16] | -0,01 [-0,09; +0,07] | +0,17 [+0,09; +0,26] | -0,00 [-0,11; +0,11] | 19 % / 9 % |
| no llega | 16463 / 7962 | -0,08 [-0,11; -0,04] | -0,10 [-0,15; -0,05] | +0,04 [-0,01; +0,09] | -0,07 [-0,14; +0,00] | 18 % / 10 % |

## Combinación elegida en exploración con umbral de 0,05R (sensibilidad)

Condiciones: H3 barrido del punto 1 = no barre (+0,1R); H1 espacio libre (ATR) = >15 ATR (+0,1R); H1 espacio libre (R, con S1) = >10R (+0,07R); H2 reacciones previas en la línea 3 = 0 (+0,07R)

| | Exploración | Confirmación |
|---|---|---|
| Base | 22530 · -0,03 [-0,06; +0,00] | 10950 · -0,08 [-0,12; -0,03] |
| Combinación | 549 · +0,26 [+0,00; +0,53] | 122 · -0,34 [-0,74; +0,13] |

## Combinación elegida en exploración (S1 + nivel)

Condiciones: ninguna supera a la base en ≥0,2R con ≥30 señales

## Dependencia de pocas monedas (todo el periodo)

- S1 + nivel: 234 monedas, R medio -0,04; sin la mejor -0,05; sin las 2 mejores -0,05. Mejores: QNT +139R, AR +79R, JUP +76R, CAP +75R, ACE +62R.
- S1 + 10R: 234 monedas, R medio +0,03; sin la mejor +0,03; sin las 2 mejores +0,03. Mejores: JUP +128R, QNT +120R, ETHFI +112R, KMNO +109R, ZEC +104R.
