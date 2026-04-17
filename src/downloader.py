import os
import re
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoDownloader:
    def __init__(self, config):
        self.temp_dir = config["paths"]["temp_dir"]
        self.quality = config["download"]["quality"]
        os.makedirs(self.temp_dir, exist_ok=True)

    def download(self, video_url):
        output_template = os.path.join(self.temp_dir, "%(id)s.%(ext)s")
        cmd = ["yt-dlp", "-f", self.quality, "--merge-output-format", "mp4", "-o", output_template, "--no-playlist", video_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(f"Download failed: {result.stderr}")
        match = re.search(r"v=([a-zA-Z0-9_-]{11})", video_url)
        if match:
            path = os.path.join(self.temp_dir, f"{match.group(1)}.mp4")
            if os.path.exists(path):
                return path
        mp4s = sorted(Path(self.temp_dir).glob("*.mp4"), key=os.path.getmtime, reverse=True)
        if mp4s:
            return str(mp4s[0])
        raise FileNotFoundError("Downloaded file not found")

    def cleanup(self, video_path):
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except OSError:
            pass
