import math
import json
import ssl
import urllib.request
import urllib.parse
from datetime import date, timedelta

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# ---------------------------------------------------------------------------
# WIN Futures basis adjustment (Ibovespa spot → WIN futures estimated price)
# ---------------------------------------------------------------------------
_selic_cache = {}

def _get_selic_anual():
    today_str = str(date.today())
    if _selic_cache.get("date") == today_str and _selic_cache.get("rate"):
        return _selic_cache["rate"]
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as r:
            data = json.loads(r.read())
        rate = float(data[0]["valor"]) / 100
    except Exception:
        rate = 0.1375  # fallback: Selic atual hardcoded
    _selic_cache["date"] = today_str
    _selic_cache["rate"] = rate
    return rate


def _nearest_wed_to_15(year, month):
    the_15th = date(year, month, 15)
    wd   = the_15th.weekday()
    back = (wd - 2) % 7
    fwd  = (2 - wd) % 7
    if back <= fwd:
        return the_15th - timedelta(days=back)
    return the_15th + timedelta(days=fwd)


def _active_win_expiry(ref_date=None):
    if ref_date is None:
        ref_date = date.today()
    for month in [2, 4, 6, 8, 10, 12]:
        exp = _nearest_wed_to_15(ref_date.year, month)
        if exp > ref_date:
            return exp
    return _nearest_wed_to_15(ref_date.year + 1, 2)


def ibov_to_win(price, ref_date=None):
    """Converte preço do índice Ibovespa (^BVSP) para estimativa do WIN futuro via custo de carrego.
    Próximo ao vencimento (≤7 dias) o mercado já convergiu — basis não é aplicado."""
    if price is None:
        return None
    if ref_date is None:
        ref_date = date.today()
    expiry = _active_win_expiry(ref_date)
    days   = (expiry - ref_date).days
    if days <= 7:
        return round(price)  # mercado convergiu, ^BVSP já é boa proxy
    selic = _get_selic_anual()
    return round(price * (1 + selic * days / 252))


# Ibovespa no Yahoo Finance
IBOV_SYMBOL = "%5EBVSP"  # ^BVSP URL-encoded
YAHOO_URL   = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=1y"

# Ativos macro via Yahoo Finance (gratuito)
YAHOO_MACRO_SYMBOLS = {
    "es1":  {"symbol": "ES%3DF",    "raw": "ES=F",      "name": "S&P 500 Futuro (ES1!)"},
    "nq1":  {"symbol": "NQ%3DF",    "raw": "NQ=F",      "name": "Nasdaq Futuro (NQ1!)"},
    "dxy":  {"symbol": "DX-Y.NYB",  "raw": "DX-Y.NYB",  "name": "Dólar Index (DXY)"},
    "bz":   {"symbol": "BZ%3DF",    "raw": "BZ=F",      "name": "Petróleo Brent (BZ=F)"},
    "spy":    {"symbol": "%5EGSPC",   "raw": "^GSPC",     "name": "S&P 500 (^GSPC)"},
    "qqq":    {"symbol": "%5ENDX",    "raw": "^NDX",      "name": "Nasdaq-100 (^NDX)"},
    "dia":    {"symbol": "%5EDJI",    "raw": "^DJI",      "name": "Dow Jones (^DJI)"},
    "vxx":    {"symbol": "%5EVIX",    "raw": "^VIX",      "name": "VIX — Volatilidade (^VIX)"},
    "usdbrl": {"symbol": "BRL%3DX",   "raw": "BRL=X",     "name": "Dólar / Real (USD/BRL)"},
    "ewz":    {"symbol": "EWZ",       "raw": "EWZ",       "name": "Brasil ETF (EWZ) — proxy WIN"},
    "pbr":    {"symbol": "PBR",       "raw": "PBR",       "name": "Petrobras ADR (PBR)"},
    "vale":   {"symbol": "VALE",      "raw": "VALE",      "name": "Vale ADR (VALE)"},
}
YAHOO_QUOTE_URL    = "https://query1.finance.yahoo.com/v8/finance/chart/{}?interval=1d&range=5d"
YAHOO_INTRADAY_URL  = "https://query1.finance.yahoo.com/v8/finance/chart/%5EBVSP?interval={interval}&range=5d"
YAHOO_FX_INTRADAY_URL    = "https://query1.finance.yahoo.com/v8/finance/chart/BRL%3DX?interval={interval}&range=1d"
YAHOO_BOVA11_INTRADAY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BOVA11.SA?interval={interval}&range=5d"

