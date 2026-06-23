from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.0.0",
            "data":    "2026-06-23",
            "commit":  "1a0f99d"
        }, 200
