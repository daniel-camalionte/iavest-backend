import urllib.request
import urllib.parse
import json
import ssl

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

BASE_URL = "https://api.twelvedata.com"

# Ativos macro (spot) — 6 créditos
MACRO_SYMBOLS = {
    "dia":    {"symbol": "DIA",     "name": "Dow Jones (DIA)"},
    "usdbrl": {"symbol": "USD/BRL", "name": "Dólar / Real (USD/BRL)"},
}



class TwelveDataClient:

    def __init__(self, api_key):
        self.api_key = api_key

    def _get(self, endpoint, params):
        params["apikey"] = self.api_key
        parts = []
        for k, v in params.items():
            parts.append(
                "{}={}".format(
                    urllib.parse.quote(str(k)),
                    urllib.parse.quote(str(v), safe=",/!")
                )
            )
        url = "{}/{}?{}".format(BASE_URL, endpoint, "&".join(parts))
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })
        try:
            response = urllib.request.urlopen(req, timeout=20, context=_SSL_CTX)
            return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8") if e.fp else ""
            try:
                return json.loads(body)
            except Exception:
                return {"status": "error", "code": e.code, "message": body}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _parse_quote(self, raw, sym, name):
        if not raw or raw.get("status") == "error":
            return {"symbol": sym, "name": name, "_error": raw.get("message") if raw else "sem dados"}
        try:
            price = float(raw.get("close") or raw.get("price") or 0)
            return {
                "symbol":         sym,
                "name":           name,
                "price":          price,
                "change":         float(raw.get("change", 0) or 0),
                "percent_change": float(raw.get("percent_change", 0) or 0),
                "is_market_open": raw.get("is_market_open", False),
            }
        except (TypeError, ValueError):
            return {"symbol": sym, "name": name, "price": 0.0, "change": 0.0, "percent_change": 0.0}

    # -------------------------------------------------------------------------
    # Macro spot + futuros pré-mercado (8 créditos — exatamente no limite free)
    # -------------------------------------------------------------------------
    def get_macro_quotes(self):
        symbols_str = ",".join(v["symbol"] for v in MACRO_SYMBOLS.values())
        data = self._get("quote", {"symbol": symbols_str})

        if isinstance(data, dict) and data.get("status") == "error":
            return {"_error": data}

        result = {}
        for key, meta in MACRO_SYMBOLS.items():
            sym  = meta["symbol"]
            raw  = data.get(sym, {}) if isinstance(data, dict) else {}
            result[key] = self._parse_quote(raw, sym, meta["name"])

        return result

    # -------------------------------------------------------------------------
    # Candles intraday (time_series)
    # -------------------------------------------------------------------------
    def get_intraday_candles(self, symbol="WIN1!", interval="15min", outputsize=60):
        """Retorna lista de candles OHLCV em ordem ASC, ou (None, mensagem_erro)."""
        data = self._get("time_series", {
            "symbol":     symbol,
            "interval":   interval,
            "outputsize": outputsize,
            "order":      "ASC",
        })
        if not data or data.get("status") == "error":
            msg = data.get("message", "Erro TwelveData") if data else "Sem resposta"
            return None, msg
        values = data.get("values", [])
        if not values:
            return None, "Nenhum candle retornado"
        candles = []
        for v in values:
            try:
                candles.append({
                    "datetime": v["datetime"],
                    "open":     float(v["open"]),
                    "high":     float(v["high"]),
                    "low":      float(v["low"]),
                    "close":    float(v["close"]),
                    "volume":   int(v.get("volume") or 0),
                })
            except (KeyError, TypeError, ValueError):
                continue
        return candles, None

    # -------------------------------------------------------------------------
    # Debug
    # -------------------------------------------------------------------------
    def debug_raw(self):
        symbols_str = ",".join(v["symbol"] for v in MACRO_SYMBOLS.values())
        return self._get("quote", {"symbol": symbols_str})
