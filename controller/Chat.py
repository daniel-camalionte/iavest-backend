from flask import request
from flask.views import MethodView
from rule.Chat import ChatRule
from model.ControllerError import ControllerError

class ChatController(MethodView):
    def post(self):
        try:
            get_json = request.get_json()

            if not get_json or not isinstance(get_json.get("messages"), list):
                return {"error": "Campo messages é obrigatório e deve ser uma lista"}, 400

            rule = ChatRule()
            data, status = rule.responder(get_json["messages"])
            return data, status

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
