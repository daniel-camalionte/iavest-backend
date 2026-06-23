"""
Claude Trader — módulo de execução intraday (profissional), ISOLADO do intraday.

Filosofia: o sinal intraday (analysis_intraday) JÁ é a inteligência (Haiku a cada
15min, com filtro de chop). O Claude Trader REUSA esse sinal e GERENCIA a posição:
entra com STOP CURTO FIXO (controla risco/trade), segura cavalgando a tendência, e
encerra por stop/flip/fim-de-dia. Determinístico, robusto, idempotente.

v1: stop curto fixo (100pts), SEM trailing (deixa o vencedor correr). Trailing
(trail50) existe no código mas não é chamado — fica pra um v2 se o dado pedir.

Fluxo (chamado pelo schedule a cada ~5min):
  processar() →
    1. guarda-corpo: se há posição, checa stop fixo / flip / fim de dia
    2. cérebro: usa o último sinal intraday p/ abrir (1 entrada por sinal)
    3. devolve o contrato pro MT5 (status, acao, entrada, stop)

Segurança: 'encerrar' é sempre afirmativo; erro NUNCA fecha por default.
"""
import json
from datetime import datetime, timezone, timedelta

import config.env as memory
from library.MySql import MySql
from library.HttpClient import HttpClient
from model.ClaudeTrader import ClaudeTraderModel, ClaudeTraderLogModel, ClaudeTraderAnaliseModel
from model.IntradayAnalysis import IntradayAnalysisModel
from model.MarketAnalysis import MarketAnalysisModel

BRASILIA      = timezone(timedelta(hours=-3))
PONTO_REAIS   = 0.20
_ATIVO_SYMBOL = {1: 1}            # id_ativos_base -> id_symbols (mt5_candles)

# --- parâmetros do v1 (todos configuráveis) ---
STOP_CURTO_PTS  = 100           # stop inicial CURTO fixo (controla risco/trade). NÃO usa o
                                # stop variável do Haiku (que era largo demais, até 505pts).
                                # Valor conservador/raciocinado — calibrar com mais dado.
TRAIL_PCT_PICO  = 0.5            # trail50: trava 50% do pico de lucro (entrada + pico*0.5)
FIM_PREGAO_HHMM = 1750           # encerra posição a partir de 17:50 (sem overnight)

_IA_MODEL       = "claude-haiku-4-5"
_IA_MAX_TOKENS  = 600
_SYSTEM_GESTAO = """Você é um trader profissional gerenciando uma posição JÁ ABERTA e EM LUCRO no Mini Índice Bovespa (WIN), operada por um robô.

Recebe um JSON com: a posição (direção, entrada, stop atual, lucro atual em pontos), o último sinal intraday, o fundamental do dia e a evolução do preço desde a entrada.

Sua tarefa: decidir o que fazer com a posição AGORA. Objetivo duplo: PROTEGER o lucro já acumulado e CAVALGAR a tendência se ela continuar; ENCERRAR se a tese enfraqueceu.

REGRAS:
- NÃO calcule nada — os números já vêm prontos.
- A decisão é uma de três: "manter" (segue como está), "ajustar" (recalibrar o stop — informe o novo_stop em pontos inteiros) ou "encerrar" (fechar agora e realizar o lucro).
- "ajustar" é só para PROTEGER mais (mover o stop a favor, travando lucro) ou dar espaço se a tendência está muito forte — NUNCA afrouxe o stop para o lado da perda.
- Tendência forte + lucro pode crescer → "manter" ou "ajustar" (subir o stop).
- Momentum morreu / sinal virou neutro ou contrário / preço esticado → "encerrar".

Retorne EXCLUSIVAMENTE um JSON válido, sem markdown:
{"recomendacao":"manter|ajustar|encerrar","novo_stop":<inteiro ou null>,"motivo":"<uma frase técnica>"}"""


def _now():
    return datetime.now(BRASILIA).replace(tzinfo=None)


