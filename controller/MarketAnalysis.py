from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required

from rule.MarketAnalysis import MarketAnalysisRule, MarketAnalysisListRule, MarketAnalysisDetailRule
from library.TwelveDataClient import TwelveDataClient
from library.YahooFinanceClient import YahooFinanceClient
from library.HttpClient import HttpClient
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
    """

    def get(self):
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

    Retorna as respostas brutas de ambas as fontes de dados para diagnóstico:
    - Twelve Data (macro US)
    - Yahoo Finance (técnicos Ibovespa)
    """

    def get(self):
        td = TwelveDataClient(memory.twelvedata["API_KEY"])
        yf = YahooFinanceClient()
        return {
            "twelve_data_macro":     td.debug_raw(),
            "yahoo_ibov_technical":  yf.get_ibov_technical(),
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