import yt_dlp

class YoutubeRule():

    CHANNEL_URL = "https://www.youtube.com/@arcmatrixfinanceira"

    def __init__(self):
        pass

    def list_videos(self):
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

        return videos, 200
