import gzip
import json
import os
from datetime import datetime


HISTORY_FILE = "history.oiv"


def empty_counts():
    return {"key": 0, "other": 0}


class CountHistory:
    def __init__(self, path=HISTORY_FILE):
        self.path = path
        self.data = {
            "version": 1,
            "carryover": {},
            "entries": [],
        }
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with gzip.open(self.path, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.data["carryover"] = data.get("carryover", {})
                self.data["entries"] = data.get("entries", [])
        except Exception:
            # 履歴は補助データなので、読めない場合は新規扱いにする。
            self.data = {"version": 1, "carryover": {}, "entries": []}

    def save(self):
        with gzip.open(self.path, "wt", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, separators=(",", ":"))

    def get_carryover(self, mode_name):
        counts = self.data.get("carryover", {}).get(mode_name, {})
        return {
            "key": int(counts.get("key", 0)),
            "other": int(counts.get("other", 0)),
        }

    def set_carryover(self, mode_name, key_count, other_count):
        self.data.setdefault("carryover", {})[mode_name] = {
            "key": int(key_count),
            "other": int(other_count),
        }

    def add_session(self, mode_name, key_count, other_count, ended_at=None):
        if key_count <= 0 and other_count <= 0:
            return
        ended_at = ended_at or datetime.now()
        other_name = "vol" if mode_name == "sdvx" else "scratch"
        self.data.setdefault("entries", []).append(
            {
                "ended_at": ended_at.isoformat(timespec="seconds"),
                "date": ended_at.strftime("%Y-%m-%d"),
                "month": ended_at.strftime("%Y/%m"),
                "mode": mode_name,
                "key": int(key_count),
                other_name: int(other_count),
                "total": int(key_count + other_count),
            }
        )

    def monthly_total(self, mode_name, month=None):
        month = month or datetime.now().strftime("%Y/%m")
        total = 0
        for entry in self.data.get("entries", []):
            if entry.get("mode") != mode_name or entry.get("month") != month:
                continue
            total += int(entry.get("total", 0))
        return total

    def has_entries(self):
        return bool(self.data.get("entries"))
