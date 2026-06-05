import time
import json
from abc import ABC, abstractmethod
from datetime import datetime, date, timezone, timedelta

import config.env as memory
from library.HttpClient import HttpClient
from library.TwelveDataClient import TwelveDataClient
from library.YahooFinanceClient import YahooFinanceClient
from model.MarketAnalysis import MarketAnalysisModel

# ---------------------------------------------------------------------------
# Cache in-memory — keyed by id_ativos_base
# ---------------------------------------------------------------------------
_cache = {}  # {id_ativos_base: {"data": None, "timestamp": None}}

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
# System prompt — WIN
# ---------------------------------------------------------------------------
_WIN_SYSTEM_PROMPT = """Você é um analista quantitativo especialista no mercado futuro brasileiro, com foco no Mini Índice Bovespa (WIN).

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

CENÁRIOS DAYTRADE (OBRIGATÓRIO):
Com base nos níveis técnicos disponíveis (prev_low, prev_high, SMA9, SMA21, SMA50, Bollinger Bands), defina 3 cenários operacionais para o dia:
- "alta": mercado rompe para cima — entrada acima do buy_trigger, stop abaixo do suporte mais próximo (SMA9 ou prev_low), alvo_1 na Bollinger superior ou SMA50, alvo_2 na resistência seguinte se houver espaço
- "baixa": mercado rompe para baixo — entrada abaixo do sell_trigger, stop acima da resistência mais próxima (SMA9 ou prev_high), alvo_1 na Bollinger inferior ou SMA50 abaixo, alvo_2 no próximo suporte relevante
- "reversao": mercado cai, toca suporte e reverte — entrada no rompimento de volta acima do pivot de mínima, stop abaixo do suporte testado, alvo_1 na região de entrada original

Regras para os cenários daytrade:
- Stop loss SEMPRE baseado em níveis técnicos reais (Bollinger, SMA, prev_high/low), nunca percentuais fixos
- Risco:retorno mínimo 1:1.5 para forca FORTE, 1:1 para forca MEDIA
- "forca": FORTE se o cenário está alinhado com a recommendation principal, FRACA se é contrário, MEDIA se é neutro
- Incluir os 3 cenários sempre, mesmo que um deles tenha forca FRACA
- "condicao": frase objetiva descrevendo quando o operador deve entrar (ex: "Se romper acima de 127500 com volume após 10h00")

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
  "daytrade_scenarios": {
    "alta":     {"condicao": "<string>", "entrada": <float>, "stop_loss": <float>, "alvo_1": <float>, "alvo_2": <float|null>, "risco_retorno": "<string>", "forca": "<FORTE|MEDIA|FRACA>"},
    "baixa":    {"condicao": "<string>", "entrada": <float>, "stop_loss": <float>, "alvo_1": <float>, "alvo_2": <float|null>, "risco_retorno": "<string>", "forca": "<FORTE|MEDIA|FRACA>"},
    "reversao": {"condicao": "<string>", "entrada": <float>, "stop_loss": <float>, "alvo_1": <float>, "alvo_2": <float|null>, "risco_retorno": "<string>", "forca": "<FORTE|MEDIA|FRACA>"}
  },
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


def _call_claude(macro: dict, technical: dict, system_prompt: str):
    api_key  = memory.anthropic["API_KEY"]
    now_br   = datetime.now(tz=BRASILIA)
    weekday  = _WEEKDAYS_PT[now_br.weekday()]
    user_content = (
        f"Analise os dados abaixo e retorne o JSON conforme instruído.\n\n"
        f"Data: {now_br.strftime('%Y-%m-%d')} ({weekday}) — horário Brasília: {now_br.strftime('%H:%M')}\n\n"
        "=== CONTEXTO MACROECONÔMICO ===\n"
        + _format_macro_for_prompt(macro) +
        "\n\n=== DADOS TÉCNICOS ===\n"
        + _format_technical_for_prompt(technical)
    )

    resp = HttpClient.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        payload={
            "model":      "claude-opus-4-5",
            "max_tokens": 2048,
            "system":     system_prompt,
            "messages":   [{"role": "user", "content": user_content}],
        },
        timeout=60,
    )

    if not resp or resp["status_code"] not in (200, 201):
        _err = resp["data"] if resp else "sem resposta"
        raise RuntimeError(f"Claude API {resp['status_code'] if resp else 'timeout'}: {_err}")

    raw_text = resp["data"]["content"][0]["text"].strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Claude retornou JSON inválido: {raw_text[:300]}")


# ---------------------------------------------------------------------------
# Base analyzer — template method compartilhado por todos os ativos
# ---------------------------------------------------------------------------
class BaseMarketAnalyzer(ABC):
    id_ativos_base: int = None

    def _cache_bucket(self) -> dict:
        if self.id_ativos_base not in _cache:
            _cache[self.id_ativos_base] = {"data": None, "timestamp": None}
        return _cache[self.id_ativos_base]

    def analyze(self, max_contracts: int):
        now_br = datetime.now(tz=BRASILIA)
        if not _is_b3_trading_day(now_br):
            weekday_names = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
            return {
                "trading_day": False,
                "date":        now_br.strftime("%Y-%m-%d"),
                "weekday":     weekday_names[now_br.weekday()],
                "message":     "B3 não opera hoje. Análise disponível apenas em dias úteis.",
            }, 200

        ttl    = memory.market["CACHE_TTL"]
        now    = time.time()
        bucket = self._cache_bucket()

        # --- Cache HIT ---
        if bucket["data"] and bucket["timestamp"] and (now - bucket["timestamp"]) < ttl:
            cached     = bucket["data"]
            vix_lv     = cached["macro_context"]["vxx"]["vix_level"]
            contracts  = _calculate_contracts(cached["score"]["total"], max_contracts, vix_lv)
            expires_at = datetime.fromtimestamp(bucket["timestamp"] + ttl, tz=BRASILIA).strftime("%Y-%m-%dT%H:%M:%S")
            return {
                **cached,
                "contracts":        contracts,
                "cached":           True,
                "cache_expires_at": expires_at,
            }, 200

        # --- Cache MISS ---
        macro, technical = self._fetch_data()

        if "_error" in macro:
            return {"error": "Falha ao coletar dados macro", "detail": macro["_error"]}, 503
        if technical.get("_error") and technical.get("price") is None:
            return {"error": "Falha ao coletar dados técnicos", "detail": technical["_error"]}, 503

        vix_price              = macro.get("vxx", {}).get("price", 0)
        vix_lv                 = _vix_level(vix_price)
        macro["vxx"]["vix_level"] = vix_lv

        try:
            claude_result = _call_claude(macro, technical, self._get_system_prompt())
        except RuntimeError as e:
            return {"error": "Falha ao processar análise com Claude", "detail": str(e)}, 500

        score_total = claude_result.get("score_total", 50)
        contracts   = _calculate_contracts(score_total, max_contracts, vix_lv)
        now_dt      = datetime.now(tz=BRASILIA)

        payload = {
            "date":              now_dt.strftime("%Y-%m-%d"),
            "generated_at":      now_dt.strftime("%H:%M"),
            "recommendation":    claude_result.get("recommendation"),
            "contracts":         contracts,
            "confidence":        claude_result.get("confidence"),
            "score": {
                "total":     score_total,
                "technical": claude_result.get("score_technical"),
                "macro":     claude_result.get("score_macro"),
            },
            "ia":                claude_result.get("ia"),
            "technical_data":    technical,
            "technical_signals": claude_result.get("technical_signals"),
            "market_context":    claude_result.get("market_context"),
            "macro_context":     macro,
            "macro_signals":     claude_result.get("macro_signals"),
            "activation_price":    claude_result.get("activation_price"),
            "blind_spots":         claude_result.get("blind_spots"),
            "daytrade_scenarios":  claude_result.get("daytrade_scenarios"),
            "narrative":           claude_result.get("narrative"),
            "cached":            False,
            "cache_ttl_minutes": ttl // 60,
            "cache_expires_at":  datetime.fromtimestamp(now + ttl, tz=BRASILIA).strftime("%Y-%m-%dT%H:%M:%S"),
        }

        bucket["data"]      = {k: v for k, v in payload.items() if k != "contracts"}
        bucket["timestamp"] = now

        self._save_analysis(claude_result, technical, macro, contracts, now_dt, payload)

        return payload, 200

    def _save_analysis(self, claude_result: dict, technical: dict, macro: dict, contracts: int, now_dt: datetime, payload: dict):
        try:
            ts   = claude_result.get("technical_signals") or {}
            ctx  = claude_result.get("market_context")    or {}
            ms   = claude_result.get("macro_signals")     or {}
            ap   = claude_result.get("activation_price")  or {}
            ia   = claude_result.get("ia")                or {}
            macd = technical.get("macd")                  or {}
            bb   = technical.get("bbands")                or {}
            adx  = technical.get("adx")                   or {}

            def _mc(key, field):
                return macro.get(key, {}).get(field)

            record = {
                "id_ativos_base":      self.id_ativos_base,
                "analyzed_at":         now_dt.strftime("%Y-%m-%d %H:%M:%S"),

                "recommendation":      claude_result.get("recommendation"),
                "confidence":          claude_result.get("confidence"),
                "contracts":           contracts,
                "ia_buy":              1 if ia.get("buy") else 0,
                "ia_sell":             1 if ia.get("sell") else 0,

                "score_total":         claude_result.get("score_total"),
                "score_technical":     claude_result.get("score_technical"),
                "score_macro":         claude_result.get("score_macro"),

                "sig_sma9":            ts.get("sma9"),
                "sig_sma21":           ts.get("sma21"),
                "sig_sma50":           ts.get("sma50"),
                "sig_ema_cross":       ts.get("ema_cross"),
                "sig_rsi":             ts.get("rsi"),
                "sig_macd":            ts.get("macd"),
                "sig_bbands":          ts.get("bbands"),
                "sig_adx":             ts.get("adx"),
                "sig_obv":             ts.get("obv"),

                "ctx_opening_gap":     ctx.get("opening_gap"),
                "ctx_consecutive_days": ctx.get("consecutive_days"),
                "ctx_momentum":        ctx.get("momentum"),

                "msig_spy":            ms.get("spy"),
                "msig_qqq":            ms.get("qqq"),
                "msig_dia":            ms.get("dia"),
                "msig_es1":            ms.get("es1"),
                "msig_nq1":            ms.get("nq1"),
                "msig_uso":            ms.get("uso"),
                "msig_vxx":            ms.get("vxx"),
                "msig_usdbrl":         ms.get("usdbrl"),
                "msig_dxy":            ms.get("dxy"),
                "msig_ewz":            ms.get("ewz"),
                "msig_pbr":            ms.get("pbr"),
                "msig_vale":           ms.get("vale"),

                "ap_trigger":          ap.get("trigger"),
                "ap_buy_trigger":      ap.get("buy_trigger"),
                "ap_sell_trigger":     ap.get("sell_trigger"),
                "ap_description":      ap.get("description"),

                "td_price":            technical.get("price"),
                "td_prev_close":       technical.get("prev_close"),
                "td_prev_high":        technical.get("prev_high"),
                "td_prev_low":         technical.get("prev_low"),
                "td_opening_gap_pct":  technical.get("opening_gap_pct"),
                "td_consecutive_days": technical.get("consecutive_days"),
                "td_volume":           technical.get("volume"),
                "td_obv":              technical.get("obv"),
                "td_sma9":             technical.get("sma9"),
                "td_sma21":            technical.get("sma21"),
                "td_sma50":            technical.get("sma50"),
                "td_sma200":           technical.get("sma200"),
                "td_ema9":             technical.get("ema9"),
                "td_ema21":            technical.get("ema21"),
                "td_rsi":              technical.get("rsi"),
                "td_macd":             macd.get("macd"),
                "td_macd_signal":      macd.get("signal"),
                "td_macd_histogram":   macd.get("histogram"),
                "td_bb_upper":         bb.get("upper"),
                "td_bb_middle":        bb.get("middle"),
                "td_bb_lower":         bb.get("lower"),
                "td_adx":              adx.get("adx"),
                "td_plus_di":          adx.get("plus_di"),
                "td_minus_di":         adx.get("minus_di"),

                "mc_spy_price":        _mc("spy",    "price"),
                "mc_spy_pct":          _mc("spy",    "percent_change"),
                "mc_qqq_price":        _mc("qqq",    "price"),
                "mc_qqq_pct":          _mc("qqq",    "percent_change"),
                "mc_dia_price":        _mc("dia",    "price"),
                "mc_dia_pct":          _mc("dia",    "percent_change"),
                "mc_es1_price":        _mc("es1",    "price"),
                "mc_es1_pct":          _mc("es1",    "percent_change"),
                "mc_nq1_price":        _mc("nq1",    "price"),
                "mc_nq1_pct":          _mc("nq1",    "percent_change"),
                "mc_uso_price":        _mc("uso",    "price"),
                "mc_uso_pct":          _mc("uso",    "percent_change"),
                "mc_vxx_price":        _mc("vxx",    "price"),
                "mc_vxx_pct":          _mc("vxx",    "percent_change"),
                "mc_vxx_level":        _mc("vxx",    "vix_level"),
                "mc_usdbrl_price":     _mc("usdbrl", "price"),
                "mc_usdbrl_pct":       _mc("usdbrl", "percent_change"),
                "mc_dxy_price":        _mc("dxy",    "price"),
                "mc_dxy_pct":          _mc("dxy",    "percent_change"),
                "mc_ewz_price":        _mc("ewz",    "price"),
                "mc_ewz_pct":          _mc("ewz",    "percent_change"),
                "mc_pbr_price":        _mc("pbr",    "price"),
                "mc_pbr_pct":          _mc("pbr",    "percent_change"),
                "mc_vale_price":       _mc("vale",   "price"),
                "mc_vale_pct":         _mc("vale",   "percent_change"),

                "blind_spots":         json.dumps(claude_result.get("blind_spots") or []),
                "daytrade_scenarios":  json.dumps(claude_result.get("daytrade_scenarios") or {}),
                "narrative":           claude_result.get("narrative", ""),
                "payload_json":        json.dumps(payload),
            }

            MarketAnalysisModel().save(record)
        except Exception:
            pass  # falha no save não deve interromper a resposta ao cliente

    def clear_cache(self):
        bucket             = self._cache_bucket()
        bucket["data"]     = None
        bucket["timestamp"] = None
        return {"cleared": True, "message": "Cache limpo com sucesso"}, 200

    @abstractmethod
    def _fetch_data(self) -> tuple:
        """Retorna (macro: dict, technical: dict) para o ativo específico."""

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Retorna o system prompt do Claude para o ativo específico."""


