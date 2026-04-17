import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ClipSegment:
    start: float
    end: float
    subtitles: list
    score: float = 0.0
    topic_summary: str = ""
    @property
    def duration(self):
        return self.end - self.start

class TopicSegmenter:
    TOPIC_BREAK_WORDS = ["で", "でさ", "というわけで", "次", "じゃあ", "ところで", "ちなみに", "あと", "それで", "えーと", "最後に"]
    VIRAL_WORDS = ["やばい", "マジ", "笑", "可愛い", "無理", "神", "最高", "おもろい", "怖い", "泣く", "エモい"]

    def __init__(self, config):
        self.min_dur = config["clips"]["min_duration"]
        self.max_dur = config["clips"]["max_duration"]
        self.clip_count = config["clips"]["count"]

    def select_clips(self, subtitles, video_path, preferences=None):
        if not subtitles:
            return []
        bounds = self._find_boundaries(subtitles)
        cands = self._gen_candidates(subtitles, bounds)
        for c in cands:
            c.score = self._score(c, preferences)
        return self._select_top(cands, self.clip_count)

    def _find_boundaries(self, subs):
        b = [0]
        for i in range(1, len(subs)):
            if subs[i].start - subs[i-1].end > 2.0:
                b.append(i)
                continue
            for w in self.TOPIC_BREAK_WORDS:
                if subs[i].text.startswith(w):
                    b.append(i)
                    break
        b.append(len(subs))
        return sorted(set(b))

    def _gen_candidates(self, subs, bounds):
        cands = []
        for i in range(len(bounds)-1):
            for j in range(i+1, len(bounds)):
                sl = subs[bounds[i]:bounds[j]]
                if not sl:
                    continue
                dur = sl[-1].end - sl[0].start
                if self.min_dur <= dur <= self.max_dur:
                    cands.append(ClipSegment(start=sl[0].start, end=sl[-1].end, subtitles=sl))
                if dur > self.max_dur:
                    break
        return cands

    def _score(self, clip, prefs=None):
        score = 0.0
        text = " ".join(s.text for s in clip.subtitles)
        for w in self.VIRAL_WORDS:
            if w in text:
                score += 3.0
        changes = sum(1 for i in range(1, len(clip.subtitles))
                      if clip.subtitles[i].speaker != clip.subtitles[i-1].speaker
                      and clip.subtitles[i].speaker != "unknown")
        score += changes * 2.0
        if 30 <= clip.duration <= 45:
            score += 5.0
        emphasis = sum(1 for s in clip.subtitles if s.style == "emphasis")
        score += emphasis * 2.5
        if prefs:
            for kw in prefs.get("boost_keywords", []):
                if kw in text:
                    score += 4.0
        clip.topic_summary = text[:50]
        return score

    def _select_top(self, cands, count):
        cands.sort(key=lambda c: c.score, reverse=True)
        sel = []
        for c in cands:
            if not any(not (c.end <= s.start or c.start >= s.end) for s in sel):
                sel.append(c)
            if len(sel) >= count:
                break
        return sel
