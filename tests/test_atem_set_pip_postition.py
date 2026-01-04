# Copyright (C) 2025-2026, Benjamin Drung <bdrung@posteo.de>
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

"""Test atem-set-pip-position."""

import pathlib
import unittest
import unittest.mock

from .scripts.atem_set_pip_position import POSITIONS, Config, parse_args

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestAtemSetPipPostition(unittest.TestCase):
    """Test atem-set-pip-position."""

    def test_parse_args_all_parameters(self) -> None:
        """Test parse_args() with all parameters given."""
        config, position = parse_args(
            ["-m", "hostname", "-i", "3", "-k", "7", "-b", "420", "-s", "153", "tr"]
        )
        self.assertEqual(config, Config("hostname", 3, 7, 420, 153))
        self.assertEqual(position, POSITIONS[2])

    def test_parse_args_list_positions(self) -> None:
        """Test parse_args() with --list-positions."""
        _, position = parse_args(["--list-positions"])
        self.assertIsNone(position)

    def test_parse_args_missing_mixer(self) -> None:
        """Test parse_args() with missing mixer argument."""
        with self.assertRaisesRegex(SystemExit, "^2$"):
            parse_args(["-c", str(FIXTURES / "empty.toml"), "tl"])

    def test_parse_args_missing_position(self) -> None:
        """Test parse_args() with missing position argument."""
        with self.assertRaisesRegex(SystemExit, "^2$"):
            parse_args(["-m", "hostname"])

    def test_parse_args_mixer_and_position(self) -> None:
        """Test parse_args() with mixer and position given."""
        config, position = parse_args(["-m", "hostname", "br"])
        self.assertEqual(config, Config("hostname", 0, 0, 300, 200))
        self.assertEqual(position, POSITIONS[4])

    def test_parse_args_unknown_position(self) -> None:
        """Test parse_args() with unknown position argument."""
        with self.assertRaisesRegex(SystemExit, "^2$"):
            parse_args(["-m", "hostname", "foobar"])

    def test_parse_args_with_config(self) -> None:
        """Test parse_args() with providing a config file."""
        config, position = parse_args(
            ["-c", str(FIXTURES / "atem.toml"), "-b", "100", "tl"]
        )
        self.assertEqual(config, Config("hostname", 0, 0, 100, 400))
        self.assertEqual(position, POSITIONS[0])
