"""Tests for bank discovery, validation, parsing and legacy migration."""
import json
import os

import pytest

from pretested import library
from pretested.library import (DataError, Library, import_subject_file,
                               load_library, load_subject_file, parse_subject,
                               question_id, slugify, validate_subject)


def subject_dict(subject_id="ai", name="AI", n_tests=1, n_questions=2):
    return {
        "id": subject_id,
        "name": name,
        "tests": [
            {
                "id": f"t{t}",
                "name": f"Test {t}",
                "questions": [
                    {
                        "question": f"{subject_id} t{t} question {q}?",
                        "options": [{"А": "a"}, {"Б": "b"}, {"В": "c"}],
                        "answer": "Б",
                    }
                    for q in range(n_questions)
                ],
            }
            for t in range(n_tests)
        ],
    }


def write_subject(directory, filename, data):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


# -- question ids ----------------------------------------------------------

def test_question_id_is_stable_and_content_addressed():
    assert question_id("abc") == question_id("abc")
    assert question_id("abc") != question_id("abd")


def test_question_id_is_independent_of_position():
    """Ids must survive shuffling and reordering within a file."""
    a = parse_subject(subject_dict())
    reordered = subject_dict()
    reordered["tests"][0]["questions"].reverse()
    b = parse_subject(reordered)
    assert sorted(q.qid for q in a.questions) == sorted(q.qid for q in b.questions)


def test_shipped_banks_have_unique_question_ids():
    """A collision would silently merge two questions' results."""
    lib = load_library(user_dir="/nonexistent", migrate_legacy=False)
    qids = [q.qid for q in lib.all_questions()]
    assert len(set(qids)) == len(qids)


def test_slugify():
    assert slugify("AI_1") == "ai_1"
    assert slugify("Hello, World!") == "hello__world"


# -- validation ------------------------------------------------------------

def test_a_good_subject_validates():
    assert validate_subject(subject_dict()) == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda d: d.pop("name"), "name"),
    (lambda d: d.update(name="  "), "name"),
    (lambda d: d.pop("tests"), "tests"),
    (lambda d: d.update(tests=[]), "tests"),
    (lambda d: d["tests"][0].pop("name"), "name"),
    (lambda d: d["tests"][0].update(questions=[]), "questions"),
    (lambda d: d["tests"][0]["questions"][0].update(question=""), "question"),
    (lambda d: d["tests"][0]["questions"][0].update(options=[{"А": "a"}]), "two options"),
    (lambda d: d["tests"][0]["questions"][0].update(answer="Z"), "answer"),
    (lambda d: d["tests"][0]["questions"][0].update(
        options=[{"А": "a"}, {"А": "b"}]), "duplicate"),
    (lambda d: d["tests"][0]["questions"][0].update(
        options=[{"А": "a", "Б": "b"}, {"В": "c"}]), "single-key"),
])
def test_validation_catches_broken_banks(mutate, expected):
    data = subject_dict()
    mutate(data)
    errors = validate_subject(data)
    assert errors, "expected a validation error"
    assert any(expected in e for e in errors), errors


def test_validation_rejects_non_objects():
    assert validate_subject([]) == ["top level must be a JSON object"]


def test_parse_subject_raises_on_invalid_data():
    data = subject_dict()
    data["tests"][0]["questions"][0]["answer"] = "Z"
    with pytest.raises(DataError):
        parse_subject(data)


# -- parsing ---------------------------------------------------------------

def test_parse_subject_builds_the_object_graph():
    subject = parse_subject(subject_dict(n_tests=2, n_questions=3))
    assert subject.id == "ai"
    assert len(subject.tests) == 2
    assert len(subject.questions) == 6
    test = subject.tests[0]
    assert test.subject_id == "ai"
    assert test.subject_name == "AI"
    assert test.key == "ai/t0"
    assert test.questions[0].options[0] == ("А", "a")


def test_ids_fall_back_to_a_slug_of_the_name():
    data = subject_dict()
    del data["id"]
    del data["tests"][0]["id"]
    subject = parse_subject(data)
    assert subject.id == "ai"           # slug of "AI"
    assert subject.tests[0].id == "test_0"  # slug of "Test 0"


def test_answer_text_resolves_the_correct_option():
    subject = parse_subject(subject_dict())
    assert subject.questions[0].answer_text == "b"


