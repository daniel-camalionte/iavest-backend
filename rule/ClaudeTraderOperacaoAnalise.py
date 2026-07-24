import config.env as memory
from model.ClaudeTraderOperacaoAnalise import ClaudeTraderOperacaoAnaliseModel

# Campos que a inteligencia pode enviar. O resto do payload e IGNORADO por
# seguranca. Campos de execucao/resultado NAO existem aqui (sao da operacao real).
#   posicao      = buy | sell (direcao dura pra execucao)  [obrigatorio]
#   tipo_posicao = TEXT livre  (resumo da entrada, ex: 'venda-curta')  [opcional]
_CAMPOS_PERMITIDOS = (
    "id_ativos_base", "id_estrategia", "posicao", "acao_mt5", "tipo_posicao", "preco_entrada",
    "stop_inicial", "stop_loss", "stop_gain", "alvo_1", "alvo_2", "motivo",
)
# preco_entrada e exigido so p/ abrir e mover_stop (ver inserir); encerrar so precisa da direcao.
_OBRIGATORIOS = ("id_estrategia", "posicao")

# Acoes que a inteligencia pode enfileirar (o processar ramifica por acao_mt5):
#   abrir      -> Haiku analisa e replica a op (status='aberta')
#   mover_stop -> repassa novo stop pro EA (status='instrucao'), pula o Haiku
#   encerrar   -> repassa fechamento pro EA (status='instrucao'), pula o Haiku (so precisa da direcao)
_ACOES_FILA = ("abrir", "mover_stop", "encerrar")
_ACOES_INSTRUCAO = ("mover_stop", "encerrar")


def _validar_stops(posicao, entrada, stop_loss, stop_gain):
    """Retorna a mensagem de erro se os stops estiverem incoerentes com a direcao; None se ok.
    Stop ausente nao e validado (e opcional) — so valida o que veio.
      compra: stop_loss < entrada < stop_gain
      venda:  stop_gain < entrada < stop_loss
    """
    try:
        entrada = float(entrada)
        sl = float(stop_loss) if stop_loss is not None else None
        sg = float(stop_gain) if stop_gain is not None else None
    except (TypeError, ValueError):
        return "preco_entrada/stop_loss/stop_gain devem ser numericos"

    if posicao == "buy":
        if sl is not None and sl >= entrada:
            return "compra: stop_loss (%g) deve ser MENOR que preco_entrada (%g)" % (sl, entrada)
        if sg is not None and sg <= entrada:
            return "compra: stop_gain (%g) deve ser MAIOR que preco_entrada (%g)" % (sg, entrada)
    else:  # sell
        if sl is not None and sl <= entrada:
            return "venda: stop_loss (%g) deve ser MAIOR que preco_entrada (%g)" % (sl, entrada)
        if sg is not None and sg >= entrada:
            return "venda: stop_gain (%g) deve ser MENOR que preco_entrada (%g)" % (sg, entrada)
    return None


class ClaudeTraderOperacaoAnaliseRule:
    """Regra da fila de analise (Fase 1). So insercao — a ordem fica 'pendente'
    e NAO vai pra EA. A aprovacao/replicacao vem em fase futura."""

    @staticmethod
    def inserir(data):
        # Auth por senha propria (sem JWT — acesso externo de aplicacao).
        # Fail-closed: sem KEY configurada no ambiente, rejeita tudo (nao abre porta).
        key = memory.claude_analise.get("KEY")
        if not key:
            return {"msg": "Rota nao configurada (CLAUDE_ANALISE_KEY ausente no ambiente)"}, 503
        if str(data.get("password", "")) != str(key):
            return {"msg": "Senha incorreta"}, 401

        # acao_mt5 (default 'abrir'): abrir, mover_stop e encerrar entram pela fila (o processar
        # ramifica). Valor invalido barra aqui.
        acao_mt5 = str(data.get("acao_mt5") or "abrir")
        if acao_mt5 not in _ACOES_FILA:
            return {"msg": "acao_mt5 deve ser 'abrir', 'mover_stop' ou 'encerrar'"}, 422

        # OBRIGATORIOS: id_estrategia e posicao sempre. preco_entrada so p/ abrir e mover_stop —
        # 'encerrar' so precisa da DIRECAO (nao carrega entrada nem stops; o EA fecha a posicao).
        obrigatorios = list(_OBRIGATORIOS)
        if acao_mt5 in ("abrir", "mover_stop"):
            obrigatorios.append("preco_entrada")
        faltando = [c for c in obrigatorios if data.get(c) in (None, "")]
        if faltando:
            return {"msg": "Campos obrigatorios faltando: " + ", ".join(faltando)}, 422

        posicao = str(data.get("posicao"))
        if posicao not in ("buy", "sell"):
            return {"msg": "posicao deve ser 'buy' ou 'sell'"}, 422

        # COERENCIA DOS STOPS (so no 'abrir'): numa compra o SL fica ABAIXO e o SG ACIMA da
        # entrada; numa venda e o inverso. Ordem com stops trocados (bug de variavel na IA) e
        # sem sentido — o stop de prejuizo ficaria onde daria lucro. Barra na porta pra a IA
        # descobrir o bug aqui. NAO se aplica a mover_stop/encerrar: um trailing legitimo CRUZA a
        # entrada (ex.: buy travando lucro com stop ACIMA da entrada) e o encerrar nem carrega
        # stops — validar aqui reprovaria instrucao valida.
        if acao_mt5 == "abrir":
            erro_stops = _validar_stops(posicao, data.get("preco_entrada"),
                                        data.get("stop_loss"), data.get("stop_gain"))
            if erro_stops:
                return {"msg": erro_stops}, 422

        row = {c: data[c] for c in _CAMPOS_PERMITIDOS if data.get(c) is not None}
        row["acao_mt5"] = acao_mt5
        row["analise"] = "pendente"

        new_id = ClaudeTraderOperacaoAnaliseModel().save(row)
        if not new_id:
            return {"msg": "Erro ao inserir na fila de analise"}, 500

        return {"id_operacao": new_id, "analise": "pendente"}, 201
