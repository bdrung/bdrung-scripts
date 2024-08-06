#!/usr/bin/python3

"""
Find packages that are affected by the py3clean bug.

Setup for the schoot:

```
apt install -y locales
locale-gen fr_FR
```

Bug: https://bugs.launchpad.net/ubuntu/+source/python3-defaults/+bug/2075337
"""

import argparse
import collections.abc
import dataclasses
import logging
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time
import typing

import apt

LOG_FORMAT = "%(name)s %(levelname)s: %(message)s"
__script_name__ = os.path.basename(sys.argv[0]) if __name__ == "__main__" else __name__


@dataclasses.dataclass
# pylint: disable=too-many-instance-attributes
class Package:
    """Represents a package row in the database."""

    name: str
    source: str
    section: str
    install_affected: bool | None
    install_duration: float | None
    install_version: str | None
    remove_affected: bool | None
    remove_duration: float | None

    @classmethod
    def from_sql(cls, row: typing.Any) -> typing.Self:
        """Convert a database row into a Package object."""
        return cls(
            name=row[0],
            source=row[1],
            section=row[2],
            install_affected=bool(row[3]) if row[3] is not None else None,
            install_duration=row[4],
            install_version=row[5],
            remove_affected=bool(row[6]) if row[6] is not None else None,
            remove_duration=row[7],
        )

    def needs_proccessing(self) -> bool:
        """Check if the packege needs to be analyzed."""
        return self.install_duration is None or (
            self.install_affected is True and self.remove_duration is None
        )

    def needs_retry(self, retry_limit: float) -> bool:
        """Check if the packege failed to analyze and needs a retry."""
        return (
            self.install_affected is None
            and self.install_duration is not None
            and self.install_duration <= retry_limit
            or (
                self.remove_affected is None
                and self.remove_duration is not None
                and self.remove_duration <= retry_limit
            )
        )


