from flask import request
from flask.views import MethodView
from rule.Youtube import YoutubeRule
from model.ControllerError import ControllerError
import rule.Youtube as youtube_rule

class VideosListController(MethodView):
    def post(self):
        try:
            ruleYoutube = YoutubeRule()
            videos, status_code = ruleYoutube.list_videos()

            return [{"result": {"data": {"json": videos}}}], status_code

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500


class VideosCacheClearController(MethodView):
    def post(self):
        try:
            youtube_rule._cache["data"] = None
            youtube_rule._cache["at"] = 0
            return {"success": True, "message": "Cache limpo com sucesso"}, 200

        except Exception as e:
            msg = ControllerError().default(e)
            return msg, 500
