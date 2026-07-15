import os
import time
from dotenv import load_dotenv

env = os.environ.get("FLASK_ENV", "prd")
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".env.{env}")
load_dotenv(env_file)

from flask import Flask, jsonify, request, g
from flask_restful import Api
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from datetime import timedelta
from flask_swagger_ui import get_swaggerui_blueprint
from blacklist import BLACKLIST

import appController
import config.env as memory
from library import Loki


app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["JWT_SECRET_KEY"] = memory.jwt["JWT_SECRET_KEY"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=memory.jwt["JWT_ACCESS_TOKEN_EXPIRES"])
app.config["JWT_BLACKLIST_ENABLED"] = True

jwt = JWTManager(app)  

@jwt.token_in_blacklist_loader
def verifica_blacklist(token):
    return token['jti'] in BLACKLIST

@jwt.revoked_token_loader
def token_de_acesso_invalidado():
    return jsonify({"msg": 'Token expirado!'}), 401

@jwt.invalid_token_loader
def token_invalido(callback):
    return jsonify({"msg": 'Token inválido ou ausente. Verifique o cabeçalho Authorization.'}), 401

### swagger config ###
SWAGGER_URL = '/swagger'
API_URL = memory.utilits["HOST"]+'/static/swagger.json'
SWAGGERUI_BLUEPRINT = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        "app_name": 'Seans-Python-Flask-REST-Boilerplate'
    }
)

app.register_blueprint(SWAGGERUI_BLUEPRINT, url_prefix=SWAGGER_URL)

api = Api(app)

CORS(app, resources={
    r"/chat": {
        "origins": ["https://www.iavest.com.br", "https://iavest.com.br"]
    }
})

# ── Monitoramento (Loki) ─────────────────────────────────────────────
# Loga no Grafana Cloud as requests das rotas de cron/analise: saber se a
# cron esta batendo, tempo de resposta e status. Fire-and-forget: nunca
# afeta a request.
_ROTAS_MONITORADAS = ("/claude-trader/", "/market/intraday", "/market/analyze")


@app.before_request
def _monitor_inicia():
    g._monitor_t0 = time.time()


@app.after_request
def _monitor_loga(resp):
    try:
        rota = request.path
        if any(rota.startswith(p) for p in _ROTAS_MONITORADAS):
            ms = int((time.time() - getattr(g, "_monitor_t0", time.time())) * 1000)
            rota_label = request.url_rule.rule if request.url_rule else rota
            account = request.args.get("account_number") or request.args.get("account") or ""
            Loki.log(
                f"{request.method} {rota}",
                nivel="info" if resp.status_code < 400 else "erro",
                rota=rota_label,
                status=resp.status_code,
                ms=ms,
                account=account,
            )
    except Exception:
        pass  # monitoramento nunca quebra a request
    return resp
# ─────────────────────────────────────────────────────────────────────

#Version
api.add_resource(appController.VersionController, '/version')
#Login
api.add_resource(appController.LogoutController, '/logout')

#Auth
api.add_resource(appController.SendCodeController, '/auth/send-code')
api.add_resource(appController.VerifyCodeController, '/auth/verify-code')
api.add_resource(appController.CompleteRegistrationController, '/auth/complete-registration')
api.add_resource(appController.AuthGoogleController, '/auth/google')

#Metatrader Login
api.add_resource(appController.MetatraderLoginController, '/metatrader/login')

#Metatrader Trade Start
api.add_resource(appController.MetatraderTradeStartController, '/metatrader/trade/start')

#Metatrader Trade Exit
api.add_resource(appController.MetatraderTradeExitController, '/metatrader/trade/exit')



#YouTube
api.add_resource(appController.VideosListController, '/trpc/videos.list')
api.add_resource(appController.VideosCacheClearController, '/trpc/videos.cache/clear')

#Planos
api.add_resource(appController.PlanoListController, '/planos')

#Corretoras
api.add_resource(appController.CorretoraListController, '/corretoras')

#Assinatura
api.add_resource(appController.AssinaturaStatusController, '/assinatura/status')
api.add_resource(appController.AssinaturaCriarController, '/assinatura/criar')
api.add_resource(appController.AssinaturaCancelarController, '/assinatura/cancelar')

#Contas MT5
api.add_resource(appController.ContaMt5ListController, '/contas-mt5')
api.add_resource(appController.ContaMt5DetailController, '/contas-mt5/<int:id>')

