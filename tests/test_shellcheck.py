# Copyright (C) 2021-2022, Benjamin Drung <bdrung@posteo.de>
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

"""Run shellcheck on Shell code."""

import subprocess
import sys
import unittest

from tests import unittest_verbosity

SHELL_SCRIPTS = ["bzr2git", "git-archive", "webcam-capture"]


def run_shellcheck(shell_scripts: list[str], verbose: bool) -> str:
    """Run shellcheck on given list of shell scripts."""
    cmd = ["shellcheck"] + shell_scripts
    if verbose:
        sys.stderr.write(f"Running following command:\n{' '.join(cmd)}\n")
    shellcheck = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, close_fds=True
    )

    if shellcheck.returncode == 0:
        return ""

    msgs = []
    if shellcheck.stderr:  # pragma: no cover
        msgs.append(
            f"shellcheck exited with code {shellcheck.returncode} and"
            f" has unexpected output on stderr:\n{shellcheck.stderr.decode().rstrip()}"
        )
    if shellcheck.stdout:
        msgs.append(f"shellcheck found issues:\n{shellcheck.stdout.decode().rstrip()}")
    if not msgs:  # pragma: no cover
        msgs.append(
            f"shellcheck exited with code {shellcheck.returncode} "
            f"and has no output on stdout or stderr."
        )
    return "\n".join(msgs)


class ShellcheckTestCase(unittest.TestCase):
    """
    This unittest class provides a test that runs the shellcheck
    on Shell source code.
    """

    def test_shellcheck(self) -> None:
        """Test: Run shellcheck on Shell source code."""
        msg = run_shellcheck(SHELL_SCRIPTS, unittest_verbosity() >= 2)
        if msg:
            self.fail(msg)  # pragma: no cover
