# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Pretested" — a GTK4 (PyGObject) desktop quiz app for drilling multiple-choice
exam banks, grouped into subjects that each hold several tests. The repo ships
one subject with 8 tests (660 Ukrainian-language university questions); the
subject layer exists so more can be added. Packaged with Nix flakes. See
`README.md` for user-facing behaviour, the bank format, and key bindings.

## Commands

```bash
nix develop                       # dev shell: python+pygobject, gtk4, pytest, xvfb-run
nix develop -c python -m pretested  # run from the source tree
nix develop -c pytest             # test suite (no display needed)
nix develop -c pytest -k locks    # a single pattern
nix build && ./result/bin/pretested
nix flake check                   # builds the package and runs the suite
```

`import gi` fails outside `nix develop` — PyGObject needs the GTK4 typelibs on
`GI_TYPELIB_PATH`. The dev shell ships `xvfb-run`, which is how to exercise the
GTK layer without a window appearing on the user's screen:

```bash
nix develop -c xvfb-run -a python3 some_gtk_script.py   # set GDK_BACKEND=x11, unset WAYLAND_DISPLAY
```

## Architecture

`pretested/` is a package with a hard split: **only `ui.py` and `app.py` import
GTK.** `library.py`, `attempt.py` and `results.py` are plain Python, which is
what lets the suite run headlessly. Keep it that way — it is the property the
tests depend on.

| Module | Responsibility |
|---|---|
| `app.py` | `Gtk.Application`; loads CSS, builds the library and results store, reports a fatal `DataError` in a `Gtk.AlertDialog` |
| `library.py` | Bank discovery, validation, parsing; `Subject`/`Test`/`Question`; question ids; legacy migration; import |
| `attempt.py` | One sitting: shuffled questions, answers, lock/reveal rules, scoring |
| `results.py` | `ResultsStore` — attempt log and per-question outcomes, atomically written |
| `ui.py` | `TestWindow` — sidebar, test row, question pane, nav grid, key controller, import dialog |

### The three UI refresh entry points

Handlers should call one of these rather than poking widgets directly. Each
cascades into the next:

- `rebuild_subject_ui()` — sidebar rows, after the library changes (e.g. import).
- `rebuild_test_ui()` — the test button row, after the subject changes. Also
  refreshes score badges and retry-button sensitivity.
- `load_question_ui()` — tears down and rebuilds the option `Gtk.CheckButton`s
  for the current question, sets feedback and sensitivity, then calls
  `update_nav_grid_styles()`.

Option radio grouping is redone with `set_group(first_button)` on freshly
created buttons each time, because the options box is rebuilt per question.

`update_nav_grid_styles()` rewrites each button's **whole** class list
(`grid-nav-btn` plus one of `correct`/`incorrect`/`answered`/`visited`/
`unvisited`, plus `active`), so a new nav-grid state must be added there — and
needs a matching rule in `style.css`, or it renders identically to its
neighbours.

`self.active_token` identifies the live selector button, e.g. `("test", "ai_1")`
or `("random", 50)`. Route every test start through `select_test()` so the
highlight cannot drift from the running attempt.

### Data locations

| What | Where |
|---|---|
| Bundled banks | `data/subjects/*.json`; installed to `$out/share/pretested/subjects/` |
| User banks | `$XDG_DATA_HOME/pretested/subjects/` |
| Results | `$XDG_DATA_HOME/pretested/results.json` |

`bundled_subjects_dirs()` walks up from the package directory looking for
`data/subjects` or `share/pretested/subjects`, so the same code resolves a
source checkout and a Nix store path. `PRETESTED_DATA_DIR` overrides it.

User files **shadow** bundled ones by filename stem. `~/.config/pretested/` no
longer holds bank data; a one-shot idempotent migration rescues hand edits from
the old `tests.json` and renames it aside.

### Question identity

`question_id()` is `sha1(question_text)[:12]`. Content-addressed deliberately:
it needed no edits to the shipped questions and survives shuffling and
reordering, which is what keeps results attached to a question. Rewording a
question resets its history.

The same question text in two tests intentionally shares one id and one
history — the shipped banks contain such a pair (AI_5 and AI_6 ask it with
different distractors). So the invariant under test is that distinct texts
map to distinct ids, i.e. no hash collisions; it is *not* that every question
instance is unique.

### Lock and reveal rules

A question is revealed when the attempt is submitted **or** its index is in
`attempt.checked`. Revealing is one-way and locks that question: `set_answer()`
refuses writes and the options are desensitized. `can_check()` additionally
requires an answer to be selected — checking an unanswered question used to lock
it and score it wrong with no escape. `reset()` is the only way back.

### Bank format gotchas

Each option is a single-key dict; `answer` holds the key. Shipped keys are
Cyrillic `А`/`Б`/`В`/`Г` — do not assume ASCII. Keyboard option selection is
therefore **positional** (`1`–`8`) with the printed letter as a secondary path,
so the app stays drillable on a Latin-only layout.

### Attempt modes

`MODE_TEST`, `MODE_RANDOM`, `MODE_WRONG` (`attempt.py`). Mode only affects
presentation and recording; the quiz flow is identical. A retry pool passes
`test_key=None` so it logs no score against any test — `results.py` skips the
attempt log for a falsy key but still records per-question outcomes.

`wrong_question_ids()` returns questions whose **most recent** answer was wrong,
so fixing one removes it from the pool and missing it again restores it.

## Conventions

- Results are derived state: a missing or corrupt `results.json` degrades to
  empty rather than stopping the app. The banks are the valuable data.
- `ResultsStore.save()` writes to a temp file and `os.replace()`s it.
- Never `sys.exit()` from library code — raise `DataError`; `app.py` surfaces it
  in a dialog, since nobody sees stderr from a desktop launcher.
- Every `install` in the flake's `postInstall` is load-bearing; do not add
  `|| true`, which previously turned missing files into a silently broken
  package.
