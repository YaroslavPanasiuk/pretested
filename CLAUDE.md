# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Pretested" — a GTK4 (PyGObject) desktop quiz app for practising multiple-choice tests. Questions live in `tests.json` (Ukrainian-language university test banks). Packaged with Nix flakes; there is no test suite, linter, or CI.

## Commands

```bash
nix develop            # dev shell with python3+pygobject3, gtk4, gobject-introspection
python3 main.py        # run from the repo (inside the dev shell)

nix build              # builds ./result -> $out/bin/pretested
nix run                # build + run

python3 tmp.py tests.json > output.txt   # export all tests to printable text + answer keys
```

Running outside `nix develop` generally fails: PyGObject needs `gi` plus the GTK4 typelibs on `GI_TYPELIB_PATH`.

## Architecture

Three modules, strict model/view split:

- `main.py` — `Gtk.Application` subclass (app id `com.pretested`). Owns the `TestModel`, loads `style.css` into the default `Gdk.Display` at startup, creates the window on activate.
- `model.py` — `TestModel`: all quiz state and logic (shuffling, answers, locking, scoring). No GTK imports.
- `ui.py` — `TestWindow`: all widgets and signal handlers. Calls into the model and re-reads its state; it never stores quiz state of its own.

The UI has exactly two refresh entry points, and handlers should call one of them rather than mutating widgets directly:

- `rebuild_test_ui()` — after a test change/reset: re-styles the test-selector row and rebuilds the question-number nav grid, then calls `load_question_ui()`.
- `load_question_ui()` — after navigation or answering: tears down and rebuilds the option `Gtk.CheckButton`s for the current question, sets feedback/sensitivity, and calls `update_nav_grid_styles()`.

Option radio grouping is done by `set_group(first_button)` on freshly created check buttons each time, because the options box is rebuilt from scratch per question.

### Data file and config dir — important

`TestModel.__init__` copies the bundled `tests.json` to `$XDG_CONFIG_HOME/pretested/tests.json` (default `~/.config/pretested/`) **only if that file does not already exist**, then reads exclusively from there. So editing the repo's `tests.json` has no effect on an already-run install — delete the copy under `~/.config/pretested/` to pick up changes. The Nix build installs the default to `$out/share/pretested/tests.json`, which `_ensure_config_exists` finds via a `../share/pretested/` path relative to the script in `$out/bin`.

### tests.json schema

```json
{"tests": [{"name": "...", "questions": [
  {"question": "...",
   "options": [{"А": "text"}, {"Б": "text"}],
   "answer": "Г"}
]}]}
```

Each option is a single-key dict mapping an answer key to its text; `answer` holds the key. Keys are Cyrillic letters (А/Б/В/Г) in the current data — don't assume ASCII. Code that iterates options uses the `for key, val in opt.items()` idiom throughout.

### Answer-reveal / locking model

An answer is revealed when `model.submitted` is true **or** the question index is in `model.checked_questions` (per-question "Check" button). Revealing is one-way and locks that question: `set_answer()` refuses writes for checked or submitted questions, and `load_question_ui()` desensitizes its options. `reset_test()` is the only way back.

`reset_test()` reshuffles questions *and* each question's options via `copy.deepcopy` of the source questions, so the original `tests_data` is never mutated. Because of the shuffle, question/option indices are only valid within one attempt.

### Random mixed tests

"Rand 20/50/100/all" call `load_random_mixed_test(sample_size)` (`-1` = all questions from every test), which pools questions across all tests and installs a synthetic `current_test` dict. `ui.py` fakes `model.current_test_idx` to the random button's position in `self.test_buttons` so the selector highlight works — `current_test_idx` is therefore not a valid index into `tests_data["tests"]` while a random mix is active.

## Styling

All visual styling is in `style.css`, applied via `add_css_class` / `set_css_classes`. `update_nav_grid_styles()` rewrites the whole class list per button (`grid-nav-btn` + one of `correct`/`incorrect`/`answered`/`visited`/`unvisited`, plus `active`), so new nav-grid states must be added there, not appended elsewhere.

## Untracked scratch files

`output.txt`, `temp.sh`, `temp.txt` are generated/experimental dumps of the question bank, not part of the app. Leave them alone; don't treat `temp.sh` as a build script.
