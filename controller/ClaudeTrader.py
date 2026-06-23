from flask import request
from flask.views import MethodView

from rule.ClaudeTrader import ClaudeTraderRule
from library.SchedulerAuth import check_scheduler_auth
from model.ControllerError import ControllerError


class ClaudeTraderEqualizarController(MethodView):
    """GET /claude-trader/equalizar?id_ativos_base=1[&id_estrategia=6]

    Chamado pelo schedule (~1min). Roda a máquina de estado (guarda-corpo +
    cérebro) e devolve o contrato pro MT5 executar (status/acao/entrada/stop/gain).
    A ordem é da ESTRATÉGIA (id_estrategia, default 6 = Claude Trader), não de um
    cliente — todos copiam. Requer header Authorization: <SCHEDULER_SECRET>.
    """

    def get(self):
        auth_error = check_scheduler_auth()
        if auth_error:
            return auth_error
        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 1))
        except (TypeError, ValueError):
            return {"error": "id_ativos_base deve ser inteiro"}, 400
        try:
            id_estrategia = int(request.args.get("id_estrategia", 6))
        except (TypeError, ValueError):
            return {"error": "id_estrategia deve ser inteiro"}, 400
        try:
            return ClaudeTraderRule.processar(id_ativos_base, id_estrategia)
        except Exception as e:
            return ControllerError().default(e), 500
