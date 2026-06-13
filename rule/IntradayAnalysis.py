import json
import time
from datetime import datetime, timezone, timedelta

import config.env as memory
from library.HttpClient import HttpClient
from library.YahooFinanceClient import YahooFinanceClient, _rsi, _ema, _macd, _ema_series_asc, ibov_to_win
from model.IntradayAnalysis import IntradayAnalysisModel
from model.IntradayOR import IntradayORModel
from model.MarketAnalysis import MarketAnalysisModel

BRASILIA = timezone(timedelta(hours=-3))

_intraday_cache = {}
_CACHE_TTL = 300  # 5 minutos


def _is_b3_open(now_br):
    """Retorna True se o pregão B3 está aberto (seg-sex, 09:00–17:55 BRT)."""
    if now_br.weekday() >= 5:
        return False
    t = now_br.hour * 100 + now_br.minute  # ex: 09:30 → 930
    return 900 <= t <= 1755

# ---------------------------------------------------------------------------
# Prompt Haiku
# ---------------------------------------------------------------------------

_HAIKU_SYSTEM = """Você é um trader profissional especialista em Mini Índice Bovespa (WIN).
Analise os dados fornecidos e retorne APENAS um JSON válido, sem texto adicional, sem markdown.

Contexto do ativo:
- WIN opera em pontos. Cada ponto vale R$0,20 por contrato.
- Stop loss e alvos devem ser valores inteiros de pontos.
- Stop loss base: entrada ± (ATR × 1.5). Ajuste para suporte/resistência mais próximo.
- NÃO calcule risco em pontos, risco em reais nem relação risco/retorno — esses campos são calculados externamente e serão ignorados.
- Na ai_justificativa, não mencione valores de RR — foque nos motivos técnicos da decisão.

Referências de contexto do dia (use obrigatoriamente na análise):
- prev_day_high/low/close: níveis estruturais do dia anterior. Preço acima de prev_day_high é breakout bullish; abaixo de prev_day_low é breakout bearish.
- opening_range_high/low: máxima e mínima dos primeiros 30min (09:00–09:30). Rompimento acima do OR é sinal de compra; abaixo é sinal de venda. Preço dentro do OR = indefinição.
- dolfut_proxy: USD/BRL tem correlação INVERSA com WIN. impacto_win=bearish significa dólar subindo → pressão vendedora no WIN. impacto_win=bullish significa dólar caindo → pressão compradora no WIN.
- bova11_volume: volume real do ETF BOVA11 (mesma bolsa B3, mesmos horários). vol_rel compara o candle atual com a média dos últimos 20. vol_rel > 1.5 = movimento com convicção; vol_rel < 0.5 = movimento fraco, não confiar em rompimentos.
- indicadores_5min: mesmo ativo no timeframe de 5min. Use para confirmar ou questionar o sinal do 15min. tf5_alinhamento=alinhado_compra/venda = sinal forte; conflitante = cautela extra.
- ema_sinal: direção atual das EMAs (alta/baixa) ou cruzamento recente (bullish_cross/bearish_cross). Cruzamento recente é sinal mais forte.
- candle_age_min: minutos entre o candle analisado e o horário atual. Se > 20min, dados estão defasados — aumentar cautela na análise.

Retorne exatamente este JSON (sem campos extras, sem comentários):
{
  "ai_direcao": "compra" ou "venda" ou "neutro",
  "ai_forca": "fraca" ou "media" ou "forte",
  "ai_confianca": <inteiro 0-100>,
  "ai_stop_loss": <pontos inteiros>,
  "ai_alvo_1": <pontos inteiros>,
  "ai_alvo_2": <pontos inteiros>,
  "ai_risco_pontos": null,
  "ai_risco_reais": null,
  "ai_relacao_rr": null,
  "ai_confluencias": ["<fator técnico a favor>", ...],
  "ai_riscos": ["<risco ou fator contrário>", ...],
  "ai_resumo": "<uma linha para exibição rápida no dashboard>",
  "ai_justificativa": "<parágrafo técnico explicando a tomada de decisão, incluindo níveis rompidos ou testados>"
}"""


