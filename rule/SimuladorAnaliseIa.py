import json
from datetime import datetime
from decimal import Decimal

import config.env as memory
from rule.SimuladorOrdemCliente import (
    SimuladorOrdemClienteRule, _Mt5Ctx, _parse_dt, BRASILIA, _ATIVO_SYMBOL,
)
from model.SimuladorAnaliseIa import SimuladorAnaliseIaModel
from model.MarketAnalysis import MarketAnalysisModel
from model.IntradayAnalysis import IntradayAnalysisModel
from library.MySql import MySql
from library.HttpClient import HttpClient
from library.PlanoAcesso import verificar_acesso, nomes_planos

ROLAGEM_PCT = 0.01   # gap overnight > 1% = troca de contrato (rolagem ~2-3%; normal < 0.6%)

_AIA_MODEL      = "claude-haiku-4-5"
_AIA_MAX_TOKENS = 1500
_AIA_VERSION    = "aia-2026-06-18.1"

_SYSTEM_ANALISE = """Você é um trader profissional fazendo a GESTÃO de uma posição JÁ ABERTA no Mini Índice Bovespa (WIN).

Recebe um JSON com: a entrada do cliente (direção, preço, stop, alvo, contratos), os cálculos da posição (P&L atual, distâncias, MFE/MAE, R/R — já prontos), o cenário fundamentalista do dia, o último sinal intraday e a evolução do mercado desde a entrada.

Sua tarefa: avaliar se a TESE DA ENTRADA ainda é válida e orientar a gestão da posição.

REGRAS:
- NÃO calcule nada — os números já vêm prontos no campo "calculo". Use-os.
- Re-derive os níveis (alvo_1, alvo_2, stop) com base no CENÁRIO ATUAL: suportes/resistências do intraday, médias e Bollinger do fundamental, máx/mín desde a entrada. NÃO repita cegamente os níveis originais da entrada.
- Se "mercado.rolagem.detectada" for true, houve TROCA DE CONTRATO no período — DESCONSIDERE o salto de preço informado (é artificial, não foi movimento real). Avise isso na análise.
- Considere o alinhamento da entrada com o fundamental (viés do dia) e com o intraday (direção/força). Operação contra a tendência maior tem expectativa menor.
- A saída é ANÁLISE TÉCNICA (a recomendação é uma observação técnica, não uma ordem de investimento).
- Escreva em português, objetivo e técnico.

Retorne EXCLUSIVAMENTE um JSON válido (sem markdown, sem texto fora do JSON):
{
  "continua_tendencia": <true|false>,
  "recomendacao": "<manter|ajustar|encerrar>",
  "alvo_1": <inteiro em pontos>,
  "alvo_2": <inteiro em pontos>,
  "stop": <inteiro em pontos>,
  "forca": "<forte|media|fraca>",
  "analise_tecnica": "<2 a 3 parágrafos: leitura do cenário, alinhamento com fundamental e intraday, o que o preço fez desde a entrada, e o porquê das conclusões>"
}"""


def _f(v):
    return float(v) if v is not None else None


