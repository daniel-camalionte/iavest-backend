from flask import request
from flask.views import MethodView

from rule.ClaudeTraderOperacaoAnalise import ClaudeTraderOperacaoAnaliseRule
from model.ControllerError import ControllerError


class ClaudeTraderOperacaoAnaliseController(MethodView):
    """POST /claude-trader/operacao-analise

    Recebe uma ordem PROPOSTA pela inteligencia nova e grava na fila de analise
    (claude_trader_operacao_analise, analise='pendente'). NAO vai pra EA — fica
    retida ate aprovacao (fase futura). Auth por senha propria no payload (sem JWT),
    porque quem chama e uma aplicacao externa nao logada.
    """

    def post(self):
        try:
            data = request.get_json(force=True, silent=True)
            if not isinstance(data, dict):
                return {"msg": "JSON inválido no corpo. Dica: no campo 'motivo', "
                               "escape as quebras de linha como \\n (JSON não aceita quebra literal)."}, 422
            return ClaudeTraderOperacaoAnaliseRule.inserir(data)
        except Exception as e:
            return ControllerError().default(e), 500