# ---------------------------------------------------------------------------
# WIN — Mini Índice Bovespa (id_ativos_base=1)
# ---------------------------------------------------------------------------
class WINAnalyzer(BaseMarketAnalyzer):
    id_ativos_base = 1

    def _fetch_data(self):
        td      = TwelveDataClient(memory.twelvedata["API_KEY"])
        yf      = YahooFinanceClient()
        macro   = td.get_macro_quotes()
        futures = yf.get_yahoo_macro_quotes()
        macro.update(futures)
        technical = yf.get_ibov_technical()
        return macro, technical

    def _get_system_prompt(self):
        return _WIN_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Registry e factory
# ---------------------------------------------------------------------------
_ANALYZERS = {
    1: WINAnalyzer,
    # 2: WDOAnalyzer,  # adicionar quando implementado
}


class MarketAnalysisRule:
    """Factory — retorna o analyzer correto para cada id_ativos_base."""

    SUPPORTED = frozenset(_ANALYZERS.keys())

    @staticmethod
    def get(id_ativos_base: int):
        cls = _ANALYZERS.get(id_ativos_base)
        return cls() if cls else None


# ---------------------------------------------------------------------------
# Helpers de listagem / detalhe
# ---------------------------------------------------------------------------

_TRADE_ACCOUNT   = '1001442906'
_ativo_base_cache = {}


