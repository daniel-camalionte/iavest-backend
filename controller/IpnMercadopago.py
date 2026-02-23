from flask import request
from flask.views import MethodView
from rule.IpnMercadopago import IpnMercadopagoRule

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
            return {"success": True}, 200
