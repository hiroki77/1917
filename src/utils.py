import os
import json
import yaml
import logging
import subprocess
from pathlib import Path

def load_config(config_path="config.yaml"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    for key in ["output_dir", "temp_dir", "data_dir", "fonts_dir", "logs_dir"]:
        os.makedirs(config["paths"][key], exist_ok=True)
    if config["channel"]["channel_id"] and not config["monitor"]["rss_url"]:
        cid = config["channel"]["channel_id"]
        config["monitor"]["rss_url"] = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    return config

def setup_logging(config):
    log_file = config["logging"]["file"]
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, config["logging"]["level"]),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()])

def run_ffmpeg(args, timeout=600):
    cmd = ["ffmpeg", "-y"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr}")
    return result

def run_ffprobe(args):
    result = subprocess.run(["ffprobe"] + args, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"FFprobe error: {result.stderr}")
    return result.stdout

def get_video_info(video_path):
    return json.loads(run_ffprobe(["-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)]))

def get_video_duration(video_path):
    return float(get_video_info(video_path)["format"]["duration"])

def get_video_resolution(video_path):
    for s in get_video_info(video_path)["streams"]:
        if s["codec_type"] == "video":
            return s["width"], s["height"]
    return 1920, 1080

def seconds_to_ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{int(s):02d}.{int((s - int(s)) * 100):02d}"

def send_termux_notification(title, message):
    try:
        subprocess.run(["termux-notification", "--title", title, "--content", message], timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

def ensure_font_installed(config):
    font_dir = config["paths"]["fonts_dir"]
    if not (list(Path(font_dir).glob("*.ttf")) + list(Path(font_dir).glob("*.otf"))):
        logging.getLogger(__name__).warning(f"fonts/ にけいふぉんと(.ttf/.otf)を配置してください")
        return False
    return True

def save_json(data, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(filepath, default=None):
    if not os.path.exists(filepath):
        return default if default is not None else {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
