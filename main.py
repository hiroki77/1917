#!/usr/bin/env python3
import os, sys, time, argparse, logging, schedule
from src.utils import load_config, setup_logging, send_termux_notification, ensure_font_installed
from src.monitor import YouTubeChannelMonitor
from src.downloader import VideoDownloader
from src.transcriber import SubtitleRecognizer
from src.segmenter import TopicSegmenter
from src.processor import VideoProcessor
from src.insights import InsightsEngine

def process(monitor, dl, tr, seg, proc, ins):
    logger = logging.getLogger(__name__)
    try:
        for video in monitor.check_new_videos():
            logger.info(f"Processing: {video['title']}")
            send_termux_notification("新着動画", video["title"])
            vp = None
            try:
                vp = dl.download(video["url"])
                subs = tr.recognize(vp)
                clips = seg.select_clips(subs, vp, ins.get_preferences())
                for i, clip in enumerate(clips[:3]):
                    out = proc.create_clip(vp, clip, subs, i+1)
                    ins.record_clip({"duration": clip.duration, "score": clip.score, "topic": clip.topic_summary})
                    logger.info(f"Clip {i+1}: {out}")
                monitor.mark_processed(video["id"])
                send_termux_notification("完了", f"{video['title']} - 3本作成")
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
            finally:
                if vp: dl.cleanup(vp)
    except Exception as e:
        logger.error(f"Monitor error: {e}", exc_info=True)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--once", action="store_true")
    p.add_argument("--insights", type=str)
    args = p.parse_args()
    config = load_config(args.config)
    setup_logging(config)
    ensure_font_installed(config)
    mon = YouTubeChannelMonitor(config)
    dl = VideoDownloader(config)
    tr = SubtitleRecognizer(config)
    seg = TopicSegmenter(config)
    proc = VideoProcessor(config)
    ins = InsightsEngine(config)
    if args.insights:
        import json
        with open(args.insights, "r", encoding="utf-8") as f:
            ins.update_insights(json.load(f))
    if args.once:
        process(mon, dl, tr, seg, proc, ins)
    else:
        iv = config["monitor"]["check_interval"]
        run = lambda: process(mon, dl, tr, seg, proc, ins)
        schedule.every(iv).seconds.do(run)
        run()
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()
