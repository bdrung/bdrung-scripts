# Copyright (C) 2023, Benjamin Drung <bdrung@ubuntu.com>
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

"""Test schroot-wrapper."""

import dataclasses
import getpass
import os
import platform
import subprocess
import tempfile
import typing
import unittest
import unittest.mock

from .scripts.schroot_wrapper import SchrootSession, main, parse_args


@dataclasses.dataclass
class RunMock:
    """Data class to map subprocess.run calls to mocked responses."""

    args: list[str]
    returncode: int
    stdout: typing.Optional[str] = None
    stderr: typing.Optional[str] = None
    call_count: int = 0


def run_side_effect(responses: list[RunMock]):
    """Side effect for subprocess.run mocks.

    The args parameter from the subprocess.run call is looked up in the
    provided `responses` list. If it is found, return the mocked
    CompletedProcess. Otherwise raise `NotImplementedError` stating the
    subprocess.run parameters.
    """

    def _subprocess_run_mock(args, **kwargs) -> subprocess.CompletedProcess:
        for response in responses:
            if response.args == args:
                response.call_count += 1
                return subprocess.CompletedProcess(
                    args, response.returncode, response.stdout, response.stderr
                )
        extra_args = "".join([f", {k}={v!r}" for k, v in kwargs.items()])
        raise NotImplementedError(f"No response specified for subprocess.run({args=}{extra_args})")

    return _subprocess_run_mock


