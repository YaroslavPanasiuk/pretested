#!/usr/bin/env python3
"""One-shot migration: convert the flat tests.json into a subject file.

The original tests.json held a bare list of tests with no subject layer. This
script regroups them into data/subjects/<id>.json. It is kept in the tree so
the migration stays reproducible, but it only ever needed to run once.

Note that it cannot reproduce data/subjects/ in full any more: AI_6 was
recovered later from a user's legacy ~/.config/pretested/tests.json, which was
never part of the repo, and merged in by hand.

Usage: python3 tools/split_tests.py tests.json data/subjects
"""
import json
import os
import sys

# Which of the original flat test names belong to which subject. Everything not
# listed here lands in a catch-all subject so no bank is ever silently dropped.
SUBJECTS = [
    {
        "id": "methodology",
        "name": "Методологія наукових досліджень",
        "tests": [
            "Методологія наукових досліджень 2025",
            "Приклад МНД 2025",
            "AI_1", "AI_2", "AI_3", "AI_4", "AI_5",
        ],
    },
]


def slugify(name):
    out = [c if c.isalnum() else "_" for c in name.lower()]
    return "".join(out).strip("_")


def main(src, dest_dir):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    by_name = {t["name"]: t for t in data["tests"]}
    claimed = set()
    os.makedirs(dest_dir, exist_ok=True)

    for subject in SUBJECTS:
        tests = []
        for test_name in subject["tests"]:
            if test_name not in by_name:
                print(f"warning: no test named {test_name!r} in {src}")
                continue
            source = by_name[test_name]
            claimed.add(test_name)
            tests.append({
                "id": slugify(test_name),
                "name": test_name,
                "questions": source["questions"],
            })

        out_path = os.path.join(dest_dir, f"{subject['id']}.json")
        payload = {"id": subject["id"], "name": subject["name"], "tests": tests}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        total = sum(len(t["questions"]) for t in tests)
        print(f"wrote {out_path}: {len(tests)} tests, {total} questions")

    leftover = [name for name in by_name if name not in claimed]
    if leftover:
        out_path = os.path.join(dest_dir, "unsorted.json")
        payload = {
            "id": "unsorted",
            "name": "Unsorted",
            "tests": [
                {"id": slugify(n), "name": n, "questions": by_name[n]["questions"]}
                for n in leftover
            ],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"wrote {out_path}: {len(leftover)} unclaimed tests")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
