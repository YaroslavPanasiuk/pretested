"""Discovery, validation and loading of question banks.

Question banks are read-only application data. They live in a bundled
directory that ships with the package, plus a writable user directory for
imported banks. Nothing in this module touches GTK, so it is testable without
a display.

Layout of a subject file:

    {"id": "ai", "name": "AI",
     "tests": [{"id": "ai_1", "name": "AI_1",
                "questions": [{"question": "...",
                               "options": [{"А": "..."}, {"Б": "..."}],
                               "answer": "Б"}]}]}

`id` is optional on both subjects and tests and falls back to a slug of the
name. Questions carry no id: identity is the hash of the question text, which
keeps results attached to a question across shuffles and reordering without
having to rewrite the existing banks.
"""
import glob
import hashlib
import json
import os
import shutil
from dataclasses import dataclass

APP_NAME = "pretested"


class DataError(Exception):
    """Raised when no usable question bank can be loaded."""


@dataclass(frozen=True)
class Question:
    qid: str
    text: str
    options: tuple  # ordered ((key, text), ...)
    answer: str

    @property
    def answer_text(self):
        for key, text in self.options:
            if key == self.answer:
                return text
        return ""


@dataclass(frozen=True)
class Test:
    id: str
    name: str
    questions: tuple
    subject_id: str
    subject_name: str

    @property
    def key(self):
        """Globally unique, stable identifier used to key stored results."""
        return f"{self.subject_id}/{self.id}"


@dataclass(frozen=True)
class Subject:
    id: str
    name: str
    tests: tuple
    source: str

    @property
    def questions(self):
        return tuple(q for t in self.tests for q in t.questions)


def question_id(text):
    """Stable identity for a question, derived from its text.

    Content-addressed so the 560 existing questions need no edits and so ids
    survive both the per-attempt shuffle and reordering within a file. Editing
    a question's wording deliberately starts its history over.
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def slugify(name):
    return "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")


# --------------------------------------------------------------------------
# Directories
# --------------------------------------------------------------------------

def user_data_dir():
    """Writable directory for imported banks and results."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def user_subjects_dir():
    return os.path.join(user_data_dir(), "subjects")


def bundled_subjects_dirs():
    """Read-only directories shipping with the application.

    Walks up from this file looking for either the in-repo `data/subjects` or
    an installed `share/pretested/subjects`, so the same code works from a
    source checkout and from a Nix store path.
    """
    override = os.environ.get("PRETESTED_DATA_DIR")
    if override:
        return [os.path.join(override, "subjects")]

    found = []
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        here = os.path.dirname(here)
        if not here or here == "/":
            break
        for candidate in (
            os.path.join(here, "data", "subjects"),
            os.path.join(here, "share", APP_NAME, "subjects"),
        ):
            if os.path.isdir(candidate):
                found.append(candidate)
    return found


# --------------------------------------------------------------------------
# Validation and parsing
# --------------------------------------------------------------------------

def validate_subject(data):
    """Return a list of human-readable problems; empty means usable.

    Shared by the loader and the UI import dialog so both judge a file the
    same way.
    """
    errors = []
    if not isinstance(data, dict):
        return ["top level must be a JSON object"]

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("missing a non-empty 'name'")

    tests = data.get("tests")
    if not isinstance(tests, list) or not tests:
        errors.append("missing a non-empty 'tests' list")
        return errors

    for ti, test in enumerate(tests):
        where = f"test {ti + 1}"
        if not isinstance(test, dict):
            errors.append(f"{where}: must be an object")
            continue
        if not isinstance(test.get("name"), str) or not test["name"].strip():
            errors.append(f"{where}: missing a non-empty 'name'")
        questions = test.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(f"{where}: missing a non-empty 'questions' list")
            continue

        for qi, q in enumerate(questions):
            qwhere = f"{where}, question {qi + 1}"
            if not isinstance(q, dict):
                errors.append(f"{qwhere}: must be an object")
                continue
            if not isinstance(q.get("question"), str) or not q["question"].strip():
                errors.append(f"{qwhere}: missing non-empty 'question' text")
            options = q.get("options")
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{qwhere}: needs at least two options")
                continue
            keys = []
            for opt in options:
                if not isinstance(opt, dict) or len(opt) != 1:
                    errors.append(f"{qwhere}: each option must be a single-key object")
                    continue
                keys.append(next(iter(opt)))
            if len(set(keys)) != len(keys):
                errors.append(f"{qwhere}: duplicate option keys")
            if q.get("answer") not in keys:
                errors.append(
                    f"{qwhere}: 'answer' {q.get('answer')!r} is not one of {keys}"
                )

    return errors


def parse_subject(data, source=""):
    """Turn validated JSON into a Subject. Raises DataError if unusable."""
    errors = validate_subject(data)
    if errors:
        raise DataError("; ".join(errors))

    subject_id = data.get("id") or slugify(data["name"])
    tests = []
    for test in data["tests"]:
        questions = tuple(
            Question(
                qid=question_id(q["question"]),
                text=q["question"],
                options=tuple(
                    (key, text) for opt in q["options"] for key, text in opt.items()
                ),
                answer=q["answer"],
            )
            for q in test["questions"]
        )
        tests.append(Test(
            id=test.get("id") or slugify(test["name"]),
            name=test["name"],
            questions=questions,
            subject_id=subject_id,
            subject_name=data["name"],
        ))

    return Subject(id=subject_id, name=data["name"],
                   tests=tuple(tests), source=source)


