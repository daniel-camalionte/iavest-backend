import time
import json
from datetime import datetime, date, timezone, timedelta

import config.env as memory
from library.HttpClient import HttpClient
from library.TwelveDataClient import TwelveDataClient
from library.YahooFinanceClient import YahooFinanceClient

# ---------------------------------------------------------------------------
# Cache in-memory
# ---------------------------------------------------------------------------
_cache = {
    "data":      None,
    "timestamp": None,
}

BRASILIA = timezone(timedelta(hours=-3))

# ---------------------------------------------------------------------------
# Feriados B3 — atualizar anualmente
# ---------------------------------------------------------------------------
B3_HOLIDAYS = {
    2026: [
        date(2026,  1,  1),  # Confraternização Universal
        date(2026,  2, 16),  # Carnaval (segunda)
        date(2026,  2, 17),  # Carnaval (terça)
        date(2026,  4,  3),  # Paixão de Cristo
        date(2026,  4, 21),  # Tiradentes
        date(2026,  5,  1),  # Dia do Trabalho
        date(2026,  6,  4),  # Corpus Christi
        date(2026,  9,  7),  # Independência do Brasil
        date(2026, 10, 12),  # Nossa Senhora Aparecida
        date(2026, 11,  2),  # Finados
        date(2026, 11, 15),  # Proclamação da República
        date(2026, 11, 20),  # Consciência Negra
        date(2026, 12, 24),  # Véspera de Natal (B3 não opera)
        date(2026, 12, 25),  # Natal
        date(2026, 12, 31),  # Véspera de Ano Novo (B3 não opera)
    ],
    2027: [
        date(2027,  1,  1),  # Confraternização Universal
    ],
}


def _is_b3_trading_day(dt: datetime) -> bool:
    """Retorna True se a data é um dia útil de operação da B3."""
    d = dt.date()
    if d.weekday() >= 5:  # sábado=5, domingo=6
        return False
    holidays = B3_HOLIDAYS.get(d.year, [])
    return d not in holidays