def _build_ativo_base(id_ativos_base, nome_only=False):
    from library.MySql import MySql
    from decimal import Decimal

    if id_ativos_base not in _ativo_base_cache:
        rows = MySql().fetch(
            "SELECT id_ativos_base, ticker_base, nome, tipo_mercado, tick_size, vencimento_periodicidade "
            "FROM ativos_base WHERE id_ativos_base = %s",
            (id_ativos_base,)
        )
        if not rows:
            _ativo_base_cache[id_ativos_base] = None
        else:
            r = rows[0]
            _ativo_base_cache[id_ativos_base] = {
                "id_ativos_base":          r["id_ativos_base"],
                "ticker_base":             r["ticker_base"],
                "nome":                    r["nome"],
                "tipo_mercado":            r["tipo_mercado"],
                "tick_size":               float(r["tick_size"]) if isinstance(r["tick_size"], Decimal) else r["tick_size"],
                "vencimento_periodicidade": r["vencimento_periodicidade"],
            }

    data = _ativo_base_cache.get(id_ativos_base)
    if data and nome_only:
        return {"nome": data["nome"]}
    return data

_ALIGN_MAP = {
    'COMPRA': 'buy',
    'VENDA':  'sell',
}


def _build_robos(analyzed_at: str, recommendation: str) -> dict:
    from library.MySql import MySql
    date_ref = str(analyzed_at)[:10]

    sql = """
        SELECT
            t.id_estrategia,
            e.nome,
            t.type,
            COUNT(*)                                                      AS total,
            SUM(CASE WHEN t.operation = 'profit' THEN 1 ELSE 0 END)      AS profit,
            SUM(CASE WHEN t.operation = 'loss'   THEN 1 ELSE 0 END)      AS loss
        FROM trade t
        INNER JOIN estrategia e ON e.id_estrategia = t.id_estrategia
        WHERE t.account_number = %s
          AND t.status         = 'closed'
          AND DATE(t.closed_at) = %s
        GROUP BY t.id_estrategia, e.nome, t.type
    """

    rows = MySql().fetch(sql, (_TRADE_ACCOUNT, date_ref)) or []

    if not rows:
        return {"operaram": False, "indice_acerto_geral": None, "alinhamento": None, "resumo": []}

    tipo_alinhado = _ALIGN_MAP.get((recommendation or '').upper())
    total_geral  = sum(int(r['total']  or 0) for r in rows)
    profit_geral = sum(int(r['profit'] or 0) for r in rows)

    resumo = []
    for r in rows:
        total  = int(r['total']  or 0)
        profit = int(r['profit'] or 0)
        loss   = int(r['loss']   or 0)
        acerto_pct = round(profit / total * 100, 1) if total else 0
        resumo.append({
            "id_estrategia": r['id_estrategia'],
            "nome":          r['nome'],
            "type":          r['type'],
            "total":         total,
            "profit":        profit,
            "loss":          loss,
            "acerto_pct":    acerto_pct,
        })

    alinhamento = {
        "analise":     (recommendation or '').upper(),
        "tipo_esperado": tipo_alinhado,
        "robos": [
            {"nome": r["nome"], "type": r["type"], "alinhado": r["type"] == tipo_alinhado}
            for r in resumo
        ],
    } if tipo_alinhado else None

    return {
        "operaram":            True,
        "indice_acerto_geral": round(profit_geral / total_geral * 100, 1) if total_geral else None,
        "alinhamento":         alinhamento,
        "resumo":              resumo,
    }


