#!/usr/bin/env python3
"""Point out the habits that make text and code read as machine-written.

    python3 tells.py README.md src/
    python3 tells.py --git            # also look at commit messages
    python3 tells.py --json docs/ > report.json

English and Turkish. Every hit is a line worth rereading.
"""

import argparse
import ast
import io
import json
import os
import re
import subprocess
import sys
import tokenize

TEXT_EXT = {".md", ".markdown", ".txt", ".rst"}
CODE_EXT = {".py"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env", "dist", "build", ".tox"}

EM_DASH = "—"

# Phrases that turn up far more in generated prose than in anything people write.
EN_PHRASES = [
    "delve", "delving", "tapestry", "testament to", "it's worth noting", "it is worth noting",
    "in today's fast-paced", "ever-evolving", "seamless", "seamlessly", "robust", "leverage",
    "leveraging", "comprehensive", "navigate the complexities", "game-changer", "game changer",
    "unlock the power", "unleash", "elevate your", "embark on", "in the realm of",
    "a myriad of", "plethora", "in conclusion", "first and foremost", "rest assured",
    "cutting-edge", "state-of-the-art", "pivotal", "meticulous", "meticulously",
    "underscores", "harness the power", "foster", "holistic", "synergy",
]
TR_PHRASES = [
    "elbette", "kesinlikle", "bu bağlamda", "önemli bir rol oynar", "önemli bir rol oynamaktadır",
    "sonuç olarak", "unutmamak gerekir ki", "göz önünde bulundurulduğunda", "kapsamlı bir",
    "sorunsuz bir şekilde", "hayati önem taşır", "günümüzün hızla değişen", "dikkat çekmek isterim",
    "şunu belirtmek gerekir", "belirtmek isterim ki", "altını çizmek gerekir", "son derece önemlidir",
    "en iyi şekilde", "bir sonraki seviyeye", "yolculuğunuzda", "keşfedelim",
    "çığır açan", "devrim niteliğinde", "oyunun kurallarını değiştiren", "bir göz atalım",
    "derinlemesine dalalım", "devreye giriyor", "günün sonunda", "dürüst olmak gerekirse",
    "büyük önem taşımaktadır", "kritik öneme sahiptir", "hızla gelişen dünyada", "dijital çağda",
    "değer katmak", "fark yaratmak",
]
# Leftovers from a chat window.
CHAT_LEFTOVERS = [
    "as an ai", "i hope this helps", "certainly!", "great question", "here's a breakdown",
    "let me know if you", "feel free to", "umarım yardımcı olur", "harika bir soru",
    "başka bir sorunuz olursa", "yardımcı olabileceğim başka",
]
# Lines that say outright who wrote it.
ASSISTANT_MARKS = [
    re.compile(r"co-authored-by:\s*(claude|chatgpt|gpt|copilot|gemini)", re.I),
    re.compile(r"generated (with|by) \[?(claude|chatgpt|copilot|gemini)", re.I),
    re.compile(r"claude\.ai/(code|chat)/", re.I),
    re.compile(r"\U0001F916\s*generated", re.I),
]

NARRATING = re.compile(
    r"^#\s*(import|initiali[sz]e|create|set|get|return|loop|iterate|call|define|increment|"
    r"check if|append|add|print|open|close|update)\b[^.]{0,40}$", re.I)
NOT_ONLY = re.compile(r"(?<![\wçğıöşü])(not (?:only|just) .{1,60}? but|"
                      r"sadece .{1,60}? değil,? (?:aynı zamanda|ayrıca)|"
                      r"yalnızca .{1,60}? değil,? (?:aynı zamanda|ayrıca))", re.I)
BANNER = re.compile(r"^\s*#\s*([-=#*~_]{3,}|.*\s[-=]{3,}\s*$)")
BOLD_LEAD = re.compile(r"^\s*[-*+]\s+\*\*[^*]+\*\*")
EMOJI_HEADING = re.compile(r"^\s*#{1,6}\s.*[\U0001F300-\U0001FAFF☀-➿]")
WORD = re.compile(r"[a-zçğıöşü]+", re.I)
# one "-maktadır" verb is fine; two in the same paragraph start to sound like a report
MEKTEDIR = re.compile(r"[a-zçğıöşü]+m[ae]kt[ae]d[ıi]r(?:lar|ler)?(?![a-zçğıöşü])", re.I)

ALL_RULES = {
    "em-dash": "em dash; a comma, colon or full stop usually reads better",
    "stock-phrase": "stock phrase",
    "chat-leftover": "chat reply leftover",
    "assistant-mark": "says it was written by an assistant",
    "bold-lead-list": "list where every item starts with a bold label",
    "emoji-heading": "emoji in a heading",
    "long-test-name": "test name reads like a sentence",
    "banner-comment": "section banner comment",
    "narrating-comment": "comment that repeats the next line",
    "echo-docstring": "docstring that repeats the function name",
    "docstring-everywhere": "nearly every function has a docstring",
    "not-only": "\"not only X but Y\" / \"sadece X değil, aynı zamanda Y\"",
    "tr-mektedir": "-mektedir/-maktadır twice in one paragraph; -iyor or -ır usually reads more natural",
}


class Finding:
    __slots__ = ("path", "line", "col", "rule", "text")

    def __init__(self, path, line, col, rule, text):
        self.path, self.line, self.col, self.rule, self.text = path, line, col, rule, text

    def as_dict(self):
        return {"path": self.path, "line": self.line, "col": self.col, "rule": self.rule, "text": self.text}

    def __str__(self):
        return "%s:%d:%d: %s: %s" % (self.path, self.line, self.col, self.rule, self.text)


def _phrase_re(phrases):
    # \b doesn't know Turkish letters, so spell the word boundary out
    body = "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))
    return re.compile(r"(?<![\wçğıöşüÇĞİÖŞÜ])(%s)(?![\wçğıöşüÇĞİÖŞÜ])" % body, re.I)


STOCK = _phrase_re(EN_PHRASES + TR_PHRASES)
CHAT = _phrase_re(CHAT_LEFTOVERS)


def _tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def check_prose(path, lines, first_line=1):
    """Prose rules. lines is either plain strings, numbered from first_line,
    or (line_no, text) pairs when the lines aren't contiguous."""
    out = []
    bold_items = []
    para_mk = []  # -maktadır verbs seen in the current paragraph
    prev_n = None
    for i, item in enumerate(lines):
        n, line = item if isinstance(item, tuple) else (first_line + i, item)
        if not line.strip() or (prev_n is not None and n != prev_n + 1):
            para_mk = []
        prev_n = n
        if "tells: ignore" in line:
            continue
        low = _tr_lower(line)
        col = line.find(EM_DASH)
        if col >= 0:
            out.append(Finding(path, n, col + 1, "em-dash", ALL_RULES["em-dash"]))
        # show the words as written; low is only for matching
        for m in STOCK.finditer(low):
            out.append(Finding(path, n, m.start() + 1, "stock-phrase", '"%s"' % line[m.start():m.end()]))
        for m in CHAT.finditer(low):
            out.append(Finding(path, n, m.start() + 1, "chat-leftover", '"%s"' % line[m.start():m.end()]))
        for rx in ASSISTANT_MARKS:
            m = rx.search(line)
            if m:
                out.append(Finding(path, n, m.start() + 1, "assistant-mark", line.strip()[:80]))
                break
        if BOLD_LEAD.match(line):
            bold_items.append(n)
        if EMOJI_HEADING.match(line):
            out.append(Finding(path, n, 1, "emoji-heading", ALL_RULES["emoji-heading"]))
        m = NOT_ONLY.search(low)
        if m:
            out.append(Finding(path, n, m.start() + 1, "not-only", line[m.start():m.end()][:60]))
        for m in MEKTEDIR.finditer(low):
            para_mk.append(line[m.start():m.end()])
            if len(para_mk) == 2:
                out.append(Finding(path, n, m.start() + 1, "tr-mektedir", ", ".join(para_mk)))
    # one or two bold labels are fine; a whole run of them is the pattern
    if len(bold_items) >= 3:
        out.append(Finding(path, bold_items[0], 1, "bold-lead-list",
                           "%d list items start with a bold label" % len(bold_items)))
    return out


def markdown_prose_lines(text):
    """Yield (line_no, line) outside fenced code blocks and <!-- tells: off --> sections."""
    fence = None
    off = False
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("<!--") and "tells: off" in s:
            off = True
            continue
        if s.startswith("<!--") and "tells: on" in s:
            off = False
            continue
        if fence:
            if s.startswith(fence):
                fence = None
            continue
        if s.startswith("```") or s.startswith("~~~"):
            fence = s[:3]
            continue
        if not off:
            yield n, line


def check_text_file(path, text):
    return check_prose(path, list(markdown_prose_lines(text)))


def _name_words(name):
    return [w for w in re.split(r"_+|(?<=[a-z])(?=[A-Z])", name) if w]


def _echoes_name(name, doc):
    words = [w.lower() for w in _name_words(name) if len(w) > 2]
    if not words:
        return False
    first = doc.strip().splitlines()[0].lower() if doc.strip() else ""
    said = set(WORD.findall(first))
    hits = sum(1 for w in words if w in said or w.rstrip("s") in said)
    # short docstring that is mostly the name again
    return hits >= max(1, len(words) * 2 // 3) and len(first.split()) <= len(words) + 4


def check_code_file(path, text):
    out = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [Finding(path, exc.lineno or 1, 1, "parse-error", "not valid Python: %s" % exc.msg)]

    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    with_doc = 0
    for fn in funcs:
        doc = ast.get_docstring(fn)
        if fn.name.startswith("test_"):
            if len(fn.name) > 45 or fn.name.count("_") > 7:
                out.append(Finding(path, fn.lineno, fn.col_offset + 1, "long-test-name", fn.name))
        if doc is None:
            continue
        with_doc += 1
        if _echoes_name(fn.name, doc):
            out.append(Finding(path, fn.body[0].lineno, 1, "echo-docstring",
                               "%s: %s" % (fn.name, doc.strip().splitlines()[0][:60])))
        start = fn.body[0].lineno
        out.extend(check_prose(path, doc.splitlines(), start))

    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        out.extend(check_prose(path, mod_doc.splitlines(), tree.body[0].lineno))

    real = [f for f in funcs if not f.name.startswith("test_") and not f.name.startswith("__")]
    if len(real) >= 8:
        documented = sum(1 for f in real if ast.get_docstring(f))
        if documented / len(real) >= 0.9:
            out.append(Finding(path, 1, 1, "docstring-everywhere",
                               "%d of %d functions have a docstring" % (documented, len(real))))

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        tokens = []
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        line, col = tok.start
        c = tok.string
        if "tells: ignore" in c or c.startswith("#!"):
            continue
        if BANNER.match(c):
            out.append(Finding(path, line, col + 1, "banner-comment", c.strip()[:60]))
        elif NARRATING.match(c):
            out.append(Finding(path, line, col + 1, "narrating-comment", c.strip()[:60]))
        for f in check_prose(path, [c], line):
            f.col += col
            out.append(f)
    return out


def check_commits(repo="."):
    """Reads `git log` on the current branch."""
    try:
        raw = subprocess.run(["git", "-C", repo, "log", "--format=%h%x00%B%x01"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("tells: can't read git log in %s (%s)" % (repo, exc))
    out = []
    for entry in raw.split("\x01"):
        entry = entry.strip("\n")
        if not entry:
            continue
        sha, _, msg = entry.partition("\x00")
        for i, line in enumerate(msg.splitlines(), 1):
            for f in check_prose("commit " + sha, [line], i):
                if f.rule in ("assistant-mark", "chat-leftover", "stock-phrase", "em-dash"):
                    out.append(f)
    return out


def walk(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(files):
                    yield os.path.join(root, name)
        else:
            yield p


def check_path(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in TEXT_EXT and ext not in CODE_EXT:
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return [Finding(path, 1, 1, "unreadable", str(exc))]
    if ext in CODE_EXT:
        return check_code_file(path, text)
    return check_text_file(path, text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tells", description="Find the habits of machine-written text and code.")
    ap.add_argument("paths", nargs="*", help="files or folders (.md .txt .rst .py)")
    ap.add_argument("--git", action="store_true", help="also check commit messages of the current repo")
    ap.add_argument("--ignore", default="", help="comma separated rule names to skip")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--rules", action="store_true", help="list the rules and exit")
    args = ap.parse_args(argv)

    if args.rules:
        for name, what in ALL_RULES.items():
            print("%-22s %s" % (name, what))
        return 0
    if not args.paths and not args.git:
        ap.error("give at least one path, or --git")

    skip = {r.strip() for r in args.ignore.split(",") if r.strip()}
    unknown = skip - set(ALL_RULES)
    if unknown:
        ap.error("unknown rule(s): %s" % ", ".join(sorted(unknown)))

    findings = []
    for path in walk(args.paths):
        findings.extend(check_path(path))
    if args.git:
        findings.extend(check_commits(args.paths[0] if args.paths and os.path.isdir(args.paths[0]) else "."))
    findings = [f for f in findings if f.rule not in skip]
    findings.sort(key=lambda f: (f.path, f.line, f.col))

    if args.json:
        json.dump([f.as_dict() for f in findings], sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        for f in findings:
            print(f)
        if findings:
            print("%d finding(s)" % len(findings), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