class Package2Affection(collections.abc.Mapping[str, bool | None]):
    """Package to Affection mapping.

    A backing SQLite database is open on __init__ and closed on object
    deletion. The data is stored in unnormalized form for creation speed
    and code simplicity.

    If database_file is set to `None` an in-memory database will be used.
    """

    def __init__(self, database_file: pathlib.Path | None = None) -> None:
        self.database_file = database_file
        self.connection = self._connect()
        self.logger = logging.getLogger(__script_name__)
        if (
            database_file is None
            or not database_file.exists()
            or database_file.stat().st_size == 0
        ):
            self._create_tables()

    def __del__(self) -> None:
        """Close the SQLite database connection on object deletion."""
        if hasattr(self, "connection"):
            self.connection.close()

    def _connect(self) -> sqlite3.Connection:
        """Opens a connection to the SQLite database file.

        If database_file is set to `None` an in-memory database will be used.
        """
        if self.database_file is None:
            database = ":memory:"
        else:
            database = f"file://{self.database_file.absolute()}"
        connection = sqlite3.connect(database)
        if hasattr(connection, "autocommit"):
            connection.autocommit = False
        return connection

    def _create_tables(self) -> None:
        """Create SQLite database tables."""
        cursor = self.connection.cursor()
        cursor.execute(
            "CREATE TABLE package_affected("
            "  package TEXT PRIMARY KEY UNIQUE NOT NULL,"
            "  source TEXT NOT NULL,"
            "  section TEXT NOT NULL,"
            "  install_affected INTEGER,"
            "  install_duration REAL,"
            "  install_version TEXT,"
            "  remove_affected INTEGER,"
            "  remove_duration REAL)"
        )
        self.connection.commit()

    def __getitem__(self, key: str) -> bool | None:
        cursor = self.connection.execute(
            "SELECT install_affected FROM package_affected WHERE package = ?", (key,)
        )
        found = cursor.fetchone()
        if found is None:
            raise KeyError(key)
        if found[0] is None:
            return None
        return bool(found[0])

    def __iter__(self) -> collections.abc.Iterator[str]:
        cursor = self.connection.execute(
            "SELECT package FROM package_affected ORDER BY package ASC"
        )
        while True:
            found = cursor.fetchone()
            if found is None:
                return
            yield found[0]

    def __len__(self) -> int:
        cursor = self.connection.execute("SELECT COUNT(*) FROM package_affected")
        found = cursor.fetchone()
        assert found is not None
        return int(found[0])

    def add_package(self, package: str, source: str, section: str) -> None:
        """Add an unprocessed package to the database."""
        self.connection.execute(
            "INSERT INTO package_affected (package, source, section) VALUES (?, ?, ?)",
            (package, source, section),
        )
        self.connection.commit()

    def add_from_apt_cache(self, architecture: str) -> int:
        """Add all Ubuntu packages from the APT cache to the database."""
        cache = apt.Cache()
        cursor = self.connection.cursor()
        added = 0
        for package in cache:
            if package.architecture() != architecture:
                continue
            for version in package.versions:
                for origin in version.origins:
                    if origin.origin == "Ubuntu":
                        break
                else:
                    # No Ubuntu origin found
                    continue
                cursor.execute(
                    "INSERT INTO package_affected (package, source, section) "
                    "VALUES (?, ?, ?) "
                    "ON CONFLICT(package) DO NOTHING",
                    (package.name, version.source_name, origin.component),
                )
                added += 1
                break
        self.connection.commit()
        self.logger.info("Added %i packages from the APT cache.", added)
        return added

    def iter_unprocessed(
        self, package_regex: str, section_regex: str, retry: float
    ) -> collections.abc.Iterator[str]:
        """Iterate over all packages that hasn't been processed yet."""
        package_re = re.compile(package_regex)
        section_re = re.compile(section_regex)
        cursor = self.connection.execute(
            "SELECT * FROM package_affected ORDER BY section ASC, package ASC"
        )
        while True:
            found = cursor.fetchone()
            if found is None:
                return
            package = Package.from_sql(found)
            if (
                (package.needs_proccessing() or package.needs_retry(retry))
                and package_re.search(package.name)
                and section_re.search(package.section)
            ):
                yield package.name

    def set_install(
        self, package: str, affected: bool | None, duration: float, version: str | None
    ) -> None:
        """Set result from install test in datadase."""
        self.connection.execute(
            "UPDATE package_affected "
            "SET install_affected = ?, install_duration = ?, install_version = ? "
            "WHERE package = ?",
            (affected, duration, version, package),
        )
        self.connection.commit()

    def set_remove(self, package: str, affected: bool | None, duration: float) -> None:
        """Set result from remove test in datadase."""
        self.connection.execute(
            "UPDATE package_affected SET remove_affected = ?, remove_duration = ? "
            "WHERE package = ?",
            (affected, duration, package),
        )
        self.connection.commit()

    def is_empty(self) -> bool:
        """Check if the database is empty."""
        cursor = self.connection.execute("SELECT 1 FROM package_affected LIMIT 1")
        return cursor.fetchone() is None

    def process_package(self, package: str, chroot: str, timeout: float) -> None:
        """Analyze the package.

        Try to install the package with ISO-8859-1 locale. If that fails,
        try to remove the package to check if the failure comes from the
        package or from a dependency.
        """
        with SchrootSession(chroot) as session:
            start = time.perf_counter()
            install_affected = session.install(package, timeout)
            duration = time.perf_counter() - start
            self.logger.info(
                "Installed %s in %f s. Result: %s", package, duration, install_affected
            )
            if install_affected is None:
                # Installation failed
                self.set_install(package, install_affected, duration, None)
                return

            if install_affected is False:
                version = session.get_version(package)
                self.set_install(package, install_affected, duration, version)
                return

        # Installation failed. Now install with UTF-8
        with SchrootSession(chroot) as session:
            start = time.perf_counter()
            install_affected = session.install(package, timeout, encoding="utf-8")
            duration = time.perf_counter() - start

            if install_affected is None:
                # Even installation with UTF-8 failed
                self.set_install(package, True, duration, None)
                return

            version = session.get_version(package)
            self.set_install(package, True, duration, version)

            start = time.perf_counter()
            remove_affected = session.remove(package, timeout)
            duration = time.perf_counter() - start
            self.set_remove(package, remove_affected, duration)

    # pylint: disable-next=too-many-arguments
    def process_matching(
        self, chroot: str, only: str, section: str, retry: float, timeout: float
    ) -> None:
        """Process all packages that have a matching name and section."""
        for package in self.iter_unprocessed(only, section, retry):
            self.process_package(package, chroot, timeout)


