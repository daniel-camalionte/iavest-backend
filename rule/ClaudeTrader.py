"""
Claude Trader — módulo de execução intraday (profissional), ISOLADO do intraday.

Filosofia: o sinal intraday (analysis_intraday) JÁ é a inteligência (Haiku a cada
15min, com filtro de chop). O Claude Trader REUSA esse sinal e GERENCIA a posição:
entra com STOP CURTO FIXO (controla risco/trade), segura cavalgando a tendência, e
encerra por stop/flip/fim-de-dia. Determinístico, robusto, idempotente.

v2.4 (HÍBRIDO de stop):
- ENTRADAS NORMAIS (rompimento intraday): stop inicial = ai_stop_loss da IA (fallback −100
  se inválido) + proteção por alvo (Haiku sobe o stop ao bater alvo1/alvo2). Dá espaço pra
  cavalgar. Risco de cauda do stop largo assumido (conta própria, 1 contrato).
- PRIMEIRO TIRO (aposta da abertura, confluência): stop −100 fixo + gain +300 fixo (fechado).
- Filtro de volume (bova11_vol_rel<0.8) veta a entrada normal. Haiku só atua no alvo.

Fluxo (chamado pelo schedule a cada ~1min):
  processar() →
    1. guarda-corpo: se há posição, checa reconciliação / fim de dia / flip / stop
    2. proteção: ao bater alvo1/alvo2, Haiku recalcula e sobe o stop
    3. cérebro: usa o último sinal intraday p/ abrir (1 entrada por sinal)
    4. devolve o contrato pro MT5 (status, acao, entrada, stop)

Segurança: 'encerrar' é sempre afirmativo; erro NUNCA fecha por default.
"""
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

import config.env as memory
from library.MySql import MySql, _direct_connect
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
FIM_PREGAO_HHMM = 1745           # encerra posição a partir de 17:45 (sem overnight)
VOL_REL_MIN     = 0.8            # FILTRO DE ENTRADA: não abre direcional com volume fraco
                                 # (bova11_vol_rel < 0.8). A própria IA cita "rompimento sem
                                 # volume tende a falhar"; 37% dos sinais saem assim. Análise
                                 # 22–25/06: vetar isso teria matado o −620 de 25/06 e levado
                                 # o P&L da janela de −835 → −115. None = não veta (sem dado).
PRIMEIRO_TIRO_GAIN     = 300     # PRIMEIRO TIRO: alvo fixo (take-profit) da aposta da abertura.
PRIMEIRO_TIRO_ATE_HHMM = 910     # só atira na janela de abertura (até 09:10). Direção vem da
                                 # CONFLUÊNCIA de abertura (EWZ×2+SPY+futuros+gap+1º candle),
                                 # não do fundamental diário nem do OR. Backtest 06: +71/tiro
                                 # no alvo +300 (vs +20 do fundamental). Risco fixo −100.

# CONFIG POR ESTRATÉGIA — os defaults abaixo são exatamente a V2.4. Cada id_estrategia pode
# SOBRESCREVER via estrategia.parametros (JSON), permitindo rodar uma VERSÃO DE TESTE (ex.:
# id=7) com outros parâmetros SEM deploy de código e SEM afetar os clientes (id=6). Ver
# _config_estrategia(). Só cobre params de CÉREBRO (o sinal intraday é compartilhado por ativo).
_CONFIG_DEFAULT = {
    "stop_normal":            "ia",                   # entradas normais: "ia"=ai_stop_loss; "fixo"=stop_fixo_pts
    "stop_fixo_pts":          STOP_CURTO_PTS,         # 100 (fallback / "fixo" / stop do primeiro tiro)
    "vol_min":                VOL_REL_MIN,            # 0.8; None = sem filtro de volume
    "primeiro_tiro":          True,                   # liga/desliga a aposta da abertura
    "primeiro_tiro_gain":     PRIMEIRO_TIRO_GAIN,     # 300
    "primeiro_tiro_ate_hhmm": PRIMEIRO_TIRO_ATE_HHMM, # 910
    "fim_pregao_hhmm":        FIM_PREGAO_HHMM,        # 1745
}

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
    """Último close do WIN no mt5_candles (preço de mercado) — SÓ candle de HOJE.
    Sem candle de hoje (feed caiu / fora de pregão) → None → processar não opera."""
    symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
    hoje = _now().strftime("%Y-%m-%d")
    rows = MySql().fetch(
        "SELECT close FROM mt5_candles WHERE id_symbols=%s AND `datetime` >= %s "
        "ORDER BY `datetime` DESC LIMIT 1",
        (symbol, hoje + " 00:00:00")) or []
    return round(float(rows[0]["close"])) if rows else None


