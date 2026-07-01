from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.6.0",
            "data":    "2026-07-01",
            "commit":  "b6cbbf0"
        }, 200
