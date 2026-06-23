from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "1.7.1",
            "data":    "2026-06-23",
            "commit":  "6805b60"
        }, 200