class TestSchrootWrapper(unittest.TestCase):
    """Test schroot-wrapper."""

    PREFIX = "schroot-wrapper-"
    maxDiff = None

    def _assert_all_run_mocks_called(self, run_mocks: list[RunMock]) -> None:
        not_called = [m for m in run_mocks if m.call_count == 0]
        if not not_called:
            return
        self.fail(
            f"Following {len(not_called)} mocks were not called: {not_called}"
        )  # pragma: no cover

    @unittest.mock.patch("subprocess.run")
    def test_install_packages_deb_files(self, run_mock: unittest.mock.MagicMock) -> None:
        """Basic test case for the main function."""
        root_call = ["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r", "--"]
        mocks = [
            RunMock(["schroot", "-c", "jammy", "-b"], 0, "session-id\n"),
            RunMock(root_call + ["apt-get", "update"], 0),
            RunMock(root_call + ["tee", "/root/tzdata_2023c-1_all.deb"], 0),
            RunMock(
                root_call
                + [
                    "apt-get",
                    "install",
                    "--no-install-recommends",
                    "-y",
                    "/root/tzdata_2023c-1_all.deb",
                ],
                0,
            ),
            RunMock(["schroot", "-c", "session-id", "-e"], 0),
        ]
        run_mock.side_effect = run_side_effect(mocks)

        with tempfile.TemporaryDirectory(prefix=self.PREFIX) as tmpdir:
            deb_file = os.path.join(tmpdir, "tzdata_2023c-1_all.deb")
            os.mknod(deb_file)
            with SchrootSession("jammy") as session:
                session.install_packages([deb_file])

        self._assert_all_run_mocks_called(mocks)
        self.assertEqual(run_mock.call_count, len(mocks))

    @unittest.mock.patch("subprocess.run")
    def test_main(self, run_mock: unittest.mock.MagicMock) -> None:
        """Basic test case for the main function."""
        user = getpass.getuser()
        root_call = ["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r", "--"]
        mocks = [
            RunMock(["schroot", "-c", "jammy", "-b"], 0, "session-id\n"),
            RunMock(root_call + ["test", "-d", "/path"], 0),
            RunMock(root_call + ["apt-get", "update"], 0),
            RunMock(
                root_call + ["apt-get", "install", "--no-install-recommends", "-y", "tzdata"], 0
            ),
            RunMock(["schroot", "-c", "session-id", "-d", "/path", "-u", user, "-r"], 0),
            RunMock(["schroot", "-c", "session-id", "-e"], 0),
        ]
        run_mock.side_effect = run_side_effect(mocks)

        self.assertEqual(main(["-p", "tzdata", "-c", "jammy", "-d", "/path"]), 0)
        self._assert_all_run_mocks_called(mocks)
        self.assertEqual(run_mock.call_count, len(mocks))

    @unittest.mock.patch("subprocess.run")
    def test_main_fallback_home_directory(self, run_mock: unittest.mock.MagicMock) -> None:
        """main(): Check fall back to home directory and creating it."""
        root_call = ["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r", "--"]
        mocks = [
            RunMock(["schroot", "-c", "lunar", "-b"], 0, "session-id\n"),
            RunMock(root_call + ["test", "-d", "/non-existing"], 1),
            RunMock(root_call + ["sh", "-c", "realpath ~me"], 0, "/home/me\n"),
            RunMock(root_call + ["test", "-d", "/home/me"], 1),
            RunMock(root_call + ["install", "-d", "-o", "me", "/home/me"], 0),
            RunMock(["schroot", "-c", "session-id", "-d", "/home/me", "-u", "me", "-r"], 37),
            RunMock(["schroot", "-c", "session-id", "-e"], 0),
        ]
        run_mock.side_effect = run_side_effect(mocks)

        self.assertEqual(main(["-c", "lunar", "-d", "/non-existing", "-u", "me"]), 37)
        self._assert_all_run_mocks_called(mocks)
        self.assertEqual(run_mock.call_count, len(mocks))

    @unittest.mock.patch("subprocess.run")
    def test_main_enable_ubuntu_proposed(self, run_mock: unittest.mock.MagicMock) -> None:
        """main(): Enable Ubuntu proposed repository."""
        root_call = ["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r", "--"]
        proposed_sources = (
            "Types: deb\n"
            "URIs: http://archive.ubuntu.com/ubuntu\n"
            "Suites: focal-proposed\n"
            "Components: main universe\n"
        )
        mocks = [
            RunMock(["schroot", "-c", "focal", "-b"], 0, "session-id\n"),
            RunMock(root_call + ["test", "-d", "/root"], 0),
            RunMock(
                root_call
                + [
                    "sh",
                    "-c",
                    f"printf '{proposed_sources}' "
                    f"> /etc/apt/sources.list.d/ubuntu-proposed.sources",
                ],
                0,
            ),
            RunMock(root_call + ["apt-get", "update"], 0),
            RunMock(["schroot", "-c", "session-id", "-d", "/root", "-u", "root", "-r"], 0),
            RunMock(["schroot", "-c", "session-id", "-e"], 0),
        ]
        run_mock.side_effect = run_side_effect(mocks)

        self.assertEqual(main(["-c", "focal", "-d", "/root", "-e", "-u", "root"]), 0)
        self._assert_all_run_mocks_called(mocks)
        self.assertEqual(run_mock.call_count, len(mocks))

    @unittest.mock.patch("subprocess.run")
    def test_main_add_ppa(self, run_mock: unittest.mock.MagicMock) -> None:
        """main(): Add PPA APT source list."""

        root_call = ["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r", "--"]
        apt_install = root_call + ["apt-get", "install", "--no-install-recommends", "-y"]
        mocks = [
            RunMock(["schroot", "-c", "mantic", "-b"], 0, "session-id\n"),
            RunMock(root_call + ["test", "-d", "/"], 0),
            RunMock(root_call + ["apt-get", "update"], 0),
            RunMock(apt_install + ["software-properties-common", "gpg-agent"], 0),
            RunMock(root_call + ["add-apt-repository", "-y", "ppa:bdrung/ppa"], 0),
            RunMock(["schroot", "-c", "session-id", "-d", "/", "-u", "root", "-r"], 42),
            RunMock(["schroot", "-c", "session-id", "-e"], 0),
        ]
        run_mock.side_effect = run_side_effect(mocks)

        self.assertEqual(
            main(["-c", "mantic", "-d", "/", "-u", "root", "--ppa", "bdrung/ppa"]), 42
        )
        self._assert_all_run_mocks_called(mocks)
        self.assertEqual(run_mock.call_count, len(mocks))

    def test_parse_args_minimal(self) -> None:
        """Test parse_args() with minimal arguments."""
        args = parse_args([])
        os_release = platform.freedesktop_os_release()
        self.assertEqual(
            args.__dict__,
            {
                "chroot": os_release["VERSION_CODENAME"],
                "directory": os.getcwd(),
                "enable_proposed": False,
                "packages": [],
                "ppa": [],
                "proposed_components": ["main", "universe"],
                "proposed_uri": "http://archive.ubuntu.com/ubuntu",
                "user": getpass.getuser(),
            },
        )

    def test_parse_args_package_split(self) -> None:
        """Test parse_args() splitting packages."""
        args = parse_args(["-p", "debconf,tzdata", "-p", "distro-info vim"])
        self.assertEqual(args.packages, ["debconf", "tzdata", "distro-info", "vim"])

    def test_parse_args_proposed_components_split(self) -> None:
        """Test parse_args() splitting proposed components."""
        args = parse_args(["--proposed-components", "main contrib non-free"])
        self.assertEqual(args.proposed_components, ["main", "contrib", "non-free"])

    @unittest.mock.patch("subprocess.run")
    def test_run_side_effect_raise_not_implemented_error(
        self, run_mock: unittest.mock.MagicMock
    ) -> None:
        """Test run_side_effect() raises NotImplementedError."""
        run_mock.side_effect = run_side_effect([])
        with self.assertRaisesRegex(
            NotImplementedError, r"for subprocess.run\(args=\['true'\], check=True\)$"
        ):
            subprocess.run(["true"], check=True)