# ---------------------------------------------------------------------------
# Prompt para o Claude
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """Você é um analista quantitativo especialista no mercado futuro brasileiro, com foco no Mini Índice Bovespa (WIN).

Sua tarefa é analisar os dados técnicos e macroeconômicos fornecidos e retornar um JSON estruturado com a análise completa.

REGRAS DE SCORING:

Score Técnico (0–100):
- Preço vs SMA9:    preço acima = +12, abaixo = 0
- Preço vs SMA21:   preço acima = +12, abaixo = 0
- Preço vs SMA50:   preço acima = +10, abaixo = 0
- EMA9 vs EMA21:    EMA9 > EMA21 (Golden Cross) = +12, caso contrário = 0
- RSI:              >55 = +12 (força), 45–55 = +6 (neutro), <45 = 0
- MACD histograma:  positivo e crescente = +12, positivo estável = +8, negativo = 0
- Bollinger Bands:  preço acima da banda do meio = +8, abaixo = 0 — ATENÇÃO: quando ADX > 25 (mercado em tendência), o sinal das Bollinger Bands perde relevância direcional e deve ser usado apenas como contexto de volatilidade, não como sinal de entrada
- ADX:              >25 (tendência forte) = +8 bônus de confirmação, <20 = sem bônus — em mercados de tendência (ADX > 25), ADX + DI têm prioridade máxima sobre BBands
- OBV:              volume confirma a direção do preço = +8, diverge = 0
- Dias consecutivos: ≥3 dias na mesma direção = +4 (momentum), ≤-3 = -4

Score Macro (0–100):
- S&P 500 (SPY):         alta >0.5% = +18, estável = +10, queda >0.5% = 0
- Nasdaq (QQQ):          alta >0.5% = +11, estável = +6, queda >0.5% = 0
- Dow Jones (DIA):       alta >0.5% = +7, estável = +4, queda >0.5% = 0
- Futuros S&P (ES1!):    alta >0.3% pré-mercado = +4 bônus, queda >0.3% = -4
- Futuros Nasdaq (NQ1!): alta >0.3% pré-mercado = +3 bônus, queda >0.3% = -3
- Petróleo (USO):        preço >100 = -15 (inflação), 80–100 = 0, <80 = +4
- USD/BRL:               variação >1% = -12 (fuga de capital), <-1% = +12, estável = 0
- VIX (VXX):             <20 = +14 (baixo estresse), 20–30 = +7 (médio), >30 = 0 (alto)
- DXY (Dólar Index):     alta >0.5% = -14 (risco emergentes), estável = 0, queda >0.5% = +14
- Brasil ETF (EWZ):      alta >1% = +18 (proxy direto do WIN gap), estável = +9, queda >1% = 0 — este é o indicador mais relevante para prever gap de abertura do Mini Índice
- Petrobras ADR (PBR):   alta >1% = +15, estável = +7, queda >1% = 0
- Vale ADR (VALE):       alta >1% = +10, estável = +5, queda >1% = 0

Score Total = (Score Técnico × 0.65) + (Score Macro × 0.35)

CONTEXTO DE MERCADO (usar na narrativa, não altera score diretamente):
- Gap de abertura: gap positivo >0.5% = abertura otimista; gap negativo >0.5% = pressão vendedora
- Dia da semana: segunda-feira tende a refletir eventos do fim de semana; sexta-feira tem menor volume
- Dias consecutivos na mesma direção: indicam momentum mas também risco de reversão após 5+ dias

PONTO CEGO OPERACIONAL:
- Se os dados de ES1! ou NQ1! estiverem ausentes (campo "_error"), informe no campo "blind_spots" que a análise não tem visibilidade dos futuros americanos pré-mercado. Entre 09:00 e 10:30 BRT, o Mini Índice é fortemente influenciado pelos futuros do S&P 500 — a ausência desse dado reduz a confiança da análise.
- Se EWZ estiver com variação 0% e mercado fechado, sinalize que não há visibilidade do gap de abertura do WIN — este é o ponto cego mais crítico pois o EWZ é o proxy direto do Mini Índice.
- Se PBR ou VALE estiverem com variação 0% e mercado fechado, sinalize que são dados do fechamento anterior, sem informação de pré-mercado.

PREÇO DE ATIVAÇÃO:
- Calcule gatilhos de entrada baseados nos níveis técnicos disponíveis (prev_low, prev_high, SMA9, SMA21, SMA50, Bollinger).
- Para VENDA: sell_trigger = menor valor entre prev_low e SMA9. Só vender se o preço romper abaixo desse nível.
- Para COMPRA: buy_trigger = maior valor entre prev_high e SMA21. Só comprar se o preço romper acima desse nível com força.
- Para INDEFINIÇÃO: calcule ambos — sell_trigger (suporte a perder) e buy_trigger (resistência a romper).
- O objetivo é evitar entrada na abertura e aguardar confirmação de rompimento após os primeiros 30 minutos de pregão.
- No campo "description", explique qual nível foi escolhido e por quê.

RECOMENDAÇÃO:
- Score ≥ 60: COMPRA      → usar IAs de compra (Sirius Trader, Yang Trader)
- Score ≤ 40: VENDA       → usar IAs de venda (Selene Trader, Ying Trader)
- Score 41–59: INDEFINIÇÃO → usar todas as IAs (ambas compra e venda)

CONFIANÇA:
- Score ≥ 80 ou ≤ 20: ALTA
- Score ≥ 65 ou ≤ 35: MEDIA
- Demais: BAIXA

Você DEVE retornar EXCLUSIVAMENTE um JSON válido, sem texto adicional, sem markdown, sem blocos de código.
TODOS os campos do formato abaixo são OBRIGATÓRIOS — incluindo "activation_price" e "blind_spots".
Exemplo de preenchimento obrigatório:
  "activation_price": {"trigger": null, "buy_trigger": 182727.67, "sell_trigger": 179915.0, "description": "Compra acima da SMA21; venda abaixo da mínima D-1"}
  "blind_spots": ["PBR e VALE com variação 0% — dados do fechamento anterior, sem pré-mercado disponível"]

Formato obrigatório:
{
  "score_technical": <int 0-100>,
  "score_macro": <int 0-100>,
  "score_total": <int 0-100>,
  "recommendation": "<COMPRA|VENDA|INDEFINIÇÃO>",
  "confidence": "<ALTA|MEDIA|BAIXA>",
  "ia": {
    "buy": <true|false>,
    "sell": <true|false>
  },
  "technical_signals": {
    "sma9": "<COMPRA|VENDA|N/D>",
    "sma21": "<COMPRA|VENDA|N/D>",
    "sma50": "<COMPRA|VENDA|N/D>",
    "ema_cross": "<GOLDEN_CROSS|DEATH_CROSS|N/D>",
    "rsi": "<COMPRA|NEUTRO|VENDA|N/D>",
    "macd": "<COMPRA|VENDA|N/D>",
    "bbands": "<COMPRA|VENDA|N/D>",
    "adx": "<TENDENCIA_FORTE|TENDENCIA_FRACA|N/D>",
    "obv": "<CONFIRMACAO|DIVERGENCIA|N/D>"
  },
  "macro_signals": {
    "spy": "<POSITIVO|NEUTRO|NEGATIVO>",
    "qqq": "<POSITIVO|NEUTRO|NEGATIVO>",
    "dia": "<POSITIVO|NEUTRO|NEGATIVO>",
    "es1": "<POSITIVO|NEUTRO|NEGATIVO>",
    "nq1": "<POSITIVO|NEUTRO|NEGATIVO>",
    "uso": "<POSITIVO|NEUTRO|NEGATIVO>",
    "vxx": "<BAIXO|MEDIO|ALTO>",
    "usdbrl": "<POSITIVO|NEUTRO|NEGATIVO>",
    "dxy": "<POSITIVO|NEUTRO|NEGATIVO>",
    "ewz": "<POSITIVO|NEUTRO|NEGATIVO>",
    "pbr": "<POSITIVO|NEUTRO|NEGATIVO>",
    "vale": "<POSITIVO|NEUTRO|NEGATIVO>"
  },
  "market_context": {
    "opening_gap": "<POSITIVO|NEUTRO|NEGATIVO>",
    "consecutive_days": <int>,
    "momentum": "<FORTE_ALTA|LEVE_ALTA|NEUTRO|LEVE_BAIXA|FORTE_BAIXA>"
  },
  "activation_price": {
    "trigger": <float | null>,
    "buy_trigger": <float | null>,
    "sell_trigger": <float | null>,
    "description": "<string explicando o nível e por que foi escolhido>"
  },
  "blind_spots": ["<string descrevendo cada ponto cego identificado>"],
  "narrative": "<string com análise fundamentalista em português, 3–5 parágrafos>"
}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _vix_level(vxx_price: float) -> str:
    if vxx_price < 20:
        return "BAIXO"
    if vxx_price < 30:
        return "MEDIO"
    return "ALTO"


def _calculate_contracts(score: int, max_contracts: int, vix_level: str) -> int:
    """
    Calcula contratos proporcionalmente à distância do score em relação ao neutro (50).
    VIX ALTO limita a no máximo 2 contratos.
    """
    confidence = abs(score - 50) / 50  # 0.0 a 1.0
    base = max(1, round(max_contracts * confidence))
    cap = 2 if vix_level == "ALTO" else max_contracts
    return min(base, cap)


def _format_macro_for_prompt(macro: dict) -> str:
    lines = []
    for key, d in macro.items():
        if "_error" in d:
            lines.append(f"  {d.get('name', key)}: N/D (erro: {d['_error']})")
        else:
            lines.append(
                f"  {d['name']}: preço={d.get('price', 'N/D')}, variação={d.get('percent_change', 0):+.2f}%"
            )
    return "\n".join(lines)


def _format_technical_for_prompt(tech: dict) -> str:
    price      = tech.get("price")
    prev_close = tech.get("prev_close")
    prev_high  = tech.get("prev_high")
    prev_low   = tech.get("prev_low")
    gap_pct    = tech.get("opening_gap_pct")
    consec     = tech.get("consecutive_days", 0)
    volume     = tech.get("volume")
    obv        = tech.get("obv")
    sma9       = tech.get("sma9")
    sma21      = tech.get("sma21")
    sma50      = tech.get("sma50")
    sma200     = tech.get("sma200")
    ema9       = tech.get("ema9")
    ema21      = tech.get("ema21")
    rsi        = tech.get("rsi")
    macd       = tech.get("macd") or {}
    bb         = tech.get("bbands") or {}
    adx        = tech.get("adx") or {}

    def fmt(v):
        return f"{v:.2f}" if v is not None else "N/D"

    def fmt_int(v):
        return f"{int(v):,}" if v is not None else "N/D"

    consec_str = f"+{consec} dias subindo" if consec > 0 else f"{consec} dias caindo" if consec < 0 else "indefinido"

    lines = [
        f"  Preço atual: {fmt(price)} pts  |  Fechamento D-1: {fmt(prev_close)} pts",
        f"  Máxima D-1: {fmt(prev_high)} pts  |  Mínima D-1: {fmt(prev_low)} pts",
        f"  Gap abertura: {fmt(gap_pct)}%   |  Dias consecutivos: {consec_str}",
        f"  Volume hoje: {fmt_int(volume)}  |  OBV acumulado: {fmt_int(obv)}",
        f"  SMA9:  {fmt(sma9)}   | SMA21: {fmt(sma21)}  | SMA50: {fmt(sma50)}  | SMA200: {fmt(sma200)}",
        f"  EMA9:  {fmt(ema9)}   | EMA21: {fmt(ema21)}",
        f"  RSI(14): {fmt(rsi)}",
        f"  MACD: linha={fmt(macd.get('macd'))} | sinal={fmt(macd.get('signal'))} | histograma={fmt(macd.get('histogram'))}",
        f"  Bollinger: superior={fmt(bb.get('upper'))} | meio={fmt(bb.get('middle'))} | inferior={fmt(bb.get('lower'))}",
        f"  ADX: {fmt(adx.get('adx'))} | +DI: {fmt(adx.get('plus_di'))} | -DI: {fmt(adx.get('minus_di'))}",
    ]
    return "\n".join(lines)


_WEEKDAYS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _call_claude(macro, technical):
    api_key  = memory.anthropic["API_KEY"]
    now_br   = datetime.now(tz=BRASILIA)
    weekday  = _WEEKDAYS_PT[now_br.weekday()]
    user_content = (
        f"Analise os dados abaixo e retorne o JSON conforme instruído.\n\n"
        f"Data: {now_br.strftime('%Y-%m-%d')} ({weekday}) — horário Brasília: {now_br.strftime('%H:%M')}\n\n"
        "=== CONTEXTO MACROECONÔMICO ===\n"
        + _format_macro_for_prompt(macro) +
        "\n\n=== DADOS TÉCNICOS — MINI ÍNDICE (WIN) / IBOVESPA ===\n"
        + _format_technical_for_prompt(technical)
    )

    resp = HttpClient.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":          api_key,
            "anthropic-version":  "2023-06-01",
            "content-type":       "application/json",
        },
        payload={
            "model":      "claude-opus-4-5",
            "max_tokens": 2048,
            "system":     SYSTEM_PROMPT,
            "messages":   [{"role": "user", "content": user_content}],
        },
        timeout=60,
    )

    if not resp or resp["status_code"] not in (200, 201):
        return None

    raw_text = resp["data"]["content"][0]["text"].strip()

    # Remove blocos markdown se Claude enviar mesmo assim
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------
class MarketAnalysisRule:

    def analyze(self, max_contracts: int):
        now_br = datetime.now(tz=BRASILIA)
        if not _is_b3_trading_day(now_br):
            weekday_names = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
            return {
                "trading_day": False,
                "date": now_br.strftime("%Y-%m-%d"),
                "weekday": weekday_names[now_br.weekday()],
                "message": "B3 não opera hoje. Análise disponível apenas em dias úteis.",
            }, 200

        ttl = memory.market["CACHE_TTL"]
        now = time.time()

        # --- Cache HIT ---
        if _cache["data"] and _cache["timestamp"] and (now - _cache["timestamp"]) < ttl:
            cached = _cache["data"]
            vix_lv = cached["macro_context"]["vxx"]["vix_level"]
            contracts = _calculate_contracts(cached["score"]["total"], max_contracts, vix_lv)
            expires_at = datetime.fromtimestamp(_cache["timestamp"] + ttl, tz=BRASILIA).strftime("%Y-%m-%dT%H:%M:%S")
            return {
                **cached,
                "contracts": contracts,
                "cached": True,
                "cache_expires_at": expires_at,
            }, 200

        # --- Cache MISS: coleta dados ---
        td        = TwelveDataClient(memory.twelvedata["API_KEY"])
        yf        = YahooFinanceClient()
        macro     = td.get_macro_quotes()
        futures   = yf.get_yahoo_macro_quotes()
        macro.update(futures)
        technical = yf.get_ibov_technical()

        # Aborta se a coleta de dados falhou por rate limit ou auth
        if "_error" in macro:
            err = macro["_error"]
            return {"error": "Falha ao coletar dados macro", "detail": err}, 503
        if technical.get("_error") and technical.get("price") is None:
            err = technical["_error"]
            return {"error": "Falha ao coletar dados técnicos", "detail": err}, 503

        vix_price = macro.get("vxx", {}).get("price", 0)
        vix_lv    = _vix_level(vix_price)
        macro["vxx"]["vix_level"] = vix_lv

        # --- Chama Claude ---
        claude_result = _call_claude(macro, technical)
        if not claude_result:
            return {"error": "Falha ao processar análise com Claude"}, 500

        score_total = claude_result.get("score_total", 50)
        contracts   = _calculate_contracts(score_total, max_contracts, vix_lv)
        now_dt      = datetime.now(tz=BRASILIA)

        payload = {
            "date":         now_dt.strftime("%Y-%m-%d"),
            "generated_at": now_dt.strftime("%H:%M"),
            "recommendation":    claude_result.get("recommendation"),
            "contracts":         contracts,
            "confidence":        claude_result.get("confidence"),
            "score": {
                "total":     score_total,
                "technical": claude_result.get("score_technical"),
                "macro":     claude_result.get("score_macro"),
            },
            "ia":              claude_result.get("ia"),
            "technical_data":  technical,
            "technical_signals": claude_result.get("technical_signals"),
            "market_context":  claude_result.get("market_context"),
            "macro_context":   macro,
            "macro_signals":   claude_result.get("macro_signals"),
            "narrative":       claude_result.get("narrative"),
            "cached":          False,
            "cache_ttl_minutes": ttl // 60,
            "cache_expires_at":  datetime.fromtimestamp(now + ttl, tz=BRASILIA).strftime("%Y-%m-%dT%H:%M:%S"),
        }

        # Armazena cache (sem o campo contracts, que é recalculado por request)
        _cache["data"]      = {k: v for k, v in payload.items() if k != "contracts"}
        _cache["timestamp"] = now

        return payload, 200

    def clear_cache(self):
        _cache["data"]      = None
        _cache["timestamp"] = None
        return {"cleared": True, "message": "Cache limpo com sucesso"}, 200
