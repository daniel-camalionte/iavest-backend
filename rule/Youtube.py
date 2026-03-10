import yt_dlp
import time

_cache = {"data": None, "at": 0}
_TTL = 24 * 3600  # 24 horas

class YoutubeRule():

    CHANNEL_URL = "https://www.youtube.com/@arcmatrixfinanceira"

    def __init__(self):
        pass

    def list_videos(self):
        if _cache["data"] and (time.time() - _cache["at"]) < _TTL:
            return _cache["data"], 200

        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'no_warnings': True,
            'playlistend': 30,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"{self.CHANNEL_URL}/videos", download=False)
            entries = info.get('entries', [])

        videos = []
        for entry in entries:
            videos.append({
                "videoId": entry.get('id', ''),
                "title": entry.get('title', ''),
                "thumbnails": entry.get('thumbnails', []),
                "viewCount": entry.get('view_count', 0),
                "publishedTimeText": entry.get('description', ''),
                "lengthSeconds": entry.get('duration', 0),
            })

        _cache["data"] = videos
        _cache["at"] = time.time()

        return videos, 200