def _json_safe(obj):
    """Converte recursivamente Decimal->float e datetime->str (JSON-serializável)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


class SimuladorAnaliseIaRule:

    @staticmethod
    def analisar(id_cliente, id_ordem):
        # Gating por plano (premium) — antes de qualquer consulta/custo
        planos = memory.planos.get("ANALISE_IA", [])
        if not verificar_acesso(id_cliente, planos):
            return SimuladorAnaliseIaRule._sem_plano(planos), 200

        ordem = SimuladorOrdemClienteRule._buscar(id_cliente, id_ordem)
        if not ordem:
            return {"error": "Ordem não encontrada"}, 404

        # Só ordem ABERTA gera análise IA. Demais → texto genérico (sem custo de Haiku).
        if ordem.get("status") != "executada":
            return SimuladorAnaliseIaRule._generico(ordem), 200

        id_ativos_base = ordem.get("id_ativos_base") or 1
        ultimo = SimuladorAnaliseIaRule._ultimo_candle(id_ativos_base)
        id_mt5_candle = ultimo["id"] if ultimo else None

        # Cache por candle: se já analisamos esta ordem com o MESMO último candle, devolve do banco.
        if id_mt5_candle:
            cache = (SimuladorAnaliseIaModel()
                     .where(["id_ordem_cliente", "=", id_ordem])
                     .where(["id_mt5_candle", "=", id_mt5_candle])
                     .order("id_analise_ia", "DESC").limit(1).find())
            if cache:
                out = {}
                try:
                    out = json.loads(cache[0]["analise"]) if cache[0].get("analise") else {}
                except Exception:
                    out = {}
                out["plano"] = True
                out["cache"] = True
                return out, 200

        # Monta o contexto determinístico e chama o Haiku para o parecer
        contexto   = SimuladorAnaliseIaRule._montar_contexto(ordem, id_ativos_base)
        analise_ia = SimuladorAnaliseIaRule._call_haiku(contexto)

        resultado = {
            "plano":            True,
            "id_ordem_cliente": id_ordem,
            "status_ordem":     "executada",
            "contexto":         contexto,
            "analise_ia":       analise_ia,
            "ia_disponivel":    analise_ia is not None,
            "gerada_em":        datetime.now(BRASILIA).strftime("%Y-%m-%d %H:%M:%S"),
            "cache":            False,
        }

        # Só persiste/cacheia se a IA respondeu (falha não vira cache — permite retry)
        if analise_ia is not None:
            try:
                SimuladorAnaliseIaModel().save({
                    "id_ordem_cliente":     id_ordem,
                    "id_mt5_candle":        id_mt5_candle,
                    "id_intraday_analysis": (contexto.get("intraday") or {}).get("id"),
                    "id_market_analysis":   (contexto.get("fundamental") or {}).get("id"),
                    "analise":              json.dumps(resultado, ensure_ascii=False),
                })
            except Exception:
                pass

        return resultado, 200

    @staticmethod
    def _call_haiku(contexto):
        """Chama o Haiku com o contexto e retorna o parecer (dict) ou None se falhar/truncar."""
        try:
            api_key  = memory.anthropic["API_KEY"]
            user_msg = ("Avalie a gestão desta posição aberta e retorne o JSON conforme instruído.\n\n"
                        + json.dumps(contexto, ensure_ascii=False, default=str))
            resp = HttpClient.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                payload={"model": _AIA_MODEL, "max_tokens": _AIA_MAX_TOKENS,
                         "system": _SYSTEM_ANALISE,
                         "messages": [{"role": "user", "content": user_msg}]},
                timeout=40,
            )
            if not resp or resp["status_code"] not in (200, 201):
                return None
            data = resp["data"]
            if data.get("stop_reason") == "max_tokens":
                return None  # truncado — não cacheia, permite retry
            raw = data["content"][0]["text"].strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip(), strict=False)  # tolera caractere de controle cru do modelo
        except Exception:
            return None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _sem_plano(planos):
        nomes = nomes_planos(planos)
        if not nomes:
            prefixo, nm, primeiro = "do plano", "Premium", "Premium"
        elif len(nomes) == 1:
            prefixo, nm, primeiro = "do plano", nomes[0], nomes[0]
        else:
            prefixo, nm, primeiro = "dos planos", " e ".join(nomes), nomes[0]
        texto = (
            f"🔒 Análise IA — exclusiva {prefixo} {nm}.\n"
            f"A Análise IA examina a sua posição aberta em tempo real, cruzando o cenário "
            f"fundamentalista, os sinais intraday e a evolução do mercado — e te diz se a tendência "
            f"da sua entrada continua válida, com alvos e stop recalculados e a leitura técnica do "
            f"porquê. É como ter um analista acompanhando cada operação sua. Assine o {primeiro} e "
            f"tenha esse copiloto em todo trade."
        )
        return {"plano": False, "plano_texto": texto}

    @staticmethod
    def _generico(ordem):
        o = SimuladorOrdemClienteRule._serialize(ordem, _Mt5Ctx())
        st = o.get("status")
        if st == "encerrada":
            rp = o.get("resultado_pontos")
            texto = (f"Operação encerrada — resultado {o.get('resultado')} "
                     f"({rp:+} pts). Análise IA disponível apenas para ordens em execução.")
        else:
            texto = "Análise IA disponível apenas para ordens em execução."
        return {
            "plano":            True,
            "id_ordem_cliente": o.get("id_ordem_cliente"),
            "status_ordem":     st,
            "analise_ia":       None,
            "texto":            texto,
            "ordem":            o,
            "cache":            False,
        }

    @staticmethod
    def _ultimo_candle(id_ativos_base):
        symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
        rows = MySql().fetch(
            "SELECT id_mt5_candle id, `datetime` dt, close FROM mt5_candles "
            "WHERE id_symbols=%s ORDER BY `datetime` DESC LIMIT 1", (symbol,)) or []
        if not rows:
            return None
        return {"id": rows[0]["id"], "dt": rows[0]["dt"], "close": round(float(rows[0]["close"]))}

    @staticmethod
    def _detecta_rolagem(candles):
        """Salto fantasma de troca de contrato: gap OVERNIGHT (entre dias) > ROLAGEM_PCT.
        Intraday é o mesmo contrato (sem salto); a rolagem aparece na virada do dia."""
        for i in range(1, len(candles)):
            prev, cur = candles[i - 1], candles[i]
            pc, cc = prev["close"], cur["close"]
            overnight = (hasattr(prev["dt"], "date") and hasattr(cur["dt"], "date")
                         and prev["dt"].date() != cur["dt"].date())
            if pc and overnight and abs(cc - pc) / pc > ROLAGEM_PCT:
                return {"detectada": True, "de": round(pc), "para": round(cc),
                        "em": cur["dt"].strftime("%Y-%m-%d %H:%M") if hasattr(cur["dt"], "strftime") else str(cur["dt"])}
        return {"detectada": False}

    @staticmethod
    def _montar_contexto(ordem, id_ativos_base):
        # 1. Fundamental atual (último do dia)
        fr = (MarketAnalysisModel()
              .where(["id_ativos_base", "=", id_ativos_base])
              .order("analyzed_at", "DESC").limit(1).find())
        f = fr[0] if fr else None
        fundamental = None
        if f:
            fundamental = {
                "id":           f.get("id_market_analysis"),
                "recomendacao": f.get("recommendation"),
                "confianca":    f.get("confidence"),
                "score_total":  f.get("score_total"),
                "niveis": {
                    "prev_high": f.get("td_prev_high"), "prev_low": f.get("td_prev_low"),
                    "sma9": f.get("td_sma9"), "sma21": f.get("td_sma21"), "sma50": f.get("td_sma50"),
                    "bb_upper": f.get("td_bb_upper"), "bb_lower": f.get("td_bb_lower"),
                },
            }

        # 2. Último sinal intraday
        ir = (IntradayAnalysisModel()
              .where(["id_ativos_base", "=", id_ativos_base])
              .order("candle_datetime", "DESC").limit(1).find())
        it = ir[0] if ir else None
        intraday = None
        if it:
            intraday = {
                "id":              it.get("id_intraday_analysis"),
                "direcao":         it.get("ai_direcao"),
                "forca":           it.get("ai_forca"),
                "confianca":       it.get("ai_confianca"),
                "rsi":             _f(it.get("ti_rsi")),
                "macd_hist":       _f(it.get("ti_macd_hist")),
                "ema_sinal":       it.get("ema_sinal"),
                "tf5_alinhamento": it.get("tf5_alinhamento"),
                "suporte_1":       it.get("sr_support_1"),
                "resistencia_1":   it.get("sr_resistance_1"),
                "win_price":       it.get("win_price"),
            }

        # 3. Evolução do mercado desde a entrada + rolagem
        ctx = _Mt5Ctx()
        candles, preco_mercado = ctx.dados(id_ativos_base)
        exec_dt = _parse_dt(ordem.get("executada_em"))
        jan = [c for c in candles if exec_dt and c["dt"] >= exec_dt] if exec_dt else []
        mercado = {
            "preco_atual":           preco_mercado,
            "candles_desde_entrada": len(jan),
            "max_desde_entrada":     round(max(c["high"] for c in jan)) if jan else None,
            "min_desde_entrada":     round(min(c["low"]  for c in jan)) if jan else None,
            "rolagem":               SimuladorAnaliseIaRule._detecta_rolagem(jan),
        }

        # 4. A ordem (com cálculo ao vivo)
        o = SimuladorOrdemClienteRule._serialize(ordem, ctx)

        # _json_safe: blinda contra Decimal/datetime que vêm crus do banco
        # (ex: td_sma9/bb_upper em analysis_market são decimal(10,2))
        return _json_safe({
            "entrada": {
                "direcao":      o.get("direcao"),
                "preco_entrada": o.get("preco_entrada"),
                "stop_loss":    o.get("stop_loss"),
                "alvo":         o.get("alvo"),
                "contratos":    o.get("contratos"),
                "executada_em": o.get("executada_em"),
            },
            "calculo":     o.get("calculo"),
            "fundamental": fundamental,
            "intraday":    intraday,
            "mercado":     mercado,
        })
