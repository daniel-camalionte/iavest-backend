from flask import request
from flask.views import MethodView
from rule.Youtube import YoutubeRule
from model.ControllerError import ControllerError

import sentry_sdk

class VideosListController(MethodView):
    def post(self):
        try:
            ruleYoutube = YoutubeRule()
            videos, status_code = ruleYoutube.list_videos()

            return [{"result": {"data": {"json": videos}}}], status_code

        except Exception as e:
            sentry_sdk.capture_exception(e)
            msg = ControllerError().default(e)
            return msg, 500