def test_load_subject_file_reports_bad_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError) as excinfo:
        load_subject_file(str(path))
    assert "broken.json" in str(excinfo.value)


# -- the library -----------------------------------------------------------

def test_load_library_reads_a_directory(tmp_path):
    bundled = tmp_path / "bundled"
    write_subject(str(bundled), "ai.json", subject_dict("ai", "AI"))
    write_subject(str(bundled), "m.json", subject_dict("m", "Methodology"))

    lib = load_library(user_dir=str(tmp_path / "user"),
                       bundled_dirs=[str(bundled)], migrate_legacy=False)
    assert [s.id for s in lib] == ["ai", "m"]
    assert len(lib) == 2


def test_subjects_are_sorted_by_name(tmp_path):
    bundled = tmp_path / "bundled"
    write_subject(str(bundled), "a.json", subject_dict("z", "Zoology"))
    write_subject(str(bundled), "b.json", subject_dict("a", "Anatomy"))
    lib = load_library(user_dir=str(tmp_path / "user"),
                       bundled_dirs=[str(bundled)], migrate_legacy=False)
    assert [s.name for s in lib] == ["Anatomy", "Zoology"]


def test_user_files_shadow_bundled_ones_by_stem(tmp_path):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    write_subject(str(bundled), "ai.json", subject_dict("ai", "Bundled AI"))
    write_subject(str(user), "ai.json", subject_dict("ai", "User AI", n_tests=3))

    lib = load_library(user_dir=str(user), bundled_dirs=[str(bundled)],
                       migrate_legacy=False)
    assert len(lib) == 1
    assert lib.subject("ai").name == "User AI"
    assert len(lib.subject("ai").tests) == 3


def test_user_files_with_other_stems_are_added(tmp_path):
    bundled = tmp_path / "bundled"
    user = tmp_path / "user"
    write_subject(str(bundled), "ai.json", subject_dict("ai", "AI"))
    write_subject(str(user), "mine.json", subject_dict("mine", "Mine"))
    lib = load_library(user_dir=str(user), bundled_dirs=[str(bundled)],
                       migrate_legacy=False)
    assert sorted(s.id for s in lib) == ["ai", "mine"]


def test_a_broken_bank_is_skipped_not_fatal(tmp_path):
    bundled = tmp_path / "bundled"
    write_subject(str(bundled), "good.json", subject_dict("good", "Good"))
    os.makedirs(str(bundled), exist_ok=True)
    (bundled / "bad.json").write_text("{nope", encoding="utf-8")

    lib = load_library(user_dir=str(tmp_path / "user"),
                       bundled_dirs=[str(bundled)], migrate_legacy=False)
    assert [s.id for s in lib] == ["good"]
    assert len(lib.problems) == 1
    assert "bad.json" in lib.problems[0]


def test_no_banks_at_all_raises_with_the_searched_paths(tmp_path):
    with pytest.raises(DataError) as excinfo:
        load_library(user_dir=str(tmp_path / "user"),
                     bundled_dirs=[str(tmp_path / "none")],
                     migrate_legacy=False)
    assert "No question banks found" in str(excinfo.value)
    assert str(tmp_path) in str(excinfo.value)


def test_library_lookups():
    lib = Library([parse_subject(subject_dict("ai", "AI", n_tests=2))])
    assert lib.subject("ai").name == "AI"
    assert lib.subject("nope") is None
    assert lib.test("ai", "t1").name == "Test 1"
    assert lib.test("ai", "nope") is None
    assert lib.test("nope", "t0") is None


def test_all_questions_can_be_scoped_to_a_subject():
    lib = Library([
        parse_subject(subject_dict("ai", "AI", n_questions=3)),
        parse_subject(subject_dict("m", "M", n_questions=4)),
    ])
    assert len(lib.all_questions()) == 7
    assert len(lib.all_questions("ai")) == 3
    assert len(lib.all_questions("nope")) == 0
    assert len(lib.questions_by_id("m")) == 4


# -- directories -----------------------------------------------------------

def test_user_data_dir_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert library.user_data_dir() == str(tmp_path / "pretested")
    assert library.user_subjects_dir() == str(tmp_path / "pretested" / "subjects")


