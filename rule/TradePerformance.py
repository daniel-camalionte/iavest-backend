import time
from library.MySql import MySql

_ACCOUNT   = '1001457239'
_MESES_PT  = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
               'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
_CACHE_TTL = 86400  # 24 horas

_cache = {}  # chave: "date_from|date_to"


def _cache_key(date_from: str, date_to: str) -> str:
    return f"{date_from}|{date_to}"


def _fetch_raw(date_from: str, date_to: str):
    sql = """
        SELECT
            DATE_FORMAT(t.closed_at, '%%Y-%%m')                       AS mes,
            t.id_estrategia,
            e.nome,
            COUNT(*)                                                   AS total,
            SUM(CASE WHEN t.operation = 'profit' THEN 1 ELSE 0 END)  AS wins,
            SUM(t.profit_loss / t.contract)                           AS ganho_por_contrato
        FROM trade t
        INNER JOIN estrategia e ON e.id_estrategia = t.id_estrategia
        WHERE t.account_number = %s
          AND t.id_estrategia IN (3, 4)
          AND t.status = 'closed'
          AND DATE(t.closed_at) BETWEEN %s AND %s
        GROUP BY DATE_FORMAT(t.closed_at, '%%Y-%%m'), t.id_estrategia, e.nome
        ORDER BY mes ASC
    """
    rows = MySql().fetch(sql, (_ACCOUNT, date_from, date_to)) or []

    meses_raw = {}
    for r in rows:
        mes    = r['mes']
        id_est = r['id_estrategia']
        if mes not in meses_raw:
            meses_raw[mes] = {}
        meses_raw[mes][id_est] = {
            'nome':       r['nome'],
            'ganho_base': float(r['ganho_por_contrato'] or 0),
            'operacoes':  int(r['total'] or 0),
            'wins':       int(r['wins']  or 0),
        }
    return meses_raw


def _get_cached_raw(date_from: str, date_to: str):
    key   = _cache_key(date_from, date_to)
    now   = time.time()
    entry = _cache.get(key)
    if entry and (now - entry["timestamp"]) < _CACHE_TTL:
        return entry["rows"], True

    meses_raw       = _fetch_raw(date_from, date_to)
    _cache[key]     = {"rows": meses_raw, "timestamp": now}
    return meses_raw, False


def _apply_multipliers(meses_raw: dict, contracts: int, capital: float):
    # Coleta o mapeamento id_estrategia → nome real da tabela
    estrategias = {}
    for mes_data in meses_raw.values():
        for id_est, d in mes_data.items():
            if id_est not in estrategias:
                estrategias[id_est] = d['nome']

    mensal            = []
    capital_acumulado = 0.0
    pico              = 0.0
    drawdown_max      = 0.0

    for mes_key in sorted(meses_raw.keys()):
        data  = meses_raw[mes_key]
        year, month = mes_key.split('-')
        mes_label   = f"{_MESES_PT[int(month) - 1]}/{year[2:]}"

        total_ganho        = sum(v['ganho_base'] * contracts for v in data.values())
        capital_acumulado += total_ganho
        total_pct          = round(total_ganho / capital * 100, 2) if capital else None

        if capital_acumulado > pico:
            pico = capital_acumulado
        if pico > 0:
            dd = (capital_acumulado - pico) / pico * 100
            if dd < drawdown_max:
                drawdown_max = dd

        item = {
            'mes':       mes_key,
            'mes_label': mes_label,
            'total': {
                'ganho':             round(total_ganho, 2),
                'pct':               total_pct,
                'capital_acumulado': round(capital_acumulado, 2),
            },
            'ias': {},
        }

        for id_est, nome in estrategias.items():
            d = data.get(id_est)
            if d:
                ganho = round(d['ganho_base'] * contracts, 2)
                item['ias'][nome] = {
                    'ganho':      ganho,
                    'pct':        round(ganho / capital * 100, 2) if capital else None,
                    'operacoes':  d['operacoes'],
                    'acerto_pct': round(d['wins'] / d['operacoes'] * 100, 1) if d['operacoes'] else 0,
                }
            else:
                item['ias'][nome] = None

        mensal.append(item)

    total_ops  = sum(d['operacoes'] for m in meses_raw.values() for d in m.values())
    total_wins = sum(d['wins']      for m in meses_raw.values() for d in m.values())
    total_ganho_geral = sum(item['total']['ganho'] for item in mensal)

    melhor = max(mensal, key=lambda x: x['total']['ganho']) if mensal else None
    pior   = min(mensal, key=lambda x: x['total']['ganho']) if mensal else None

    summary = {
        'total_operacoes':     total_ops,
        'acerto_geral_pct':    round(total_wins / total_ops * 100, 1) if total_ops else 0,
        'capital_acumulado':   round(total_ganho_geral, 2),
        'drawdown_maximo_pct': round(drawdown_max, 2),
        'ias':                 list(estrategias.values()),
        'melhor_mes': {
            'mes':   melhor['mes_label'],
            'ganho': melhor['total']['ganho'],
            'pct':   melhor['total']['pct'],
        } if melhor else None,
        'pior_mes': {
            'mes':   pior['mes_label'],
            'ganho': pior['total']['ganho'],
            'pct':   pior['total']['pct'],
        } if pior else None,
    }

    return summary, mensal


class TradePerformanceRule:

    @staticmethod
    def clear_cache():
        _cache.clear()
        return {"success": True, "message": "Cache limpo com sucesso"}, 200

    @staticmethod
    def mensal(contracts: int = 2, capital: float = 2000.0,
               date_from: str = '2026-01-01', date_to: str = None):
        from datetime import date
        if not date_to:
            date_to = date.today().strftime('%Y-%m-%d')

        meses_raw, cached = _get_cached_raw(date_from, date_to)
        summary, mensal   = _apply_multipliers(meses_raw, contracts, capital)

        return {
            'success':   True,
            'contracts': contracts,
            'capital':   capital,
            'date_from': date_from,
            'date_to':   date_to,
            'cached':    cached,
            'summary':   summary,
            'mensal':    mensal,
        }, 200
