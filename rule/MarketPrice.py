from datetime import datetime
from decimal import Decimal

from library.MySql import MySql

# nome amigável por tipo de símbolo (fallback: o próprio type)
_NOME_SYMBOL = {
    "WIN": "Mini Índice",
    "WDO": "Mini Dólar",
}

# janela usada na média de referência (último candle vs média dos N)
_MEDIA_N = 15
# zona-morta (% do preço) abaixo da qual a tendência é considerada "lateral"
_LATERAL_PCT = 0.0003  # 0,03%


def _val(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


class MarketPriceRule:
    """Último preço de mercado (último candle do MT5) por símbolo."""

    @staticmethod
    def latest(id_symbols=None):
        sql = (
            "SELECT c.id_symbols, s.type, s.ticker, "
            "c.`datetime`, c.open, c.high, c.low, c.close, c.tick_vol, c.vol "
            "FROM mt5_candles c "
            "JOIN symbols s ON s.id_symbols = c.id_symbols "
            "JOIN (SELECT id_symbols, MAX(`datetime`) mx FROM mt5_candles GROUP BY id_symbols) m "
            "  ON m.id_symbols = c.id_symbols AND m.mx = c.`datetime` "
        )
        params = 0
        if id_symbols:
            sql += "WHERE c.id_symbols = %s "
            params = (id_symbols,)
        sql += "ORDER BY c.id_symbols"

        rows = MySql().fetch(sql, params) or []

        data = []
        for r in rows:
            tipo  = r.get("type")
            close = _val(r.get("close"))
            media_15, delta_15, tendencia = MarketPriceRule._stats(r.get("id_symbols"))
            data.append({
                "id_symbols": r.get("id_symbols"),
                "type":       tipo,
                "ticker":     r.get("ticker"),
                "nome":       _NOME_SYMBOL.get(tipo, tipo),
                "datetime":   _val(r.get("datetime")),
                "open":       _val(r.get("open")),
                "high":       _val(r.get("high")),
                "low":        _val(r.get("low")),
                "close":      close,
                "preco":      round(close) if close is not None else None,
                "media_15":   media_15,
                "delta_15":   delta_15,
                "tendencia":  tendencia,
                "tick_vol":   r.get("tick_vol"),
                "vol":        r.get("vol"),
            })

        return {"data": data}, 200

    @staticmethod
    def _stats(id_symbols, n=_MEDIA_N):
        """Média dos últimos N closes, delta (atual - média) em pontos e tendência.

        delta > 0  → preço acima da média (alta)
        delta < 0  → preço abaixo da média (baixa)
        |delta| dentro da zona-morta (_LATERAL_PCT do preço) → lateral
        """
        rows = MySql().fetch(
            "SELECT close FROM mt5_candles WHERE id_symbols=%s "
            "ORDER BY `datetime` DESC LIMIT %s",
            (id_symbols, n)
        ) or []
        closes = [float(r["close"]) for r in rows if r.get("close") is not None]
        if len(closes) < 2:
            return None, None, None

        atual = closes[0]
        media = sum(closes) / len(closes)
        delta = atual - media

        if abs(delta) <= media * _LATERAL_PCT:
            tendencia = "lateral"
        elif delta > 0:
            tendencia = "alta"
        else:
            tendencia = "baixa"

        return round(media), round(delta), tendencia
