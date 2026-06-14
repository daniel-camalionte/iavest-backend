from flask import request
from flask.views import MethodView
from rule.AuthGoogle import AuthGoogleRule


class AuthGoogleController(MethodView):
    def post(self):
        data = request.get_json(silent=True) or {}
        return AuthGoogleRule.login(data)
