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


def _relacao_rr(media_ganho, media_perda):
    """media_ganho / abs(media_perda), None se sem dados."""
    if not media_ganho or not media_perda:
        return None
    return round(media_ganho / abs(media_perda), 2)


def _build_mensal_kpis(meses_raw, estrategia_map):
    mensal = []
    capital_acumulado = 0.0
    pico = 0.0
    drawdown_max = 0.0

    # acumuladores globais
    total_ops = total_wins = 0
    g_total_ganho = g_total_perda = 0.0

    for mes_key in sorted(meses_raw.keys()):
        year, month = mes_key.split('-')
        mes_label = f"{_MESES_PT[int(month) - 1]}/{year[2:]}"
        data = meses_raw[mes_key]

        ganho_mes = sum(v['ganho'] for v in data.values())
        ops_mes   = sum(v['total'] for v in data.values())
        wins_mes  = sum(v['wins']  for v in data.values())
        total_ops  += ops_mes
        total_wins += wins_mes
        g_total_ganho += sum(v['total_ganho'] for v in data.values())
        g_total_perda += sum(v['total_perda'] for v in data.values())

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
                mg = round(d['total_ganho'] / d['wins'],  2) if d['wins']                    else None
                mp = round(d['total_perda'] / (d['total'] - d['wins']), 2) if (d['total'] - d['wins']) else None
                ias[nome] = {
                    'ganho':        round(d['ganho'], 2),
                    'operacoes':    d['total'],
                    'wins':         d['wins'],
                    'losses':       d['total'] - d['wins'],
                    'acerto_pct':   round(d['wins'] / d['total'] * 100, 1) if d['total'] else 0,
                    'total_ganho':  round(d['total_ganho'], 2),
                    'total_perda':  round(d['total_perda'], 2),
                    'media_ganho':  mg,
                    'media_perda':  mp,
                    'relacao_rr':   _relacao_rr(mg, mp),
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

    total_losses = total_ops - total_wins
    g_media_ganho = round(g_total_ganho / total_wins,   2) if total_wins   else None
    g_media_perda = round(g_total_perda / total_losses, 2) if total_losses else None

    kpis = {
        'total_operacoes':     total_ops,
        'wins':                total_wins,
        'losses':              total_losses,
        'acerto_pct':          round(total_wins / total_ops * 100, 1) if total_ops else 0,
        'lucro_total':         round(capital_acumulado, 2),
        'total_ganho':         round(g_total_ganho, 2),
        'total_perda':         round(g_total_perda, 2),
        'media_ganho':         g_media_ganho,
        'media_perda':         g_media_perda,
        'relacao_rr':          _relacao_rr(g_media_ganho, g_media_perda),
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
                DATE_FORMAT(t.closed_at, '%%Y-%%m')                                        AS mes,
                t.id_estrategia,
                e.nome,
                COUNT(*)                                                                     AS total,
                SUM(CASE WHEN t.operation = 'profit' THEN 1     ELSE 0    END)              AS wins,
                SUM(t.profit_loss)                                                           AS ganho_total,
                SUM(CASE WHEN t.operation = 'profit' THEN t.profit_loss ELSE 0 END)         AS total_ganho,
                SUM(CASE WHEN t.operation = 'loss'   THEN t.profit_loss ELSE 0 END)         AS total_perda
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
                'nome':        r['nome'],
                'ganho':       float(r['ganho_total']  or 0),
                'total':       int(r['total']           or 0),
                'wins':        int(r['wins']            or 0),
                'total_ganho': float(r['total_ganho']  or 0),
                'total_perda': float(r['total_perda']  or 0),
            }

        mensal, kpis = _build_mensal_kpis(meses_raw, estrategia_map)
        radar_ia     = _fetch_radar_ia(date_from, date_to)

        estrategias_list = [
            {'id': id_est, 'nome': nome}
            for id_est, nome in sorted(estrategia_map.items())
        ]

        return {
            'success':        True,
            'account_number': active,
            'accounts':       valid_numbers,
            'date_from':      date_from,
            'date_to':        date_to,
            'estrategias':    estrategias_list,
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

        count_sql = f"""
            SELECT COUNT(*) AS total
            FROM trade t
            WHERE t.account_number = %s
              AND t.status = 'closed'
              AND t.index_start IS NOT NULL
              AND t.index_exit  IS NOT NULL
              AND t.profit_loss IS NOT NULL
              AND DATE(t.closed_at) BETWEEN %s AND %s
              {est_clause}
        """
        count_row = MySql().fetch(count_sql, tuple([active, date_from, date_to] + est_params))
        total = int(count_row[0]['total']) if count_row else 0

        return {
            'success':        True,
            'account_number': active,
            'date_from':      date_from,
            'date_to':        date_to,
            'total':          total,
            'limit':          limit,
            'offset':         offset,
            'has_more':       (offset + limit) < total,
            'data':           [_serialize(r) for r in rows],
        }, 200
