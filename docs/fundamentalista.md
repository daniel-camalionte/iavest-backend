# O Fundamentalista (Market Analysis) — o que ele faz

> Análise **fundamentalista/macro diária** do WIN (Mini Índice). Junta **dados técnicos do
> Ibovespa** + **contexto macroeconômico global** e pede pro **Claude Opus** produzir um
> parecer estruturado (score, recomendação, cenários de daytrade, narrativa). É o **"viés do
> dia"** que alimenta o resto do sistema. Código: [rule/MarketAnalysis.py](../rule/MarketAnalysis.py).

---

## 1. Visão geral em uma frase
A cada chamada, ele **coleta ~12 indicadores macro + ~15 indicadores técnicos**, **converte os
níveis do Ibovespa para a escala do WIN**, manda tudo pro **Claude Opus 4.8** com um prompt que
define **regras de pontuação**, e devolve um **JSON** com **score (0–100), recomendação
(COMPRA/VENDA/INDEFINIÇÃO), confiança, gatilhos de entrada, 3 cenários de daytrade e uma
narrativa**. Pós-processa de forma determinística (contratos, tick, R/R), **salva no banco** e
**cacheia**.

## 2. Rotas (todas em `/market`)
| Rota | O que faz |
|---|---|
| `GET /market/analyze?id_ativos_base=1&contracts=N` | **Roda a análise** (ou devolve do cache). `contracts` = máximo de contratos. |
| `GET /market/analysis` | Lista as últimas 10 análises (grid + chart marker). |
| `GET /market/analysis/<id>` ou `/latest` | Detalhe de uma análise (com cenários, blind spots, robôs). |
| `GET /market/cache` | Limpa o cache. |
| `GET /market/ping` / `/debug` / `/price` | Saúde / debug / preço. |

> Obs: as rotas `/market/intraday/*` são de **outro módulo** (o intraday/Haiku), não do fundamentalista.

## 3. Modelo de IA
- **Claude Opus 4.8** (`claude-opus-4-8`), `max_tokens=4096`, via API Anthropic.
- O fundamentalista usa **Claude** (não OpenAI). O Chat é que usa OpenAI — não misturar.

---

## 4. O fluxo completo (passo a passo)

```
/market/analyze
   │
   ├─ 0. É dia útil da B3? (não opera fds/feriado) ──── não → devolve "B3 não opera hoje"
   │
   ├─ 1. Cache válido? (TTL por ativo) ──── sim → recalcula só os contratos e devolve
   │
   ├─ 2. Coleta dados (Yahoo Finance):
   │       macro     = get_yahoo_macro_quotes()   (SPY, EWZ, VIX, dólar, …)
   │       technical = get_ibov_technical()        (Ibov diário, 1 ano: SMA/RSI/MACD/…)
   │
   ├─ 3. Converte Ibovespa → WIN (basis empírico: WIN_real / Ibov_real)
   │       (preço, prev high/low, SMAs, EMAs, Bollinger viram escala do WIN)
   │
   ├─ 4. Classifica o VIX (BAIXO/MEDIO/ALTO)
   │
   ├─ 5. Chama o Claude Opus com o system prompt (regras de score) + os dados
   │
   ├─ 6. Pós-processa de forma DETERMINÍSTICA:
   │       - contratos = f(score, max_contracts, VIX)
   │       - arredonda gatilhos e cenários pro tick do WIN (múltiplos de 5)
   │       - conserta cenários de daytrade (R/R ≥ 1.5, stop no lado certo, dropa alvo_2)
   │
   ├─ 7. Monta o payload, cacheia e SALVA no banco (analysis_market)
   │
   └─ 8. Devolve o JSON pro cliente
```

---

## 5. Dados de entrada

### 5a. Macroeconômicos (Yahoo Finance) — contexto global
| Indicador | Ticker | Por quê |
|---|---|---|
| S&P 500 | ^GSPC / SPY | direção do mercado americano |
| Nasdaq-100 | ^NDX / QQQ | tech US |
| Dow Jones | ^DJI / DIA | blue chips US |
| Futuros S&P | ES1! | **pré-mercado** (influencia o WIN 09:00–10:30) |
| Futuros Nasdaq | NQ1! | pré-mercado tech |
| Petróleo Brent | BZ=F | inflação / Petrobras |
| USD/BRL | dólar | correlação **inversa** com WIN (fuga de capital) |
| VIX | ^VIX | estresse/medo do mercado |
| DXY | índice do dólar | risco pra emergentes |
| **EWZ** | ETF Brasil | **proxy mais direto do gap de abertura do WIN** |
| Petrobras ADR | PBR | peso pesado do índice |
| Vale ADR | VALE | peso pesado do índice |