def _serialize(row: dict) -> dict:
    from decimal import Decimal
    from datetime import datetime, date
    result = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, (datetime, date)):
            result[k] = str(v)
        else:
            result[k] = v
    return result


_CHART_MAP = {
    "COMPRA":     {"position": "belowBar", "color": "#26a69a", "shape": "arrowUp"},
    "VENDA":      {"position": "aboveBar", "color": "#ef5350", "shape": "arrowDown"},
    "INDEFINIÇÃO": {"position": "belowBar", "color": "#FF9800", "shape": "circle"},
}


def _build_chart_marker(row: dict) -> dict:
    rec   = (row.get("recommendation") or "").upper()
    style = _CHART_MAP.get(rec, _CHART_MAP["INDEFINIÇÃO"])
    conf  = row.get("confidence") or ""
    return {
        "time":     str(row["analyzed_at"])[:10],
        "position": style["position"],
        "color":    style["color"],
        "shape":    style["shape"],
        "text":     f"{rec} {conf}".strip(),
    }


def _row_to_grid(row: dict) -> dict:
    row = _serialize(row)
    return {
        "id_market_analysis": row.get("id_market_analysis"),
        "analyzed_at":        row.get("analyzed_at"),
        "id_ativos_base":     row.get("id_ativos_base"),
        "ativo_base":         _build_ativo_base(row.get("id_ativos_base"), nome_only=True),
        "recommendation":     row.get("recommendation"),
        "confidence":         row.get("confidence"),
        "contracts":          row.get("contracts"),
        "score": {
            "total":     row.get("score_total"),
            "technical": row.get("score_technical"),
            "macro":     row.get("score_macro"),
        },
        "td_price":     row.get("td_price"),
        "chart_marker": _build_chart_marker(row),
    }


