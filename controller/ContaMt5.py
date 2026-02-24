from flask import request
from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.ContaMt5 import ContaMt5Rule
from model.ControllerError import ControllerError

class ContaMt5ListController(MethodView):
    @jwt_required
    def get(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            filtros = {
                "account": request.args.get("account"),
                "account_number": request.args.get("account_number"),
                "page": request.args.get("page", 1, type=int)
            }

            rule = ContaMt5Rule()
            data, status = rule.listar(id_usuario, filtros)
            return data, status

        except Exception as e:
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

            rule = ContaMt5Rule()
            data, status = rule.criar(id_usuario, get_json)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class ContaMt5DetailController(MethodView):
    @jwt_required
    def put(self, id):
        try:
            get_json = request.get_json()

            if not get_json:
                return {"success": False, "message": "Dados não informados"}, 400

            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = ContaMt5Rule()
            data, status = rule.atualizar(id_usuario, id, get_json)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500

    @jwt_required
    def delete(self, id):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = ContaMt5Rule()
            data, status = rule.deletar(id_usuario, id)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
