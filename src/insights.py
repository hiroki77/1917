import os
import json
import logging
from datetime import datetime
from src.utils import load_json, save_json

logger = logging.getLogger(__name__)

class InsightsEngine:
    def __init__(self, config):
        self.enabled = config["insights"]["enabled"]
        self.data_file = config["insights"]["data_file"]
        self.data = load_json(self.data_file, default={"clips": [], "preferences": {"boost_keywords": [], "preferred_duration": 35, "avoid_keywords": []}})

    def get_preferences(self):
        return self.data.get("preferences", {}) if self.enabled else {}

    def record_clip(self, clip_info):
        self.data["clips"].append({"timestamp": datetime.now().isoformat(), "duration": clip_info.get("duration", 0), "score": clip_info.get("score", 0), "topic": clip_info.get("topic", ""), "views": 0, "likes": 0})
        save_json(self.data, self.data_file)

    def update_insights(self, insights_data):
        if not insights_data:
            return
        for clip in insights_data.get("clips", []):
            for ex in self.data["clips"]:
                if ex["topic"] == clip.get("topic", ""):
                    ex["views"] = clip.get("views", 0)
                    ex["likes"] = clip.get("likes", 0)
        scored = [c for c in self.data["clips"] if c.get("views", 0) > 0]
        if scored:
            scored.sort(key=lambda c: c.get("views", 0), reverse=True)
            words = {}
            for c in scored[:5]:
                for w in c.get("topic", "").split():
                    if len(w) >= 2:
                        words[w] = words.get(w, 0) + 1
            self.data["preferences"]["boost_keywords"] = [w for w, _ in sorted(words.items(), key=lambda x: -x[1])[:10]]
            durations = [c.get("duration", 35) for c in scored[:5]]
            self.data["preferences"]["preferred_duration"] = round(sum(durations) / len(durations))
        save_json(self.data, self.data_file)
