import calendar
from datetime import datetime as _dt
from library.MySql import MySql
from library.YahooFinanceClient import YahooFinanceClient, _rsi, _ema, _macd


def _to_unix(dt_str):
    """Converte 'YYYY-MM-DD HH:MM:SS' BRT (UTC-3) para Unix timestamp UTC."""
    dt = _dt.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return int(calendar.timegm(dt.timetuple())) + 3 * 3600


def _interp_rsi(rsi):
    if rsi is None:
        return None
    if rsi >= 70:
        return "Sobrecomprado"
    if rsi >= 55:
        return "Levemente comprado"
    if rsi <= 30:
        return "Sobrevendido"
    if rsi <= 45:
        return "Levemente vendido"
    return "Neutro"


def _interp_ema(ema9, ema21):
    if ema9 is None or ema21 is None:
        return None
    if ema9 > ema21:
        return "EMA9 acima da EMA21 — tendência de alta"
    if ema9 < ema21:
        return "EMA9 abaixo da EMA21 — tendência de baixa"
    return "EMAs cruzadas — indefinição"


def _interp_macd(hist):
    if hist is None:
        return None
    if hist > 0:
        return "Histograma positivo — momentum de alta"
    if hist < 0:
        return "Histograma negativo — momentum de baixa"
    return "Histograma zerado — sem momentum"


def _calc_indicadores(candles, entry_ts):
    """Calcula RSI, EMA9/21 e MACD usando os candles até o momento de entrada."""
    # candles até a entrada (inclusive)
    subset = [c for c in candles if c["time"] <= entry_ts]
    if len(subset) < 2:
        return None

    closes_desc = list(reversed([c["close"] for c in subset]))

    rsi  = _rsi(closes_desc)
    ema9  = _ema(closes_desc, 9)
    ema21 = _ema(closes_desc, 21)
    macd  = _macd(closes_desc)
    hist  = macd["histogram"] if macd else None

    return {
        "rsi":            rsi,
        "rsi_label":      _interp_rsi(rsi),
        "ema9":           ema9,
        "ema21":          ema21,
        "ema_label":      _interp_ema(ema9, ema21),
        "macd_histogram": hist,
        "macd_label":     _interp_macd(hist),
        "nota":           "Indicadores calculados no candle de entrada — contexto técnico, não a lógica interna do robô.",
    }


class TradeCandlesRule:

    @staticmethod
    def get(id_trade, id_usuario):
        sql = """
            SELECT
                t.id_trade,
                t.id_estrategia,
                e.nome          AS estrategia_nome,
                t.type,
                t.operation,
                t.index_start,
                t.index_exit,
                t.contract,
                t.profit_loss,
                t.created_at,
                t.closed_at,
                mc.id_usuario
            FROM trade t
            INNER JOIN estrategia e          ON e.id_estrategia   = t.id_estrategia
            INNER JOIN metatrader_configs mc ON mc.account_number = t.account_number
            WHERE t.id_trade = %s
              AND mc.id_usuario = %s
            LIMIT 1
        """
        rows = MySql().fetch(sql, (id_trade, id_usuario)) or []
        if not rows:
            return {"error": "Trade não encontrado"}, 404

        r = rows[0]

        created_at = str(r['created_at'])
        closed_at  = str(r['closed_at'])
        date_str   = created_at[:10]

        candles, err = YahooFinanceClient().get_ibov_candles_for_date(date_str, interval="15m")
        if err or not candles:
            return {"error": f"Erro ao buscar candles: {err}"}, 502

        entry_ts = _to_unix(created_at)
        exit_ts  = _to_unix(closed_at)

        is_buy       = r['type'] == 'buy'
        entry_color  = "#26a69a" if is_buy else "#ef5350"
        exit_color   = "#ef5350" if is_buy else "#26a69a"
        pl           = float(r['profit_loss'])  if r['profit_loss']  is not None else 0
        index_start  = int(r['index_start'])    if r['index_start']  is not None else None
        index_exit   = int(r['index_exit'])     if r['index_exit']   is not None else None
        contract     = int(r['contract'])       if r['contract']     is not None else None
        pl_fmt       = f"+R${pl:.2f}" if pl >= 0 else f"-R${abs(pl):.2f}"

        markers = [
            {
                "time":     entry_ts,
                "type":     "entry",
                "price":    index_start,
                "color":    entry_color,
                "position": "belowBar" if is_buy else "aboveBar",
                "shape":    "arrowUp"  if is_buy else "arrowDown",
                "label":    "E",
                "text":     f"Entrada {'Compra' if is_buy else 'Venda'} — {index_start:,}".replace(",", "."),
            },
            {
                "time":     exit_ts,
                "type":     "exit",
                "price":    index_exit,
                "color":    exit_color,
                "position": "aboveBar" if is_buy else "belowBar",
                "shape":    "arrowDown" if is_buy else "arrowUp",
                "label":    "S",
                "text":     f"Saída — {index_exit:,} ({pl_fmt})".replace(",", "."),
            },
        ]

        trade = {
            "id_trade":        int(r['id_trade']),
            "estrategia_nome": r['estrategia_nome'],
            "type":            r['type'],
            "operation":       r['operation'],
            "index_start":     index_start,
            "index_exit":      index_exit,
            "contract":        contract,
            "profit_loss":     pl,
            "created_at":      created_at,
            "closed_at":       closed_at,
        }

        return {
            "success":     True,
            "trade":       trade,
            "markers":     markers,
            "candles":     candles,
            "indicadores": _calc_indicadores(candles, entry_ts),
        }, 200