class MarketAnalysisListRule:

    @staticmethod
    def list(date_filter: str = None, id_ativos_base: int = None):
        model = MarketAnalysisModel()

        model.order("analyzed_at", "DESC").limit(10)

        if date_filter:
            model.where(["DATE(analyzed_at)", "=", date_filter])

        if id_ativos_base:
            model.where(["id_ativos_base", "=", id_ativos_base])

        rows = model.find() or []
        return {"data": [_row_to_grid(r) for r in rows]}, 200


class MarketAnalysisDetailRule:

    @staticmethod
    def detail(id_market_analysis: int = None, id_ativos_base: int = None):
        model = MarketAnalysisModel()

        if id_market_analysis:
            rows = model.find_one(id_market_analysis)
            if not rows:
                return {"error": "Análise não encontrada"}, 404
            row = rows[0]
        else:
            if id_ativos_base:
                model.where(["id_ativos_base", "=", id_ativos_base])
            rows = model.order("analyzed_at", "DESC").limit(1).find()
            if not rows:
                return {"error": "Nenhuma análise disponível"}, 404
            row = rows[0]

        row = _serialize(row)
        row.pop("payload_json", None)

        for _json_col in ("blind_spots", "daytrade_scenarios"):
            val = row.get(_json_col)
            if val and isinstance(val, str):
                try:
                    row[_json_col] = json.loads(val)
                except Exception:
                    pass

        row["ativo_base"]   = _build_ativo_base(row.get("id_ativos_base"))
        row["chart_marker"] = _build_chart_marker(row)

        try:
            row["robos"] = _build_robos(row.get("analyzed_at"), row.get("recommendation"))
        except Exception:
            row["robos"] = None

        return row, 200