import requests
import re
import xml.etree.ElementTree as ET
import time

_cache = {"data": None, "at": 0, "channel_id": None}
_TTL = 24 * 3600

# ID fixo do canal @arcmatrixfinanceira — confirmado via youtube.com/channel/UCona5HYxc4la5iGi_45iHaA
_CHANNEL_ID_FALLBACK = "UCona5HYxc4la5iGi_45iHaA"


class YoutubeRule():

    CHANNEL_HANDLE = "@arcmatrixfinanceira"

    def _get_channel_id(self):
        if _cache["channel_id"]:
            return _cache["channel_id"]

        if _CHANNEL_ID_FALLBACK:
            _cache["channel_id"] = _CHANNEL_ID_FALLBACK
            return _cache["channel_id"]

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            resp = requests.get(f"https://www.youtube.com/{self.CHANNEL_HANDLE}", headers=headers, timeout=10)

            for pattern in [r'"channelId":"(UC[^"]+)"', r'"externalId":"(UC[^"]+)"', r'"browseId":"(UC[^"]+)"']:
                match = re.search(pattern, resp.text)
                if match:
                    _cache["channel_id"] = match.group(1)
                    return _cache["channel_id"]
        except Exception:
            pass

        raise Exception("Não foi possível obter o channel_id do YouTube. Configure _CHANNEL_ID_FALLBACK em rule/Youtube.py")

    def list_videos(self):
        if _cache["data"] and (time.time() - _cache["at"]) < _TTL:
            return _cache["data"], 200

        channel_id = self._get_channel_id()

        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404:
            return [], 200
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'media': 'http://search.yahoo.com/mrss/',
            'yt': 'http://www.youtube.com/xml/schemas/2015'
        }

        videos = []
        for entry in root.findall('atom:entry', ns):
            yt_id = entry.find('yt:videoId', ns)
            title = entry.find('atom:title', ns)
            published = entry.find('atom:published', ns)
            group = entry.find('media:group', ns)
            thumbnail = group.find('media:thumbnail', ns) if group is not None else None
            community = group.find('media:community', ns) if group is not None else None
            stats = community.find('media:statistics', ns) if community is not None else None

            videos.append({
                "videoId": yt_id.text if yt_id is not None else '',
                "title": title.text if title is not None else '',
                "thumbnails": [{"url": thumbnail.get('url', ''), "width": int(thumbnail.get('width', 0)), "height": int(thumbnail.get('height', 0))}] if thumbnail is not None else [],
                "viewCount": int(stats.get('views', 0)) if stats is not None else 0,
                "publishedTimeText": published.text if published is not None else '',
                "lengthSeconds": 0,
            })

        _cache["data"] = videos
        _cache["at"] = time.time()

        return videos, 200
