# Pretested

A GTK4 desktop app for drilling multiple-choice exam banks. Questions are
grouped into **subjects**, each holding one or more **tests**. The repo ships
one subject, *Методологія наукових досліджень*, with 8 tests (660 questions). It shuffles
questions and options on every attempt, can reveal a single answer or score a
whole test, remembers your results between sessions, and can re-serve exactly
the questions you got wrong.

## Running it

```bash
nix run                  # build and run
nix build                # build only; binary at ./result/bin/pretested
nix develop              # dev shell (python + pygobject, gtk4, pytest, xvfb-run)
nix develop -c python -m pretested
```

Outside the dev shell `import gi` will fail: PyGObject needs the GTK4
typelibs on `GI_TYPELIB_PATH`.

## Tests

The quiz logic, bank loading and results store import no GTK, so the suite
runs without a display.

```bash
nix develop -c pytest                       # the whole suite
nix develop -c pytest tests/test_attempt.py # one file
nix develop -c pytest -k locks              # one pattern
nix flake check                             # the suite, via the flake
```

## Controls

| Key | Action |
|---|---|
| `1`–`8` | Pick an option by position |
| `А`/`Б`/`В`/`Г` | Pick an option by its printed letter |
| `←` / `→` | Previous / next question |
| `Return` | Check the current answer |
| `Ctrl+Return` | Submit the test |

Checking an answer reveals it and **locks that question for good** — it is a
practice aid, not a hint you can take back. Only *Reset Test* clears it.

The grid on the right colours every question: unvisited, visited, answered,
correct, incorrect. *Retry wrong* builds an attempt from the questions whose
most recent answer was wrong, either within the current subject or across all
of them. Answering one correctly drops it from that pool; missing it again puts
it back.

## Where things live

| What | Path |
|---|---|
| Bundled question banks | `data/subjects/*.json` in the repo, installed to `$out/share/pretested/subjects/` |
| Your imported banks | `$XDG_DATA_HOME/pretested/subjects/` (usually `~/.local/share/pretested/subjects/`) |
| Your results | `$XDG_DATA_HOME/pretested/results.json` |

Bundled banks are read-only; the writable directory holds only what you add or
accumulate. A user file **shadows** a bundled one with the same filename, so
dropping your own `ai.json` into the user directory replaces the shipped one
wholesale. Set `PRETESTED_DATA_DIR` to point the app at a different bundled
directory.

Earlier versions copied the bank into `~/.config/pretested/tests.json` once and
then read only from there, which meant updated banks could never reach an
existing install. That file is now obsolete: on first run anything you had
added by hand is rescued into an "Imported" subject and the file is renamed to
`tests.json.migrated`. It is never deleted, and you can remove it yourself once
you are happy.

## Adding a subject

Either press **Import bank…** in the sidebar and pick a JSON file, or write one
into `data/subjects/` to ship it with the app. The format:

```json
{
  "id": "ai",
  "name": "AI",
  "tests": [
    {
      "id": "ai_1",
      "name": "AI_1",
      "questions": [
        {
          "question": "Which of these is true?",
          "options": [
            {"А": "first option"},
            {"Б": "second option"},
            {"В": "third option"},
            {"Г": "fourth option"}
          ],
          "answer": "Б"
        }
      ]
    }
  ]
}
```

- Each option is a **single-key object** mapping an answer key to its text, and
  `answer` holds one of those keys. Keys are arbitrary strings — the shipped
  banks use Cyrillic `А`/`Б`/`В`/`Г`, not ASCII.
- `id` is optional on subjects and tests and falls back to a slug of the name.
- Questions carry no id. Identity is a hash of the question text, which is what
  attaches your results to a question across shuffles and reordering. Rewording
  a question deliberately starts its history over. The same question appearing
  in two tests therefore shares one history, even if the distractors differ —
  answering it correctly in one counts for the other.

Imports are validated before being accepted, and a malformed file is reported
with the specific problem rather than being half-loaded.

## Tooling

```bash
python3 tools/export_tests.py data/subjects/*.json > output.txt
```

Writes every test as printable text followed by its answer key, for revising on
paper. `tools/split_tests.py` is the one-shot migration that produced
`data/subjects/` from the original flat `tests.json`; it is kept only so that
step stays reproducible. It no longer reproduces `data/subjects/` in full —
`AI_6` was recovered later from a legacy `~/.config/pretested/tests.json` and
merged in by hand.