#Robos
api.add_resource(appController.RobosListController, '/robos')

#Etapas
api.add_resource(appController.EtapaListController, '/etapa')
api.add_resource(appController.EtapaUsuarioController, '/etapa/usuario')

#Ticket
api.add_resource(appController.TicketTypeListController, '/ticket/types')
api.add_resource(appController.TicketListController, '/tickets')
api.add_resource(appController.TicketCreateController, '/ticket')

#Usuario
api.add_resource(appController.UsuarioController, '/usuario')

#Assinatura Asaas
api.add_resource(appController.AssinaturaAsaasCriarController, '/assinatura/asaas/criar')
api.add_resource(appController.AssinaturaAsaasCancelarController, '/assinatura/asaas/cancelar')
api.add_resource(appController.AssinaturaAsaasInvoiceController, '/assinatura/asaas/invoice')

#Webhook
api.add_resource(appController.WebhookMercadoPagoController, '/webhook/mercadopago')
api.add_resource(appController.WebhookMercadoPagoReprocessController, '/webhook/mercadopago/reprocess')
api.add_resource(appController.WebhookAsaasController, '/webhook/asaas')

#IPN
api.add_resource(appController.IpnMercadoPagoController, '/ipn/mercadopago')

#Chat IA
api.add_resource(appController.ChatController, '/chat')

#Termo Aceite
api.add_resource(appController.TermoAceiteController, '/termo-aceite')

#FAQ
api.add_resource(appController.FaqListController, '/faq')
api.add_resource(appController.FaqCacheClearController, '/faq/cache')

#Performance Landing Page
api.add_resource(appController.TradePerformanceMensalController, '/performance/mensal')
api.add_resource(appController.TradePerformanceCacheClearController, '/performance/cache')

#Performance Dashboard (JWT)
api.add_resource(appController.PerformanceDashboardController, '/performance/dashboard')
api.add_resource(appController.PerformanceTradesController, '/performance/trades')
api.add_resource(appController.TradeCandlesController, '/performance/trade-candles')

#Market Analysis
api.add_resource(appController.MarketAnalysisPingController, '/market/ping')
api.add_resource(appController.MarketAnalyzeController, '/market/analyze')
api.add_resource(appController.MarketCacheClearController, '/market/cache')
api.add_resource(appController.MarketDebugController, '/market/debug')
api.add_resource(appController.MarketAnalysisListController, '/market/analysis')
api.add_resource(appController.MarketAnalysisDetailController, '/market/analysis/<int:id_market_analysis>', '/market/analysis/latest')
api.add_resource(appController.MarketPriceController, '/market/price')

#Intraday Analysis
api.add_resource(appController.IntradayAnalyzeController, '/market/intraday')
api.add_resource(appController.IntradayResolvePendingController, '/market/intraday/resolve')
api.add_resource(appController.IntradayHealthController, '/market/intraday/health')
api.add_resource(appController.IntradayAnalysisLatestController, '/market/intraday/latest')
api.add_resource(appController.IntradayAnalysisListController, '/market/intraday/list')
api.add_resource(appController.IntradayResumoController, '/market/intraday/resumo')

#Simulador de Ordens
api.add_resource(appController.SimuladorOrdemListaController, '/simulador/ordem')
api.add_resource(appController.SimuladorOrdemItemController, '/simulador/ordem/<int:id_ordem>')
api.add_resource(appController.SimuladorOrdemEncerrarController, '/simulador/ordem/<int:id_ordem>/encerrar')
api.add_resource(appController.SimuladorAnaliseIaController, '/simulador/ordem/<int:id_ordem>/analise-ia')

#Claude Trader (execução intraday profissional)
api.add_resource(appController.ClaudeTraderEqualizarController, '/claude-trader/equalizar')

#Claude Trader — fila de análise (inteligência nova insere ordens propostas; sem JWT, senha própria)
api.add_resource(appController.ClaudeTraderOperacaoAnaliseController, '/claude-trader/operacao-analise')

#Claude Trader — analisador da fila (schedule: Haiku aprova/reprova + replica; SCHEDULER_SECRET)
api.add_resource(appController.ClaudeTraderOperacaoAnaliseProcessarController, '/claude-trader/operacao-analise/processar')

#touch ~/apps_wsgi/stg.wsgi


if __name__ == '__main__':
    app.run(debug=True)