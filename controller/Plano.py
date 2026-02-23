from flask.views import MethodView
from rule.Plano import PlanoRule
from model.ControllerError import ControllerError

class PlanoListController(MethodView):
    def get(self):
        try:
            rule = PlanoRule()
            data, status = rule.listar()
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
