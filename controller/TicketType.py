from flask.views import MethodView
from flask_jwt_extended import jwt_required
from rule.TicketType import TicketTypeRule
from model.ControllerError import ControllerError

class TicketTypeListController(MethodView):
    @jwt_required
    def get(self):
        try:
            rule = TicketTypeRule()
            data, status = rule.listar()
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
