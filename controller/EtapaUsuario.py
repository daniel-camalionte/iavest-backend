from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.EtapaUsuario import EtapaUsuarioRule
from model.ControllerError import ControllerError

import sentry_sdk

class EtapaUsuarioController(MethodView):
    @jwt_required
    def get(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = EtapaUsuarioRule()
            data, status = rule.listar(id_usuario)
            return data, status

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500

    @jwt_required
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json:
                return {"success": False, "message": "Dados obrigatórios não informados"}, 400

            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = EtapaUsuarioRule()
            data, status = rule.registrar(id_usuario, get_json)
            return data, status

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500
