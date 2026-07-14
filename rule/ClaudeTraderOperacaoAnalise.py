import config.env as memory
from model.ClaudeTraderOperacaoAnalise import ClaudeTraderOperacaoAnaliseModel

# Campos que a inteligencia pode enviar. O resto do payload e IGNORADO por
# seguranca. Campos de execucao/resultado NAO existem aqui (sao da operacao real).
#   posicao      = buy | sell (direcao dura pra execucao)  [obrigatorio]
#   tipo_posicao = TEXT livre  (resumo da entrada, ex: 'venda-curta')  [opcional]
_CAMPOS_PERMITIDOS = (
    "id_ativos_base", "id_estrategia", "posicao", "tipo_posicao", "preco_entrada",
    "stop_inicial", "stop_loss", "stop_gain", "alvo_1", "alvo_2", "motivo",
)
_OBRIGATORIOS = ("id_estrategia", "posicao", "preco_entrada")


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

        faltando = [c for c in _OBRIGATORIOS if data.get(c) in (None, "")]
        if faltando:
            return {"msg": "Campos obrigatorios faltando: " + ", ".join(faltando)}, 422

        if str(data.get("posicao")) not in ("buy", "sell"):
            return {"msg": "posicao deve ser 'buy' ou 'sell'"}, 422

        row = {c: data[c] for c in _CAMPOS_PERMITIDOS if data.get(c) is not None}
        row["analise"] = "pendente"

        new_id = ClaudeTraderOperacaoAnaliseModel().save(row)
        if not new_id:
            return {"msg": "Erro ao inserir na fila de analise"}, 500

        return {"id_operacao": new_id, "analise": "pendente"}, 201
