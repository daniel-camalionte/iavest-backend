import json
from datetime import datetime, timezone, timedelta

import config.env as memory
from library.HttpClient import HttpClient
from library.MySql import MySql
from model.ClaudeTraderOperacaoAnalise import ClaudeTraderOperacaoAnaliseModel
from model.ClaudeTraderOperacaoAnaliseVeredito import ClaudeTraderOperacaoAnaliseVeredictoModel
from model.ClaudeTrader import ClaudeTraderModel  # claude_trader_operacao (fluxo real)

BRASILIA        = timezone(timedelta(hours=-3))
_ATIVO_SYMBOL   = {1: 1}          # id_ativos_base -> id_symbols (mt5_candles). 1 = WIN.
_IA_MODEL       = "claude-haiku-4-5"
_IA_MAX_TOKENS  = 600
_LOTE_DEFAULT   = 5
_MAX_TENTATIVAS = 3

_SYSTEM = (
    "Voce e um analista de risco. Recebe uma ENTRADA proposta no mini-indice WIN "
    "(direcao, preco de entrada, stops) + o raciocinio do sinal (motivo) + a leitura "
    "fundamentalista do dia + a leitura intraday mais proxima. Decida se a entrada faz "
    "sentido e deve ser APROVADA ou REPROVADA. Seja criterioso: reprove entradas incoerentes "
    "com o contexto. Retorne EXCLUSIVAMENTE um JSON valido, sem markdown:\n"
    '{"veredito":"aprovado|reprovado","confianca":<inteiro 0-100>,"motivo":"<uma frase objetiva>"}'
)


def _now():
    return datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S")


def _fundamentalista_do_dia(id_ativos_base, ref_dt):
    """analysis_market do dia da proposta (o mais recente). None se nao rodou."""
    rows = MySql().fetch(
        "SELECT * FROM analysis_market WHERE id_ativos_base=%s AND DATE(analyzed_at)=DATE(%s) "
        "ORDER BY analyzed_at DESC LIMIT 1",
        (id_ativos_base, ref_dt)
    ) or []
    return rows[0] if rows else None


def _intraday_proximo(id_ativos_base, ref_dt):
    """analysis_intraday do dia com analyzed_at mais proximo do insert. None se nao houver."""
    rows = MySql().fetch(
        "SELECT * FROM analysis_intraday WHERE id_ativos_base=%s AND DATE(analyzed_at)=DATE(%s) "
        "ORDER BY ABS(TIMESTAMPDIFF(SECOND, analyzed_at, %s)) ASC LIMIT 1",
        (id_ativos_base, ref_dt, ref_dt)
    ) or []
    return rows[0] if rows else None


def _dir_fund(fund):
    if not fund:
        return "indisponivel"
    rec = str(fund.get("recommendation") or "").lower()
    if "buy" in rec or "compra" in rec:
        return "compra"
    if "sell" in rec or "venda" in rec:
        return "venda"
    return "neutro"


def _dir_intra(intra):
    if not intra:
        return "indisponivel"
    d = str(intra.get("ai_direcao") or "").lower()
    return d if d in ("compra", "venda", "neutro") else "neutro"


def _monta_contexto(prop, fund, intra):
    return {
        "proposta": {
            "posicao":       prop.get("posicao"),
            "tipo_posicao":  prop.get("tipo_posicao"),
            "preco_entrada": prop.get("preco_entrada"),
            "stop_loss":     prop.get("stop_loss"),
            "stop_gain":     prop.get("stop_gain"),
        },
        "motivo_sinal": prop.get("motivo"),
        "fundamentalista_dia": {
            "direcao":       _dir_fund(fund),
            "recommendation": fund.get("recommendation") if fund else None,
            "confidence":    fund.get("confidence") if fund else None,
        },
        "intraday_proximo": {
            "direcao":     _dir_intra(intra),
            "ai_forca":    intra.get("ai_forca") if intra else None,
            "ai_confianca": intra.get("ai_confianca") if intra else None,
            "analyzed_at": str(intra.get("analyzed_at")) if intra else None,
        },
    }


