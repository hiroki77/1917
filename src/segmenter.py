import os
import re
import json
import time
import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    genai = None
    gtypes = None

@dataclass
class ClipSegment:
    start: float
    end: float
    subtitles: list
    score: float = 0.0
    topic_summary: str = ""
    reason: str = ""
    @property
    def duration(self):
        return self.end - self.start

class TopicSegmenter:
    TOPIC_BREAK_WORDS = ["で", "でさ", "というわけで", "次", "じゃあ", "ところで", "ちなみに", "あと", "それで", "最後に"]
    VIRAL_WORDS = ["やばい", "マジ", "笑", "可愛い", "無理", "神", "最高", "おもろい", "怖い", "泣く", "エモい"]

    def __init__(self, config):
        self.min_dur = config["clips"]["min_duration"]
        self.max_dur = config["clips"]["max_duration"]
        self.clip_count = config["clips"]["count"]
        tc = config["transcription"]
        self._gemini = None
        self._model = tc.get("gemini_model", "gemini-2.0-flash")
        gkey = tc.get("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")
        if gkey and genai:
            self._gemini = genai.Client(api_key=gkey)

    def select_clips(self, subtitles, video_path, preferences=None):
        if not subtitles:
            return []
        if self._gemini:
            clips = self._select_gemini(subtitles, preferences)
            if clips:
                return clips
            logger.warning("Gemini失敗、ルールベースにフォールバック")
        return self._select_rules(subtitles, preferences)

    def _select_gemini(self, subtitles, preferences=None):
        lines = []
        for s in subtitles:
            sp = {"aya": "綾", "junpei": "純平"}.get(s.speaker, "?")
            lines.append(f"[{s.start:.1f}-{s.end:.1f}] {sp}: {s.text}")
        transcript = "\n".join(lines)
        boost = ""
        if preferences:
            kws = preferences.get("boost_keywords", [])
            if kws: boost += f"\n過去バズキーワード: {", ".join(kws)}"
            pd = preferences.get("preferred_duration", 0)
            if pd: boost += f"\n過去バズ平均時間: {pd}秒"
        prompt = (
            "以下は中町兄妹(YouTube)の動画の全字幕です。"
            f"\n\n{transcript}\n\n"
            f"この動画から切り抜き動画を3本作ります。\n"
            f"【必須】\n"
            f"- {self.min_dur}秒以上{self.max_dur}秒以内\n"
            "- 話の導入→展開→オチまで綺麗に収まること\n"
            "- 話の途中で切れないこと\n"
            "- 3クリップは重複しない\n"
            "【優先】\n"
            "- 兄妹の掛け合いが面白い部分\n"
            "- リアクションが大きい(笑い、驚き、ツッコミ)\n"
            "- バズりやすいキャッチーな話題\n"
            f"{boost}\n\n"
            "JSON配列のみ出力。説明不要。\n"
            '[{"start":秒,"end":秒,"topic":"要約","reason":"選定理由","score":1-10},...]'
        )
        for attempt in range(3):
            try:
                resp = self._gemini.models.generate_content(
                    model=self._model,
                    contents=gtypes.Content(parts=[gtypes.Part.from_text(prompt)], role="user"),
                    config=gtypes.GenerateContentConfig(temperature=0.3, max_output_tokens=1500))
                m = re.search(r'\[.*\]', resp.text.strip(), re.DOTALL)
                if not m: continue
                items = json.loads(m.group())
                clips = []
                for it in items[:self.clip_count]:
                    s, e = float(it["start"]), float(it["end"])
                    if e - s < self.min_dur: e = s + self.min_dur
                    if e - s > self.max_dur: e = s + self.max_dur
                    cs = [sub for sub in subtitles if sub.start >= s and sub.end <= e]
                    clips.append(ClipSegment(start=s, end=e, subtitles=cs,
                        score=float(it.get("score", 5)), topic_summary=it.get("topic", ""),
                        reason=it.get("reason", "")))
                if clips:
                    for i, c in enumerate(clips):
                        logger.info(f"  Clip{i+1}: {c.start:.0f}-{c.end:.0f}s ({c.duration:.0f}s) 「{c.topic_summary}」")
                    return clips
            except Exception as e:
                logger.warning(f"Gemini error (attempt {attempt+1}): {e}")
                if attempt < 2: time.sleep(2 ** attempt)
        return []

    def _select_rules(self, subtitles, preferences=None):
        bounds = [0]
        for i in range(1, len(subtitles)):
            if subtitles[i].start - subtitles[i-1].end > 2.0:
                bounds.append(i); continue
            for w in self.TOPIC_BREAK_WORDS:
                if subtitles[i].text.startswith(w): bounds.append(i); break
        bounds.append(len(subtitles))
        bounds = sorted(set(bounds))
        cands = []
        for i in range(len(bounds)-1):
            for j in range(i+1, len(bounds)):
                sl = subtitles[bounds[i]:bounds[j]]
                if not sl: continue
                dur = sl[-1].end - sl[0].start
                if self.min_dur <= dur <= self.max_dur:
                    cands.append(ClipSegment(start=sl[0].start, end=sl[-1].end, subtitles=sl))
                if dur > self.max_dur: break
        for c in cands:
            text = " ".join(s.text for s in c.subtitles)
            sc = sum(3.0 for w in self.VIRAL_WORDS if w in text)
            sc += sum(2.0 for i in range(1, len(c.subtitles))
                      if c.subtitles[i].speaker != c.subtitles[i-1].speaker and c.subtitles[i].speaker != "unknown")
            if 30 <= c.duration <= 45: sc += 5.0
            c.score = sc; c.topic_summary = text[:50]
        cands.sort(key=lambda c: c.score, reverse=True)
        sel = []
        for c in cands:
            if not any(not (c.end <= s.start or c.start >= s.end) for s in sel):
                sel.append(c)
            if len(sel) >= self.clip_count: break
        return sel
