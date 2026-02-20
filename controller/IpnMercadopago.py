from flask import request
from flask.views import MethodView
from rule.IpnMercadopago import IpnMercadopagoRule

import sentry_sdk

class IpnMercadoPagoController(MethodView):
    def post(self):
        try:
            topic = request.args.get("topic", "")
            resource_id = request.args.get("id", "")

            if not topic or not resource_id:
                return {"success": True}, 200

            rule = IpnMercadopagoRule()
            data, status = rule.processar(topic, resource_id)
            return data, status

        except Exception as e:
            sentry_sdk.set_context("request", {
                "topic": request.args.get("topic", ""),
                "resource_id": request.args.get("id", "")
            })
            sentry_sdk.capture_exception(e)
            return {"success": True}, 200
