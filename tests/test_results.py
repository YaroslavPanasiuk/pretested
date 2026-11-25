"""Tests for the persistent results store."""
import json
import os

from pretested.results import MAX_ATTEMPTS_PER_TEST, ResultsStore


def store(tmp_path, name="results.json"):
    return ResultsStore(str(tmp_path / name))


def test_a_missing_file_starts_empty(tmp_path):
    s = store(tmp_path)
    assert s.attempts("ai/ai_1") == []
    assert s.last_attempt("ai/ai_1") is None
    assert s.wrong_question_ids() == set()


def test_record_and_read_back(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 8, 10, {"q1": True, "q2": False},
                     title="AI 1", mode="test")

    last = s.last_attempt("ai/ai_1")
    assert last["score"] == 8
    assert last["total"] == 10
    assert last["title"] == "AI 1"
    assert last["mode"] == "test"
    assert isinstance(last["when"], int)


def test_results_survive_a_reload(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 5, 10, {"q1": False})
    again = ResultsStore(s.path)
    assert again.last_attempt("ai/ai_1")["score"] == 5
    assert again.wrong_question_ids() == {"q1"}


def test_the_file_is_valid_json_on_disk(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 1, 2, {"q1": True})
    with open(s.path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["attempts"]["ai/ai_1"][0]["score"] == 1
    assert data["questions"]["q1"]["last_correct"] is True


def test_no_temp_file_is_left_behind(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 1, 2, {"q1": True})
    assert not os.path.exists(s.path + ".tmp")


def test_a_corrupt_file_degrades_to_empty(tmp_path):
    path = tmp_path / "results.json"
    path.write_text("{not json", encoding="utf-8")
    s = ResultsStore(str(path))
    assert s.last_attempt("ai/ai_1") is None
    # And it recovers: a new write replaces the corrupt file.
    s.record_attempt("ai/ai_1", 1, 1, {"q1": True})
    assert ResultsStore(str(path)).last_attempt("ai/ai_1")["score"] == 1


def test_a_json_file_of_the_wrong_shape_degrades_to_empty(tmp_path):
    path = tmp_path / "results.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert ResultsStore(str(path)).wrong_question_ids() == set()


def test_attempt_log_is_capped(tmp_path):
    s = store(tmp_path)
    for i in range(MAX_ATTEMPTS_PER_TEST + 10):
        s.record_attempt("ai/ai_1", i, 100, {})
    log = s.attempts("ai/ai_1")
    assert len(log) == MAX_ATTEMPTS_PER_TEST
    # The most recent attempts are the ones kept.
    assert log[-1]["score"] == MAX_ATTEMPTS_PER_TEST + 9


def test_attempts_are_kept_per_test(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 1, 10, {})
    s.record_attempt("ai/ai_2", 9, 10, {})
    assert s.last_attempt("ai/ai_1")["score"] == 1
    assert s.last_attempt("ai/ai_2")["score"] == 9


def test_an_attempt_with_no_test_key_logs_no_score(tmp_path):
    """Retry pools are not tests, so they must not appear in any test's history."""
    s = store(tmp_path)
    s.record_attempt(None, 3, 5, {"q1": False, "q2": True})
    with open(s.path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["attempts"] == {}
    # But the per-question outcomes are still recorded.
    assert s.wrong_question_ids() == {"q1"}


# -- the retry pool --------------------------------------------------------

def test_wrong_ids_track_only_the_latest_outcome(tmp_path):
    s = store(tmp_path)
    s.record_attempt("t", 0, 1, {"q1": False})
    assert s.wrong_question_ids() == {"q1"}

    # Getting it right drops it from the pool...
    s.record_attempt("t", 1, 1, {"q1": True})
    assert s.wrong_question_ids() == set()

    # ...and getting it wrong again puts it back.
    s.record_attempt("t", 0, 1, {"q1": False})
    assert s.wrong_question_ids() == {"q1"}


def test_wrong_ids_span_multiple_tests(tmp_path):
    s = store(tmp_path)
    s.record_attempt("ai/ai_1", 1, 2, {"q1": False, "q2": True})
    s.record_attempt("m/m_1", 0, 1, {"q3": False})
    assert s.wrong_question_ids() == {"q1", "q3"}


def test_seen_and_wrong_counts_accumulate(tmp_path):
    s = store(tmp_path)
    s.record_attempt("t", 0, 1, {"q1": False})
    s.record_attempt("t", 0, 1, {"q1": False})
    s.record_attempt("t", 1, 1, {"q1": True})
    stats = s.stats("q1")
    assert stats["seen"] == 3
    assert stats["wrong"] == 2
    assert stats["last_correct"] is True


def test_stats_for_an_unknown_question(tmp_path):
    assert store(tmp_path).stats("nope") == {}


def test_forget_question(tmp_path):
    s = store(tmp_path)
    s.record_attempt("t", 0, 1, {"q1": False})
    s.forget_question("q1")
    assert s.wrong_question_ids() == set()


# -- history ---------------------------------------------------------------

def test_best_attempt_picks_the_highest_ratio(tmp_path):
    s = store(tmp_path)
    s.record_attempt("t", 5, 10, {})
    s.record_attempt("t", 9, 10, {})
    s.record_attempt("t", 7, 10, {})
    assert s.best_attempt("t")["score"] == 9
    assert s.last_attempt("t")["score"] == 7


def test_best_attempt_handles_a_zero_total(tmp_path):
    s = store(tmp_path)
    s.record_attempt("t", 0, 0, {})
    assert s.best_attempt("t") is not None


def test_best_attempt_of_an_unknown_test(tmp_path):
    assert store(tmp_path).best_attempt("nope") is None


def test_the_store_creates_its_directory(tmp_path):
    nested = tmp_path / "a" / "b" / "results.json"
    s = ResultsStore(str(nested))
    s.record_attempt("t", 1, 1, {})
    assert os.path.exists(nested)
