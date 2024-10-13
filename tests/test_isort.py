# Copyright (C) 2021, Benjamin Drung <bdrung@debian.org>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Run isort to check if Python import definitions are sorted."""

import subprocess
import sys
import unittest

from . import get_source_files, unittest_verbosity


class IsortTestCase(unittest.TestCase):
    """
    This unittest class provides a test that runs isort to check if
    Python import definitions are sorted. The list of source files
    is provided by the get_source_files() function.
    """

    def test_isort(self) -> None:
        """Test: Run isort on Python source code."""
        cmd = ["isort", "--check-only", "--diff"] + get_source_files()
        if unittest_verbosity() >= 2:
            sys.stderr.write(f"Running following command:\n{' '.join(cmd)}\n")
        process = subprocess.run(cmd, capture_output=True, check=False, text=True)

        if process.returncode != 0:  # pragma: no cover
            self.fail(
                f"isort found unsorted Python import definitions:\n"
                f"{process.stdout.strip()}"
            )
