# Copyright (C) 2022, Benjamin Drung <bdrung@posteo.de>
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

"""Test copy-mtime."""

import unittest
import unittest.mock

from .scripts.copy_mtime import main


class TestMain(unittest.TestCase):
    """Test main function."""

    @unittest.mock.patch("os.path.getmtime")
    @unittest.mock.patch("os.utime")
    def test_main(self, utime_mock, getmtime_mock):
        """Test main with mocked API calls."""
        mtime = 1648903471.3638148
        getmtime_mock.return_value = mtime
        self.assertEqual(main(["source", "target"]), 0)
        getmtime_mock.assert_called_once_with("source")
        utime_mock.assert_called_once_with("target", (mtime, mtime))
