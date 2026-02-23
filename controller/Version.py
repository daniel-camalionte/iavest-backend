from flask.views import MethodView
from datetime import datetime

class VersionController(MethodView):
    def get(self):
        return {
            "version": "1.2",
            "datetime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, 200
