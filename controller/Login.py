from flask.views import MethodView
from flask_jwt_extended import jwt_required, get_raw_jwt
from blacklist import BLACKLIST
from model.ControllerError import ControllerError

import sentry_sdk

class LogoutController(MethodView):
    @jwt_required
    def post(self):
        try:
            jwt_id = get_raw_jwt()["jti"] # JWT Token Ifentifier
            BLACKLIST.add(jwt_id)
            return {"msg": 'Logout realizado com sucesso!'}, 200

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500