def _ultimo_sinal(id_ativos_base=1):
    """Último sinal intraday — SÓ de HOJE. Nunca abre/decide por sinal de ontem."""
    hoje = _now().strftime("%Y-%m-%d")
    r = (IntradayAnalysisModel()
         .where(["id_ativos_base", "=", id_ativos_base])
         .where(["candle_datetime", ">=", hoje + " 00:00:00"])
         .order("candle_datetime", "DESC").limit(1).find())
    return r[0] if r else None


def _market_analysis_id(id_ativos_base=1):
    r = (MarketAnalysisModel()
         .where(["id_ativos_base", "=", id_ativos_base])
         .order("analyzed_at", "DESC").limit(1).find())
    return r[0]["id_market_analysis"] if r else None


def _confluencia_abertura(id_ativos_base=1):
    """Direção do PRIMEIRO TIRO pela CONFLUÊNCIA de abertura (pré-mercado) — não pelo
    fundamental diário (perma-bearish) nem pelo OR. EWZ (proxy do gap do WIN, peso 2) + SPY
    + futuros US + gap + direção do 1º candle. Retorna 'buy'/'sell' se |conf|>=2, senão None."""
    hoje = _now().strftime("%Y-%m-%d")
    m = (MarketAnalysisModel()
         .where(["id_ativos_base", "=", id_ativos_base])
         .where(["DATE(analyzed_at)", "=", hoje])
         .order("analyzed_at", "DESC").limit(1).find())
    if not m:
        return None  # sem fundamental do dia → sem confluência
    a = m[0]

    def _v(x, th):
        if x is None:
            return 0
        x = float(x)
        return 1 if x > th else (-1 if x < -th else 0)

    # direção do 1º candle do dia (close - open)
    symbol = _ATIVO_SYMBOL.get(id_ativos_base, id_ativos_base)
    rows = MySql().fetch(
        "SELECT open, close FROM mt5_candles WHERE id_symbols=%s AND `datetime` >= %s "
        "ORDER BY `datetime` ASC LIMIT 1",
        (symbol, hoje + " 00:00:00")) or []
    primeiro = 0
    if rows:
        d = float(rows[0]["close"]) - float(rows[0]["open"])
        primeiro = 1 if d > 0 else (-1 if d < 0 else 0)

    conf = (2 * _v(a.get("mc_ewz_pct"), 0.3)
            + _v(a.get("mc_spy_pct"), 0.3)
            + _v(a.get("mc_es1_pct"), 0.2)
            + _v(a.get("td_opening_gap_pct"), 0.2)
            + primeiro)
    if conf >= 2:
        return "buy"
    if conf <= -2:
        return "sell"
    return None


def _config_estrategia(id_estrategia):
    """Config da estratégia: defaults (V2.4) sobrescritos por estrategia.parametros (JSON).
    Permite rodar uma versão de teste por id_estrategia (ex.: 6=prod V2.4, 7=teste) SEM
    deploy de código e sem afetar os outros ids. Erro/ausência → usa defaults (V2.4)."""
    cfg = dict(_CONFIG_DEFAULT)
    try:
        rows = MySql().fetch("SELECT parametros FROM estrategia WHERE id_estrategia=%s LIMIT 1",
                             (id_estrategia,)) or []
        p = rows[0].get("parametros") if rows else None
        if p:
            p = json.loads(p) if isinstance(p, str) else p
            if isinstance(p, dict):
                cfg.update(p)
    except Exception:
        pass
    return cfg


