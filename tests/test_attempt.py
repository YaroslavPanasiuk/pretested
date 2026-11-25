"""Tests for one sitting's state: shuffling, locking, scoring."""
import random

import pytest

from pretested.attempt import (Attempt, MODE_TEST, MODE_WRONG,
                               sample_questions)
from pretested.library import Question, question_id


def make_question(text, correct="Б"):
    return Question(
        qid=question_id(text),
        text=text,
        options=(("А", "first"), ("Б", "second"), ("В", "third"), ("Г", "fourth")),
        answer=correct,
    )


def make_questions(n=5):
    return [make_question(f"Question {i}") for i in range(n)]


def test_requires_at_least_one_question():
    with pytest.raises(ValueError):
        Attempt([])


def test_attempt_presents_every_source_question():
    questions = make_questions(5)
    attempt = Attempt(questions)
    assert attempt.total == 5
    assert sorted(q.qid for q in attempt.questions) == sorted(q.qid for q in questions)


def test_shuffle_is_deterministic_for_a_given_seed():
    questions = make_questions(20)
    first = Attempt(questions, rng=random.Random(1234))
    second = Attempt(questions, rng=random.Random(1234))
    assert [q.qid for q in first.questions] == [q.qid for q in second.questions]
    assert [q.options for q in first.questions] == [q.options for q in second.questions]


def test_shuffle_actually_reorders():
    questions = make_questions(30)
    attempt = Attempt(questions, rng=random.Random(7))
    assert [q.qid for q in attempt.questions] != [q.qid for q in questions]


def test_options_are_shuffled_but_preserved():
    attempt = Attempt(make_questions(10), rng=random.Random(99))
    for q in attempt.questions:
        assert sorted(q.options) == sorted(q.source.options)


def test_source_questions_are_not_mutated_by_reset():
    questions = make_questions(10)
    original = [q.options for q in questions]
    attempt = Attempt(questions, rng=random.Random(3))
    for _ in range(5):
        attempt.reset()
    assert [q.options for q in questions] == original


# -- answering and locking -------------------------------------------------

def test_set_and_get_answer():
    attempt = Attempt(make_questions(3))
    assert attempt.get_answer() is None
    assert attempt.set_answer("А") is True
    assert attempt.get_answer() == "А"


def test_cannot_check_without_an_answer():
    """The bug this guards: Check used to lock an unanswered question."""
    attempt = Attempt(make_questions(3))
    assert attempt.can_check() is False
    assert attempt.check() is False
    assert 0 not in attempt.checked
    assert attempt.is_revealed(0) is False


def test_check_locks_once_answered():
    attempt = Attempt(make_questions(3))
    attempt.set_answer("А")
    assert attempt.can_check() is True
    assert attempt.check() is True
    assert attempt.is_revealed(0) is True
    # Already revealed: checking again is refused.
    assert attempt.can_check() is False
    assert attempt.check() is False


def test_locked_question_rejects_a_new_answer():
    attempt = Attempt(make_questions(3))
    attempt.set_answer("А")
    attempt.check()
    assert attempt.set_answer("Б") is False
    assert attempt.get_answer() == "А"


def test_submitting_locks_every_question():
    attempt = Attempt(make_questions(3))
    attempt.submit()
    assert all(attempt.is_locked(i) for i in range(attempt.total))
    assert attempt.set_answer("А") is False
    assert attempt.can_check() is False


def test_reset_clears_answers_and_locks():
    attempt = Attempt(make_questions(4))
    attempt.set_answer("А")
    attempt.check()
    attempt.submit()
    attempt.reset()
    assert attempt.answers == {}
    assert attempt.checked == set()
    assert attempt.visited == set()
    assert attempt.submitted is False
    assert attempt.current_idx == 0


# -- navigation ------------------------------------------------------------

def test_navigation_clamps_to_range():
    attempt = Attempt(make_questions(3))
    attempt.prev_question()
    assert attempt.current_idx == 0
    for _ in range(10):
        attempt.next_question()
    assert attempt.current_idx == 2
    attempt.navigate(-5)
    assert attempt.current_idx == 2
    attempt.navigate(99)
    assert attempt.current_idx == 2
    attempt.navigate(1)
    assert attempt.current_idx == 1


def test_mark_visited_tracks_the_current_question():
    attempt = Attempt(make_questions(3))
    attempt.mark_visited()
    attempt.navigate(2)
    attempt.mark_visited()
    assert attempt.visited == {0, 2}


# -- scoring ---------------------------------------------------------------

def test_score_counts_only_correct_answers():
    attempt = Attempt(make_questions(4), rng=random.Random(5))
    for i in range(attempt.total):
        attempt.navigate(i)
        if i < 3:
            attempt.set_answer(attempt.current().answer)
    score, total = attempt.submit()
    assert (score, total) == (3, 4)


def test_unanswered_questions_count_as_wrong():
    attempt = Attempt(make_questions(4))
    score, total = attempt.submit()
    assert (score, total) == (0, 4)


def test_answered_count():
    attempt = Attempt(make_questions(5))
    assert attempt.answered_count() == 0
    attempt.set_answer("А")
    attempt.navigate(1)
    attempt.set_answer("Б")
    assert attempt.answered_count() == 2


def test_outcomes_report_every_question_by_id():
    attempt = Attempt(make_questions(4), rng=random.Random(11))
    attempt.navigate(0)
    attempt.set_answer(attempt.current().answer)
    outcomes = attempt.outcomes()
    assert len(outcomes) == 4
    assert sum(outcomes.values()) == 1
    assert set(outcomes) == {q.qid for q in attempt.questions}


def test_attempt_metadata_is_carried_through():
    attempt = Attempt(make_questions(2), title="T", mode=MODE_WRONG,
                      subject_id="ai", test_key="ai/ai_1")
    assert (attempt.title, attempt.mode) == ("T", MODE_WRONG)
    assert (attempt.subject_id, attempt.test_key) == ("ai", "ai/ai_1")
    assert Attempt(make_questions(2)).mode == MODE_TEST


# -- sampling --------------------------------------------------------------

def test_sample_questions_respects_count():
    questions = make_questions(50)
    assert len(sample_questions(questions, 20, random.Random(1))) == 20


def test_sample_questions_treats_negative_as_everything():
    questions = make_questions(10)
    assert len(sample_questions(questions, -1, random.Random(1))) == 10


def test_sample_questions_caps_at_pool_size():
    questions = make_questions(10)
    assert len(sample_questions(questions, 999, random.Random(1))) == 10


def test_sample_questions_does_not_repeat():
    questions = make_questions(40)
    picked = sample_questions(questions, 15, random.Random(2))
    assert len({q.qid for q in picked}) == 15
