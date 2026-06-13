from library.MySql import MySql
from datetime import date as _date
from decimal import Decimal
from datetime import datetime as _dt

_MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
              'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def _serialize(row):
    result = dict(row)
    for k, v in result.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, _dt):
            result[k] = v.strftime('%Y-%m-%d %H:%M:%S')
    return result


def _build_est_filter(estrategias):
    if not estrategias:
        return "", []
    placeholders = ','.join(['%s'] * len(estrategias))
    return f"AND t.id_estrategia IN ({placeholders})", list(estrategias)


def _build_mensal_kpis(meses_raw, estrategia_map):
    mensal = []
    capital_acumulado = 0.0
    pico = 0.0
    drawdown_max = 0.0
    total_ops = total_wins = 0

    for mes_key in sorted(meses_raw.keys()):
        year, month = mes_key.split('-')
        mes_label = f"{_MESES_PT[int(month) - 1]}/{year[2:]}"
        data = meses_raw[mes_key]

        ganho_mes = sum(v['ganho'] for v in data.values())
        ops_mes   = sum(v['total'] for v in data.values())
        wins_mes  = sum(v['wins']  for v in data.values())
        total_ops  += ops_mes
        total_wins += wins_mes

        capital_acumulado += ganho_mes
        if capital_acumulado > pico:
            pico = capital_acumulado
        dd = (capital_acumulado - pico) / pico * 100 if pico > 0 else 0.0
        if dd < drawdown_max:
            drawdown_max = dd

        ias = {}
        for id_est, nome in estrategia_map.items():
            d = data.get(id_est)
            if d:
                ias[nome] = {
                    'ganho':      round(d['ganho'], 2),
                    'operacoes':  d['total'],
                    'wins':       d['wins'],
                    'losses':     d['total'] - d['wins'],
                    'acerto_pct': round(d['wins'] / d['total'] * 100, 1) if d['total'] else 0,
                }
            else:
                ias[nome] = None

        mensal.append({
            'mes':               mes_key,
            'mes_label':         mes_label,
            'ganho':             round(ganho_mes, 2),
            'operacoes':         ops_mes,
            'wins':              wins_mes,
            'losses':            ops_mes - wins_mes,
            'capital_acumulado': round(capital_acumulado, 2),
            'ias':               ias,
        })

    melhor = max(mensal, key=lambda x: x['ganho']) if mensal else None
    pior   = min(mensal, key=lambda x: x['ganho']) if mensal else None

    kpis = {
        'total_operacoes':     total_ops,
        'wins':                total_wins,
        'losses':              total_ops - total_wins,
        'acerto_pct':          round(total_wins / total_ops * 100, 1) if total_ops else 0,
        'lucro_total':         round(capital_acumulado, 2),
        'drawdown_maximo_pct': round(drawdown_max, 2),
        'melhor_mes':          {'mes': melhor['mes_label'], 'ganho': melhor['ganho']} if melhor else None,
        'pior_mes':            {'mes': pior['mes_label'],   'ganho': pior['ganho']}   if pior   else None,
    }

    return mensal, kpis


def _fetch_radar_ia(date_from, date_to):
    sql = """
        SELECT resultado_direcao, COUNT(*) AS total
        FROM analysis_intraday
        WHERE resultado_direcao IS NOT NULL
          AND DATE(analyzed_at) BETWEEN %s AND %s
        GROUP BY resultado_direcao
    """
    rows = MySql().fetch(sql, (date_from, date_to)) or []
    counts = {'favor': 0, 'contra': 0, 'neutro': 0}
    for r in rows:
        key = r.get('resultado_direcao')
        if key in counts:
            counts[key] = int(r['total'])
    total = sum(counts.values())
    if not total:
        return None
    return {
        'total_sinais': total,
        'favor':        counts['favor'],
        'contra':       counts['contra'],
        'neutro':       counts['neutro'],
        'favor_pct':    round(counts['favor'] / total * 100, 1),
        'contra_pct':   round(counts['contra'] / total * 100, 1),
        'neutro_pct':   round(counts['neutro'] / total * 100, 1),
        'nota':         'Sinais baseados em dados históricos — não influenciam as operações',
    }


