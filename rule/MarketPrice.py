from datetime import datetime
from decimal import Decimal

from library.MySql import MySql

# nome amigável por tipo de símbolo (fallback: o próprio type)
_NOME_SYMBOL = {
    "WIN": "Mini Índice",
    "WDO": "Mini Dólar",
}


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
                "tick_vol":   r.get("tick_vol"),
                "vol":        r.get("vol"),
            })

        return {"data": data}, 200