def _call_haiku(contexto):
    """Chama o Haiku. Retorna dict {veredito, confianca, motivo} ou None."""
    try:
        user_msg = ("Analise esta entrada e retorne o JSON conforme instruido.\n\n"
                    + json.dumps(contexto, ensure_ascii=False, default=str))
        resp = HttpClient.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": memory.anthropic["API_KEY"],
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            payload={"model": _IA_MODEL, "max_tokens": _IA_MAX_TOKENS,
                     "system": _SYSTEM,
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
        return json.loads(raw.strip(), strict=False)
    except Exception:
        return None


def _replicar(prop, fund, intra):
    """Insere a proposta aprovada em claude_trader_operacao (fluxo real). Retorna o id_operacao."""
    op = {
        "id_ativos_base":     prop["id_ativos_base"],
        "id_estrategia":      prop["id_estrategia"],
        "id_market_analysis": fund.get("id_market_analysis") if fund else None,
        "id_intraday_origem": intra.get("id_intraday_analysis") if intra else None,
        "origem":             prop.get("origem") or "principal",
        "tipo_posicao":       prop["posicao"],          # posicao (buy/sell) -> tipo_posicao da operacao
        "contratos":          1,
        "preco_entrada":      prop.get("preco_entrada"),
        "stop_inicial":       prop.get("stop_inicial") or prop.get("stop_loss"),
        "stop_loss":          prop.get("stop_loss"),
        "stop_gain":          prop.get("stop_gain"),
        "alvo_1":             prop.get("alvo_1"),
        "alvo_2":             prop.get("alvo_2"),
        "protegido_nivel":    0,
        "status":             "aberta",
        "acao_mt5":           "abrir",
        "modo":               "real",
        "abertura_em":        _now(),
        "motivo":             prop.get("motivo"),
        "id_operacao_analise": prop["id_operacao"],     # rastro proposta -> operacao real
    }
    return ClaudeTraderModel().save(op)


def _preco_atual(id_ativos_base):
    """Ultimo close do WIN (mt5_candles). None se o feed estiver sem dado."""
    symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
    r = MySql().fetch("SELECT close FROM mt5_candles WHERE id_symbols=%s "
                      "ORDER BY `datetime` DESC LIMIT 1", (symbol,)) or []
    try:
        return int(r[0]["close"]) if r else None
    except (KeyError, TypeError, ValueError):
        return None


def _fora_da_banda(posicao, preco, stop_loss, stop_gain):
    """REGRA 'fora_da_banda': o preco atual tem que estar DENTRO da banda operacional da
    propria ordem [SL, SG]. Se saiu, a entrada nao vale mais:
      - abaixo do SL (compra): a tese morreu — entraria e tomaria stop na hora
      - acima do SG (compra):  o movimento JA aconteceu — entraria com o alvo atras
    Auto-calibrante: cada ordem define sua tolerancia (stop largo tolera mais deriva).
    Fail-open: sem preco/stops, nao barra (deixa o Haiku/EA decidir).
    """
    if preco is None or stop_loss is None or stop_gain is None:
        return False
    try:
        preco, sl, sg = int(preco), int(stop_loss), int(stop_gain)
    except (TypeError, ValueError):
        return False
    if posicao == "buy":
        return not (sl < preco < sg)
    return not (sg < preco < sl)


def _estrategia_parada(id_estrategia):
    """KILL SWITCH (estrategia.stop_geral=1): nao replica pro fluxo real. Continua analisando e
    gravando o veredito (o dado e valioso pra calibracao) — so nao cria a op. Fail-safe: erro nao
    para (a entrega tambem checa o stop_geral, entao ela e a barreira final)."""
    try:
        r = MySql().fetch("SELECT stop_geral FROM estrategia WHERE id_estrategia=%s LIMIT 1",
                          (id_estrategia,))
        return bool(r and int(r[0].get("stop_geral") or 0) == 1)
    except Exception:
        return False


def _falhou(id_analise, tentativas_atual, msg):
    tent = (tentativas_atual or 0) + 1
    status = "erro" if tent >= _MAX_TENTATIVAS else "pendente"
    ClaudeTraderOperacaoAnaliseModel().update({"tentativas": tent, "analise": status}, id_analise)
    return {"id_operacao_analise": id_analise, "veredito": None, "erro": msg,
            "tentativas": tent, "status": status}


class ClaudeTraderOperacaoAnaliseProcessarRule:
    """Fase 2: varre os pendentes, o Claude Haiku aprova/reprova, grava veredito,
    atualiza a analise e replica pra claude_trader_operacao (conforme o toggle)."""

    @staticmethod
    def processar(limite=_LOTE_DEFAULT):
        enforce = str(memory.claude_analise.get("ENFORCE", "false")).lower() == "true"
        pendentes = (ClaudeTraderOperacaoAnaliseModel()
                     .where(["analise", "=", "pendente"])
                     .order("id_operacao", "ASC")
                     .limit(limite)
                     .find()) or []

        detalhes = []
        for prop in pendentes:
            detalhes.append(ClaudeTraderOperacaoAnaliseProcessarRule._um(prop, enforce))
        return {"processados": len(detalhes), "enforce": enforce, "detalhes": detalhes}, 200

    @staticmethod
    def _um(prop, enforce):
        id_analise = prop["id_operacao"]
        try:
            ref_dt = prop.get("created_at")
            fund  = _fundamentalista_do_dia(prop["id_ativos_base"], ref_dt)
            intra = _intraday_proximo(prop["id_ativos_base"], ref_dt)
            contexto = _monta_contexto(prop, fund, intra)

            # REGRA 'fora_da_banda' — roda ANTES do Haiku: se o preco ja saiu da banda [SL, SG]
            # da propria ordem, a entrada nao vale mais e nem faz sentido gastar chamada de API.
            # Fica registrada com regra='fora_da_banda' pra dar pra medir depois se a regra presta.
            preco = _preco_atual(prop["id_ativos_base"])
            if _fora_da_banda(prop["posicao"], preco, prop.get("stop_loss"), prop.get("stop_gain")):
                veredito, regra, confianca = "reprovado", "fora_da_banda", 0
                resp = None
                motivo_v = ("Preco atual %s saiu da banda operacional [SL %s, SG %s] da ordem "
                            "(entrada %s) — entrada defasada" %
                            (preco, prop.get("stop_loss"), prop.get("stop_gain"),
                             prop.get("preco_entrada")))
            else:
                resp = _call_haiku(contexto)
                if not resp or resp.get("veredito") not in ("aprovado", "reprovado"):
                    return _falhou(id_analise, prop.get("tentativas"), "resposta invalida do Haiku")
                veredito, regra = resp["veredito"], "llm"
                confianca = resp.get("confianca")
                motivo_v = resp.get("motivo")

            ClaudeTraderOperacaoAnaliseVeredictoModel().save({
                "id_operacao_analise":     id_analise,
                "veredito":                veredito,
                "regra":                   regra,
                "confianca":               int(confianca) if isinstance(confianca, (int, float)) else None,
                "fundamentalista_direcao": _dir_fund(fund),
                "intraday_direcao":        _dir_intra(intra),
                "id_market_analysis":      fund.get("id_market_analysis") if fund else None,
                "id_intraday_origem":      intra.get("id_intraday_analysis") if intra else None,
                "motivo":                  motivo_v,
                "analise_json":            json.dumps({"contexto": contexto, "preco_atual": preco,
                                                       "regra": regra, "resposta": resp},
                                                      ensure_ascii=False, default=str),
                "toggle_enforcado":        1 if enforce else 0,
            })

            ClaudeTraderOperacaoAnaliseModel().update({"analise": veredito}, id_analise)

            # Replicacao: modo sombra (enforce=false) SEMPRE replica; enforce=true so aprovado.
            # KILL SWITCH: stop_geral=1 -> nao replica (a entrega barraria de qualquer forma),
            # mas o veredito acima JA foi gravado (nao perde historico durante uma parada).
            parada = _estrategia_parada(prop["id_estrategia"])
            id_operacao = None
            if not parada and ((not enforce) or (veredito == "aprovado")):
                id_operacao = _replicar(prop, fund, intra)

            return {"id_operacao_analise": id_analise, "veredito": veredito, "regra": regra,
                    "confianca": confianca, "id_operacao_replicada": id_operacao,
                    "stop_geral": parada}
        except Exception as e:
            return _falhou(id_analise, prop.get("tentativas"), str(e))