# Quantidade mínima de candles para cálculos confiáveis
MIN_CANDLES = 200


# ---------------------------------------------------------------------------
# Cálculo local de indicadores técnicos
# Entrada: listas em ordem DESC (mais recente primeiro)
# ---------------------------------------------------------------------------

def _sma(closes_desc, period):
    if len(closes_desc) < period:
        return None
    return round(sum(closes_desc[:period]) / period, 2)


def _ema_series_asc(closes_asc, period):
    if len(closes_asc) < period:
        return []
    k = 2.0 / (period + 1)
    ema = sum(closes_asc[:period]) / period
    result = [None] * (period - 1) + [ema]
    for price in closes_asc[period:]:
        ema = price * k + ema * (1 - k)
        result.append(ema)
    return result


def _ema(closes_desc, period):
    series = _ema_series_asc(list(reversed(closes_desc)), period)
    if not series:
        return None
    val = next((v for v in reversed(series) if v is not None), None)
    return round(val, 2) if val is not None else None


def _rsi(closes_desc, period=14):
    closes_asc = list(reversed(closes_desc))
    if len(closes_asc) < period + 1:
        return None
    deltas = [closes_asc[i + 1] - closes_asc[i] for i in range(len(closes_asc) - 1)]
    avg_gain = sum(max(d, 0) for d in deltas[:period]) / period
    avg_loss = sum(max(-d, 0) for d in deltas[:period]) / period
    for d in deltas[period:]:
        avg_gain = (avg_gain * (period - 1) + max(d, 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-d, 0)) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_gain / avg_loss), 2)


def _macd(closes_desc):
    closes_asc = list(reversed(closes_desc))
    ema12 = _ema_series_asc(closes_asc, 12)
    ema26 = _ema_series_asc(closes_asc, 26)
    if not ema12 or not ema26:
        return None
    macd_line = [
        ema12[i] - ema26[i]
        for i in range(len(closes_asc))
        if ema12[i] is not None and ema26[i] is not None
    ]
    if len(macd_line) < 9:
        return None
    signal_series = _ema_series_asc(macd_line, 9)
    signal_val = next((v for v in reversed(signal_series) if v is not None), None)
    if signal_val is None:
        return None
    macd_val = macd_line[-1]
    return {
        "macd":      round(macd_val, 2),
        "signal":    round(signal_val, 2),
        "histogram": round(macd_val - signal_val, 2),
    }


def _bbands(closes_desc, period=20):
    if len(closes_desc) < period:
        return None
    window = closes_desc[:period]
    middle = sum(window) / period
    std = math.sqrt(sum((x - middle) ** 2 for x in window) / period)
    return {
        "upper":  round(middle + 2 * std, 2),
        "middle": round(middle, 2),
        "lower":  round(middle - 2 * std, 2),
    }


def _wilder_smooth(data, period):
    if len(data) < period:
        return []
    smoothed = sum(data[:period]) / period  # média, não soma
    result = [smoothed]
    for val in data[period:]:
        smoothed = (smoothed * (period - 1) + val) / period
        result.append(smoothed)
    return result


def _obv(closes_desc, volumes_desc):
    """On-Balance Volume — acumulado de volume com direção do preço."""
    closes_asc  = list(reversed(closes_desc))
    volumes_asc = list(reversed(volumes_desc))
    if len(closes_asc) < 2:
        return None
    obv = 0
    for i in range(1, len(closes_asc)):
        if closes_asc[i] > closes_asc[i - 1]:
            obv += volumes_asc[i]
        elif closes_asc[i] < closes_asc[i - 1]:
            obv -= volumes_asc[i]
    return obv