# ---------------------------------------------------------------------------
# Cálculos locais sobre candles intraday (ordem ASC)
# ---------------------------------------------------------------------------

def _atr(candles_asc, period=14):
    n = len(candles_asc)
    if n < period + 1:
        return None
    tr_list = []
    for i in range(1, n):
        h  = candles_asc[i]["high"]
        l  = candles_asc[i]["low"]
        pc = candles_asc[i - 1]["close"]
        tr_list.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(tr_list) < period:
        return None
    return round(sum(tr_list[-period:]) / period, 2)


def _pivot_levels(candles_asc, n=2):
    """Retorna (resistencias, suportes) com os n pivôs mais recentes."""
    length = len(candles_asc)
    resistances, supports = [], []
    for i in range(1, length - 1):
        if candles_asc[i]["high"] > candles_asc[i - 1]["high"] and candles_asc[i]["high"] > candles_asc[i + 1]["high"]:
            resistances.append(round(candles_asc[i]["high"]))
        if candles_asc[i]["low"] < candles_asc[i - 1]["low"] and candles_asc[i]["low"] < candles_asc[i + 1]["low"]:
            supports.append(round(candles_asc[i]["low"]))
    resistances = list(dict.fromkeys(reversed(resistances)))[:n]
    supports    = list(dict.fromkeys(reversed(supports)))[:n]
    return resistances, supports


def _opening_range(candles_asc, now_br):
    """Máxima e mínima dos primeiros 30min do pregão atual (09:00–09:29 BRT)."""
    today = now_br.date()
    or_candles = [
        c for c in candles_asc
        if datetime.fromtimestamp(c["datetime"], tz=BRASILIA).date() == today
        and 900 <= datetime.fromtimestamp(c["datetime"], tz=BRASILIA).hour * 100
                + datetime.fromtimestamp(c["datetime"], tz=BRASILIA).minute < 930
    ]
    if not or_candles:
        return None, None
    return max(c["high"] for c in or_candles), min(c["low"] for c in or_candles)


def _prev_day_levels(candles_asc, now_br):
    """High, low e close do pregão anterior extraídos dos candles já disponíveis."""
    prev = now_br.date() - timedelta(days=1)
    while prev.weekday() >= 5:  # pula fim de semana
        prev -= timedelta(days=1)
    prev_candles = [
        c for c in candles_asc
        if datetime.fromtimestamp(c["datetime"], tz=BRASILIA).date() == prev
    ]
    if not prev_candles:
        return None, None, None
    return (
        max(c["high"]  for c in prev_candles),
        min(c["low"]   for c in prev_candles),
        prev_candles[-1]["close"],
    )


def _calc_indicators(candles_asc):
    closes_asc  = [c["close"] for c in candles_asc]
    closes_desc = list(reversed(closes_asc))

    macd_data   = _macd(closes_desc)
    atr         = _atr(candles_asc)
    resistances, supports = _pivot_levels(candles_asc)

    return {
        "ti_rsi":          _rsi(closes_desc, 14),
        "ti_macd":         macd_data["macd"]      if macd_data else None,
        "ti_macd_signal":  macd_data["signal"]    if macd_data else None,
        "ti_macd_hist":    macd_data["histogram"] if macd_data else None,
        "ti_ema9":         _ema(closes_desc, 9),
        "ti_ema21":        _ema(closes_desc, 21),
        "win_atr":         atr,
        "sr_resistance_1": resistances[0] if len(resistances) > 0 else None,
        "sr_resistance_2": resistances[1] if len(resistances) > 1 else None,
        "sr_support_1":    supports[0]    if len(supports) > 0    else None,
        "sr_support_2":    supports[1]    if len(supports) > 1    else None,
    }


