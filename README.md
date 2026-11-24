# tells

Points out the habits that make text and code read as machine-written, in English and Turkish. It doesn't rewrite anything and it doesn't guess who wrote what. It lists the lines worth a second look.

<!-- tells: off -->
```
$ cat notes.md
# Release notes

We delve into a robust new parser — faster and simpler.

Bu sürümde hatalar giderilmektedir ve testler güncellenmektedir.

I hope this helps!

$ python3 tells.py notes.md
notes.md:3:4: stock-phrase: "delve"
notes.md:3:17: stock-phrase: "robust"
notes.md:3:35: em-dash: em dash; a comma, colon or full stop usually reads better
notes.md:5:47: tr-mektedir: giderilmektedir, güncellenmektedir
notes.md:7:1: chat-leftover: "I hope this helps"
```
<!-- tells: on -->

It's meant for a last pass before publishing a README, a post or a repo. Some hits will be fine as they are; treat the output as a reading list.

## Running it

Python 3.9+, standard library only. Download `tells.py` or clone the repo, then:

```
python3 tells.py README.md
python3 tells.py src/ docs/
python3 tells.py --git .
python3 tells.py --json . > findings.json
python3 tells.py --rules
```

Each finding is `path:line:col: rule: detail`. The exit code is 1 when anything turns up.

## In Claude Code

The repo is also a Claude Code plugin with a `tells` skill. After writing or editing something you'll publish, the agent runs the checker and fixes the flagged lines without inventing anything new.

```
/plugin marketplace add alidoganerr/tells
/plugin install tells@tells
```

The skill is in `skills/tells/SKILL.md` if you want to copy it somewhere else.

## In CI

GitHub Action:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0          # only needed for git: true
- uses: alidoganerr/tells@v0.1.0
  with:
    paths: README.md docs
    ignore: em-dash
    git: true
```

pre-commit:

```yaml
- repo: https://github.com/alidoganerr/tells
  rev: v0.1.0
  hooks:
    - id: tells
```

## What it looks at

`.md`, `.markdown`, `.txt` and `.rst` files are read as prose. Fenced code blocks are skipped.

In `.py` files the prose rules run on comments and docstrings, and a few code habits are checked on top: docstrings that only repeat the name, banner comments, comments that say what the next line already says, very long test names, and files where nearly every function has a docstring. String literals are left alone.

With `--git` it also reads the commit messages on the current branch and flags assistant credit lines.

For Turkish there's a separate guide with examples: [yapay-zeka-turkcesi](https://github.com/alidoganerr/yapay-zeka-turkcesi). tells checks the parts of it that can be counted.

Turn rules off with `--ignore em-dash,stock-phrase`. To skip one line, put `tells: ignore` on it (in Markdown, `<!-- tells: ignore -->` keeps it invisible). A whole section can go between `<!-- tells: off -->` and `<!-- tells: on -->`.

The phrase lists sit at the top of `tells.py`. They're short on purpose and you'll likely want to edit them.

## Caveats

People write em dashes too, and every word on the stock list has honest uses. A clean run doesn't prove anything either.

The Turkish list is shorter than the English one. Matching is plain text, so a reworded phrase gets through.

Tests: `python3 -m unittest`. One of them runs the checker on this repo, so this README has to pass it as well.

Ali Doğaner. MIT licensed.
