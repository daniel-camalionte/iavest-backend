from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.Robos import RobosRule
from model.ControllerError import ControllerError

class RobosListController(MethodView):
    @jwt_required
    def get(self):
        try:
            identity = get_jwt_identity()
            id_usuario = identity.get("id_usuario")

            rule = RobosRule()
            data, status = rule.listar(id_usuario)
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
