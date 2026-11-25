"""One sitting at a set of questions: shuffling, answers, locking, scoring.

Holds no GTK state and no file handles, so the whole quiz flow is testable
headlessly. Questions arrive from `library` as immutable `Question` objects;
an attempt keeps its own shuffled view of them, which is why no deep copy of
the source bank is needed.
"""
import random

# Attempt modes. `mode` only affects presentation and how results are recorded;
# the quiz flow itself is identical for all three.
MODE_TEST = "test"
MODE_RANDOM = "random"
MODE_WRONG = "wrong"


class AttemptQuestion:
    """A question as presented in this attempt, with options shuffled."""

    __slots__ = ("source", "options")

    def __init__(self, source, options):
        self.source = source
        self.options = options

    @property
    def qid(self):
        return self.source.qid

    @property
    def text(self):
        return self.source.text

    @property
    def answer(self):
        return self.source.answer

    @property
    def answer_text(self):
        return self.source.answer_text


class Attempt:
    def __init__(self, questions, title="", mode=MODE_TEST,
                 subject_id=None, test_key=None, rng=None):
        if not questions:
            raise ValueError("an attempt needs at least one question")
        self._source = tuple(questions)
        self.title = title
        self.mode = mode
        self.subject_id = subject_id
        self.test_key = test_key
        self._rng = rng or random.Random()
        self.reset()

    # -- lifecycle ---------------------------------------------------------

    def reset(self):
        """Reshuffle questions and each question's options, clearing answers."""
        order = list(self._source)
        self._rng.shuffle(order)
        self.questions = []
        for source in order:
            options = list(source.options)
            self._rng.shuffle(options)
            self.questions.append(AttemptQuestion(source, options))

        self.current_idx = 0
        self.answers = {}
        self.visited = set()
        self.checked = set()
        self.submitted = False

    # -- navigation --------------------------------------------------------

    @property
    def total(self):
        return len(self.questions)

    def current(self):
        return self.questions[self.current_idx]

    def navigate(self, index):
        if 0 <= index < self.total:
            self.current_idx = index

    def next_question(self):
        self.navigate(self.current_idx + 1)

    def prev_question(self):
        self.navigate(self.current_idx - 1)

    def mark_visited(self):
        self.visited.add(self.current_idx)

    # -- answering ---------------------------------------------------------

    def get_answer(self, idx=None):
        return self.answers.get(self.current_idx if idx is None else idx)

    def set_answer(self, key):
        """Record an answer unless the question is already locked."""
        if self.is_locked(self.current_idx):
            return False
        self.answers[self.current_idx] = key
        return True

    def is_locked(self, idx):
        return self.submitted or idx in self.checked

    def is_revealed(self, idx=None):
        return self.is_locked(self.current_idx if idx is None else idx)

    def can_check(self):
        # Checking reveals the answer and locks the question permanently, so
        # refuse while nothing is selected: otherwise a stray click scores the
        # question wrong with no way back short of a full reset.
        return (
            not self.submitted
            and self.current_idx not in self.checked
            and self.get_answer() is not None
        )

    def check(self):
        if not self.can_check():
            return False
        self.checked.add(self.current_idx)
        return True

    # -- scoring -----------------------------------------------------------

    def is_correct(self, idx):
        return self.answers.get(idx) == self.questions[idx].answer

    def answered_count(self):
        return len(self.answers)

    def score(self):
        return sum(1 for i in range(self.total) if self.is_correct(i))

    def submit(self):
        self.submitted = True
        return self.score(), self.total

    # -- results -----------------------------------------------------------

    def outcomes(self):
        """{qid: bool} for every question, for persisting to the results store."""
        return {q.qid: self.is_correct(i) for i, q in enumerate(self.questions)}


def sample_questions(questions, count, rng=None):
    """Pick `count` questions at random; -1 or more than available means all."""
    rng = rng or random.Random()
    pool = list(questions)
    if count is None or count < 0 or count >= len(pool):
        size = len(pool)
    else:
        size = count
    return rng.sample(pool, size)