def load_subject_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise DataError(f"{os.path.basename(path)}: {e}") from e
    return parse_subject(data, source=path)


# --------------------------------------------------------------------------
# The library
# --------------------------------------------------------------------------

class Library:
    """All subjects available to the app, bundled plus user-imported."""

    def __init__(self, subjects, problems=()):
        self.subjects = list(subjects)
        self.problems = list(problems)

    def __iter__(self):
        return iter(self.subjects)

    def __len__(self):
        return len(self.subjects)

    def subject(self, subject_id):
        for s in self.subjects:
            if s.id == subject_id:
                return s
        return None

    def test(self, subject_id, test_id):
        subject = self.subject(subject_id)
        if subject:
            for t in subject.tests:
                if t.id == test_id:
                    return t
        return None

    def all_questions(self, subject_id=None):
        if subject_id is None:
            return tuple(q for s in self.subjects for q in s.questions)
        subject = self.subject(subject_id)
        return subject.questions if subject else ()

    def questions_by_id(self, subject_id=None):
        return {q.qid: q for q in self.all_questions(subject_id)}


def load_library(user_dir=None, bundled_dirs=None, migrate_legacy=True):
    """Load every subject file, letting user files shadow bundled ones.

    Shadowing is by filename stem, so dropping `ai.json` into the user
    directory replaces the bundled `ai.json` wholesale.
    """
    user_dir = user_subjects_dir() if user_dir is None else user_dir
    bundled_dirs = bundled_subjects_dirs() if bundled_dirs is None else bundled_dirs

    by_stem = {}
    for directory in list(bundled_dirs) + [user_dir]:
        for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
            by_stem[os.path.splitext(os.path.basename(path))[0]] = path

    if migrate_legacy:
        bundled_texts = set()
        for path in by_stem.values():
            try:
                for test in load_subject_file(path).tests:
                    bundled_texts.update(q.text for q in test.questions)
            except DataError:
                pass
        migrated = migrate_legacy_config(bundled_texts, user_dir)
        if migrated:
            by_stem[os.path.splitext(os.path.basename(migrated))[0]] = migrated

    subjects, problems = [], []
    for stem in sorted(by_stem):
        try:
            subjects.append(load_subject_file(by_stem[stem]))
        except DataError as e:
            problems.append(str(e))

    if not subjects:
        searched = ", ".join(list(bundled_dirs) + [user_dir]) or "(nowhere)"
        detail = (" Problems: " + "; ".join(problems)) if problems else ""
        raise DataError(f"No question banks found. Searched: {searched}.{detail}")

    subjects.sort(key=lambda s: s.name.lower())
    return Library(subjects, problems)


# --------------------------------------------------------------------------
# Legacy migration
# --------------------------------------------------------------------------

def legacy_config_file():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME, "tests.json")


def migrate_legacy_config(bundled_texts, user_dir):
    """Rescue hand edits from the old ~/.config/pretested/tests.json.

    Earlier versions copied the bundled bank into the config directory once and
    then read only from there, which meant new banks could never reach an
    existing user. That copy is now obsolete. If it contains questions the
    bundled banks do not, keep them as an imported subject; either way rename
    it so this runs at most once. The file is never deleted.

    Returns the path of the imported subject file, or None.
    """
    legacy = legacy_config_file()
    if not os.path.exists(legacy):
        return None

    imported_path = None
    try:
        with open(legacy, encoding="utf-8") as f:
            data = json.load(f)
        extra = [
            test for test in data.get("tests", [])
            if any(q.get("question") not in bundled_texts
                   for q in test.get("questions", []))
        ]
        if extra:
            os.makedirs(user_dir, exist_ok=True)
            imported_path = os.path.join(user_dir, "imported-tests.json")
            payload = {
                "id": "imported",
                "name": "Imported (from old config)",
                "tests": [
                    {"id": slugify(t.get("name", f"test_{i}")),
                     "name": t.get("name", f"Test {i + 1}"),
                     "questions": t.get("questions", [])}
                    for i, t in enumerate(extra)
                ],
            }
            if not validate_subject(payload):
                _atomic_write_json(imported_path, payload)
            else:
                imported_path = None
    except (OSError, json.JSONDecodeError):
        imported_path = None

    try:
        os.rename(legacy, legacy + ".migrated")
    except OSError:
        pass

    return imported_path


def _atomic_write_json(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def import_subject_file(src, user_dir=None):
    """Validate an external subject file and copy it into the user directory.

    Returns the destination path. Raises DataError if the file is unusable.
    """
    user_dir = user_subjects_dir() if user_dir is None else user_dir
    subject = load_subject_file(src)  # raises DataError with the reason

    os.makedirs(user_dir, exist_ok=True)
    stem = slugify(subject.id) or "imported"
    dest = os.path.join(user_dir, f"{stem}.json")
    n = 2
    while os.path.exists(dest) and not os.path.samefile(src, dest):
        dest = os.path.join(user_dir, f"{stem}-{n}.json")
        n += 1
    shutil.copy2(src, dest)
    return dest
