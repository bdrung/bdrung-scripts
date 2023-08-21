# Copyright (C) 2023, Benjamin Drung <bdrung@posteo.de>
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

"""Test dpkg-which."""

import contextlib
import io
import unittest
import unittest.mock

from .scripts.dpkg_which import dpkg_which, main


class TestDpkgWhich(unittest.TestCase):
    """Test dpkg-which."""

    maxDiff = None

    def test_main_success(self) -> None:
        """Test successfully finding the command."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            returncode = main(["ls"])
        self.assertEqual(stdout.getvalue(), "coreutils: /bin/ls\n")
        self.assertEqual(returncode, 0)

    def test_main_failure(self) -> None:
        """Test not finding the command."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            returncode = main(["non-existing-binary"])
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(returncode, 1)

    def test_main_partially_success(self) -> None:
        """Test finding only one of two commands."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            returncode = main(["non-existing-binary", "sort"])
        self.assertEqual(stdout.getvalue(), "coreutils: /usr/bin/sort\n")
        self.assertEqual(returncode, 1)

    @unittest.mock.patch("shutil.which")
    def test_manually_installed_binary(self, which_mock: unittest.mock.MagicMock) -> None:
        """Test command installed outside of dpkg."""
        which_mock.return_value = "/sbin/manually-installed-binary"
        self.assertEqual(dpkg_which("manually-installed-binary"), None)
