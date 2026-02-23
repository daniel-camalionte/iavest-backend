from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.Auth import AuthRule
from model.ControllerError import ControllerError

import re
class SendCodeController(MethodView):
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json or not get_json.get("email"):
                return {"success": False, "message": "Email inválido"}, 400

            email = get_json.get("email")
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                return {"success": False, "message": "Email inválido"}, 400

            ruleAuth = AuthRule()
            result, status_code = ruleAuth.send_code(get_json)

            return result, status_code

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class VerifyCodeController(MethodView):
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json or not get_json.get("email") or not get_json.get("code"):
                return {"success": False, "message": "Email e código são obrigatórios"}, 400

            email = get_json.get("email")
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                return {"success": False, "message": "Email inválido"}, 400

            code = get_json.get("code")
            if not re.match(r'^\d{6}$', str(code)):
                return {"success": False, "message": "Código deve ter 6 dígitos"}, 400

            ruleAuth = AuthRule()
            result, status_code = ruleAuth.verify_code(get_json)

            return result, status_code

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class CompleteRegistrationController(MethodView):
    @jwt_required
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json:
                return {"success": False, "message": "Dados inválidos"}, 400

            # Validar campos obrigatórios
            required_fields = ["nome", "email", "cpf_cnpj", "ddd", "telefone"]
            for field in required_fields:
                if not get_json.get(field):
                    return {"success": False, "message": f"Campo {field} é obrigatório"}, 400

            email = get_json.get("email")
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                return {"success": False, "message": "Email inválido"}, 400

            identity = get_jwt_identity()
            ruleAuth = AuthRule()
            result, status_code = ruleAuth.complete_registration(get_json, identity)

            return result, status_code

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
