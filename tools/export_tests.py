#!/usr/bin/env python3
"""Export subject banks as printable text, with a separate answer key.

Usage:
    python3 tools/export_tests.py data/subjects/ai.json [more.json ...]
    python3 tools/export_tests.py data/subjects/*.json > output.txt
"""
import json
import sys


def export(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    subject_name = data.get("name", "Unnamed subject")
    print(f"{'=' * 80}\nSubject: {subject_name}\n{'=' * 80}\n")

    for test in data.get("tests", []):
        test_name = test.get("name", "noname")
        questions = test.get("questions", [])

        lines = [f"Test name: {test_name}", ""]
        answers = [f"{test_name} (answers):"]

        for number, q in enumerate(questions, start=1):
            options = [") ".join(next(iter(opt.items()))) for opt in q["options"]]
            lines.append(f"{number}. {q['question']}")
            lines.append("")
            lines.extend(options)
            lines.append("")
            lines.append("-" * 80)
            lines.append("")
            answers.append(f"{number}. {q['answer']}")

        print("\n".join(lines))
        print()
        print("\n".join(answers))
        print("\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for arg in sys.argv[1:]:
        export(arg)
