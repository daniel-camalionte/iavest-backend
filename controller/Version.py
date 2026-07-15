from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.6.3",
            "data":    "2026-07-14",
            "commit":  "b6cbbf0"
        }, 200