def _consecutive_days(closes_desc):
    """
    Conta quantos dias consecutivos o preço fechou na mesma direção.
    Retorna valor positivo para alta (ex: 3 = 3 dias subindo),
    negativo para baixa (ex: -2 = 2 dias caindo).
    """
    if len(closes_desc) < 2:
        return 0
    # closes_desc[0] = mais recente
    direction = 1 if closes_desc[0] > closes_desc[1] else -1
    count = 1
    for i in range(1, len(closes_desc) - 1):
        cur_dir = 1 if closes_desc[i] > closes_desc[i + 1] else -1
        if cur_dir == direction:
            count += 1
        else:
            break
    return count * direction


def _adx(closes_desc, highs_desc, lows_desc, period=14):
    closes_asc = list(reversed(closes_desc))
    highs_asc  = list(reversed(highs_desc))
    lows_asc   = list(reversed(lows_desc))
    n = len(closes_asc)
    if n < period * 2 + 1:
        return None
    tr_list, pdm_list, mdm_list = [], [], []
    for i in range(1, n):
        h, l, pc = highs_asc[i], lows_asc[i], closes_asc[i - 1]
        ph, pl   = highs_asc[i - 1], lows_asc[i - 1]
        tr  = max(h - l, abs(h - pc), abs(l - pc))
        up  = h - ph
        dn  = pl - l
        tr_list.append(tr)
        pdm_list.append(up if up > dn and up > 0 else 0)
        mdm_list.append(dn if dn > up and dn > 0 else 0)
    tr_s  = _wilder_smooth(tr_list,  period)
    pdm_s = _wilder_smooth(pdm_list, period)
    mdm_s = _wilder_smooth(mdm_list, period)
    if not tr_s:
        return None
    pdi_list, mdi_list, dx_list = [], [], []
    for i in range(len(tr_s)):
        if tr_s[i] == 0:
            continue
        pdi = 100 * pdm_s[i] / tr_s[i]
        mdi = 100 * mdm_s[i] / tr_s[i]
        pdi_list.append(pdi)
        mdi_list.append(mdi)
        dsum = pdi + mdi
        dx_list.append(100 * abs(pdi - mdi) / dsum if dsum else 0)
    adx_s = _wilder_smooth(dx_list, period)
    if not adx_s or not pdi_list:
        return None
    return {
        "adx":      round(adx_s[-1], 2),
        "plus_di":  round(pdi_list[-1], 2),
        "minus_di": round(mdi_list[-1], 2),
    }


# ---------------------------------------------------------------------------
# Client — usa urllib diretamente (Python 3.7 compatível, sem dependências)
# ---------------------------------------------------------------------------

