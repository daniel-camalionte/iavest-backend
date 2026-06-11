from library.base.BaseModel import BaseModel


class YoutubeCacheModel(BaseModel):

    def __init__(self):
        super().__init__()

    def table(self):
        return 'youtube_cache'

    def pk(self):
        return 'channel_id'

    def fields(self):
        return {
            "channel_id": "channel_id",
            "videos":     "videos",
            "updated_at": "updated_at",
        }
