# Copyright (C) 2022, Benjamin Drung <bdrung@ubuntu.com>
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

"""Test userlint."""

import subprocess
import tempfile
import unittest
import unittest.mock

from .scripts.userlint import (
    Author,
    Committer,
    Person,
    is_valid_email,
    is_valid_name,
    main,
)


class TestPerson(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test Person class."""

    def setUp(self) -> None:
        self.valid = {Author("Benjamin Drung", "bdrung@ubuntu.com")}

    def test_name_is_email(self) -> None:
        person = Author("bdrung@ubuntu.com", "")
        self.assertEqual(
            person.suggested_mailmap(self.valid),
            "Benjamin Drung <bdrung@ubuntu.com> bdrung@ubuntu.com <>",
        )

    def test_name_contains_email(self) -> None:
        person = Author("Benjamin Drung bdrung@ubuntu.com", "")
        self.assertEqual(
            person.suggested_mailmap(set()),
            "Benjamin Drung <bdrung@ubuntu.com> Benjamin Drung bdrung@ubuntu.com <>",
        )

    def test_empty_email_existing_name(self) -> None:
        person = Author("Benjamin Drung", "")
        self.assertEqual(
            person.suggested_mailmap(self.valid),
            "Benjamin Drung <bdrung@ubuntu.com> Benjamin Drung <>",
        )

    def test_invalid_email(self) -> None:
        person = Author("bdrung@ubuntu.com", "bdrung@localhost")
        self.assertEqual(
            person.suggested_mailmap(self.valid),
            "Benjamin Drung <bdrung@ubuntu.com> bdrung@ubuntu.com <bdrung@localhost>",
        )

    def test_invalid_name(self) -> None:
        person = Author("bdrung", "bdrung@ubuntu.com")
        self.assertEqual(
            person.suggested_mailmap(self.valid),
            "Benjamin Drung <bdrung@ubuntu.com> bdrung <bdrung@ubuntu.com>",
        )

    def test_multiple_email_addresses(self) -> None:
        self.valid.add(Author("Benjamin Drung", "bdrung@debian.org"))
        person = Author("Benjamin Drung", "bdrung@localhost")
        with self.assertLogs(level="WARNING") as context_manager:
            self.assertEqual(person.suggested_mailmap(self.valid), None)
        self.assertEqual(len(context_manager.output), 1, context_manager.output)
        self.assertRegex(
            context_manager.output[0],
            "^WARNING.*Found 2 matching persons for name 'Benjamin Drung': .*$",
        )

    def test_repr(self) -> None:
        # pylint: disable=eval-used
        person = Person("Benjamin Drung", "bdrung@ubuntu.com", "function")
        self.assertEqual(eval(repr(person)), person)

    def test_repr_author(self) -> None:
        # pylint: disable=eval-used
        author = Author("Benjamin Drung", "bdrung@ubuntu.com")
        self.assertEqual(eval(repr(author)), author)

    def test_repr_committer(self) -> None:
        # pylint: disable=eval-used
        committer = Committer("Benjamin Drung", "bdrung@ubuntu.com")
        self.assertEqual(eval(repr(committer)), committer)

    def test_sort(self) -> None:
        person1 = Author("John Doe", "john.doe@example.com")
        person2 = Committer("Benjamin Drung", "bdrung@ubuntu.com")
        self.assertEqual(sorted([person1, person2]), [person2, person1])


class TestUserlint(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test userlint."""

    PREFIX = "userlint-"

    def test_valid_email_address(self) -> None:
        self.assertTrue(is_valid_email("bdrung@ubuntu.com"))

    def test_empty_email_address(self) -> None:
        self.assertFalse(is_valid_email(""))

    def test_email_at_localhost(self) -> None:
        self.assertFalse(is_valid_email("iain@intrepid"))

    def test_valid_user_name(self) -> None:
        self.assertTrue(is_valid_name("Benjamin Drung"))

    def test_empty_user_name(self) -> None:
        self.assertFalse(is_valid_name(""))

    def test_user_name_is_email(self) -> None:
        self.assertFalse(is_valid_name("bdrung@ubuntu.com"))

    def test_user_name_is_nickname(self) -> None:
        self.assertFalse(is_valid_name("mathiaz"))

    @staticmethod
    def _commit(directory: str, message: str, author: str | None = None) -> None:
        cmd = ["git", "commit", "--allow-empty", "-m", message]
        if author:
            cmd.append(f"--author={author}")
        subprocess.run(cmd, check=True, cwd=directory)

    def _prepare_git_repository(self, directory: str, name: str, email: str) -> None:
        subprocess.run(["git", "init", "-b", "main"], check=True, cwd=directory)
        subprocess.run(["git", "config", "user.name", name], check=True, cwd=directory)
        subprocess.run(
            ["git", "config", "user.email", email], check=True, cwd=directory
        )
        self._commit(directory, "Initial commit")

    def test_main(self) -> None:
        with tempfile.TemporaryDirectory(prefix=self.PREFIX) as tmpdir:
            self._prepare_git_repository(tmpdir, "Benjamin Drung", "bdrung@ubuntu.com")
            with self.assertLogs(level="INFO") as context_manager:
                self.assertEqual(main(["-d", tmpdir]), 0)

        self.assertEqual(len(context_manager.output), 1, context_manager.output)
        self.assertRegex(
            context_manager.output[0],
            "^INFO:.*:Checked 1 commits, found 1 valid and no invalid entries.$",
        )

    def test_main_invalid(self) -> None:
        with tempfile.TemporaryDirectory(prefix=self.PREFIX) as tmpdir:
            self._prepare_git_repository(tmpdir, "bdrung@ubuntu.com", "")
            with self.assertLogs(level="INFO") as context_manager:
                self.assertEqual(main(["-d", tmpdir]), 1)

        self.assertEqual(len(context_manager.output), 1, context_manager.output)
        self.assertRegex(
            context_manager.output[0],
            "^WARNING:.*:Checked 1 commits, found 0 valid and 1 invalid entries:\n"
            "bdrung@ubuntu.com <>$",
        )

    def test_main_suggest_mailmap(self) -> None:
        with tempfile.TemporaryDirectory(prefix=self.PREFIX) as tmpdir:
            self._prepare_git_repository(tmpdir, "Benjamin Drung", "bdrung@ubuntu.com")
            self._commit(tmpdir, "Second commit", "bdrung@ubuntu.com <>")
            with self.assertLogs(level="INFO") as context_manager:
                self.assertEqual(main(["-d", tmpdir]), 1)

        self.assertEqual(len(context_manager.output), 2, context_manager.output)
        self.assertRegex(
            context_manager.output[0],
            "^WARNING:.*:Checked 2 commits, found 1 valid and 1 invalid entries:\n"
            "bdrung@ubuntu.com <>$",
        )
        self.assertRegex(
            context_manager.output[1],
            "^INFO:.*:Suggested mailmap:\n"
            "Benjamin Drung <bdrung@ubuntu.com> bdrung@ubuntu.com <>$",
        )
