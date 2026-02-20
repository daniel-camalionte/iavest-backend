from flask.views import MethodView

class TesteController(MethodView):
    def get(self):
        return {"message": "teste pipeline"}, 200