### 5b. Técnicos (do Ibovespa diário, histórico de ~1 ano)
- **Preço/níveis:** preço atual, fechamento D-1, máxima/mínima D-1, **gap de abertura**, dias consecutivos na mesma direção, volume, OBV.
- **Médias:** SMA 9/21/50/200, EMA 9/21.
- **Osciladores/tendência:** RSI(14), MACD (linha/sinal/histograma), Bollinger Bands (sup/meio/inf), ADX (+DI/−DI).

> Os indicadores são calculados no **Ibovespa diário** (mais histórico e confiável), e depois os **níveis de preço** são convertidos pra escala do WIN.

## 6. Conversão Ibovespa → WIN
Usa um **basis empírico**: `basis = WIN_real_fechamento / Ibov_real` (último candle real do WIN na
`mt5_candles`). É mais fiel que o carrego teórico (SELIC), que superestimava o WIN em ~3% e divergia
do intraday. Fallback: carrego teórico se não houver candle do WIN. Guarda o **Ibov spot** original
(`td_ibov_price`) pra exibição.

---

## 7. O Scoring (definido no prompt do Claude)

### Score Técnico (0–100) — soma de sinais
| Sinal | Pontos |
|---|---|
| Preço > SMA9 / SMA21 / SMA50 | +12 / +12 / +10 |
| EMA9 > EMA21 (Golden Cross) | +12 |
| RSI > 55 / 45–55 / < 45 | +12 / +6 / 0 |
| MACD histograma positivo crescente / estável / negativo | +12 / +8 / 0 |
| Bollinger: preço acima do meio | +8 *(perde relevância se ADX>25)* |
| ADX > 25 (tendência forte) | +8 bônus |
| OBV confirma o preço | +8 |
| ≥3 dias na mesma direção | +4 (ou −4 se ≤−3) |

### Score Macro (0–100) — soma de sinais
| Sinal | Pontos (alta / estável / queda) |
|---|---|
| S&P 500 | +18 / +10 / 0 |
| Nasdaq | +11 / +6 / 0 |
| Dow | +7 / +4 / 0 |
| Futuros ES1 / NQ1 (pré-mercado) | ±4 / ±3 bônus |
| Brent | <80 = +4 ; >100 = −15 (inflação) |
| USD/BRL | cai >1% = +12 ; sobe >1% = −12 |
| VIX | <20 = +14 ; 20–30 = +7 ; >30 = 0 |
| DXY | cai >0.5% = +14 ; sobe >0.5% = −14 |
| **EWZ** | alta >1% = **+18** (mais relevante p/ o gap) |
| Petrobras ADR | +15 / +7 / 0 |
| Vale ADR | +10 / +5 / 0 |

### Score Total
```
Score Total = (Técnico × 0,65) + (Macro × 0,35)
```

## 8. Recomendação e Confiança
| Score Total | Recomendação | IAs acionadas |
|---|---|---|
| ≥ 60 | **COMPRA** | Sirius / Yang (compra) |
| ≤ 40 | **VENDA** | Selene / Ying (venda) |
| 41–59 | **INDEFINIÇÃO** | todas (compra e venda) |

| Confiança | Faixa |
|---|---|
| **ALTA** | score ≥ 80 ou ≤ 20 |
| **MEDIA** | score ≥ 65 ou ≤ 35 |
| **BAIXA** | demais |

---

## 9. O que o Claude devolve (JSON)
- `score_technical`, `score_macro`, `score_total`
- `recommendation` (COMPRA/VENDA/INDEFINIÇÃO) + `confidence` (ALTA/MEDIA/BAIXA)
- `ia`: `{buy, sell}` — quais robôs ligar
- `technical_signals`: leitura de cada indicador técnico (SMA, RSI, MACD, ADX, OBV…)
- `macro_signals`: leitura de cada indicador macro (SPY, EWZ, VIX, dólar…)
- `market_context`: gap de abertura, dias consecutivos, momentum
- **`activation_price`**: gatilhos de entrada (`buy_trigger`, `sell_trigger`) — **objetivo: NÃO entrar na abertura, esperar romper níveis após os 30 primeiros min**
- **`blind_spots`**: pontos cegos (ex.: ES1/NQ1 ausentes → sem visão dos futuros US; EWZ 0% mercado fechado → sem visão do gap)
- **`daytrade_scenarios`**: 3 cenários — **alta**, **baixa**, **reversão** — cada um com `condicao`, `entrada`, `stop_loss`, `alvo_1`, `risco_retorno`, `forca`
- `narrative`: análise fundamentalista em texto (3–5 parágrafos, PT)

