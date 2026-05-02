import os
import logging
from datetime import datetime
from src.utils import run_ffmpeg, get_video_resolution, seconds_to_ass_time, send_termux_notification

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, config):
        self.zoom = config["video"]["zoom_factor"]
        self.crf = config["video"]["crf"]
        self.codec = config["video"]["codec"]
        self.output_dir = config["paths"]["output_dir"]
        self.temp_dir = config["paths"]["temp_dir"]
        self.sub_cfg = config["subtitles"]
        os.makedirs(self.output_dir, exist_ok=True)

    def create_clip(self, video_path, clip, subtitles, index):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(self.output_dir, f"clip_{ts}_{index}.mp4")
        seg = os.path.join(self.temp_dir, f"seg_{index}.mp4")
        zoomed = os.path.join(self.temp_dir, f"zoom_{index}.mp4")
        ass = os.path.join(self.temp_dir, f"sub_{index}.ass")
        try:
            w, h = get_video_resolution(video_path)
            run_ffmpeg(["-ss", str(clip.start), "-i", str(video_path), "-t", str(clip.duration), "-c", "copy", "-avoid_negative_ts", "make_zero", seg])
            zw, zh = int(w * self.zoom), int(h * self.zoom)
            cx, cy = (zw - w) // 2, zh - h
            run_ffmpeg(["-i", seg, "-vf", f"scale={zw}:{zh},crop={w}:{h}:{cx}:{cy}", "-c:v", self.codec, "-crf", str(self.crf), "-c:a", "aac", zoomed], timeout=300)
            clip_subs = [s for s in subtitles if s.start >= clip.start and s.end <= clip.end]
            self._write_ass(clip_subs, clip.start, ass, w, h)
            fonts_dir = os.path.join(os.path.dirname(self.output_dir), "fonts")
            vf = f"ass={ass}:fontsdir={fonts_dir}" if os.path.isdir(fonts_dir) and os.listdir(fonts_dir) else f"ass={ass}"
            run_ffmpeg(["-i", zoomed, "-vf", vf, "-c:v", self.codec, "-crf", str(self.crf), "-c:a", "copy", out], timeout=300)
            return out
        finally:
            for p in [seg, zoomed, ass]:
                if os.path.exists(p):
                    os.remove(p)

    def _write_ass(self, subs, clip_start, path, w, h):
        font = self.sub_cfg["font_name"]
        ns, es = self.sub_cfg["normal_font_size"], self.sub_cfg["emphasis_font_size"]
        sw, mv = self.sub_cfg["stroke_width"], self.sub_cfg["margin_v"]
        ac, jc, sc = self._rgb2ass(self.sub_cfg["aya_color"]), self._rgb2ass(self.sub_cfg["junpei_color"]), self._rgb2ass(self.sub_cfg["stroke_color"])
        header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nScaledBorderAndShadow: yes\n\n"
                  f"[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
                  f"Style: AyaNormal,{font},{ns},{ac},&H000000FF,{sc},&H80000000,-1,0,0,0,100,100,0,0,1,{sw},0,2,10,10,{mv},1\n"
                  f"Style: AyaEmphasis,{font},{es},{ac},&H000000FF,{sc},&H80000000,-1,0,0,0,100,100,0,0,1,{sw+1},0,2,10,10,{mv},1\n"
                  f"Style: JunpeiNormal,{font},{ns},{jc},&H000000FF,{sc},&H80000000,-1,0,0,0,100,100,0,0,1,{sw},0,2,10,10,{mv},1\n"
                  f"Style: JunpeiEmphasis,{font},{es},{jc},&H000000FF,{sc},&H80000000,-1,0,0,0,100,100,0,0,1,{sw+1},0,2,10,10,{mv},1\n\n"
                  f"[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        lines = []
        for s in subs:
            t0 = seconds_to_ass_time(max(0, s.start - clip_start))
            t1 = seconds_to_ass_time(s.end - clip_start)
            style = ("Aya" if s.speaker == "aya" else "Junpei" if s.speaker == "junpei" else "Aya") + ("Emphasis" if s.style == "emphasis" else "Normal")
            lines.append(f"Dialogue: 0,{t0},{t1},{style},,0,0,0,,{s.text}")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(header + "\n".join(lines) + "\n")

    @staticmethod
    def _rgb2ass(hex_rgb):
        hex_rgb = hex_rgb.lstrip("#")
        r, g, b = int(hex_rgb[0:2], 16), int(hex_rgb[2:4], 16), int(hex_rgb[4:6], 16)
        return f"&H00{b:02X}{g:02X}{r:02X}"
