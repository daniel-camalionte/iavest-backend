from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "1.7.2",
            "data":    "2026-06-23",
            "commit":  "4bee280"
        }, 200
