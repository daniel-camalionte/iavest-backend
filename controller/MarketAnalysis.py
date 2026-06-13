from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required

from rule.MarketAnalysis import MarketAnalysisRule, MarketAnalysisListRule, MarketAnalysisDetailRule
from rule.IntradayAnalysis import IntradayAnalysisRule, IntradayAnalysisLatestRule, IntradayAnalysisListRule
from library.YahooFinanceClient import YahooFinanceClient
from library.HttpClient import HttpClient
from library.SchedulerAuth import check_scheduler_auth
import config.env as memory


class MarketAnalysisPingController(MethodView):
    def get(self):
        api_key = memory.anthropic["API_KEY"]
        if not api_key:
            return {"status": "error", "msg": "ANTHROPIC_API_KEY não configurada"}, 500

        resp = HttpClient.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            payload={
                "model":      "claude-opus-4-5",
                "max_tokens": 50,
                "messages":   [{"role": "user", "content": "Responda apenas: OK"}],
            },
            timeout=15,
        )

        if resp and resp["status_code"] == 200:
            data = resp["data"]
            return {
                "status":   "success",
                "msg":      "Conexão com Claude API funcionando",
                "model":    data.get("model"),
                "response": data["content"][0]["text"],
            }, 200

        detail = resp["data"] if resp else "Sem resposta"
        return {"status": "error", "msg": "Erro na API", "detail": detail}, 500


class MarketAnalyzeController(MethodView):
    """
    GET /market/analyze?id_ativos_base=1&contracts=1

    id_ativos_base define o ativo analisado:
      1 = Mini Índice (WIN)

    contracts define o máximo de contratos — o sistema recalcula a quantidade
    real com base no score e no nível do VIX.

    Requer header Authorization: <SCHEDULER_SECRET>
    """

    def get(self):
        auth_error = check_scheduler_auth()
        if auth_error:
            return auth_error

        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 0))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'id_ativos_base' deve ser um número inteiro"}, 400

        try:
            contracts = int(request.args.get("contracts", 1))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'contracts' deve ser um número inteiro"}, 400

        if contracts < 1:
            return {"error": "Parâmetro 'contracts' deve ser >= 1"}, 400

        analyzer = MarketAnalysisRule.get(id_ativos_base)
        if not analyzer:
            return {
                "error":     f"id_ativos_base={id_ativos_base} não suportado",
                "supported": sorted(MarketAnalysisRule.SUPPORTED),
            }, 400

        data, status = analyzer.analyze(contracts)
        return data, status


class MarketCacheClearController(MethodView):
    """
    DELETE /market/cache?id_ativos_base=1

    Limpa o cache do analyzer especificado, forçando nova chamada na próxima requisição.
    """

    def delete(self):
        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 0))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'id_ativos_base' deve ser um número inteiro"}, 400

        analyzer = MarketAnalysisRule.get(id_ativos_base)
        if not analyzer:
            return {
                "error":     f"id_ativos_base={id_ativos_base} não suportado",
                "supported": sorted(MarketAnalysisRule.SUPPORTED),
            }, 400

        data, status = analyzer.clear_cache()
        return data, status


class MarketDebugController(MethodView):
    """
    GET /market/debug

    Retorna as respostas brutas do Yahoo Finance para diagnóstico.
    """

    def get(self):
        yf = YahooFinanceClient()
        return {
            "yahoo_macro":          yf.get_yahoo_macro_quotes(),
            "yahoo_ibov_technical": yf.get_ibov_technical(),
        }, 200


class MarketAnalysisListController(MethodView):
    """GET /market/analysis — listagem das últimas análises (limit 10)"""

    @jwt_required
    def get(self):
        date_filter = request.args.get("date")

        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 0)) or None
        except (TypeError, ValueError):
            id_ativos_base = None

        return MarketAnalysisListRule.list(
            date_filter=date_filter,
            id_ativos_base=id_ativos_base,
        )


class MarketAnalysisDetailController(MethodView):
    """GET /market/analysis/<id> — detalhe completo; sem id retorna último registro"""

    @jwt_required
    def get(self, id_market_analysis=None):
        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 0)) or None
        except (TypeError, ValueError):
            id_ativos_base = None

        return MarketAnalysisDetailRule.detail(
            id_market_analysis=id_market_analysis,
            id_ativos_base=id_ativos_base,
        )


class IntradayAnalyzeController(MethodView):
    """
    POST /market/intraday?id_ativos_base=1&interval_min=15

    Executa análise intraday do WIN via Claude Haiku 4.5.
    Requer análise fundamentalista do dia já executada.
    Requer header Authorization: <SCHEDULER_SECRET>
    """

    def post(self):
        auth_error = check_scheduler_auth()
        if auth_error:
            return auth_error

        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 1))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'id_ativos_base' deve ser um número inteiro"}, 400

        try:
            interval_min = int(request.args.get("interval_min", 15))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'interval_min' deve ser um número inteiro"}, 400

        if interval_min not in (5, 15, 30):
            return {"error": "Parâmetro 'interval_min' deve ser 5, 15 ou 30"}, 400

        return IntradayAnalysisRule.analyze(
            id_ativos_base=id_ativos_base,
            interval_min=interval_min,
        )


class IntradayAnalysisLatestController(MethodView):
    """GET /market/intraday/latest — último sinal intraday (cache 5min)"""

    def get(self):
        try:
            id_ativos_base = int(request.args.get("id_ativos_base", 0)) or None
        except (TypeError, ValueError):
            id_ativos_base = None

        return IntradayAnalysisLatestRule.latest(id_ativos_base=id_ativos_base)


class IntradayAnalysisListController(MethodView):
    """GET /market/intraday/list?id_market_analysis=X&limit=50&offset=0"""

    def get(self):
        try:
            id_market_analysis = int(request.args.get("id_market_analysis", 0))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'id_market_analysis' é obrigatório e deve ser inteiro"}, 400

        if not id_market_analysis:
            return {"error": "Parâmetro 'id_market_analysis' é obrigatório"}, 400

        try:
            limit  = max(1, min(int(request.args.get("limit",  50)), 200))
            offset = max(0, int(request.args.get("offset", 0)))
        except (TypeError, ValueError):
            limit, offset = 50, 0

        return IntradayAnalysisListRule.list_by_market(id_market_analysis, limit, offset)