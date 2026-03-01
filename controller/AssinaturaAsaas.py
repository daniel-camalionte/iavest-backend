from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.AssinaturaAsaas import AssinaturaAsaasRule
from model.ControllerError import ControllerError

class AssinaturaAsaasCriarController(MethodView):
    @jwt_required
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json or not get_json.get("plano_id"):
                return {"success": False, "message": "Campo plano_id é obrigatório"}, 400

            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            remote_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()

            rule = AssinaturaAsaasRule()
            data, status = rule.criar(id_usuario, get_json, remote_ip)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class AssinaturaAsaasInvoiceController(MethodView):
    @jwt_required
    def get(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = AssinaturaAsaasRule()
            data, status = rule.invoice(id_usuario)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class AssinaturaAsaasCancelarController(MethodView):
    @jwt_required
    def post(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = AssinaturaAsaasRule()
            data, status = rule.cancelar(id_usuario)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
