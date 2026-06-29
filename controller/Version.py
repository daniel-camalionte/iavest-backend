from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.6.0",
            "data":    "2026-06-27",
            "commit":  "e6f2377"
        }, 200
