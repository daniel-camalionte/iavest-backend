from library.base.BaseModel import BaseModel


class ClaudeTraderOperacaoAnaliseModel(BaseModel):
    """Fila de analise: ordens PROPOSTAS pela inteligencia nova, aguardando
    aprovacao antes de replicar pro fluxo real. NAO e lida pela EA — e so um
    deposito da PROPOSTA pura. Coluna de controle: analise (pendente|aprovado|reprovado).
    O rastro proposta->operacao real fica em claude_trader_operacao.id_operacao_analise.

    Campos de direcao:
      - posicao: buy | sell (a direcao "dura" pra execucao)
      - tipo_posicao: TEXT livre — resumo da entrada (ex: 'venda-curta', 'entrada longa')

    acao_mt5 (abrir|mover_stop|encerrar): o que a proposta pede ao fluxo real.
      - abrir: Haiku analisa e replica a op nova (fluxo padrao).
      - mover_stop: repassa novo stop de uma entrada JA analisada (pula o Haiku).
      - encerrar: reservado — hoje e manual em claude_trader_operacao.acao_mt5.
    """

    def table(self):
        return 'claude_trader_operacao_analise'

    def pk(self):
        return 'id_operacao'

    def fields(self):
        return {
            "id_operacao":    "id_operacao",
            "id_ativos_base": "id_ativos_base",
            "id_estrategia":  "id_estrategia",
            "posicao":        "posicao",
            "acao_mt5":       "acao_mt5",
            "tipo_posicao":   "tipo_posicao",
            "preco_entrada":  "preco_entrada",
            "stop_inicial":   "stop_inicial",
            "stop_loss":      "stop_loss",
            "stop_gain":      "stop_gain",
            "alvo_1":         "alvo_1",
            "alvo_2":         "alvo_2",
            "motivo":         "motivo",
            "analise":        "analise",
            "created_at":     "created_at",
            "updated_at":     "updated_at",
        }
