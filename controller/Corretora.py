from flask.views import MethodView
from rule.Corretora import CorretoraRule
from model.ControllerError import ControllerError

import sentry_sdk

class CorretoraListController(MethodView):
    def get(self):
        try:
            rule = CorretoraRule()
            data, status = rule.listar()
            return data, status

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500