class YahooFinanceClient:

    def _fetch_symbol(self, symbol_encoded):
        """Busca cotação de qualquer símbolo via Yahoo Finance."""
        url = YAHOO_QUOTE_URL.format(symbol_encoded)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            return json.loads(response.read().decode("utf-8")), None
        except Exception as e:
            return None, str(e)

    def get_yahoo_macro_quotes(self):
        """Retorna cotações dos futuros e ADRs estratégicos via Yahoo Finance."""
        result = {}
        for key, meta in YAHOO_MACRO_SYMBOLS.items():
            data, err = self._fetch_symbol(meta["symbol"])
            if err or not data:
                result[key] = {"symbol": meta["raw"], "name": meta["name"], "_error": err or "Sem dados"}
                continue
            try:
                r      = data["chart"]["result"][0]
                quotes = r["indicators"]["quote"][0]
                closes = [c for c in quotes.get("close", []) if c is not None]
                if len(closes) < 2:
                    result[key] = {"symbol": meta["raw"], "name": meta["name"], "_error": "Dados insuficientes"}
                    continue
                price      = round(closes[-1], 2)
                prev_close = round(closes[-2], 2)
                change     = round(price - prev_close, 2)
                pct        = round((change / prev_close) * 100, 4) if prev_close else 0.0
                result[key] = {
                    "symbol":         meta["raw"],
                    "name":           meta["name"],
                    "price":          price,
                    "change":         change,
                    "percent_change": pct,
                    "is_market_open": r.get("meta", {}).get("marketState", "") == "REGULAR",
                }
            except (KeyError, IndexError, TypeError) as e:
                result[key] = {"symbol": meta["raw"], "name": meta["name"], "_error": str(e)}
        return result

    def _fetch_ibov(self):
        """Busca série histórica diária do Ibovespa via Yahoo Finance API."""
        url = YAHOO_URL.format(IBOV_SYMBOL)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            return json.loads(response.read().decode("utf-8")), None
        except Exception as e:
            return None, str(e)

    def get_ibov_technical(self):
        """Calcula todos os indicadores técnicos do Ibovespa (^BVSP)."""
        data, err = self._fetch_ibov()
        if err or not data:
            return {"_error": err or "Sem dados"}

        try:
            result = data["chart"]["result"][0]
            quotes = result["indicators"]["quote"][0]

            # Remove None values (dias sem dados) mantendo alinhamento
            closes_raw  = quotes.get("close",  [])
            highs_raw   = quotes.get("high",   [])
            lows_raw    = quotes.get("low",    [])
            opens_raw   = quotes.get("open",   [])
            volumes_raw = quotes.get("volume", [])

            candles = [
                (c, h, l, o, v)
                for c, h, l, o, v in zip(closes_raw, highs_raw, lows_raw, opens_raw, volumes_raw)
                if c is not None and h is not None and l is not None
            ]

            if not candles:
                return {"_error": "Nenhum candle válido retornado"}

            # Inverte para ordem DESC (mais recente primeiro)
            candles.reverse()
            closes_desc  = [c[0] for c in candles]
            highs_desc   = [c[1] for c in candles]
            lows_desc    = [c[2] for c in candles]
            opens_desc   = [c[3] for c in candles]
            volumes_desc = [c[4] if c[4] is not None else 0 for c in candles]

            # D-1 context
            prev_close  = closes_desc[1] if len(closes_desc) > 1 else None
            prev_high   = highs_desc[1]  if len(highs_desc) > 1 else None
            prev_low    = lows_desc[1]   if len(lows_desc) > 1 else None
            open_today  = opens_desc[0]  if opens_desc else None
            gap_pct     = None
            if prev_close and open_today and prev_close != 0:
                gap_pct = round((open_today - prev_close) / prev_close * 100, 2)

            return {
                "price":           round(closes_desc[0], 2),
                "prev_close":      round(prev_close, 2) if prev_close else None,
                "prev_high":       round(prev_high, 2)  if prev_high  else None,
                "prev_low":        round(prev_low, 2)   if prev_low   else None,
                "opening_gap_pct": gap_pct,
                "consecutive_days": _consecutive_days(closes_desc),
                "volume":          int(volumes_desc[0]) if volumes_desc else None,
                "obv":             _obv(closes_desc, volumes_desc),
                "sma9":   _sma(closes_desc, 9),
                "sma21":  _sma(closes_desc, 21),
                "sma50":  _sma(closes_desc, 50),
                "sma200": _sma(closes_desc, 200),
                "ema9":   _ema(closes_desc, 9),
                "ema21":  _ema(closes_desc, 21),
                "rsi":    _rsi(closes_desc, 14),
                "macd":   _macd(closes_desc),
                "bbands": _bbands(closes_desc, 20),
                "adx":    _adx(closes_desc, highs_desc, lows_desc, 14),
            }
        except (KeyError, IndexError, TypeError) as e:
            return {"_error": "Erro ao processar dados do Yahoo Finance", "_detail": str(e)}

    def get_dolfut_intraday(self, interval="15m"):
        """Retorna variação intraday do USD/BRL como proxy do DOLFUT (correlação inversa com WIN)."""
        url = YAHOO_FX_INTRADAY_URL.format(interval=interval)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return None, str(e)

        try:
            result     = data["chart"]["result"][0]
            meta       = result.get("meta", {})
            quotes     = result["indicators"]["quote"][0]
            closes     = [c for c in quotes.get("close", []) if c is not None]

            if not closes:
                return None, "Sem dados de fechamento"

            price      = round(closes[-1], 4)
            prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")

            if prev_close and prev_close > 0:
                change_pct = round((price - prev_close) / prev_close * 100, 4)
            else:
                opens    = [o for o in quotes.get("open", []) if o is not None]
                day_open = opens[0] if opens else None
                change_pct = round((price - day_open) / day_open * 100, 4) if day_open else None

            # Correlação inversa: USD/BRL sobe → WIN tende a cair
            if change_pct is not None:
                impacto_win = "bearish" if change_pct > 0.1 else ("bullish" if change_pct < -0.1 else "neutro")
            else:
                impacto_win = None

            return {"price": price, "change_pct": change_pct, "impacto_win": impacto_win}, None
        except Exception as e:
            return None, str(e)

    def get_bova11_intraday(self, interval="15m", avg_periods=20):
        """Volume real do BOVA11.SA como proxy de liquidez do WIN (mesma bolsa, mesmos horários)."""
        url = YAHOO_BOVA11_INTRADAY_URL.format(interval=interval)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return None, str(e)

        try:
            result     = data["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            quotes     = result["indicators"]["quote"][0]

            closes  = quotes.get("close",  [])
            highs   = quotes.get("high",   [])
            lows    = quotes.get("low",    [])
            opens   = quotes.get("open",   [])
            volumes = quotes.get("volume", [])

            candles     = []
            raw_volumes = []
            for i, ts in enumerate(timestamps):
                c = closes[i]  if i < len(closes)  else None
                h = highs[i]   if i < len(highs)   else None
                l = lows[i]    if i < len(lows)    else None
                o = opens[i]   if i < len(opens)   else None
                v = volumes[i] if i < len(volumes) else None
                if c is None or h is None or l is None:
                    continue
                candles.append({
                    "datetime": ts,
                    "open":  round(o if o else c, 2),
                    "high":  round(h, 2),
                    "low":   round(l, 2),
                    "close": round(c, 2),
                    "volume": int(v) if v else 0,
                })
                if v is not None and v > 0:
                    raw_volumes.append(int(v))

            if not candles or not raw_volumes:
                return None, "Sem dados suficientes"

            current_vol = raw_volumes[-1]
            history     = raw_volumes[:-1][-avg_periods:]

            if not history:
                return None, "Histórico insuficiente"

            avg_vol = sum(history) / len(history)
            vol_rel = round(current_vol / avg_vol, 2) if avg_vol > 0 else None

            if vol_rel is None:
                nivel = None
            elif vol_rel >= 2.0:
                nivel = "muito_alto"
            elif vol_rel >= 1.5:
                nivel = "alto"
            elif vol_rel >= 0.8:
                nivel = "normal"
            elif vol_rel >= 0.5:
                nivel = "baixo"
            else:
                nivel = "muito_baixo"

            return {
                "volume":     current_vol,
                "avg_volume": round(avg_vol),
                "vol_rel":    vol_rel,
                "nivel":      nivel,
                "candles":    candles,
            }, None
        except Exception as e:
            return None, str(e)

    def get_ibov_intraday(self, interval="15m"):
        """Retorna candles intraday do Ibovespa (^BVSP) em ordem ASC."""
        url = YAHOO_INTRADAY_URL.format(interval=interval)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return None, str(e)

        try:
            result     = data["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            quotes     = result["indicators"]["quote"][0]

            closes  = quotes.get("close",  [])
            highs   = quotes.get("high",   [])
            lows    = quotes.get("low",    [])
            opens   = quotes.get("open",   [])
            volumes = quotes.get("volume", [])

            candles = []
            for i, ts in enumerate(timestamps):
                c = closes[i]  if i < len(closes)  else None
                h = highs[i]   if i < len(highs)   else None
                l = lows[i]    if i < len(lows)    else None
                o = opens[i]   if i < len(opens)   else None
                v = volumes[i] if i < len(volumes) else None

                if c is None or h is None or l is None:
                    continue

                candles.append({
                    "datetime": ts,
                    "open":     round(o if o else c),
                    "high":     round(h),
                    "low":      round(l),
                    "close":    round(c),
                    "volume":   int(v) if v else 0,
                })

            if not candles:
                return None, "Nenhum candle retornado"

            return candles, None
        except (KeyError, IndexError, TypeError) as e:
            return None, str(e)
