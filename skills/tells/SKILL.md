---
name: tells
description: Run after writing or editing prose that will be published (README, docs, release notes, blog post, LinkedIn post, commit messages) to catch the habits of machine-written text in English or Turkish, then fix the lines it flags.
---

# tells

`tells.py` lives at the root of this plugin, two folders above this file. If it isn't there (for example the skill was copied on its own), download it:

```
curl -sO https://raw.githubusercontent.com/alidoganerr/tells/main/tells.py
```

## When

After you've written or changed text that will be published. Skip it for chat replies and throwaway notes.

## How

1. Run it on the files you touched: `python3 tells.py README.md docs/`. For text that isn't in a file yet, save it as a `.md` file first. Add `--git` to check commit messages on the current branch.
2. Each line of output is `path:line:col: rule: detail`. Exit code 0 means nothing was found.
3. Fix each flagged line by saying the same thing in plainer words:
   - don't swap one stock word for another stock word
   - don't add facts, numbers, names or experiences that weren't there
   - replace an em dash with a comma, colon, full stop or brackets
   - in Turkish, turn "-mektedir / -maktadır" chains into "-iyor / -ır"
4. Run it again. Stop when it's clean or when the remaining hits are deliberate; mark those with `tells: ignore` on the same line.

A hit is a reason to reread a line, not proof that something is wrong. If a word on the list is the right word (a "robust" estimator in statistics, say), keep it. <!-- tells: ignore -->

`python3 tells.py --rules` lists every rule.
