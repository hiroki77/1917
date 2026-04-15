import os
import re
import json
import logging
import subprocess
from src.utils import load_json, save_json

try:
    import feedparser
except ImportError:
    feedparser = None

logger = logging.getLogger(__name__)

class YouTubeChannelMonitor:
    def __init__(self, config):
        self.config = config
        self.channel_id = config["channel"]["channel_id"]
        self.channel_name = config["channel"]["name"]
        self.history_file = os.path.join(config["paths"]["data_dir"], "processed_videos.json")
        self.processed = load_json(self.history_file, default=[])
        if not self.channel_id:
            self.channel_id = self._resolve_channel_id()

    def _resolve_channel_id(self):
        try:
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--print", "channel_id", "--playlist-items", "1", f"ytsearch1:{self.channel_name}"],
                capture_output=True, text=True, timeout=30)
            cid = result.stdout.strip()
            if cid and cid.startswith("UC"):
                return cid
        except Exception:
            pass
        return "UCkEMjbMBUEhmz08tPMSvfvA"

    def check_new_videos(self):
        new_videos = []
        if feedparser:
            new_videos = self._check_via_rss()
        if not new_videos:
            new_videos = self._check_via_ytdlp()
        processed_ids = set(self.processed)
        return [v for v in new_videos if v["id"] not in processed_ids]

    def _check_via_rss(self):
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"
            feed = feedparser.parse(url)
            videos = []
            for entry in feed.entries[:5]:
                vid = getattr(entry, "yt_videoid", "")
                if not vid:
                    m = re.search(r"v=([a-zA-Z0-9_-]{11})", entry.link)
                    vid = m.group(1) if m else ""
                if vid:
                    videos.append({"id": vid, "title": entry.title, "url": f"https://www.youtube.com/watch?v={vid}", "published": entry.get("published", "")})
            return videos
        except Exception:
            return []

    def _check_via_ytdlp(self):
        try:
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s", "--playlist-items", "1-5",
                 f"https://www.youtube.com/channel/{self.channel_id}/videos"],
                capture_output=True, text=True, timeout=60)
            videos = []
            for line in result.stdout.strip().split("\n"):
                if "\t" in line:
                    vid, title = line.split("\t", 1)
                    videos.append({"id": vid, "title": title, "url": f"https://www.youtube.com/watch?v={vid}", "published": ""})
            return videos
        except Exception:
            return []

    def mark_processed(self, video_id):
        if video_id not in self.processed:
            self.processed.append(video_id)
            save_json(self.processed, self.history_file)
