import re
from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.Usuario import UsuarioRule
from model.ControllerError import ControllerError


def _validar_cpf(cpf):
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    for i, r in enumerate([10, 11]):
        total = sum(int(cpf[j]) * (r - j) for j in range(i + 9))
        digito = (total * 10 % 11) % 10
        if digito != int(cpf[9 + i]):
            return False
    return True


class UsuarioController(MethodView):
    @jwt_required
    def get(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = UsuarioRule()
            data, status = rule.get(id_usuario)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500

    @jwt_required
    def put(self):
        try:
            get_json = request.get_json()

            if not get_json:
                return {"success": False, "message": "Dados inválidos"}, 400

            if not get_json.get("cpf_cnpj"):
                return {"success": False, "message": "Campo cpf_cnpj é obrigatório"}, 400

            cpf = re.sub(r'\D', '', get_json.get("cpf_cnpj", ""))
            if not _validar_cpf(cpf):
                return {"success": False, "message": "CPF inválido"}, 400

            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = UsuarioRule()
            data, status = rule.update(id_usuario, get_json)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
