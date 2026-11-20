import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import tells


def rules(findings):
    return [f.rule for f in findings]


class ProseTests(unittest.TestCase):
    def test_em_dash(self):
        out = tells.check_text_file("a.md", "One thing — and another.\n")
        self.assertEqual(rules(out), ["em-dash"])
        self.assertEqual(out[0].col, 11)

    def test_en_and_tr_phrases(self):
        text = "Let's delve into it.\nBu bağlamda önemli bir rol oynar.\n"
        found = [f.text for f in tells.check_text_file("a.md", text)]
        self.assertIn('"delve"', found)
        self.assertIn('"bu bağlamda"', found)
        self.assertIn('"önemli bir rol oynar"', found)

    def test_turkish_capitals(self):
        # capital first letter, and İ lowered the Turkish way
        out = tells.check_text_file("a.md", "Elbette! KESİNLİKLE.\n")
        self.assertEqual([f.text for f in out], ['"elbette"', '"kesinlikle"'])

    def test_no_match_inside_words(self):
        self.assertEqual(tells.check_text_file("a.md", "fosterage, delves? no: robustness\n"), [])

    def test_chat_leftover(self):
        out = tells.check_text_file("a.md", "I hope this helps.\n")
        self.assertEqual(rules(out), ["chat-leftover"])

    def test_assistant_mark(self):
        out = tells.check_text_file("a.md", "Co-Authored-By: Claude <noreply@anthropic.com>\n")
        self.assertEqual(rules(out), ["assistant-mark"])

    def test_bold_lead_list_needs_three(self):
        two = "- **Fast:** yes\n- **Small:** yes\n"
        three = two + "- **Free:** yes\n"
        self.assertEqual(tells.check_text_file("a.md", two), [])
        self.assertEqual(rules(tells.check_text_file("a.md", three)), ["bold-lead-list"])

    def test_emoji_heading(self):
        self.assertEqual(rules(tells.check_text_file("a.md", "## \U0001F680 Quick start\n")), ["emoji-heading"])

    def test_code_fences_and_off_blocks_skipped(self):
        text = ("```\nwe leverage it — seamlessly\n```\n"
                "<!-- tells: off -->\ndelve\n<!-- tells: on -->\n"
                "plain line\n")
        self.assertEqual(tells.check_text_file("a.md", text), [])

    def test_ignore_comment(self):
        self.assertEqual(tells.check_text_file("a.md", "robust <!-- tells: ignore -->\n"), [])


class CodeTests(unittest.TestCase):
    def check(self, src):
        return tells.check_code_file("m.py", src)

    def test_long_test_name(self):
        src = "def test_parser_rejects_empty_input_when_strict_mode_is_on():\n    pass\n"
        self.assertEqual(rules(self.check(src)), ["long-test-name"])

    def test_short_test_name(self):
        self.assertEqual(self.check("def test_empty_input():\n    pass\n"), [])

    def test_echo_docstring(self):
        src = 'def load_config(path):\n    """Load the config."""\n    return open(path).read()\n'
        self.assertEqual(rules(self.check(src)), ["echo-docstring"])

    def test_useful_docstring_kept(self):
        src = ('def load_config(path):\n'
               '    """Missing keys fall back to defaults; unknown keys are an error."""\n'
               '    return path\n')
        self.assertEqual(self.check(src), [])

    def test_banner_and_narrating(self):
        src = "# ---------- helpers ----------\nx = 1\n# Increment the counter\nx += 1\n# keeps the old order\n"
        self.assertEqual(rules(self.check(src)), ["banner-comment", "narrating-comment"])

    def test_docstring_everywhere(self):
        funcs = "".join('def f%d(a):\n    """Turn a into something else, %d."""\n    return a\n' % (i, i)
                        for i in range(8))
        self.assertIn("docstring-everywhere", rules(self.check(funcs)))

    def test_prose_rules_in_comments(self):
        out = self.check("x = 1  # a robust fix — for now\n")
        self.assertEqual(sorted(rules(out)), ["em-dash", "stock-phrase"])
        self.assertEqual([f.col for f in out if f.rule == "em-dash"], [23])

    def test_strings_are_not_prose(self):
        self.assertEqual(self.check('MSG = "we leverage a robust and seamless pipeline"\n'), [])

    def test_syntax_error(self):
        self.assertEqual(rules(self.check("def (:\n")), ["parse-error"])


class CliTests(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tells.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_folder_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ok.md"), "w", encoding="utf-8") as fh:
                fh.write("Nothing to see.\n")
            self.assertEqual(self.run_main(d)[0], 0)
            with open(os.path.join(d, "bad.md"), "w", encoding="utf-8") as fh:
                fh.write("A seamless experience.\n")
            os.mkdir(os.path.join(d, "node_modules"))
            with open(os.path.join(d, "node_modules", "x.md"), "w", encoding="utf-8") as fh:
                fh.write("delve\n")
            code, out, err = self.run_main(d)
            self.assertEqual(code, 1)
            self.assertIn("bad.md:1:3: stock-phrase", out)
            self.assertNotIn("node_modules", out)
            self.assertIn("1 finding", err)

    def test_json_and_ignore(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("robust — yes\n")
            code, out, _ = self.run_main("--json", p)
            self.assertEqual(sorted(x["rule"] for x in json.loads(out)), ["em-dash", "stock-phrase"])
            code, out, _ = self.run_main("--ignore", "em-dash,stock-phrase", p)
            self.assertEqual((code, out), (0, ""))

    def test_unknown_rule(self):
        with self.assertRaises(SystemExit):
            self.run_main("--ignore", "nope", ".")

    def test_git_messages(self):
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", "-C", d] + list(a), check=True, capture_output=True)
            git("init", "-q")
            git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty",
                "-m", "Fix parser\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
            git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty",
                "-m", "Tidy up")
            found = tells.check_commits(d)
            self.assertEqual(rules(found), ["assistant-mark"])
            self.assertEqual(found[0].line, 3)


class SelfTest(unittest.TestCase):
    def test_repo_passes_its_own_check(self):
        here = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.run([sys.executable, os.path.join(here, "tells.py"), here],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout)


if __name__ == "__main__":
    unittest.main()
