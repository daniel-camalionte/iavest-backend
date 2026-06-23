from flask import request
from flask.views import MethodView

from rule.ClaudeTrader import ClaudeTraderRule
from library.SchedulerAuth import check_scheduler_auth
from model.ControllerError import ControllerError


class ClaudeTraderEqualizarController(MethodView):
    """GET /claude-trader/equalizar?id_ativos_base=1[&account_number=X]

    Chamado pelo schedule (~5min). Roda a máquina de estado (guarda-corpo +
    cérebro) e devolve o contrato pro MT5 executar (status/acao/entrada/stop/gain).
    Requer header Authorization: <SCHEDULER_SECRET>.
    """

    def get(self):
        auth_error = check_scheduler_auth()
        if auth_error:
            return auth_error
        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 1))
        except (TypeError, ValueError):
            return {"error": "id_ativos_base deve ser inteiro"}, 400
        account_number = request.args.get("account_number")
        try:
            return ClaudeTraderRule.processar(id_ativos_base, account_number)
        except Exception as e:
            return ControllerError().default(e), 500
