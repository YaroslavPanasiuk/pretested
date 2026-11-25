# Prompt template: generate a test from source links

Fill in the four `{{...}}` placeholders and paste the block below into a model
with web access. It returns one test object ready to append to a subject's
`tests` array in `data/subjects/<subject>.json`.

| Placeholder | What to put | Example |
|---|---|---|
| `{{SUBJECT}}` | Subject name, as it appears in the sidebar | `Методологія наукових досліджень` |
| `{{LINKS}}` | One URL per line | `https://example.edu/lecture-4` |
| `{{TEST_NAME}}` | Name for the new test | `AI_7` |
| `{{COUNT}}` | How many questions | `50` |

Optional: change `LANGUAGE` and `OPTION KEYS` in the prompt if the subject is
not Ukrainian. The shipped banks use Cyrillic `А`/`Б`/`В`/`Г` — note these are
Cyrillic letters, not the Latin `A`/`B`/`B`/`T` they resemble.

After generating, validate before committing:

```bash
python3 -c "
import json
from pretested.library import validate_subject
test = json.load(open('new_test.json', encoding='utf-8'))
errors = validate_subject({'name': 'x', 'tests': [test]})
print('\n'.join(errors) if errors else 'valid')
"
```

---

````
You are writing a multiple-choice exam bank for the subject
"{{SUBJECT}}".

SOURCE MATERIAL
Read these pages and base every question strictly on what they contain:

{{LINKS}}

Do not use outside knowledge to introduce facts that are absent from these
sources. If the sources do not contain enough material for {{COUNT}}
questions at the required difficulty, produce fewer and say so explicitly
after the JSON — do not pad with invented or filler content.

TASK
Write {{COUNT}} multiple-choice questions as a single test named
"{{TEST_NAME}}".

LANGUAGE: write every question and option in the same language as the source
material.
OPTION KEYS: use exactly four options per question, keyed "А", "Б", "В", "Г"
(Cyrillic letters).

DIFFICULTY — the central requirement
The test must be genuinely hard, while every question has exactly one
defensible answer. These two goals pull against each other; the resolution is
that difficulty must come from the distractors being *attractive*, never from
the question being *vague*.

Build each distractor using one of these techniques, and vary them:
  1. A true statement from the source that does not answer the question asked.
  2. The right concept at the wrong scope or level of abstraction.
  3. A correct relationship with the causal direction reversed.
  4. A statement correct except for one quantifier (only / all / always /
     necessarily / sufficient vs necessary).
  5. The definition of an adjacent term that students routinely confuse with
     the one asked about.
  6. A widespread misconception that the source explicitly corrects.
  7. A statement that is half right: one accurate clause joined to a false one.

AMBIGUITY — hard constraints, apply to every question
  - Exactly one option fully satisfies the stem. Before finalising a question,
    check each of the other three and be able to state the specific sentence
    in the source that rules it out. If you cannot, rewrite it.
  - The correct option must be correct on the source's own terms, not by
    being the "best of a bad set" or requiring a judgement call about which
    answer is *better*. Never ask which option is "most important", "best",
    or "most appropriate" unless the source itself ranks them explicitly.
  - No "all of the above", "none of the above", "both А and Б", or any option
    that refers to other options.
  - No negative stems ("which is NOT...") unless the negation is unavoidable;
    if used, the negated word must be capitalised.
  - No question may depend on information from another question.
  - Nothing may hinge on trivia such as a date, page number or author name
    unless the source treats that fact as substantive.

AVOIDING GIVEAWAYS — the correct answer must not be guessable from form alone
  - Make all four options closely similar in length, grammatical structure,
    and level of detail. A conspicuously longer or more hedged option is the
    most common tell; do not let the correct one be the longest.
  - Do not concentrate absolute words (always, never, every, no) in the
    distractors and cautious words (may, can, often) in the correct option.
  - Distribute the correct key roughly evenly across А, Б, В and Г. Do not
    follow a repeating pattern.
  - Every option must be grammatically consistent with the stem, so no option
    can be eliminated for reading awkwardly.

OUTPUT FORMAT
Return exactly one JSON object in a ```json code block, and nothing else
inside that block. Shape:

```json
{
  "id": "slug_of_the_test_name",
  "name": "{{TEST_NAME}}",
  "questions": [
    {
      "question": "Full question text, ending in a question mark?",
      "options": [
        {"А": "text of the first option"},
        {"Б": "text of the second option"},
        {"В": "text of the third option"},
        {"Г": "text of the fourth option"}
      ],
      "answer": "В"
    }
  ]
}
```

Format rules, all enforced by the app's validator:
  - "id" is lowercase, with every non-alphanumeric character replaced by an
    underscore. It must be unique among the tests in this subject.
  - Each entry in "options" is an object with EXACTLY ONE key. Four separate
    objects, not one object with four keys.
  - Option keys are unique within a question.
  - "answer" holds exactly one of that question's option keys.
  - No trailing commas, no comments, no markdown inside any string.
  - Question text must be plain text: no HTML, no LaTeX, no line breaks.
  - Every question's text must be unique, and must not repeat the wording of
    a question already in this subject. The app identifies a question by a
    hash of its text, so two questions worded identically are treated as the
    same question and share one result history.

AFTER THE JSON
Outside the code block, add a short verification table with one row per
question: the question number, the key you marked correct, and for each of
the three distractors a few words naming the sentence or idea in the source
that rules it out. Keep this out of the JSON — the app has no field for it.
````

---

## Variant: a complete, importable subject

To generate a whole new subject that the app can import directly through
**Import bank…**, replace the OUTPUT FORMAT shape above with this, and change
"one test" to the number of tests you want:

```json
{
  "id": "slug_of_subject_name",
  "name": "{{SUBJECT}}",
  "tests": [
    {"id": "test_1", "name": "Test 1", "questions": []}
  ]
}
```

Save it as `<id>.json` and import it, or drop it in `data/subjects/` to ship
it with the app.