## 10. Pós-processamento determinístico (depois do Claude)
A IA **não decide matemática sozinha** — o código corrige:
- **Contratos:** calculados localmente (ver §11).
- **Tick do WIN:** todos os níveis arredondados pra **múltiplos de 5**.
- **Cenários de daytrade** (`_enrich_daytrade_scenarios`):
  - valida a direção pela **geometria** (alvo vs entrada), não pelo nome;
  - **aperta o stop** pra garantir **R/R ≥ 1,5** no alvo_1;
  - conserta **stop do lado errado**;
  - **dropa o alvo_2** (evita bug de ordenação);
  - calcula `risco_pontos` e `risco_reais` (× R$0,20/pt).

## 11. Cálculo de contratos
```python
confidence = |score − 50| / 50          # 0.0 a 1.0 (distância do neutro)
base       = max(1, round(max_contracts × confidence))
cap        = 2 se VIX ALTO senão max_contracts
contratos  = min(base, cap)
```
Ou seja: **quanto mais longe de 50 (mais convicção), mais contratos** — limitado a 2 se o VIX
estiver alto (mercado estressado).

## 12. Cache
- Cache **in-memory por `id_ativos_base`**, TTL configurável (`memory.market["CACHE_TTL"]`).
- No cache HIT, **recalcula só os contratos** (porque o `max_contracts` da chamada pode mudar) e devolve o resto.

## 13. Dia útil da B3
Não roda em fim de semana nem feriado (`B3_HOLIDAYS`, atualizado por ano). Fora de dia útil,
devolve `{"trading_day": false, "message": "B3 não opera hoje"}`.

---

## 14. Persistência (tabela `analysis_market`)
Cada análise salva **tudo**: scores, recomendação, confiança, contratos, `ia_buy/ia_sell`, os
sinais técnicos (`sig_*`), os sinais macro (`msig_*`), o contexto (`ctx_*`), os gatilhos (`ap_*`),
os dados técnicos convertidos (`td_*`), os dados macro brutos (`mc_*`), `blind_spots`,
`daytrade_scenarios` (JSON), `narrative` e o `payload_json` completo. Falha no save **não** derruba a
resposta.

## 15. Como conecta com o resto do sistema
- **Intraday (Haiku):** usa a recomendação do fundamentalista como **"viés do dia"** (contexto/regime) — mas **quem decide compra/venda no intraday é o próprio intraday**, não o fundamental (o fundamental é contexto, não veto).
- **Primeiro Tiro** (quando ligado): a **confluência de abertura** lê `mc_ewz_pct`, `mc_spy_pct`, `mc_es1_pct`, `td_opening_gap_pct` desta análise.
- **Robôs (Sirius/Selene/Yang/Ying):** o `ia.buy/sell` diz quais ligar; o detalhe (`/analysis/<id>`) mostra **quais robôs operaram no dia e se estavam alinhados** com a recomendação.
- **Front:** listagem com **chart marker** (seta verde COMPRA / vermelha VENDA / círculo laranja INDEFINIÇÃO) + score + preço.

## 16. Robustez / pontos de atenção
- **Pontos cegos explícitos:** o prompt obriga o Claude a sinalizar quando faltam ES1/NQ1 (sem visão dos futuros US 09:00–10:30) ou EWZ (proxy do gap) — porque isso **reduz a confiança**.
- **Parse tolerante:** `json.loads(strict=False)` — o modelo às vezes solta caractere de controle cru numa string; sem isso a rota estourava 500.
- **Tag de versão nos erros** (`mkt-2026-06-17.1`): confirma se o servidor está com o código atualizado e se a resposta truncou (`max_tokens`).
- **EWZ é o indicador mais crítico** pro gap de abertura — o prompt dá peso máximo a ele.

---

### Resumo de uma linha
O fundamentalista é o **"economista" do sistema**: lê o mundo (macro US, dólar, commodities, EWZ) e
o gráfico diário do Ibov, pede ao **Claude Opus** um parecer com **score + recomendação + cenários**,
ajusta tudo pro WIN de forma determinística, e entrega o **viés do dia** que orienta os robôs e
contextualiza o intraday.
