from flask.views import MethodView


class VersionController(MethodView):
    def get(self):
        return {
            "version": "2.0.2",
            "data":    "2026-06-25",
            "commit":  "fc99f1f"
        }, 200
