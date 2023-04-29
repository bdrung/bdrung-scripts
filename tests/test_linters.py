# Copyright (C) 2022, Benjamin Drung <bdrung@posteo.de>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""Test linter test cases."""

import contextlib
import io
import os
import tempfile
import unittest
import unittest.mock

from tests.test_shellcheck import run_shellcheck


class TestLinters(unittest.TestCase):
    """
    This unittest class tests the linter test cases.
    """

    def test_shellcheck_succeeds(self):
        """shellchecks succeeds on shell code."""
        with tempfile.TemporaryDirectory() as tempdir:
            shell = os.path.join(tempdir, "test.sh")
            with open(shell, "w", encoding="utf-8") as shell_file:
                shell_file.write("#!/bin/sh\n")

            self.assertEqual(run_shellcheck([shell], False), "")

    def test_shellcheck_succeeds_verbose(self):
        """shellchecks succeeds on shell code in verbose mode."""
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as tempdir:
            shell = os.path.join(tempdir, "test.sh")
            with open(shell, "w", encoding="utf-8") as shell_file:
                shell_file.write("#!/bin/sh\n")

            with contextlib.redirect_stderr(stderr):
                self.assertEqual(run_shellcheck([shell], True), "")
            self.assertEqual(
                stderr.getvalue(), f"Running following command:\nshellcheck {shell}\n"
            )

    def test_shellcheck_fails(self):
        """shellchecks fails on shell code."""
        with tempfile.TemporaryDirectory() as tempdir:
            shell = os.path.join(tempdir, "test.sh")
            with open(shell, "w", encoding="utf-8") as shell_file:
                shell_file.write("#!/bin/sh\necho $HOME\n")

            self.assertEqual(
                run_shellcheck([shell], False),
                f"""shellcheck found issues:

In {shell} line 2:
echo $HOME
     ^---^ SC2086 (info): Double quote to prevent globbing and word splitting.

Did you mean:{' '}
echo "$HOME"

For more information:
  https://www.shellcheck.net/wiki/SC2086 -- Double quote to prevent globbing ...""",
            )
