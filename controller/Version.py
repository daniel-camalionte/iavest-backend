from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.6.4",
            "data":    "2026-07-22",
            "commit":  "b6cbbf0"
        }, 200
