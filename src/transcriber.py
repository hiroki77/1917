import os
import re
import json
import logging
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List
import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None
try:
    import whisper
except ImportError:
    whisper = None
try:
    import easyocr
except ImportError:
    easyocr = None

from src.utils import run_ffmpeg, get_video_resolution, get_video_duration

logger = logging.getLogger(__name__)

@dataclass
class SubtitleEntry:
    start: float
    end: float
    text: str
    speaker: str
    style: str
    confidence: float = 1.0
    def to_dict(self):
        return asdict(self)

class SubtitleRecognizer:
    AYA_HSV_LOWER = np.array([140, 50, 150])
    AYA_HSV_UPPER = np.array([175, 255, 255])
    JUNPEI_HSV_LOWER = np.array([80, 50, 150])
    JUNPEI_HSV_UPPER = np.array([100, 255, 255])

    def __init__(self, config):
        self.config = config
        self.whisper_model_name = config["transcription"]["whisper_model"]
        self.language = config["transcription"]["language"]
        self.frame_interval = config["transcription"]["frame_interval"]
        self.subtitle_region_ratio = config["transcription"]["subtitle_region_ratio"]
        self.temp_dir = config["paths"]["temp_dir"]
        self._whisper_model = None
        self._ocr_reader = None

    def _get_whisper(self):
        if self._whisper_model is None:
            self._whisper_model = whisper.load_model(self.whisper_model_name)
        return self._whisper_model

    def _get_ocr(self):
        if self._ocr_reader is None:
            self._ocr_reader = easyocr.Reader(["ja", "en"], gpu=False)
        return self._ocr_reader

    def recognize(self, video_path):
        whisper_segs = self._run_whisper(video_path)
        ocr_segs = self._run_ocr_pipeline(video_path)
        merged = self._merge(whisper_segs, ocr_segs)
        return self._clean(merged)

    def _run_whisper(self, video_path):
        audio = os.path.join(self.temp_dir, "audio.wav")
        run_ffmpeg(["-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio])
        try:
            result = self._get_whisper().transcribe(audio, language=self.language, word_timestamps=True, verbose=False)
            segs = []
            for s in result.get("segments", []):
                t = s["text"].strip()
                if t:
                    segs.append(SubtitleEntry(start=s["start"], end=s["end"], text=t, speaker="unknown", style="normal"))
            return segs
        finally:
            if os.path.exists(audio):
                os.remove(audio)

    def _run_ocr_pipeline(self, video_path):
        if cv2 is None:
            return []
        w, h = get_video_resolution(video_path)
        sub_y = int(h * (1 - self.subtitle_region_ratio))
        frames_dir = os.path.join(self.temp_dir, "frames")
        os.makedirs(frames_dir, exist_ok=True)
        try:
            fps = 1.0 / self.frame_interval
            run_ffmpeg(["-i", str(video_path), "-vf", f"fps={fps},crop=iw:{h-sub_y}:0:{sub_y}", "-q:v", "2", os.path.join(frames_dir, "f_%06d.jpg")], timeout=1200)
            reader = self._get_ocr()
            raw = []
            for i, fp in enumerate(sorted(Path(frames_dir).glob("f_*.jpg"))):
                ts = i * self.frame_interval
                frame = cv2.imread(str(fp))
                if frame is None:
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                bright = np.sum(gray > 180) / gray.size
                if not (0.01 < bright < 0.40):
                    raw.append((ts, "", "unknown", "normal"))
                    continue
                ocr_res = reader.readtext(str(fp), detail=1, paragraph=True)
                if not ocr_res:
                    raw.append((ts, "", "unknown", "normal"))
                    continue
                text = "".join(d[1] for d in ocr_res if len(d) >= 2).strip()
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                pink = np.sum(cv2.inRange(hsv, self.AYA_HSV_LOWER, self.AYA_HSV_UPPER) > 0)
                cyan = np.sum(cv2.inRange(hsv, self.JUNPEI_HSV_LOWER, self.JUNPEI_HSV_UPPER) > 0)
                speaker = "aya" if pink > cyan and pink > 100 else ("junpei" if cyan > 100 else "unknown")
                style = "normal"
                raw.append((ts, text, speaker, style))
            return self._group(raw)
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)

    def _group(self, raw):
        entries = []
        cur_text, cur_spk, cur_sty, start, end = "", "unknown", "normal", 0.0, 0.0
        for ts, text, spk, sty in raw:
            if text == cur_text and text:
                end = ts + self.frame_interval
            else:
                if cur_text:
                    entries.append(SubtitleEntry(start=start, end=end, text=cur_text, speaker=cur_spk, style=cur_sty, confidence=0.9))
                cur_text, cur_spk, cur_sty, start, end = text, spk, sty, ts, ts + self.frame_interval
        if cur_text:
            entries.append(SubtitleEntry(start=start, end=end, text=cur_text, speaker=cur_spk, style=cur_sty, confidence=0.9))
        return entries

    def _merge(self, whisper_segs, ocr_segs):
        if not ocr_segs:
            return whisper_segs
        if not whisper_segs:
            return ocr_segs
        merged = []
        for o in ocr_segs:
            merged.append(o)
        return merged

    def _clean(self, entries):
        cleaned = []
        for e in entries:
            if not e.text.strip():
                continue
            e.text = re.sub(r'\s+', ' ', e.text).strip()
            if e.end - e.start < 0.3:
                continue
            cleaned.append(e)
        cleaned.sort(key=lambda x: x.start)
        dedup = []
        for e in cleaned:
            if dedup and dedup[-1].text == e.text and abs(dedup[-1].start - e.start) < 0.5:
                if (e.end - e.start) > (dedup[-1].end - dedup[-1].start):
                    dedup[-1] = e
                continue
            dedup.append(e)
        return dedup
