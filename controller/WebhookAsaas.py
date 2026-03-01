from flask import request
from flask.views import MethodView
from rule.WebhookAsaas import WebhookAsaasRule
import config.env as memory

class WebhookAsaasController(MethodView):
    def post(self):
        try:
            # Validar token do webhook
            token = request.headers.get("asaas-access-token", "")
            if memory.asaas.get("WEBHOOK_TOKEN") and token != memory.asaas["WEBHOOK_TOKEN"]:
                return {"success": False, "message": "Token inválido"}, 403

            get_json = request.get_json(silent=True)

            if not get_json:
                return {"success": True}, 200

            rule = WebhookAsaasRule()
            data, status = rule.processar(get_json)
            return data, status

        except Exception:
            return {"success": True}, 200
