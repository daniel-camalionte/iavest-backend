from datetime import datetime, timezone, timedelta
from decimal import Decimal

from model.SimuladorOrdemCliente import SimuladorOrdemClienteModel
from model.MarketAnalysis import MarketAnalysisModel
from library.MySql import MySql

BRASILIA      = timezone(timedelta(hours=-3))
PONTO_REAIS   = 0.20           # R$ por ponto por contrato (WIN)
_ATIVO_SYMBOL = {1: 1}         # id_ativos_base -> id_symbols (mt5_candles)


def _now_str():
    return datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(v):
    """Aceita datetime ou string ('YYYY-MM-DD HH:MM:SS' ou ISO com 'T')."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.replace(tzinfo=None) if v.tzinfo else v
    s = str(v)[:19].replace("T", " ")
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d")
        except Exception:
            return None


def _dt_in(v):
    """Normaliza data/hora vinda do body para 'YYYY-MM-DD HH:MM:SS' ou None."""
    d = _parse_dt(v)
    return d.strftime("%Y-%m-%d %H:%M:%S") if d else None


class SimuladorOrdemClienteRule:

    # ------------------------------------------------------------------ CRUD
    @staticmethod
    def criar(id_cliente, dados):
        """Cadastra a ordem JÁ EXECUTADA (aberta) — o cadastro é a própria operação."""
        direcao = (dados.get("direcao") or "").lower()
        if direcao not in ("compra", "venda"):
            return {"error": "Campo 'direcao' deve ser 'compra' ou 'venda'"}, 400
        if dados.get("preco_entrada") is None:
            return {"error": "Campo 'preco_entrada' é obrigatório"}, 400

        # data/hora da execução (abertura real no MT5) — do body ou agora
        executada_em = _dt_in(dados.get("executada_em")) or _now_str()

        id_ativos_base = 1
        # análise fundamental do dia da operação (resolvida pela data)
        mkt = (MarketAnalysisModel()
               .where(["id_ativos_base", "=", id_ativos_base])
               .where(["DATE(analyzed_at)", "=", executada_em[:10]])
               .order("analyzed_at", "DESC").limit(1).find())
        id_market = mkt[0]["id_market_analysis"] if mkt else None

        novo_id = SimuladorOrdemClienteModel().save({
            "id_cliente":         id_cliente,
            "executada_em":       executada_em,
            "id_ativos_base":     id_ativos_base,
            "id_market_analysis": id_market,
            "direcao":            direcao,
            "contratos":          dados.get("contratos"),
            "preco_entrada":      dados.get("preco_entrada"),
            "stop_loss":          dados.get("stop_loss"),
            "alvo":               dados.get("alvo"),
            "status":             "executada",
        })
        if not isinstance(novo_id, int) or novo_id <= 0:
            return {"error": "Falha ao criar ordem"}, 500
        ordem, _ = SimuladorOrdemClienteRule.detalhe(id_cliente, novo_id)
        return ordem, 201

    @staticmethod
    def encerrar(id_cliente, id_ordem, dados=None):
        ordem = SimuladorOrdemClienteRule._buscar(id_cliente, id_ordem)
        if not ordem:
            return {"error": "Ordem não encontrada"}, 404
        if ordem.get("status") != "executada":
            return {"error": "Só é possível encerrar uma ordem 'executada'"}, 422

        dados = dados or {}
        encerrada_em = _dt_in(dados.get("encerrada_em"))
        if not encerrada_em:
            return {"error": "Campo 'encerrada_em' é obrigatório (data/hora do encerramento no MT5)"}, 400

        entrada = ordem.get("preco_entrada")
        # preço de saída: do body, ou o WIN do mt5 no horário do encerramento
        preco_saida = dados.get("preco_saida")
        if preco_saida is None:
            preco_saida = SimuladorOrdemClienteRule._preco_em(ordem.get("id_ativos_base") or 1, encerrada_em)

        upd = {"status": "encerrada", "encerrada_em": encerrada_em, "preco_saida": preco_saida}
        if preco_saida is not None and entrada is not None:
            gp = (preco_saida - entrada) if ordem.get("direcao") == "compra" else (entrada - preco_saida)
            upd["resultado_pontos"] = gp
            upd["resultado"]        = "profit" if gp > 0 else "loss" if gp < 0 else "breakeven"
        SimuladorOrdemClienteModel().update(upd, id_ordem)
        return SimuladorOrdemClienteRule.detalhe(id_cliente, id_ordem)

    @staticmethod
    def deletar(id_cliente, id_ordem):
        ordem = SimuladorOrdemClienteRule._buscar(id_cliente, id_ordem)
        if not ordem:
            return {"error": "Ordem não encontrada"}, 404
        SimuladorOrdemClienteModel().delete(id_ordem)
        return {"deleted": True}, 200

    @staticmethod
    def listar(id_cliente, status=None, data=None):
        m = SimuladorOrdemClienteModel().where(["id_cliente", "=", id_cliente])
        if status:
            m.where(["status", "=", status])
        if data:
            m.where(["DATE(executada_em)", "=", data])
        rows = m.order("executada_em", "DESC").find() or []
        ctx = _Mt5Ctx()
        return {"data": [SimuladorOrdemClienteRule._serialize(r, ctx) for r in rows]}, 200

    @staticmethod
    def detalhe(id_cliente, id_ordem):
        ordem = SimuladorOrdemClienteRule._buscar(id_cliente, id_ordem)
        if not ordem:
            return {"error": "Ordem não encontrada"}, 404
        return SimuladorOrdemClienteRule._serialize(ordem, _Mt5Ctx()), 200

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _buscar(id_cliente, id_ordem):
        rows = (SimuladorOrdemClienteModel()
                .where(["id_ordem_cliente", "=", id_ordem])
                .where(["id_cliente", "=", id_cliente])
                .limit(1).find())
        return rows[0] if rows else None

    @staticmethod
    def _preco_em(id_ativos_base, dt_str):
        """Último close do WIN (mt5) até a data/hora informada."""
        symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
        rows = MySql().fetch(
            "SELECT close FROM mt5_candles WHERE id_symbols=%s AND `datetime` <= %s "
            "ORDER BY `datetime` DESC LIMIT 1", (symbol, dt_str)) or []
        return round(float(rows[0]["close"])) if rows else None

    @staticmethod
    def _serialize(ordem, ctx):
        o = {}
        for k, v in ordem.items():
            if isinstance(v, Decimal):
                o[k] = float(v)
            elif isinstance(v, datetime):
                o[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            else:
                o[k] = v

        direcao   = o.get("direcao")
        entrada   = o.get("preco_entrada")
        stop      = o.get("stop_loss")
        alvo      = o.get("alvo")
        contratos = o.get("contratos") or 1
        status    = o.get("status")
        aberta    = status == "executada"
        fechada   = status == "encerrada"
        candles, preco_mercado = ctx.dados(o.get("id_ativos_base") or 1)

        def pl(preco):
            if entrada is None or preco is None:
                return None
            return (preco - entrada) if direcao == "compra" else (entrada - preco)

        calc = {
            "preco_mercado": preco_mercado,
            "ganho_pontos": None, "ganho_reais": None, "situacao": None,
            "risco_pontos": None, "risco_reais": None,
            "retorno_alvo_pontos": None, "rr": None,
            "dist_stop_pontos": None, "dist_alvo_pontos": None, "pct_ate_alvo": None,
            "mfe_pontos": None, "mae_pontos": None, "duracao_min": None,
            "atingiu": "aberta" if aberta else None,
        }

        if entrada is not None and stop is not None:
            calc["risco_pontos"] = abs(entrada - stop)
            calc["risco_reais"]  = round(calc["risco_pontos"] * PONTO_REAIS * contratos, 2)
        if entrada is not None and alvo is not None:
            calc["retorno_alvo_pontos"] = abs(alvo - entrada)
            if calc["risco_pontos"]:
                calc["rr"] = round(calc["retorno_alvo_pontos"] / calc["risco_pontos"], 2)

        if (aberta or fechada) and entrada is not None:
            # ganho: ao vivo (aberta) ou travado no encerramento (fechada)
            if fechada and o.get("resultado_pontos") is not None:
                gp = o.get("resultado_pontos")
            else:
                gp = pl(preco_mercado)
            if gp is not None:
                calc["ganho_pontos"] = gp
                calc["ganho_reais"]  = round(gp * PONTO_REAIS * contratos, 2)
                calc["situacao"]     = "ganhando" if gp > 0 else "perdendo" if gp < 0 else "neutro"

            if aberta and preco_mercado is not None:
                if stop is not None:
                    calc["dist_stop_pontos"] = abs(preco_mercado - stop)
                if alvo is not None:
                    calc["dist_alvo_pontos"] = abs(preco_mercado - alvo)
                    if calc["retorno_alvo_pontos"]:
                        calc["pct_ate_alvo"] = max(0, min(100, round(pl(preco_mercado) / calc["retorno_alvo_pontos"] * 100)))

            # janela: execução -> encerramento (fechada) ou -> agora (aberta)
            exec_dt = _parse_dt(o.get("executada_em"))
            fim_dt  = _parse_dt(o.get("encerrada_em")) if fechada else datetime.now(BRASILIA).replace(tzinfo=None)
            if exec_dt and fim_dt:
                jan = [c for c in candles if exec_dt <= c["dt"] <= fim_dt]
                if jan:
                    if direcao == "compra":
                        calc["mfe_pontos"] = round(max(c["high"] for c in jan) - entrada)
                        calc["mae_pontos"] = round(min(c["low"]  for c in jan) - entrada)
                    else:
                        calc["mfe_pontos"] = round(entrada - min(c["low"]  for c in jan))
                        calc["mae_pontos"] = round(entrada - max(c["high"] for c in jan))
                    if aberta:
                        for c in jan:
                            if direcao == "compra":
                                hit_stop = stop is not None and c["low"]  <= stop
                                hit_alvo = alvo is not None and c["high"] >= alvo
                            else:
                                hit_stop = stop is not None and c["high"] >= stop
                                hit_alvo = alvo is not None and c["low"]  <= alvo
                            if hit_stop:
                                calc["atingiu"] = "stop"; break
                            if hit_alvo:
                                calc["atingiu"] = "alvo"; break
                calc["duracao_min"] = round((fim_dt - exec_dt).total_seconds() / 60)

        o["calculo"] = calc
        return o


class _Mt5Ctx:
    """Cache de candles do mt5 por ativo, para não consultar o banco por ordem."""
    def __init__(self):
        self._cache = {}

    def dados(self, id_ativos_base):
        if id_ativos_base in self._cache:
            return self._cache[id_ativos_base]
        symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
        cutoff = (datetime.now(BRASILIA) - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
        rows = MySql().fetch(
            "SELECT `datetime` dt, high, low, close FROM mt5_candles "
            "WHERE id_symbols=%s AND `datetime` >= %s ORDER BY `datetime`",
            (symbol, cutoff)
        ) or []
        candles = [{"dt": r["dt"], "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"])} for r in rows]
        preco = round(candles[-1]["close"]) if candles else None
        self._cache[id_ativos_base] = (candles, preco)
        return candles, preco