def _ema_crossover(candles_asc, fast=9, slow=21):
    """Detecta direção e cruzamento das EMAs nos últimos 2 candles."""
    closes     = [c["close"] for c in candles_asc]
    fast_series = _ema_series_asc(closes, fast)
    slow_series = _ema_series_asc(closes, slow)
    fast_valid  = [v for v in fast_series if v is not None]
    slow_valid  = [v for v in slow_series if v is not None]
    if len(fast_valid) < 2 or len(slow_valid) < 2:
        return None
    curr = fast_valid[-1] - slow_valid[-1]
    prev = fast_valid[-2] - slow_valid[-2]
    if curr > 0 and prev <= 0:
        return "bullish_cross"
    if curr < 0 and prev >= 0:
        return "bearish_cross"
    return "alta" if curr > 0 else "baixa"


def _avaliar_resultado(prev, candles_asc, now_br):
    """Avalia se a análise anterior atingiu stop, alvo ou expirou."""
    direcao = prev.get("ai_direcao")
    stop    = prev.get("ai_stop_loss")
    alvo_1  = prev.get("ai_alvo_1")
    alvo_2  = prev.get("ai_alvo_2")

    if direcao == "neutro" or not stop or not alvo_1:
        return "neutro", None

    prev_candle_at = prev.get("candle_datetime")
    if isinstance(prev_candle_at, str):
        prev_dt = datetime.strptime(prev_candle_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BRASILIA)
    elif prev_candle_at:
        prev_dt = prev_candle_at if prev_candle_at.tzinfo else prev_candle_at.replace(tzinfo=BRASILIA)
    else:
        return None, None

    post_candles = [
        c for c in candles_asc
        if datetime.fromtimestamp(c["datetime"], tz=BRASILIA) > prev_dt
    ]
    if not post_candles:
        return None, None

    for c in post_candles:
        if direcao == "compra":
            if c["low"] <= stop:
                return "stop_atingido", round(stop)
            if alvo_2 and c["high"] >= alvo_2:
                return "alvo_2_atingido", round(alvo_2)
            if c["high"] >= alvo_1:
                return "alvo_1_atingido", round(alvo_1)
        elif direcao == "venda":
            if c["high"] >= stop:
                return "stop_atingido", round(stop)
            if alvo_2 and c["low"] <= alvo_2:
                return "alvo_2_atingido", round(alvo_2)
            if c["low"] <= alvo_1:
                return "alvo_1_atingido", round(alvo_1)

    return "expirado", round(post_candles[-1]["close"])


def _tf_alinhamento(ema15, ema5):
    """Compara sinal de EMA entre 15min e 5min."""
    bull = {"alta", "bullish_cross"}
    bear = {"baixa", "bearish_cross"}
    if ema15 in bull and ema5 in bull:
        return "alinhado_compra"
    if ema15 in bear and ema5 in bear:
        return "alinhado_venda"
    return "conflitante"


# ---------------------------------------------------------------------------
# Haiku API
# ---------------------------------------------------------------------------

def _call_haiku(user_msg):
    resp = HttpClient.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key":         memory.anthropic["API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        payload={
            "model":      "claude-haiku-4-5",
            "max_tokens": 1024,
            "system":     _HAIKU_SYSTEM,
            "messages":   [{"role": "user", "content": user_msg}],
        },
        timeout=30,
    )
    if not resp or resp["status_code"] != 200:
        return None
    return resp["data"]["content"][0]


def _parse_haiku(text):
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Serialização
# ---------------------------------------------------------------------------

