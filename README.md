# tells

A small checker for the habits that give machine-written text and code away: em dashes in every other sentence, stock phrases, leftovers from a chat window, a bold label on every bullet, docstrings that repeat the function name, test names that read like sentences, assistant credit lines in commit messages. It knows English and Turkish.

It's meant for a last pass before publishing a README or pushing a repo. It doesn't decide who wrote something. It points at lines worth a second read, and some of them will be fine as they are.

## Running it

Python 3.9+, standard library only.

```
python3 tells.py README.md
python3 tells.py src/ docs/
python3 tells.py --git .
python3 tells.py --json . > findings.json
python3 tells.py --rules
```

Each finding is one line, `path:line:col: rule: detail`. The exit code is 1 when anything turns up, so it can run in CI.

## What it looks at

`.md`, `.txt` and `.rst` files are read as prose. Fenced code blocks are skipped.

In `.py` files the prose rules run on comments and docstrings, and a few code habits are checked on top: docstrings that only repeat the name, banner comments, comments that say what the next line already says, very long test names, and files where nearly every function has a docstring. String literals are left alone.

With `--git` it also reads the commit messages on the current branch.

`--rules` prints the list. Turn rules off with `--ignore em-dash,stock-phrase`. To skip a single line, put `tells: ignore` on it. In Markdown a whole section can go between `<!-- tells: off -->` and `<!-- tells: on -->`.

The phrase lists sit at the top of `tells.py`. They're short on purpose and you'll likely want to edit them.

## Caveats

People write em dashes too, and every word on the stock list has honest uses. A clean run doesn't prove anything either. Treat the output as a reading list.

The Turkish list is shorter than the English one. Matching is plain text, so it won't catch a phrase that has been reworded.

Tests: `python3 -m unittest`. One of them runs the checker on this repo, so this README has to pass it as well.

Ali Doğaner. MIT licensed.
