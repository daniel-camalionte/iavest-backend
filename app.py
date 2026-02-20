import os
from dotenv import load_dotenv

env = os.environ.get("FLASK_ENV", "stg")
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".env.{env}")
load_dotenv(env_file)

from flask import Flask, jsonify, request
from flask_restful import Api
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from flask_swagger_ui import get_swaggerui_blueprint
from blacklist import BLACKLIST

import appController
import config.env as memory

try:
    import sentry_sdk
    sentry_sdk.init(
        dsn=memory.sentry["DSN"],
        traces_sample_rate=1.0,
        send_default_pii=True
    )
except Exception:
    pass

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["JWT_SECRET_KEY"] = memory.jwt["JWT_SECRET_KEY"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = memory.jwt["JWT_ACCESS_TOKEN_EXPIRES"]
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

#Version
api.add_resource(appController.VersionController, '/version')

#Login
api.add_resource(appController.LogoutController, '/logout')

#Auth
api.add_resource(appController.SendCodeController, '/auth/send-code')
api.add_resource(appController.VerifyCodeController, '/auth/verify-code')
api.add_resource(appController.CompleteRegistrationController, '/auth/complete-registration')

#Metatrader Login
api.add_resource(appController.MetatraderLoginController, '/metatrader/login')

#Metatrader Trade Start
api.add_resource(appController.MetatraderTradeStartController, '/metatrader/trade/start')

#Metatrader Trade Exit
api.add_resource(appController.MetatraderTradeExitController, '/metatrader/trade/exit')



#YouTube
api.add_resource(appController.VideosListController, '/trpc/videos.list')

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

#Webhook
api.add_resource(appController.WebhookMercadoPagoController, '/webhook/mercadopago')
api.add_resource(appController.WebhookMercadoPagoReprocessController, '/webhook/mercadopago/reprocess')

#IPN
api.add_resource(appController.IpnMercadoPagoController, '/ipn/mercadopago')

#touch ~/apps_wsgi/stg.wsgi


if __name__ == '__main__':
    app.run(debug=True)