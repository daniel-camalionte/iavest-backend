from flask.views import MethodView
from rule.Etapa import EtapaRule
from model.ControllerError import ControllerError

import sentry_sdk

class EtapaListController(MethodView):
    def get(self):
        try:
            rule = EtapaRule()
            data, status = rule.listar()
            return data, status

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500
