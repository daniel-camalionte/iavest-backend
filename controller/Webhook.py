from flask import request
from flask.views import MethodView
from rule.Webhook import WebhookRule
from model.ControllerError import ControllerError
import config.env as memory

import sentry_sdk
import hmac
import hashlib

class WebhookMercadoPagoController(MethodView):
    def post(self):
        get_json = None
        try:
            # Validar assinatura do MercadoPago
            webhook_secret = memory.mercadopago.get("WEBHOOK_SECRET", "")
            if webhook_secret and not self._validar_assinatura(webhook_secret):
                return {"success": False, "message": "Assinatura inválida"}, 403

            get_json = request.get_json(silent=True)

            if not get_json:
                return {"success": True}, 200

            rule = WebhookRule()
            data, status = rule.mercadopago(get_json)
            return data, status

        except Exception as e:
            sentry_sdk.set_context("request", {"payload": get_json})
            sentry_sdk.capture_exception(e)
            return {"success": True}, 200

    def _validar_assinatura(self, secret):
        x_signature = request.headers.get("x-signature", "")
        x_request_id = request.headers.get("x-request-id", "")

        if not x_signature:
            return False

        # Extrair ts e v1 do header: "ts=123456,v1=abcdef..."
        parts = {}
        for part in x_signature.split(","):
            kv = part.split("=", 1)
            if len(kv) == 2:
                parts[kv[0].strip()] = kv[1].strip()

        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")

        if not ts or not v1:
            return False

        # Montar o template conforme documentação do MercadoPago
        # id vem da query string: ?data.id=XXX
        data_id = request.args.get("data.id", "")

        manifest = "id:{data_id};request-id:{request_id};ts:{ts};".format(
            data_id=data_id,
            request_id=x_request_id,
            ts=ts
        )

        # Gerar HMAC-SHA256
        computed = hmac.new(
            secret.encode("utf-8"),
            manifest.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(computed, v1)

class WebhookMercadoPagoReprocessController(MethodView):
    def post(self):
        try:
            get_json = request.get_json(silent=True)

            if not get_json or not get_json.get("id_webhook"):
                return {"success": False, "message": "id_webhook é obrigatório"}, 400

            rule = WebhookRule()
            data, status = rule.reprocessar(get_json["id_webhook"])
            return data, status

        except Exception as e:
            sentry_sdk.capture_exception(e)
            return {"success": False, "message": str(e)}, 500