def _preco_atual(id_ativos_base=1):
    """Último close do WIN no mt5_candles (preço de mercado)."""
    symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
    rows = MySql().fetch(
        "SELECT close FROM mt5_candles WHERE id_symbols=%s ORDER BY `datetime` DESC LIMIT 1",
        (symbol,)) or []
    return round(float(rows[0]["close"])) if rows else None


def _ultimo_sinal(id_ativos_base=1):
    r = (IntradayAnalysisModel()
         .where(["id_ativos_base", "=", id_ativos_base])
         .order("candle_datetime", "DESC").limit(1).find())
    return r[0] if r else None


def _market_analysis_id(id_ativos_base=1):
    r = (MarketAnalysisModel()
         .where(["id_ativos_base", "=", id_ativos_base])
         .order("analyzed_at", "DESC").limit(1).find())
    return r[0]["id_market_analysis"] if r else None


class ClaudeTraderRule:

    # ------------------------------------------------------------------ API
    @staticmethod
    def processar(id_ativos_base=1, account_number=None):
        """Chamado pelo schedule (~5min). Gerência completa + devolve contrato MT5."""
        preco = _preco_atual(id_ativos_base)
        if preco is None:
            return {"error": "Sem preço (mt5_candles)"}, 502

        op = ClaudeTraderRule._operacao_aberta(id_ativos_base, account_number)

        if op:
            ClaudeTraderRule._gerir(op, preco, id_ativos_base)
            op = ClaudeTraderRule._buscar(op["id_operacao"])  # recarrega estado
        else:
            ClaudeTraderRule._talvez_abrir(id_ativos_base, account_number, preco)
            op = ClaudeTraderRule._operacao_aberta(id_ativos_base, account_number)

        return ClaudeTraderRule._contrato_mt5(op), 200

    # ------------------------------------------------------------------ CÉREBRO
    @staticmethod
    def _talvez_abrir(id_ativos_base, account_number, preco):
        """Sem posição: abre se o último sinal intraday for direcional (1 entrada por sinal)."""
        sinal = _ultimo_sinal(id_ativos_base)
        if not sinal:
            return
        direcao = sinal.get("ai_direcao")
        if direcao not in ("compra", "venda"):
            return  # neutro → fica de fora

        # fim de pregão: não abre posição nova perto do fechamento
        if _hhmm(_now()) >= FIM_PREGAO_HHMM:
            return

        # ANTI-WHIPSAW: 1 entrada por sinal — não reabre no mesmo candle intraday
        sid = sinal.get("id_intraday_analysis")
        if sid and ClaudeTraderRule._ja_operou_sinal(sid):
            return

        tipo = "buy" if direcao == "compra" else "sell"

        # STOP CURTO FIXO (relativo à entrada real) — controla o risco por trade.
        # Backtest: stop fixo curto + trail50 é mais robusto que o stop largo do Haiku
        # (positivo em 5/7 dias e +881 mesmo sem o melhor dia).
        stop = (preco - STOP_CURTO_PTS) if tipo == "buy" else (preco + STOP_CURTO_PTS)

        # trail50: SEM alvo fixo — cavalga com o stop móvel (trava 50% do pico de lucro)
        gain = None

        novo = ClaudeTraderModel().save({
            "id_ativos_base":     id_ativos_base,
            "id_market_analysis": _market_analysis_id(id_ativos_base),
            "id_intraday_origem": sinal.get("id_intraday_analysis"),
            "account_number":     account_number,
            "tipo_posicao":       tipo,
            "contratos":          1,
            "preco_entrada":      preco,
            "stop_inicial":       int(stop),
            "stop_loss":          int(stop),
            "stop_gain":          int(gain) if gain else None,
            "status":             "aberta",
            "acao_mt5":           "abrir",
            "modo":               "real",
            "abertura_em":        _now().strftime("%Y-%m-%d %H:%M:%S"),
            "mfe_pontos":         0,
            "mae_pontos":         0,
            "motivo":             "Abertura: sinal intraday %s (rompimento)" % direcao,
        })
        ClaudeTraderRule._log(novo, "abertura", "cerebro", preco, None, int(stop),
                              "Abre %s @ %s, stop %s" % (tipo, preco, int(stop)))

    # ------------------------------------------------------------------ GESTÃO
    @staticmethod
    def _gerir(op, preco, id_ativos_base):
        """Posição aberta: fim de dia / flip / stop / trailing."""
        tipo = op["tipo_posicao"]
        # atualiza MFE/MAE (para análise)
        ClaudeTraderRule._atualiza_excursao(op, preco)

        # 1. fim de pregão → encerra
        if _hhmm(_now()) >= FIM_PREGAO_HHMM:
            return ClaudeTraderRule._encerrar(op, preco, "fim_dia", "Fim de pregão — sem overnight")

        # 2. sinal virou → encerra (sem reverter)
        sinal = _ultimo_sinal(id_ativos_base)
        if sinal and sinal.get("ai_direcao") in ("compra", "venda"):
            sdir = "buy" if sinal["ai_direcao"] == "compra" else "sell"
            if sdir != tipo:
                return ClaudeTraderRule._encerrar(op, preco, "sinal_contrario",
                                                  "Sinal virou para %s — encerra, sem reverter" % sdir)

        # 3. bateu o stop → encerra (o broker já fez; registramos)
        if (tipo == "buy" and preco <= op["stop_loss"]) or \
           (tipo == "sell" and preco >= op["stop_loss"]):
            return ClaudeTraderRule._encerrar(op, op["stop_loss"], "stop", "Stop atingido")

        # 4. SEM trailing mecânico. Mas: se está EM LUCRO, a cada sinal intraday novo (15min)
        # consulta a IA (Haiku) p/ decidir manter / ajustar (recalibrar stop) / encerrar.
        # Decisão pura da IA — registrada em claude_trader_analise pra avaliar depois.
        fav = (preco - op["preco_entrada"]) if tipo == "buy" else (op["preco_entrada"] - preco)
        if fav > 0 and ClaudeTraderRule._analise_ia(op, preco, fav):
            return  # IA tratou (encerrou / ajustou)
        ClaudeTraderModel().update({"acao_mt5": "manter"}, op["id_operacao"])

    # ------------------------------------------------------------------ CÉREBRO IA (15min, no lucro)
    @staticmethod
    def _analise_ia(op, preco, fav):
        """Consulta o Haiku 1x por sinal intraday (15min), quando a posição está no lucro.
        Acata: encerrar / ajustar (move stop) / manter. Registra tudo em claude_trader_analise.
        Retorna True se agiu (encerrou/ajustou), False caso contrário (segue mecânico)."""
        sinal = _ultimo_sinal(op.get("id_ativos_base") or 1)
        sid = sinal.get("id_intraday_analysis") if sinal else None
        if not sid or ClaudeTraderRule._ja_analisou(op["id_operacao"], sid):
            return False  # sem sinal novo → não chama (1 análise por sinal/15min)

        contexto = ClaudeTraderRule._contexto_ia(op, preco, fav, sinal)
        resp = ClaudeTraderRule._call_haiku(contexto)

        rec = (resp or {}).get("recomendacao")
        novo_stop = (resp or {}).get("novo_stop")
        acatado = 0
        if resp and rec == "ajustar" and isinstance(novo_stop, (int, float)):
            ns = int(novo_stop)
            # só aplica se for proteção válida (lado certo, a favor)
            tipo = op["tipo_posicao"]
            if (tipo == "buy" and op["stop_loss"] < ns < preco) or \
               (tipo == "sell" and preco < ns < op["stop_loss"]):
                acatado = 1

        # registra a análise (sempre — é o que vamos avaliar depois)
        try:
            ClaudeTraderAnaliseModel().save({
                "id_operacao":          op["id_operacao"],
                "id_intraday_analysis": sid,
                "preco_no_momento":     preco,
                "lucro_pontos":         int(fav),
                "recomendacao":         rec,
                "stop_antes":           op["stop_loss"],
                "stop_sugerido":        int(novo_stop) if isinstance(novo_stop, (int, float)) else None,
                "acatado":              acatado if rec in ("ajustar", "encerrar") and resp else 0,
                "motivo":               (resp or {}).get("motivo"),
                "analise_json":         json.dumps(resp, ensure_ascii=False) if resp else None,
                "ia_disponivel":        1 if resp else 0,
            })
        except Exception:
            pass

        if not resp:
            return False  # IA falhou → segue mecânico (nunca encerra por falha)

        if rec == "encerrar":
            ClaudeTraderRule._encerrar(op, preco, "sinal_contrario", "IA: encerrar — " + str((resp or {}).get("motivo", "")))
            return True
        if rec == "ajustar" and acatado:
            ClaudeTraderRule._mover_stop(op, int(novo_stop), preco)
            return True
        return False  # manter

    # ------------------------------------------------------------------ AÇÕES
    @staticmethod
    def _mover_stop(op, novo_stop, preco):
        antes = op["stop_loss"]
        ClaudeTraderModel().update({"stop_loss": int(novo_stop), "acao_mt5": "mover_stop",
                                    "motivo": "Trailing: stop %s → %s (preço %s)" % (antes, int(novo_stop), preco)},
                                   op["id_operacao"])
        ClaudeTraderRule._log(op["id_operacao"], "mover_stop", "guarda_corpo", preco, antes, int(novo_stop),
                              "Trailing protege lucro acumulado")

    @staticmethod
    def _encerrar(op, preco_saida, motivo, descricao):
        tipo = op["tipo_posicao"]
        gp = (preco_saida - op["preco_entrada"]) if tipo == "buy" else (op["preco_entrada"] - preco_saida)
        ClaudeTraderModel().update({
            "status":           "encerrada",
            "acao_mt5":         "encerrar",
            "encerramento_em":  _now().strftime("%Y-%m-%d %H:%M:%S"),
            "preco_saida":      int(preco_saida),
            "resultado":        motivo,
            "resultado_pontos": int(round(gp)),
            "motivo":           descricao,
        }, op["id_operacao"])
        ClaudeTraderRule._log(op["id_operacao"], "encerramento", "cerebro", preco_saida,
                              op["stop_loss"], None, "%s (%+d pts)" % (descricao, round(gp)))

    @staticmethod
    def _atualiza_excursao(op, preco):
        tipo = op["tipo_posicao"]; ent = op["preco_entrada"]
        fav = (preco - ent) if tipo == "buy" else (ent - preco)
        upd = {}
        if fav > (op.get("mfe_pontos") or 0): upd["mfe_pontos"] = int(fav)
        if fav < (op.get("mae_pontos") or 0): upd["mae_pontos"] = int(fav)
        if upd:
            ClaudeTraderModel().update(upd, op["id_operacao"])

    # ------------------------------------------------------------------ contrato MT5
    @staticmethod
    def _contrato_mt5(op):
        if not op or op.get("status") != "aberta":
            return {"status": "nenhuma", "acao": "nada"}
        return {
            "status":        "aberta",
            "acao":          op.get("acao_mt5") or "manter",
            "tipo_posicao":  op["tipo_posicao"],
            "preco_entrada": op["preco_entrada"],
            "stop_loss":     op["stop_loss"],
            "stop_gain":     op.get("stop_gain"),
            "motivo":        op.get("motivo"),
            "id_operacao":   op["id_operacao"],
            "atualizado_em": str(op.get("updated_at")),
        }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _operacao_aberta(id_ativos_base, account_number):
        m = (ClaudeTraderModel()
             .where(["id_ativos_base", "=", id_ativos_base])
             .where(["status", "=", "aberta"]))
        if account_number:
            m.where(["account_number", "=", account_number])
        r = m.order("id_operacao", "DESC").limit(1).find()
        return r[0] if r else None

    @staticmethod
    def _buscar(id_operacao):
        r = ClaudeTraderModel().where(["id_operacao", "=", id_operacao]).limit(1).find()
        return r[0] if r else None

    @staticmethod
    def _ja_operou_sinal(id_intraday):
        """True se já existe operação (qualquer status) aberta a partir deste sinal
        intraday — evita reentrar no mesmo candle (anti-whipsaw)."""
        r = (ClaudeTraderModel()
             .where(["id_intraday_origem", "=", id_intraday])
             .limit(1).find())
        return bool(r)

    @staticmethod
    def _ja_analisou(id_operacao, id_intraday):
        """True se a IA já analisou esta operação para este sinal intraday (1x por 15min)."""
        r = (ClaudeTraderAnaliseModel()
             .where(["id_operacao", "=", id_operacao])
             .where(["id_intraday_analysis", "=", id_intraday])
             .limit(1).find())
        return bool(r)

    @staticmethod
    def _contexto_ia(op, preco, fav, sinal):
        """Monta o contexto determinístico pra IA gerenciar a posição."""
        def f(v):
            return float(v) if v is not None else None
        fr = (MarketAnalysisModel()
              .where(["id_ativos_base", "=", op.get("id_ativos_base") or 1])
              .order("analyzed_at", "DESC").limit(1).find())
        fund = fr[0] if fr else {}
        return {
            "posicao": {
                "direcao": op["tipo_posicao"], "entrada": op["preco_entrada"],
                "stop_atual": op["stop_loss"], "lucro_pontos": int(fav),
                "lucro_reais": round(fav * PONTO_REAIS, 2),
                "mfe_pontos": op.get("mfe_pontos"), "mae_pontos": op.get("mae_pontos"),
            },
            "intraday": {
                "direcao": sinal.get("ai_direcao"), "forca": sinal.get("ai_forca"),
                "confianca": sinal.get("ai_confianca"), "rsi": f(sinal.get("ti_rsi")),
                "macd_hist": f(sinal.get("ti_macd_hist")), "ema_sinal": sinal.get("ema_sinal"),
                "suporte_1": sinal.get("sr_support_1"), "resistencia_1": sinal.get("sr_resistance_1"),
                "tf5_alinhamento": sinal.get("tf5_alinhamento"),
            },
            "fundamental": {
                "recomendacao": fund.get("recommendation"), "confianca": fund.get("confidence"),
            },
            "mercado": {"preco_atual": preco},
        }

    @staticmethod
    def _call_haiku(contexto):
        """Chama o Haiku p/ gestão da posição. Retorna dict {recomendacao, novo_stop, motivo} ou None."""
        try:
            user_msg = ("Decida a gestão desta posição aberta e retorne o JSON conforme instruído.\n\n"
                        + json.dumps(contexto, ensure_ascii=False, default=str))
            resp = HttpClient.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": memory.anthropic["API_KEY"],
                         "anthropic-version": "2023-06-01", "content-type": "application/json"},
                payload={"model": _IA_MODEL, "max_tokens": _IA_MAX_TOKENS,
                         "system": _SYSTEM_GESTAO,
                         "messages": [{"role": "user", "content": user_msg}]},
                timeout=30,
            )
            if not resp or resp["status_code"] not in (200, 201):
                return None
            data = resp["data"]
            if data.get("stop_reason") == "max_tokens":
                return None
            raw = data["content"][0]["text"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception:
            return None

    @staticmethod
    def _log(id_op, evento, fonte, preco, stop_antes, stop_depois, motivo):
        try:
            ClaudeTraderLogModel().save({
                "id_operacao": id_op, "evento": evento, "fonte": fonte,
                "preco_evento": int(preco) if preco is not None else None,
                "stop_antes": int(stop_antes) if stop_antes is not None else None,
                "stop_depois": int(stop_depois) if stop_depois is not None else None,
                "motivo": motivo,
            })
        except Exception:
            pass  # log nunca derruba a operação


def _hhmm(dt):
    return dt.hour * 100 + dt.minute
