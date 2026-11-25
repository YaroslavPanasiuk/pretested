"""Persistent record of attempts and per-question outcomes.

Stored as a single JSON file in the user's data directory. Two things are
kept: a capped log of finished attempts (to show the last score per test) and
the latest outcome per question id (to drive the "retry wrong answers" mode).

Keeping only the *latest* outcome per question is deliberate: once a question
is answered correctly it leaves the retry pool, and getting it wrong again
puts it back.

GTK-free, so it is testable headlessly.
"""
import json
import os
import time

from .library import user_data_dir

# How many finished attempts to keep per test key. Enough to show recent
# history without the file growing without bound.
MAX_ATTEMPTS_PER_TEST = 20


class ResultsStore:
    def __init__(self, path=None):
        self.path = path or os.path.join(user_data_dir(), "results.json")
        self._data = self._load()

    # -- persistence -------------------------------------------------------

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            # A missing or corrupt results file must never stop the app: the
            # question banks are the valuable data, this is derived state.
            return {"version": 1, "attempts": {}, "questions": {}}

        if not isinstance(data, dict):
            return {"version": 1, "attempts": {}, "questions": {}}
        data.setdefault("version", 1)
        data.setdefault("attempts", {})
        data.setdefault("questions", {})
        return data

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            # Atomic replace, so an interrupted write cannot truncate the file.
            os.replace(tmp, self.path)
        except OSError as e:
            print(f"Warning: could not save results to {self.path}: {e}")

    # -- recording ---------------------------------------------------------

    def record_attempt(self, test_key, score, total, outcomes, title="", mode=""):
        """Store a finished attempt and fold its outcomes into the per-question record."""
        if test_key:
            log = self._data["attempts"].setdefault(test_key, [])
            log.append({
                "when": int(time.time()),
                "score": score,
                "total": total,
                "title": title,
                "mode": mode,
            })
            del log[:-MAX_ATTEMPTS_PER_TEST]

        questions = self._data["questions"]
        now = int(time.time())
        for qid, correct in outcomes.items():
            record = questions.setdefault(qid, {"seen": 0, "wrong": 0})
            record["seen"] = record.get("seen", 0) + 1
            if not correct:
                record["wrong"] = record.get("wrong", 0) + 1
            record["last_correct"] = bool(correct)
            record["last_seen"] = now

        self.save()

    def forget_question(self, qid):
        self._data["questions"].pop(qid, None)

    # -- reading -----------------------------------------------------------

    def attempts(self, test_key):
        return list(self._data["attempts"].get(test_key, []))

    def last_attempt(self, test_key):
        log = self._data["attempts"].get(test_key)
        return log[-1] if log else None

    def best_attempt(self, test_key):
        log = self._data["attempts"].get(test_key)
        if not log:
            return None
        return max(log, key=lambda a: (a["score"] / a["total"]) if a["total"] else 0)

    def wrong_question_ids(self):
        """Question ids whose most recent answer was wrong."""
        return {
            qid for qid, rec in self._data["questions"].items()
            if rec.get("last_correct") is False
        }

    def stats(self, qid):
        return dict(self._data["questions"].get(qid, {}))
