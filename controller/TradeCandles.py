from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.TradeCandles import TradeCandlesRule


class TradeCandlesController(MethodView):
    @jwt_required
    def get(self):
        identity   = get_jwt_identity()
        id_usuario = identity.get("id_usuario")

        try:
            id_trade = int(request.args.get("id_trade", 0))
        except (TypeError, ValueError):
            return {"error": "Parâmetro id_trade inválido"}, 400

        if not id_trade:
            return {"error": "Parâmetro id_trade obrigatório"}, 400

        return TradeCandlesRule.get(id_trade, id_usuario)
