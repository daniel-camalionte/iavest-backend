from flask import request
from flask.views import MethodView
from rule.TradePerformance import TradePerformanceRule


class TradePerformanceCacheClearController(MethodView):

    def delete(self):
        return TradePerformanceRule.clear_cache()


class TradePerformanceMensalController(MethodView):

    def get(self):
        try:
            contracts = max(1, int(request.args.get('contracts', 2)))
        except (ValueError, TypeError):
            contracts = 2

        try:
            capital = float(request.args.get('capital', contracts * 1000))
            if capital <= 0:
                capital = float(contracts * 1000)
        except (ValueError, TypeError):
            capital = float(contracts * 1000)

        date_from = request.args.get('date_from', '2026-01-01')
        date_to   = request.args.get('date_to',   None)

        result, status = TradePerformanceRule.mensal(contracts, capital, date_from, date_to)
        return result, status
