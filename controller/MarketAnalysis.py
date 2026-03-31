from flask import request
from flask.views import MethodView

from rule.MarketAnalysis import MarketAnalysisRule
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
    GET /market/analyze?contracts=10

    Retorna a análise do mercado com recomendação de operação.
    O parâmetro `contracts` define o máximo de contratos — o sistema
    recalcula a quantidade real com base no score e no nível do VIX.
    """

    def get(self):
        try:
            contracts = int(request.args.get("contracts", 1))
        except (TypeError, ValueError):
            return {"error": "Parâmetro 'contracts' deve ser um número inteiro"}, 400

        if contracts < 1:
            return {"error": "Parâmetro 'contracts' deve ser >= 1"}, 400

        rule = MarketAnalysisRule()
        data, status = rule.analyze(contracts)
        return data, status


class MarketCacheClearController(MethodView):
    """
    DELETE /market/cache

    Limpa o cache da análise, forçando uma nova chamada na próxima requisição.
    """

    def delete(self):
        rule = MarketAnalysisRule()
        data, status = rule.clear_cache()
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
            "twelve_data_macro": td.debug_raw(),
            "yahoo_ibov_technical": yf.get_ibov_technical(),
        }, 200