def _serialize_row(row):
    result = dict(row)
    for field in ("ai_confluencias", "ai_riscos"):
        val = result.get(field)
        if val and isinstance(val, str):
            try:
                result[field] = json.loads(val)
            except Exception:
                pass
    result.pop("payload_json", None)
    from decimal import Decimal
    for key, val in list(result.items()):
        if isinstance(val, datetime):
            result[key] = val.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(val, Decimal):
            result[key] = float(val)
    return result


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class IntradayAnalysisRule:

    @staticmethod
    def analyze(id_ativos_base=1, interval_min=15):
        now_br = datetime.now(BRASILIA)
        today  = now_br.strftime("%Y-%m-%d")

        # 1a. Melhoria 1 — pregão B3 aberto?
        if not _is_b3_open(now_br):
            return {
                "error": f"Pregão B3 fechado. Análise disponível seg-sex das 09:00 às 17:55 BRT (agora: {now_br.strftime('%H:%M')} BRT)."
            }, 422

        # 1b. Anti-duplicata — bloqueia nova análise se já existe uma recente
        wait_min  = interval_min // 2
        cutoff    = (now_br - timedelta(minutes=wait_min)).strftime("%Y-%m-%d %H:%M:%S")
        recent_check = IntradayAnalysisModel()
        recent_check.where(["id_ativos_base", "=", id_ativos_base])
        recent_check.where(["analyzed_at", ">=", cutoff])
        recent_rows = recent_check.order("analyzed_at", "DESC").limit(1).find()
        if recent_rows:
            last_at = recent_rows[0].get("analyzed_at")
            if isinstance(last_at, str):
                last_dt = datetime.strptime(last_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=BRASILIA)
            else:
                last_dt = last_at.replace(tzinfo=BRASILIA) if last_at.tzinfo is None else last_at
            proxima = last_dt + timedelta(minutes=wait_min)
            return {
                "error":           "Análise recente já existe. Aguarde o próximo intervalo.",
                "ultima_analise":  last_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "proxima_analise": proxima.strftime("%Y-%m-%d %H:%M:%S"),
                "disponivel_em":   f"{proxima.strftime('%H:%M:%S')} BRT",
            }, 422

        # 1c. Busca análise fundamentalista do dia
        mkt_model = MarketAnalysisModel()
        mkt_model.where(["DATE(analyzed_at)", "=", today])
        mkt_model.where(["id_ativos_base", "=", id_ativos_base])
        mkt_rows = mkt_model.order("analyzed_at", "DESC").limit(1).find()

        if not mkt_rows:
            return {
                "error": "Análise fundamentalista do dia ainda não foi executada. Execute /market/analyze primeiro."
            }, 422

        morning            = mkt_rows[0]
        id_market_analysis = morning.get("id_market_analysis")

        # 2. Candles intraday Ibovespa via Yahoo Finance (^BVSP = proxy do WIN)
        yf           = YahooFinanceClient()
        candles, err = yf.get_ibov_intraday(interval=f"{interval_min}m")

        if err or not candles:
            return {"error": f"Erro ao buscar candles intraday: {err}"}, 502

        # Melhoria 3 — usa o último candle com movimento (^BVSP não reporta volume no intraday)
        last = None
        for candidate in reversed(candles[-5:]):
            if candidate["high"] != candidate["low"]:
                last = candidate
                break

        if last is None:
            sample = candles[-3:] if len(candles) >= 3 else candles
            return {
                "error": "Nenhum candle com movimento real nos últimos intervalos.",
                "debug_candles": [
                    {"volume": c["volume"], "high": c["high"], "low": c["low"], "close": c["close"]}
                    for c in sample
                ],
            }, 422

        today_date      = now_br.date()
        win_price       = ibov_to_win(round(last["close"]), today_date)
        win_open        = ibov_to_win(round(last["open"]),  today_date)
        win_high        = ibov_to_win(round(last["high"]),  today_date)
        win_low         = ibov_to_win(round(last["low"]),   today_date)
        win_volume      = last["volume"] or None  # ^BVSP não reporta volume intraday
        candle_datetime = datetime.fromtimestamp(last["datetime"], tz=BRASILIA).strftime("%Y-%m-%d %H:%M:%S")

        # 2b. Avalia resultado da análise anterior (se houver sem resultado)
        prev_rows = (
            IntradayAnalysisModel()
            .where(["id_ativos_base", "=", id_ativos_base])
            .where(["DATE(analyzed_at)", "=", today])
            .order("analyzed_at", "DESC")
            .limit(1)
            .find()
        )
        if prev_rows and prev_rows[0].get("resultado") is None:
            prev_rec = prev_rows[0]
            res_val, res_preco = _avaliar_resultado(prev_rec, candles, now_br)
            if res_val:
                IntradayAnalysisModel().update({
                    "resultado":       res_val,
                    "resultado_preco": res_preco,
                    "resultado_at":    now_br.strftime("%Y-%m-%d %H:%M:%S"),
                }, prev_rec.get("id_intraday_analysis"))

        # 3. Indicadores + níveis do dia
        ind = _calc_indicators(candles)

        # Ajuste basis WIN: converte todos os níveis de preço de ^BVSP para WIN futuro
        for _f in ("ti_ema9", "ti_ema21",
                   "sr_resistance_1", "sr_resistance_2",
                   "sr_support_1",    "sr_support_2"):
            if ind.get(_f) is not None:
                ind[_f] = ibov_to_win(ind[_f], today_date)

        # Fix #3 — S/R ordenado por proximidade ao preço atual (após ajuste)
        _res = sorted([v for v in [ind["sr_resistance_1"], ind["sr_resistance_2"]] if v is not None and v > win_price])
        _sup = sorted([v for v in [ind["sr_support_1"],    ind["sr_support_2"]]    if v is not None and v < win_price], reverse=True)
        ind["sr_resistance_1"] = _res[0] if len(_res) > 0 else None
        ind["sr_resistance_2"] = _res[1] if len(_res) > 1 else None
        ind["sr_support_1"]    = _sup[0] if len(_sup) > 0 else None
        ind["sr_support_2"]    = _sup[1] if len(_sup) > 1 else None

        # Fix #2a — EMA crossover
        ema_sinal = _ema_crossover(candles)

        # Fix #2b — candle age (frescor dos dados)
        candle_dt     = datetime.fromtimestamp(last["datetime"], tz=BRASILIA)
        candle_age_min = round((now_br - candle_dt).total_seconds() / 60)

        # BOVA11 — candles para OR + dados de volume
        bova11, _ = yf.get_bova11_intraday(interval=f"{interval_min}m")
        bova11_candles = bova11.get("candles", []) if bova11 else []

        # OR persistido: busca no banco; se não existir, calcula e salva
        or_row = (
            IntradayORModel()
            .where(["id_ativos_base", "=", id_ativos_base])
            .where(["data", "=", today])
            .limit(1)
            .find()
        )
        if or_row and or_row[0].get("or_high"):
            or_high = ibov_to_win(or_row[0].get("or_high"), today_date)
            or_low  = ibov_to_win(or_row[0].get("or_low"),  today_date)
        else:
            _or_h, _or_l = _opening_range(bova11_candles, now_br)
            if _or_h is None:
                _or_h, _or_l = _opening_range(candles, now_br)
            if _or_h is not None:
                try:
                    IntradayORModel().save({
                        "id_ativos_base": id_ativos_base,
                        "data":           today,
                        "or_high":        round(_or_h),
                        "or_low":         round(_or_l),
                    })
                except Exception:
                    pass  # UNIQUE KEY: OR já salvo por chamada concorrente
            or_high = ibov_to_win(round(_or_h), today_date) if _or_h else None
            or_low  = ibov_to_win(round(_or_l), today_date) if _or_l else None

        prev_day_high, prev_day_low, prev_day_close = _prev_day_levels(candles, now_br)
        prev_day_high  = ibov_to_win(prev_day_high,  today_date)
        prev_day_low   = ibov_to_win(prev_day_low,   today_date)
        prev_day_close = ibov_to_win(prev_day_close, today_date)

        # 4. Macro atual (Yahoo Finance)
        macro   = yf.get_yahoo_macro_quotes()
        vix     = macro.get("vxx", {}).get("price")
        usdbrl  = macro.get("usdbrl", {}).get("price")
        es1_pct = macro.get("es1", {}).get("percent_change")

        if vix is not None:
            vix_level = "baixo" if vix < 20 else ("medio" if vix < 30 else "alto")
        else:
            vix_level = None

        # DOLFUT proxy (USD/BRL intraday)
        dolfut, _ = yf.get_dolfut_intraday(interval=f"{interval_min}m")

        # Fix #4 — 5min timeframe
        candles_5m, _ = yf.get_ibov_intraday(interval="5m")
        if candles_5m:
            ind_5m        = _calc_indicators(candles_5m)
            tf5_rsi       = ind_5m["ti_rsi"]
            tf5_macd_hist = ind_5m["ti_macd_hist"]
            tf5_ema_sinal = _ema_crossover(candles_5m)
            tf5_alinhamento = _tf_alinhamento(ema_sinal or "baixa", tf5_ema_sinal or "baixa")
        else:
            tf5_rsi = tf5_macd_hist = tf5_ema_sinal = tf5_alinhamento = None

        # Posição do preço em relação aos níveis do dia
        if prev_day_high and prev_day_low:
            if win_price > prev_day_high:
                preco_vs_prev = "acima_do_prev_high"
            elif win_price < prev_day_low:
                preco_vs_prev = "abaixo_do_prev_low"
            else:
                preco_vs_prev = "dentro_do_range_anterior"
        else:
            preco_vs_prev = None

        if or_high and or_low:
            if win_price > or_high:
                preco_vs_or = "acima_do_opening_range"
            elif win_price < or_low:
                preco_vs_or = "abaixo_do_opening_range"
            else:
                preco_vs_or = "dentro_do_opening_range"
        else:
            preco_vs_or = None

        # 5. Monta mensagem para o Haiku
        user_msg = json.dumps({
            "ativo":        "WIN — Mini Índice Bovespa",
            "horario":      now_br.strftime("%H:%M"),
            "intervalo":    f"{interval_min}min",
            "preco_atual":  win_price,
            "candle_atual": {
                "open": win_open, "high": win_high,
                "low":  win_low,  "close": win_price,
            },
            "indicadores_15min": {
                "rsi":        ind["ti_rsi"],
                "macd":       ind["ti_macd"],
                "macd_sinal": ind["ti_macd_signal"],
                "macd_hist":  ind["ti_macd_hist"],
                "ema9":       ind["ti_ema9"],
                "ema21":      ind["ti_ema21"],
                "ema_sinal":  ema_sinal,
                "atr":        ind["win_atr"],
            },
            "indicadores_5min": {
                "rsi":           tf5_rsi,
                "macd_hist":     tf5_macd_hist,
                "ema_sinal":     tf5_ema_sinal,
                "alinhamento":   tf5_alinhamento,
            },
            "candle_age_min": candle_age_min,
            "niveis_pivot": {
                "resistencia_1": ind["sr_resistance_1"],
                "resistencia_2": ind["sr_resistance_2"],
                "suporte_1":     ind["sr_support_1"],
                "suporte_2":     ind["sr_support_2"],
            },
            "niveis_do_dia": {
                "prev_day_high":      prev_day_high,
                "prev_day_low":       prev_day_low,
                "prev_day_close":     prev_day_close,
                "opening_range_high": or_high,
                "opening_range_low":  or_low,
                "preco_vs_prev_day":  preco_vs_prev,
                "preco_vs_or":        preco_vs_or,
            },
            "macro_atual": {
                "vix":              vix,
                "nivel_vix":        vix_level,
                "usdbrl":           usdbrl,
                "sp500_fut_pct":    es1_pct,
            },
            "dolfut_proxy": {
                "usdbrl_price":      dolfut.get("price")      if dolfut else None,
                "usdbrl_change_pct": dolfut.get("change_pct") if dolfut else None,
                "impacto_win":       dolfut.get("impacto_win") if dolfut else None,
            },
            "bova11_volume": {
                "volume":     bova11.get("volume")     if bova11 else None,
                "avg_volume": bova11.get("avg_volume") if bova11 else None,
                "vol_rel":    bova11.get("vol_rel")    if bova11 else None,
                "nivel":      bova11.get("nivel")      if bova11 else None,
            },
            "vies_do_dia":     morning.get("recommendation"),
            "confianca_manha": morning.get("confidence"),
        }, ensure_ascii=False)

        # 6. Chama Haiku
        haiku_block = _call_haiku(user_msg)
        if not haiku_block:
            return {"error": "Erro na chamada ao Claude Haiku"}, 502

        ai = _parse_haiku(haiku_block.get("text", ""))

        # Validação mínima — campos críticos obrigatórios
        _required = ["ai_direcao"]
        if ai.get("ai_direcao") != "neutro":
            _required += ["ai_stop_loss", "ai_alvo_1"]
        _missing  = [f for f in _required if ai.get(f) is None]
        if _missing:
            return {
                "error": f"Resposta do Haiku incompleta. Campos ausentes: {_missing}",
                "raw":   haiku_block.get("text", "")[:500],
            }, 502

        # 7. Melhoria 4 — corrige stop loss se estiver do lado errado
        atr          = ind.get("win_atr") or 300
        ai_direcao   = ai.get("ai_direcao", "neutro")
        ai_stop_loss = ai.get("ai_stop_loss")

        if ai_direcao == "compra" and ai_stop_loss and ai_stop_loss >= win_price:
            ai["ai_stop_loss"] = win_price - round(atr * 1.5)
        elif ai_direcao == "venda" and ai_stop_loss and ai_stop_loss <= win_price:
            ai["ai_stop_loss"] = win_price + round(atr * 1.5)

        # Direção neutro — stop e alvos não fazem sentido operacional
        if ai_direcao == "neutro":
            ai["ai_stop_loss"]    = None
            ai["ai_alvo_1"]       = None
            ai["ai_alvo_2"]       = None
            ai["ai_risco_pontos"] = None
            ai["ai_risco_reais"]  = None
            ai["ai_relacao_rr"]   = None
        else:
            # Risco e RR calculados localmente — nunca confiar na IA para matemática
            stop = ai.get("ai_stop_loss")
            if stop:
                risco_pontos = abs(win_price - stop)
                ai["ai_risco_pontos"] = risco_pontos
                ai["ai_risco_reais"]  = round(risco_pontos * 0.20, 2)

                alvo_1 = ai.get("ai_alvo_1")
                alvo_2 = ai.get("ai_alvo_2")
                if alvo_1 and risco_pontos > 0:
                    rr_1 = round(abs(alvo_1 - win_price) / risco_pontos, 2)
                    if alvo_2:
                        rr_2 = round(abs(alvo_2 - win_price) / risco_pontos, 2)
                        ai["ai_relacao_rr"] = f"T1 1:{rr_1} / T2 1:{rr_2}"
                    else:
                        ai["ai_relacao_rr"] = f"1:{rr_1}"

        # 8. Persiste no banco
        save_data = {
            "id_ativos_base":     id_ativos_base,
            "id_market_analysis": id_market_analysis,
            "analyzed_at":        now_br.strftime("%Y-%m-%d %H:%M:%S"),
            "candle_datetime":    candle_datetime,
            "candle_age_min":     candle_age_min,
            "interval_min":       interval_min,
            "win_price":          win_price,
            "win_open":           win_open,
            "win_high":           win_high,
            "win_low":            win_low,
            "win_volume":         win_volume,
            "win_atr":            ind["win_atr"],
            "ti_rsi":             ind["ti_rsi"],
            "ti_macd":            ind["ti_macd"],
            "ti_macd_signal":     ind["ti_macd_signal"],
            "ti_macd_hist":       ind["ti_macd_hist"],
            "ti_ema9":            ind["ti_ema9"],
            "ti_ema21":           ind["ti_ema21"],
            "ema_sinal":          ema_sinal,
            "tf5_rsi":            tf5_rsi,
            "tf5_macd_hist":      tf5_macd_hist,
            "tf5_ema_sinal":      tf5_ema_sinal,
            "tf5_alinhamento":    tf5_alinhamento,
            "sr_resistance_1":    ind["sr_resistance_1"],
            "sr_resistance_2":    ind["sr_resistance_2"],
            "sr_support_1":       ind["sr_support_1"],
            "sr_support_2":       ind["sr_support_2"],
            "mc_vix":             vix,
            "mc_vix_level":       vix_level,
            "mc_usdbrl":          usdbrl,
            "prev_day_high":      round(prev_day_high)  if prev_day_high  else None,
            "prev_day_low":       round(prev_day_low)   if prev_day_low   else None,
            "prev_day_close":     round(prev_day_close) if prev_day_close else None,
            "or_high":            round(or_high)        if or_high        else None,
            "or_low":             round(or_low)         if or_low         else None,
            "dolfut_price":       dolfut.get("price")      if dolfut else None,
            "dolfut_chg_pct":     dolfut.get("change_pct") if dolfut else None,
            "bova11_volume":      bova11.get("volume")     if bova11 else None,
            "bova11_vol_rel":     bova11.get("vol_rel")    if bova11 else None,
            "bova11_vol_nivel":   bova11.get("nivel")      if bova11 else None,
            "ai_direcao":         ai.get("ai_direcao", "neutro"),
            "ai_forca":           ai.get("ai_forca"),
            "ai_confianca":       ai.get("ai_confianca"),
            "ai_stop_loss":       ai.get("ai_stop_loss"),
            "ai_alvo_1":          ai.get("ai_alvo_1"),
            "ai_alvo_2":          ai.get("ai_alvo_2"),
            "ai_risco_pontos":    ai.get("ai_risco_pontos"),
            "ai_risco_reais":     ai.get("ai_risco_reais"),
            "ai_relacao_rr":      ai.get("ai_relacao_rr"),
            "ai_confluencias":    json.dumps(ai.get("ai_confluencias", []), ensure_ascii=False),
            "ai_riscos":          json.dumps(ai.get("ai_riscos", []), ensure_ascii=False),
            "ai_resumo":          ai.get("ai_resumo"),
            "ai_justificativa":   ai.get("ai_justificativa"),
            "payload_json":       json.dumps(haiku_block, ensure_ascii=False),
        }

        model = IntradayAnalysisModel()
        model.save(save_data)

        _intraday_cache.clear()

        result = dict(save_data)
        result["resultado"]       = None
        result["resultado_preco"] = None
        result["resultado_at"]    = None
        result.pop("payload_json", None)
        for field in ("ai_confluencias", "ai_riscos"):
            val = result.get(field)
            if val and isinstance(val, str):
                try:
                    result[field] = json.loads(val)
                except Exception:
                    pass
        result["vies_do_dia"]     = morning.get("recommendation")
        result["confianca_manha"] = morning.get("confidence")

        return result, 200


class IntradayAnalysisLatestRule:

    @staticmethod
    def latest(id_ativos_base=None):
        cache_key = f"latest_{id_ativos_base}"
        cached    = _intraday_cache.get(cache_key)
        if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
            return cached["data"], 200

        model = IntradayAnalysisModel()
        if id_ativos_base:
            model.where(["id_ativos_base", "=", id_ativos_base])
        rows = model.order("analyzed_at", "DESC").limit(1).find()

        if not rows:
            return {"error": "Nenhuma análise intraday disponível"}, 404

        row = _serialize_row(rows[0])
        _intraday_cache[cache_key] = {"data": row, "ts": time.time()}
        return row, 200


class IntradayAnalysisListRule:

    @staticmethod
    def list_by_market(id_market_analysis, limit=50, offset=0):
        model = IntradayAnalysisModel()
        model.where(["id_market_analysis", "=", id_market_analysis])
        rows = model.order("analyzed_at", "ASC").limit(limit).offset(offset).find() or []
        return {
            "data":   [_serialize_row(r) for r in rows],
            "limit":  limit,
            "offset": offset,
        }, 200
