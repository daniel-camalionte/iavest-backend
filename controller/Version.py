from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.5.0",
            "data":    "2026-06-25",
            "commit":  "e6f2377"
        }, 200