@contextmanager
def _lock_operacao(id_ativos_base, id_estrategia, timeout=8):
    """Serializa o processar() por (ativo, estratégia) com um advisory lock do MySQL.

    GET_LOCK é por CONEXÃO: mantemos UMA conexão dedicada aberta durante toda a
    seção crítica — não dá pra usar o pool (MySql fecha a conexão a cada query, o
    que devolveria o lock). Impede a corrida lê(SELECT 'aberta')/escreve(INSERT)
    que, sob duas chamadas simultâneas, abriria 2 posições ao mesmo tempo.
    Faz yield True se conseguiu o lock; False se outra execução já o detém.
    """
    nome = "claude_trader_oper_%s_%s" % (id_ativos_base, id_estrategia)
    conn = _direct_connect()
    got = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, %s) AS got", (nome, timeout))
            row = cur.fetchone()
        got = bool(row and row.get("got") == 1)
        yield got
    finally:
        try:
            if got:
                with conn.cursor() as cur:
                    cur.execute("SELECT RELEASE_LOCK(%s)", (nome,))
        finally:
            conn.close()


class ClaudeTraderRule:

    # ------------------------------------------------------------------ API
    @staticmethod
    def processar(id_ativos_base=1, id_estrategia=6):
        """Chamado pelo schedule (~1min). Gerência completa + devolve contrato MT5.
        id_estrategia (default 6 = Claude Trader): a ordem é da estratégia, não de
        um cliente — todos copiam a mesma posição."""
        preco = _preco_atual(id_ativos_base)
        if preco is None:
            return {"error": "Sem preço (mt5_candles)"}, 502

        # LOCK: serializa execuções concorrentes do mesmo (ativo, estratégia). Sem ele,
        # duas chamadas simultâneas a /equalizar poderiam ambas ler "sem posição"
        # e ambas abrir → 2 posições ativas ao mesmo tempo.
        with _lock_operacao(id_ativos_base, id_estrategia) as locked:
            if not locked:
                # outra execução já está processando este ativo/estratégia agora:
                # não mexe, só devolve o estado atual pro MT5.
                op = ClaudeTraderRule._operacao_aberta(id_ativos_base, id_estrategia)
                return ClaudeTraderRule._contrato_mt5(op), 200

            cfg = _config_estrategia(id_estrategia)   # defaults V2.4; id pode sobrescrever
            op = ClaudeTraderRule._operacao_aberta(id_ativos_base, id_estrategia)

            if op:
                ClaudeTraderRule._gerir(op, preco, id_ativos_base, cfg)
                op = ClaudeTraderRule._buscar(op["id_operacao"])  # recarrega estado
            else:
                # PRIMEIRO TIRO (janela de abertura) tem prioridade; senão, fluxo normal V2.1.
                if not ClaudeTraderRule._talvez_primeiro_tiro(id_ativos_base, id_estrategia, preco, cfg):
                    ClaudeTraderRule._talvez_abrir(id_ativos_base, id_estrategia, preco, cfg)
                op = ClaudeTraderRule._operacao_aberta(id_ativos_base, id_estrategia)

        return ClaudeTraderRule._contrato_mt5(op), 200

    # ------------------------------------------------------------------ CÉREBRO
    @staticmethod
    def _talvez_abrir(id_ativos_base, id_estrategia, preco, cfg):
        """Sem posição: abre se o último sinal intraday for direcional (1 entrada por sinal)."""
        sinal = _ultimo_sinal(id_ativos_base)
        if not sinal:
            return
        direcao = sinal.get("ai_direcao")
        if direcao not in ("compra", "venda"):
            return  # neutro → fica de fora

        # FILTRO DE VOLUME (cfg.vol_min): rompimento sem volume tende a falhar. Se o sinal veio
        # com bova11_vol_rel < vol_min, não abre. None (sem dado ou cfg sem filtro) não veta.
        vol_min = cfg.get("vol_min")
        vol_rel = sinal.get("bova11_vol_rel")
        if vol_min is not None and vol_rel is not None and float(vol_rel) < float(vol_min):
            return  # volume fraco → não opera o rompimento

        # fim de pregão: não abre posição nova perto do fechamento
        if _hhmm(_now()) >= cfg["fim_pregao_hhmm"]:
            return

        # ANTI-WHIPSAW: 1 entrada por sinal — não reabre no mesmo candle intraday
        sid = sinal.get("id_intraday_analysis")
        if sid and ClaudeTraderRule._ja_operou_sinal(sid):
            return

        tipo = "buy" if direcao == "compra" else "sell"

        # STOP da entrada normal (cfg.stop_normal): "ia" = ai_stop_loss (cavalga; fallback fixo
        # se vier do lado errado da entrada); "fixo" = stop_fixo_pts. A proteção por alvo sobe o
        # stop depois. O PRIMEIRO TIRO tem stop fechado próprio. (V2.4: default "ia".)
        sfp = cfg["stop_fixo_pts"]
        ai_stop = sinal.get("ai_stop_loss")
        if cfg["stop_normal"] == "ia" and ai_stop and \
           ((tipo == "buy" and ai_stop < preco) or (tipo == "sell" and ai_stop > preco)):
            stop = int(ai_stop)
            origem_stop = "ia"
        else:
            stop = (preco - sfp) if tipo == "buy" else (preco + sfp)
            origem_stop = "fixo" if cfg["stop_normal"] != "ia" else "fallback"

        # Alvos da IA: gatilhos de PROTEÇÃO (acionam o Haiku), NÃO take-profit fixo no MT5.
        alvo_1 = int(sinal["ai_alvo_1"]) if sinal.get("ai_alvo_1") else None
        alvo_2 = int(sinal["ai_alvo_2"]) if sinal.get("ai_alvo_2") else None

        novo = ClaudeTraderModel().save({
            "id_ativos_base":     id_ativos_base,
            "id_market_analysis": _market_analysis_id(id_ativos_base),
            "id_intraday_origem": sinal.get("id_intraday_analysis"),
            "id_estrategia":      id_estrategia,
            "tipo_posicao":       tipo,
            "contratos":          1,
            "preco_entrada":      preco,
            "stop_inicial":       int(stop),
            "stop_loss":          int(stop),
            "stop_gain":          None,        # sem TP fixo — o alvo gere proteção, não fecha
            "alvo_1":             alvo_1,
            "alvo_2":             alvo_2,
            "protegido_nivel":    0,
            "status":             "aberta",
            "acao_mt5":           "abrir",
            "modo":               "real",
            "abertura_em":        _now().strftime("%Y-%m-%d %H:%M:%S"),
            "mfe_pontos":         0,
            "mae_pontos":         0,
            "motivo":             "Abertura: sinal %s | stop %s (%s) alvo1 %s alvo2 %s"
                                  % (direcao, int(stop), origem_stop, alvo_1, alvo_2),
        })
        ClaudeTraderRule._log(novo, "abertura", "cerebro", preco, None, int(stop),
                              "Abre %s @ %s, stop %s (%s), alvo1 %s alvo2 %s"
                              % (tipo, preco, int(stop), origem_stop, alvo_1, alvo_2))

    # ------------------------------------------------------------------ PRIMEIRO TIRO
    @staticmethod
    def _ja_operou_hoje(id_ativos_base, id_estrategia):
        """True se já existe QUALQUER operação hoje (qualquer status) — o primeiro tiro é a
        1ª operação do dia, então isso garante 1 tiro/dia."""
        hoje = _now().strftime("%Y-%m-%d")
        r = (ClaudeTraderModel()
             .where(["id_ativos_base", "=", id_ativos_base])
             .where(["id_estrategia", "=", id_estrategia])
             .where(["DATE(abertura_em)", "=", hoje])
             .limit(1).find())
        return bool(r)

    @staticmethod
    def _talvez_primeiro_tiro(id_ativos_base, id_estrategia, preco, cfg):
        """PRIMEIRO TIRO — aposta da abertura. Na janela de abertura (até cfg.primeiro_tiro_ate_hhmm)
        e sem nenhuma operação ainda hoje, se a CONFLUÊNCIA de abertura for clara, abre 1 tiro com
        stop fixo (cfg.stop_fixo_pts) + gain fixo (cfg.primeiro_tiro_gain). stop_gain setado MARCA
        o primeiro tiro p/ o _gerir. Retorna True se atirou."""
        if not cfg.get("primeiro_tiro"):
            return False
        if _hhmm(_now()) > cfg["primeiro_tiro_ate_hhmm"]:
            return False
        if ClaudeTraderRule._ja_operou_hoje(id_ativos_base, id_estrategia):
            return False
        tipo = _confluencia_abertura(id_ativos_base)
        if tipo not in ("buy", "sell"):
            return False  # confluência fraca/mista → não atira

        sfp = cfg["stop_fixo_pts"]; ptg = cfg["primeiro_tiro_gain"]
        stop = (preco - sfp) if tipo == "buy" else (preco + sfp)
        gain = (preco + ptg) if tipo == "buy" else (preco - ptg)
        novo = ClaudeTraderModel().save({
            "id_ativos_base":     id_ativos_base,
            "id_market_analysis": _market_analysis_id(id_ativos_base),
            "id_intraday_origem": None,
            "id_estrategia":      id_estrategia,
            "tipo_posicao":       tipo,
            "contratos":          1,
            "preco_entrada":      preco,
            "stop_inicial":       int(stop),
            "stop_loss":          int(stop),
            "stop_gain":          int(gain),   # TP FIXO — marca o primeiro tiro
            "alvo_1":             None,
            "alvo_2":             None,
            "protegido_nivel":    0,
            "status":             "aberta",
            "acao_mt5":           "abrir",
            "modo":               "real",
            "abertura_em":        _now().strftime("%Y-%m-%d %H:%M:%S"),
            "mfe_pontos":         0,
            "mae_pontos":         0,
            "motivo":             "Primeiro tiro: confluência abertura %s | stop %s gain %s"
                                  % (tipo, int(stop), int(gain)),
        })
        ClaudeTraderRule._log(novo, "abertura", "cerebro", preco, None, int(stop),
                              "Primeiro tiro %s @ %s, stop %s, gain %s"
                              % (tipo, preco, int(stop), int(gain)))
        return True

    # ------------------------------------------------------------------ GESTÃO
    @staticmethod
    def _gerir(op, preco, id_ativos_base, cfg):
        """Posição aberta: reconciliação / fim de dia / flip / stop / trailing."""
        tipo = op["tipo_posicao"]

        # 0. RECONCILIAÇÃO: posição que sobrou de um dia anterior (o encerramento de
        # fim de pregão não rodou naquele dia, ex.: schedule fora do ar). Encerra agora
        # e emite a ordem pro MT5 — garante o flat e não gerencia posição velha como se
        # fosse de hoje. Tem precedência sobre tudo.
        hoje = _now().strftime("%Y-%m-%d")
        abertura = str(op.get("abertura_em") or "")[:10]
        if abertura and abertura < hoje:
            return ClaudeTraderRule._encerrar(op, preco, "fim_dia",
                                              "Posição de dia anterior — encerra (reconciliação)")

        # atualiza MFE/MAE (para análise)
        ClaudeTraderRule._atualiza_excursao(op, preco)

        # 1. fim de pregão → encerra
        if _hhmm(_now()) >= cfg["fim_pregao_hhmm"]:
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

        # 3b. PRIMEIRO TIRO: take-profit FIXO. Só ops com stop_gain setado (o primeiro tiro);
        # as entradas normais têm stop_gain None e cavalgam com proteção por alvo.
        sg = op.get("stop_gain")
        if sg and ((tipo == "buy" and preco >= sg) or (tipo == "sell" and preco <= sg)):
            return ClaudeTraderRule._encerrar(op, sg, "alvo", "Primeiro tiro: alvo atingido")

        # 4. V2: proteção acionada por ALVO. O Haiku NÃO roda mais a cada tick — só quando o
        # preço atinge o alvo1 (e depois o alvo2) do intraday. Aí recalcula e PROTEGE o
        # capital subindo o stop. protegido_nivel evita reacionar no mesmo alvo.
        nivel = op.get("protegido_nivel") or 0
        alvo_1 = op.get("alvo_1")
        alvo_2 = op.get("alvo_2")

        def _hit(alvo):
            return alvo and ((tipo == "buy" and preco >= alvo) or (tipo == "sell" and preco <= alvo))

        alvo_nivel = 2 if _hit(alvo_2) else (1 if _hit(alvo_1) else 0)
        if alvo_nivel > nivel:
            return ClaudeTraderRule._proteger_no_alvo(op, preco, alvo_nivel)

        ClaudeTraderModel().update({"acao_mt5": "manter"}, op["id_operacao"])

    # ------------------------------------------------------------- PROTEÇÃO NO ALVO (Haiku)
    @staticmethod
    def _proteger_no_alvo(op, preco, alvo_nivel):
        """V2: acionado quando o preço bate alvo1/alvo2 do intraday. Chama o Haiku p/
        recalcular e PROTEGER o capital: sobe o stop (no MÍNIMO breakeven). Acata
        encerrar; se o Haiku sugerir stop mais protetor, usa o mais apertado. Registra em
        claude_trader_analise e marca protegido_nivel pra não reacionar no mesmo alvo."""
        tipo = op["tipo_posicao"]
        entrada = op["preco_entrada"]
        atual = op["stop_loss"]
        fav = (preco - entrada) if tipo == "buy" else (entrada - preco)
        sinal = _ultimo_sinal(op.get("id_ativos_base") or 1)
        sid = sinal.get("id_intraday_analysis") if sinal else op.get("id_intraday_origem")

        resp = ClaudeTraderRule._call_haiku(ClaudeTraderRule._contexto_ia(op, preco, fav, sinal))
        rec = (resp or {}).get("recomendacao")
        novo_stop = (resp or {}).get("novo_stop")

        # stop protetor: no MÍNIMO breakeven (entrada). Se o Haiku sugerir um stop ainda
        # mais protetor (lado certo, entre o atual e o preço), usa o mais apertado.
        if tipo == "buy":
            alvo_stop = max(int(entrada), int(atual))
            if rec == "ajustar" and isinstance(novo_stop, (int, float)) and atual < int(novo_stop) < preco:
                alvo_stop = max(alvo_stop, int(novo_stop))
            aplicar = alvo_stop > atual
        else:
            alvo_stop = min(int(entrada), int(atual))
            if rec == "ajustar" and isinstance(novo_stop, (int, float)) and preco < int(novo_stop) < atual:
                alvo_stop = min(alvo_stop, int(novo_stop))
            aplicar = alvo_stop < atual

        try:
            ClaudeTraderAnaliseModel().save({
                "id_operacao":          op["id_operacao"],
                "id_intraday_analysis": sid,
                "preco_no_momento":     preco,
                "lucro_pontos":         int(fav),
                "recomendacao":         rec,
                "stop_antes":           atual,
                "stop_sugerido":        int(novo_stop) if isinstance(novo_stop, (int, float)) else None,
                "acatado":              1 if (rec in ("ajustar", "encerrar") and resp) else 0,
                "motivo":               "ALVO%s | %s" % (alvo_nivel, (resp or {}).get("motivo")),
                "analise_json":         json.dumps(resp, ensure_ascii=False) if resp else None,
                "ia_disponivel":        1 if resp else 0,
            })
        except Exception:
            pass

        # marca o nível protegido (sempre — pra não reacionar no mesmo alvo)
        ClaudeTraderModel().update({"protegido_nivel": alvo_nivel}, op["id_operacao"])

        if resp and rec == "encerrar":
            return ClaudeTraderRule._encerrar(op, preco, "sinal_contrario",
                                              "IA no alvo%s: encerrar — %s" % (alvo_nivel, (resp or {}).get("motivo", "")))
        if aplicar:
            return ClaudeTraderRule._mover_stop(op, alvo_stop, preco)
        ClaudeTraderModel().update({"acao_mt5": "manter"}, op["id_operacao"])

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
    def _operacao_aberta(id_ativos_base, id_estrategia):
        # id_estrategia sempre presente (default 6) → filtro sempre aplicado, sem o
        # caso NULL inconsistente que existia com account_number.
        r = (ClaudeTraderModel()
             .where(["id_ativos_base", "=", id_ativos_base])
             .where(["status", "=", "aberta"])
             .where(["id_estrategia", "=", id_estrategia])
             .order("id_operacao", "DESC").limit(1).find())
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
