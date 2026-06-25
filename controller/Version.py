from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.1.0",
            "data":    "2026-06-25",
            "commit":  "68bf47d"
        }, 200
