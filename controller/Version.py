from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.0.1",
            "data":    "2026-06-23",
            "commit":  "c82620a"
        }, 200
