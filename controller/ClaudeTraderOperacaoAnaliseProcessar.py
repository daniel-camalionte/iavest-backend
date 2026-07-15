from flask import request
from flask.views import MethodView

from rule.ClaudeTraderOperacaoAnaliseProcessar import ClaudeTraderOperacaoAnaliseProcessarRule
from library.SchedulerAuth import check_scheduler_auth
from model.ControllerError import ControllerError


class ClaudeTraderOperacaoAnaliseProcessarController(MethodView):
    """GET /claude-trader/operacao-analise/processar[?limite=5]

    Chamado por um schedule (~1min). Pega ate `limite` propostas pendentes,
    o Claude Haiku aprova/reprova cada uma, grava o veredito, atualiza a analise
    e replica pra claude_trader_operacao (modo sombra sempre replica; enforce so
    aprovado). Requer auth de scheduler (SCHEDULER_SECRET).
    """

    def get(self):
        auth_error = check_scheduler_auth()
        if auth_error:
            return auth_error
        try:
            limite = int(request.args.get("limite", 5))
        except (TypeError, ValueError):
            limite = 5
        try:
            return ClaudeTraderOperacaoAnaliseProcessarRule.processar(limite)
        except Exception as e:
            return ControllerError().default(e), 500
