"""Test find_affected.py."""

import pathlib
import sqlite3
import subprocess
import tempfile
import typing
import unittest
import unittest.mock
from unittest.mock import MagicMock

import apt

from find_affected import Package2Affection, SchrootSession


class SchrootSessionMock(SchrootSession):
    """Mock the SchrootSession class."""

    def __init__(self, chroot: str) -> None:
        print(f"*** init chroot = {chroot}")
        super().__init__(chroot)
        self.run_calls: list[list[str]] = []

    def __enter__(self) -> typing.Self:
        print("*** enter")
        self.session = "mocked-schroot-session"
        return self

    def __exit__(self, exc_type: typing.Any, exc_val: typing.Any, exc_tb: typing.Any) -> None:
        assert self.session
        self.session = None

    # pylint: disable-next=too-many-arguments
    def run(
        self,
        cmd: list[str],
        check: bool = True,
        directory: str = "/",
        stdin: typing.IO[bytes] | None = None,
        stdout: int | None = None,
        timeout: float | None = None,
        user: str = "root",
    ) -> subprocess.CompletedProcess[bytes]:
        """Run schroot session."""
        assert self.session is not None
        return subprocess.CompletedProcess(MagicMock, 0, b"Version: 1.0-2", b"")


class TestPackage2Affection(unittest.TestCase):
    """Test Package2Affection class."""

    @unittest.mock.patch("apt.Cache", spec=apt.Cache)
    def test_add_from_apt_cache(self, cache_mock: MagicMock) -> None:
        """Test add_from_apt_cache() method."""
        ppa_origin = MagicMock(component="main", origin="bdrung")
        main_origin = MagicMock(component="main", origin="Ubuntu")
        cloud_init = MagicMock()
        cloud_init.architecture.return_value = "amd64"
        cloud_init.name = "cloud-init"
        cloud_init.versions = [
            MagicMock(
                source_name="cloud-init",
                version="24.1.3-0ubuntu3.3",
                origins=[ppa_origin, main_origin],
            )
        ]
        my_custom_package = MagicMock()
        my_custom_package.architecture.return_value = "amd64"
        my_custom_package.name = "custom-package"
        my_custom_package.versions = [
            MagicMock(source_name="custom-source", version="1.0", origins=[ppa_origin])
        ]
        dpkg_dev = MagicMock()
        dpkg_dev.architecture.return_value = "amd64"
        dpkg_dev.name = "dpkg-dev"
        dpkg_dev.versions = [
            MagicMock(source_name="dpkg", version="1.22.6ubuntu11", origins=[ppa_origin]),
            MagicMock(source_name="dpkg", version="1.22.6ubuntu6", origins=[main_origin]),
        ]
        acl_i386 = MagicMock()
        acl_i386.architecture.return_value = "i386"
        acl_i386.name = "acl:i386"
        dpkg_dev.versions = [
            MagicMock(source_name="acl", version="2.3.2-1build1", origins=[main_origin])
        ]
        cache_mock.return_value.__iter__.return_value = iter(
            [my_custom_package, dpkg_dev, acl_i386, cloud_init]
        )

        package2affection = Package2Affection()
        self.assertEqual(package2affection.add_from_apt_cache("amd64"), 2)
        self.assertEqual(dict(package2affection), {"cloud-init": None, "dpkg-dev": None})
        self.assertEqual(len(package2affection), 2)

    def test_iter_unprocessed(self) -> None:
        """Test iter_unprocessed() method."""
        package2affection = Package2Affection()
        package2affection.add_package("cloud-init", "cloud-init", "main")
        package2affection.add_package("dash", "dash", "main")
        package2affection.add_package("python3-keystone", "keystone", "main")
        package2affection.set_install("dash", False, 1.0, "0.5.12-6ubuntu5")
        package2affection.set_install("python3-keystone", None, 20.0, None)
        unprocessed = list(package2affection.iter_unprocessed(".*", ".*", 0.0))
        self.assertEqual(unprocessed, ["cloud-init"])
        retry = list(package2affection.iter_unprocessed(".*", ".*", 60.0))
        self.assertEqual(retry, ["cloud-init", "python3-keystone"])

    @unittest.mock.patch("find_affected.SchrootSession", SchrootSessionMock)
    def test_process_package_unaffected(self) -> None:
        """Test process_package() for an unaffected package."""
        package2affection = Package2Affection()
        package2affection.add_package("dash", "dash", "main")
        package2affection.process_package("dash", "noble-locale", 60.0)
        self.assertEqual(package2affection["dash"], False)

    def test_create_and_reopen(self) -> None:
        """Test openening an existing database."""
        with tempfile.NamedTemporaryFile(suffix=".sqlite3") as db_file:
            package2affection = Package2Affection(pathlib.Path(db_file.name))
            self.assertEqual(dict(package2affection), {})
            self.assertTrue(package2affection.is_empty())
            package2affection.add_package("cloud-init", "cloud-init", "main")
            package2affection.add_package("dash", "dash", "main")
            package2affection.set_install("dash", False, 1.0, "0.5.12-6ubuntu5")
            self.assertFalse(package2affection.is_empty())
            del package2affection

            package2affection = Package2Affection(pathlib.Path(db_file.name))
            self.assertEqual(dict(package2affection), {"cloud-init": None, "dash": False})
            self.assertFalse(package2affection.is_empty())

    @unittest.mock.patch("sqlite3.connect")
    def test_clean_deletion_on_failure(self, connect_mock: MagicMock) -> None:
        """Test clean deletion on __init__ failure."""
        connect_mock.side_effect = sqlite3.OperationalError
        with self.assertRaises(sqlite3.OperationalError):
            Package2Affection(pathlib.Path("/non-existing.sqlite3"))
