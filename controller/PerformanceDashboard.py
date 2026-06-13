from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.PerformanceDashboard import PerformanceDashboardRule


class PerformanceDashboardController(MethodView):
    @jwt_required
    def get(self):
        identity   = get_jwt_identity()
        id_usuario = identity.get("id_usuario")

        account_number = request.args.get("account_number") or None

        est_raw = request.args.get("estrategias")
        estrategias = None
        if est_raw:
            try:
                estrategias = [int(e.strip()) for e in est_raw.split(',') if e.strip()]
            except ValueError:
                return {"error": "Parâmetro 'estrategias' deve ser inteiros separados por vírgula"}, 400

        date_from = request.args.get("date_from", "2026-01-01")
        date_to   = request.args.get("date_to") or None

        return PerformanceDashboardRule.dashboard(
            id_usuario=id_usuario,
            account_number=account_number,
            estrategias=estrategias,
            date_from=date_from,
            date_to=date_to,
        )


class PerformanceTradesController(MethodView):
    @jwt_required
    def get(self):
        identity   = get_jwt_identity()
        id_usuario = identity.get("id_usuario")

        account_number = request.args.get("account_number") or None

        est_raw = request.args.get("estrategias")
        estrategias = None
        if est_raw:
            try:
                estrategias = [int(e.strip()) for e in est_raw.split(',') if e.strip()]
            except ValueError:
                return {"error": "Parâmetro 'estrategias' deve ser inteiros separados por vírgula"}, 400

        date_from = request.args.get("date_from", "2026-01-01")
        date_to   = request.args.get("date_to") or None

        try:
            limit  = max(1, min(int(request.args.get("limit",  20)), 100))
            offset = max(0, int(request.args.get("offset", 0)))
        except (TypeError, ValueError):
            limit, offset = 20, 0

        return PerformanceDashboardRule.trades(
            id_usuario=id_usuario,
            account_number=account_number,
            estrategias=estrategias,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