def test_data_dir_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PRETESTED_DATA_DIR", str(tmp_path))
    assert library.bundled_subjects_dirs() == [str(tmp_path / "subjects")]


def test_bundled_dirs_resolve_in_the_source_tree(monkeypatch):
    monkeypatch.delenv("PRETESTED_DATA_DIR", raising=False)
    dirs = library.bundled_subjects_dirs()
    assert dirs, "the shipped data/subjects directory should be discoverable"
    assert all(os.path.isdir(d) for d in dirs)


# -- importing -------------------------------------------------------------

def test_import_copies_a_valid_bank(tmp_path):
    src = write_subject(str(tmp_path / "src"), "whatever.json",
                        subject_dict("smoke", "Smoke"))
    user = tmp_path / "user"
    dest = import_subject_file(src, user_dir=str(user))
    assert os.path.basename(dest) == "smoke.json"
    assert load_subject_file(dest).id == "smoke"


def test_import_rejects_a_broken_bank(tmp_path):
    data = subject_dict()
    data["tests"][0]["questions"][0]["answer"] = "Z"
    src = write_subject(str(tmp_path / "src"), "bad.json", data)
    with pytest.raises(DataError) as excinfo:
        import_subject_file(src, user_dir=str(tmp_path / "user"))
    assert "answer" in str(excinfo.value)
    assert not os.path.exists(tmp_path / "user" / "ai.json")


def test_importing_twice_does_not_overwrite(tmp_path):
    user = tmp_path / "user"
    first = write_subject(str(tmp_path / "a"), "x.json", subject_dict("smoke", "One"))
    second = write_subject(str(tmp_path / "b"), "x.json", subject_dict("smoke", "Two"))
    d1 = import_subject_file(first, user_dir=str(user))
    d2 = import_subject_file(second, user_dir=str(user))
    assert d1 != d2
    assert load_subject_file(d1).name == "One"
    assert load_subject_file(d2).name == "Two"


# -- legacy migration ------------------------------------------------------

def legacy_payload():
    return {"tests": [
        {"name": "Bundled copy", "questions": [
            {"question": "already shipped?", "options": [{"А": "a"}, {"Б": "b"}],
             "answer": "Б"}]},
        {"name": "My own notes", "questions": [
            {"question": "added by hand?", "options": [{"А": "a"}, {"Б": "b"}],
             "answer": "Б"}]},
    ]}


def test_migration_rescues_only_hand_added_questions(monkeypatch, tmp_path):
    config = tmp_path / "config" / "pretested"
    os.makedirs(config)
    legacy = config / "tests.json"
    legacy.write_text(json.dumps(legacy_payload()), encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    user = tmp_path / "user"
    imported = library.migrate_legacy_config({"already shipped?"}, str(user))

    assert imported is not None
    subject = load_subject_file(imported)
    assert [t.name for t in subject.tests] == ["My own notes"]
    # The original is renamed aside, never deleted.
    assert not legacy.exists()
    assert (config / "tests.json.migrated").exists()


def test_migration_is_a_no_op_when_nothing_was_added(monkeypatch, tmp_path):
    config = tmp_path / "config" / "pretested"
    os.makedirs(config)
    legacy = config / "tests.json"
    legacy.write_text(json.dumps(legacy_payload()), encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    known = {"already shipped?", "added by hand?"}
    assert library.migrate_legacy_config(known, str(tmp_path / "user")) is None
    assert (config / "tests.json.migrated").exists()


def test_migration_is_idempotent(monkeypatch, tmp_path):
    config = tmp_path / "config" / "pretested"
    os.makedirs(config)
    (config / "tests.json").write_text(json.dumps(legacy_payload()), encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    user = tmp_path / "user"
    first = library.migrate_legacy_config(set(), str(user))
    assert first is not None
    # Second run has no legacy file left to act on.
    assert library.migrate_legacy_config(set(), str(user)) is None


def test_migration_survives_a_corrupt_legacy_file(monkeypatch, tmp_path):
    config = tmp_path / "config" / "pretested"
    os.makedirs(config)
    (config / "tests.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

    assert library.migrate_legacy_config(set(), str(tmp_path / "user")) is None
    assert (config / "tests.json.migrated").exists()


def test_no_legacy_file_is_fine(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    assert library.migrate_legacy_config(set(), str(tmp_path / "user")) is None
