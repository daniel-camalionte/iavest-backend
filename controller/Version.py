from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.6.2",
            "data":    "2026-07-13",
            "commit":  "b6cbbf0"
        }, 200