class SchrootSession:
    """Context manager to hold a schroot session."""

    def __init__(self, chroot: str) -> None:
        self.chroot = chroot
        self.session: str | None = None
        self.logger = logging.getLogger(__script_name__)

    def __enter__(self) -> typing.Self:
        process = subprocess.run(
            ["schroot", "-c", self.chroot, "-b"],
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
        )
        self.session = process.stdout.strip()
        return self

    def __exit__(self, exc_type: typing.Any, exc_val: typing.Any, exc_tb: typing.Any) -> None:
        assert self.session
        subprocess.run(["schroot", "-c", self.session, "-e"], check=True)
        self.session = None

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
        # pylint: disable=too-many-arguments
        """Run schroot session."""
        assert self.session is not None
        schroot_cmd = ["schroot", "-c", self.session, "-d", directory, "-u", user, "-r"]
        if cmd:
            schroot_cmd.append("--")
            schroot_cmd += cmd
        self.logger.info("Running: %s", " ".join(schroot_cmd))
        return subprocess.run(
            schroot_cmd, check=check, stdin=stdin, stdout=stdout, timeout=timeout
        )

    def install(self, package: str, timeout: float, encoding: str = "ISO-8859-1") -> bool | None:
        """Return True if UnicodeDecodeError found in output."""
        self.logger.info("Checking '%s'...", package)
        cmd = [
            "env",
            f"LC_ALL=fr_FR.{encoding}",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "install",
            "--reinstall",
            "-y",
            "--no-install-recommends",
            package,
        ]
        try:
            process = self.run(cmd, check=False, stdout=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        if b"UnicodeDecodeError: 'utf-8' codec can't decode byte" in process.stdout:
            return True
        if process.returncode != 0:
            self.logger.error(
                "Failed to install:\n%s\n%s\n%s",
                f"{'>' * 40} {package} {'>' * 40}",
                process.stdout.decode(encoding),
                f"{'<' * 40} {package} {'<' * 40}",
            )
            return None
        return False

    def get_version(self, package: str) -> str:
        """Determine the version of the installed package."""
        dpkg = self.run(["dpkg", "-s", package], stdout=subprocess.PIPE)
        version = re.search(r"^Version:\s+(.*)$", dpkg.stdout.decode(), re.M)
        assert version
        return version.group(1)

    def remove(self, package: str, timeout: float) -> bool | None:
        """Return True if UnicodeDecodeError found in output."""
        self.logger.info("Remove '%s'...", package)
        cmd = [
            "env",
            "LC_ALL=fr_FR.ISO-8859-1",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "remove",
            "-y",
            package,
        ]
        try:
            process = self.run(cmd, check=False, stdout=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None
        if b"UnicodeDecodeError: 'utf-8' codec can't decode byte" in process.stdout:
            return True
        if process.returncode != 0:
            self.logger.error(
                "Failed to remove:\n%s\n%s\n%s",
                f"{'>' * 40} {package} {'>' * 40}",
                process.stdout.decode("ISO-8859-1"),
                f"{'<' * 40} {package} {'<' * 40}",
            )
            return None
        return False


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default="amd64")
    parser.add_argument("-c", "--chroot", default="noble-locale")
    parser.add_argument(
        "-u", "--update", action="store_true", help="Update list of package from the APT cache"
    )
    parser.add_argument(
        "-o",
        "--only",
        default=".*",
        help="Only process the package that match the given regular expression",
    )
    parser.add_argument(
        "-s",
        "--section",
        default=".*",
        help="Only process the package from sections that match the given regular expression",
    )
    parser.add_argument(
        "-t", "--timeout", type=float, default=3600.0, help="Timeout for each install run"
    )
    parser.add_argument(
        "--retry",
        type=float,
        default=0.0,
        help="Retry failed packages that took less than the given seconds.",
    )
    parser.add_argument("--db", default="affected.sqlite3")
    args = parser.parse_args()
    logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

    package2affection = Package2Affection(pathlib.Path(args.db))
    if args.update or package2affection.is_empty():
        package2affection.add_from_apt_cache(args.arch)
    package2affection.process_matching(
        args.chroot, args.only, args.section, args.retry, args.timeout
    )


if __name__ == "__main__":
    _main()