class PerformanceDashboardRule:

    @staticmethod
    def get_accounts(id_usuario):
        sql = """
            SELECT account_number, account, status
            FROM metatrader_configs
            WHERE id_usuario = %s
            ORDER BY created_at ASC
        """
        return MySql().fetch(sql, (id_usuario,)) or []

    @staticmethod
    def dashboard(id_usuario, account_number=None, estrategias=None,
                  date_from='2026-01-01', date_to=None):
        if not date_to:
            date_to = _date.today().strftime('%Y-%m-%d')

        accounts = PerformanceDashboardRule.get_accounts(id_usuario)
        if not accounts:
            return {"error": "Nenhuma conta MT5 encontrada para este usuário"}, 404

        valid_numbers = [a['account_number'] for a in accounts]
        active = account_number if account_number in valid_numbers else valid_numbers[0]

        est_clause, est_params = _build_est_filter(estrategias)

        sql = f"""
            SELECT
                DATE_FORMAT(t.closed_at, '%%Y-%%m')                      AS mes,
                t.id_estrategia,
                e.nome,
                COUNT(*)                                                   AS total,
                SUM(CASE WHEN t.operation = 'profit' THEN 1 ELSE 0 END)  AS wins,
                SUM(t.profit_loss)                                         AS ganho_total
            FROM trade t
            INNER JOIN estrategia e ON e.id_estrategia = t.id_estrategia
            WHERE t.account_number = %s
              AND t.status = 'closed'
              AND t.index_start IS NOT NULL
              AND t.index_exit  IS NOT NULL
              AND t.profit_loss IS NOT NULL
              AND DATE(t.closed_at) BETWEEN %s AND %s
              {est_clause}
            GROUP BY mes, t.id_estrategia, e.nome
            ORDER BY mes ASC
        """
        rows = MySql().fetch(sql, tuple([active, date_from, date_to] + est_params)) or []

        meses_raw = {}
        estrategia_map = {}
        for r in rows:
            mes, id_est = r['mes'], r['id_estrategia']
            estrategia_map[id_est] = r['nome']
            if mes not in meses_raw:
                meses_raw[mes] = {}
            meses_raw[mes][id_est] = {
                'nome':  r['nome'],
                'ganho': float(r['ganho_total'] or 0),
                'total': int(r['total'] or 0),
                'wins':  int(r['wins']  or 0),
            }

        mensal, kpis = _build_mensal_kpis(meses_raw, estrategia_map)
        radar_ia     = _fetch_radar_ia(date_from, date_to)

        return {
            'success':        True,
            'account_number': active,
            'accounts':       valid_numbers,
            'date_from':      date_from,
            'date_to':        date_to,
            'kpis':           kpis,
            'mensal':         mensal,
            'radar_ia':       radar_ia,
        }, 200

    @staticmethod
    def trades(id_usuario, account_number=None, estrategias=None,
               date_from='2026-01-01', date_to=None, limit=20, offset=0):
        if not date_to:
            date_to = _date.today().strftime('%Y-%m-%d')

        accounts = PerformanceDashboardRule.get_accounts(id_usuario)
        if not accounts:
            return {"error": "Nenhuma conta MT5 encontrada"}, 404

        valid_numbers = [a['account_number'] for a in accounts]
        active = account_number if account_number in valid_numbers else valid_numbers[0]

        est_clause, est_params = _build_est_filter(estrategias)

        sql = f"""
            SELECT
                t.id_trade,
                t.id_estrategia,
                e.nome                               AS estrategia_nome,
                t.type,
                t.index_start,
                t.index_exit,
                t.contract,
                t.operation,
                t.profit_loss,
                ROUND(t.profit_loss / t.contract, 2) AS profit_loss_por_contrato,
                t.created_at,
                t.closed_at,
                t.notes
            FROM trade t
            INNER JOIN estrategia e ON e.id_estrategia = t.id_estrategia
            WHERE t.account_number = %s
              AND t.status = 'closed'
              AND t.index_start IS NOT NULL
              AND t.index_exit  IS NOT NULL
              AND t.profit_loss IS NOT NULL
              AND DATE(t.closed_at) BETWEEN %s AND %s
              {est_clause}
            ORDER BY t.closed_at DESC
            LIMIT %s OFFSET %s
        """
        params = tuple([active, date_from, date_to] + est_params + [limit, offset])
        rows   = MySql().fetch(sql, params) or []

        return {
            'success':        True,
            'account_number': active,
            'date_from':      date_from,
            'date_to':        date_to,
            'limit':          limit,
            'offset':         offset,
            'data':           [_serialize(r) for r in rows],
        }, 200
