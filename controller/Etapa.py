from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_jwt_identity
from rule.Etapa import EtapaRule
from model.ControllerError import ControllerError

class EtapaListController(MethodView):
    @jwt_required
    def get(self):
        try:
            rule = EtapaRule()
            data, status = rule.listar()
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
