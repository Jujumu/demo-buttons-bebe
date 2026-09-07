"""Synthetic backup-restore validation tests; no live paths or secrets."""
from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "ops"))

import recovery_restore  # noqa: E402


class FakePolicy:
    def __call__(self, path, kind):
        if kind == "sqlite":
            return path == "/restore/webhook.sqlite3"
        if kind == "file":
            return path == "/restore/.env"
        return False


def make_plan():
    return {
        "schema": 1,
        "release_commit": "0" * 40,
        "recipient_sha256": "1" * 64,
        "entries": [
            {"path": "/restore/.env", "kind": "file"},
            {"path": "/restore/webhook.sqlite3", "kind": "sqlite"},
        ],
    }


def make_sqlite_bytes():
    # A minimal valid SQLite database file: header page from an empty database.
    # Creating a real one with the sqlite3 module is easier and stays portable.
    import sqlite3

    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as handle:
        path = Path(handle.name)
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE demo(value TEXT)")
    connection.commit()
    connection.close()
    data = path.read_bytes()
    path.unlink()
    return data


def make_archive(records_payloads):
    """Build an uncompressed tar with manifest.json and payload members."""
    manifest = {
        "schema": 1,
        "plan": make_plan(),
        "records": [record for record, _ in records_payloads],
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        manifest_bytes = json.dumps(manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(manifest_bytes)
        archive.addfile(info, io.BytesIO(manifest_bytes))
        for (_, payload_bytes), index in zip(records_payloads, range(len(records_payloads))):
            name = f"payload-{index:06d}"
            info = tarfile.TarInfo(name)
            info.size = len(payload_bytes)
            archive.addfile(info, io.BytesIO(payload_bytes))
    return buffer.getvalue()


class RecoveryRestoreTests(unittest.TestCase):
    def setUp(self):
        # private_directory() traverses each path component with O_NOFOLLOW
        # from the filesystem root, so the fixture must live under a real
        # (non-symlinked) absolute prefix. On macOS /tmp is a symlink to
        # /private/tmp, which O_NOFOLLOW correctly refuses.
        self.temp = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _write_archive(self, data):
        archive = self.root / "archive.tar"
        archive.write_bytes(data)
        return archive

    def _destination(self):
        destination = self.root / "restore-output"
        destination.mkdir(mode=0o700)
        return destination

    def _file_record(self, path, data, payload):
        return (
            {
                "path": path,
                "kind": "file",
                "mode": 0o600,
                "uid": 0,
                "gid": 0,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "payload": payload,
            },
            data,
        )

    def _sqlite_record(self, path, data, payload):
        return (
            {
                "path": path,
                "kind": "sqlite",
                "mode": 0o600,
                "uid": 0,
                "gid": 0,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "payload": payload,
            },
            data,
        )

    def test_well_formed_archive_restores_into_empty_private_destination(self):
        env_data = b"synthetic restore content\n"
        sqlite_data = make_sqlite_bytes()
        records_payloads = [
            self._file_record("/restore/.env", env_data, "payload-000000"),
            self._sqlite_record("/restore/webhook.sqlite3", sqlite_data, "payload-000001"),
        ]
        archive = self._write_archive(make_archive(records_payloads))
        destination = self._destination()

        result = recovery_restore.validate_archive(archive, destination, make_plan(), policy=FakePolicy())

        self.assertEqual(result["verification"], "isolated-files-and-sqlite-validated")
        self.assertEqual(result["members"], 2)
        self.assertFalse(result["services_started"])
        restored_env = destination / "payload-000000"
        restored_db = destination / "payload-000001"
        self.assertEqual(restored_env.read_bytes(), env_data)
        self.assertEqual(restored_db.read_bytes(), sqlite_data)
        self.assertEqual(stat.S_IMODE(restored_env.stat().st_mode), 0o600)
        self.assertTrue((destination / "manifest.json").is_file())

    def test_record_outside_approved_plan_is_rejected(self):
        env_data = b"synthetic restore content\n"
        records_payloads = [self._file_record("/outside/plan.txt", env_data, "payload-000000")]
        archive = self._write_archive(make_archive(records_payloads))
        destination = self._destination()

        with self.assertRaises(ValueError):
            recovery_restore.validate_archive(archive, destination, make_plan(), policy=FakePolicy())

        self.assertFalse(list(destination.iterdir()))

    def test_unexpected_archive_member_is_rejected(self):
        env_data = b"synthetic restore content\n"
        records_payloads = [self._file_record("/restore/.env", env_data, "payload-000000")]
        data = make_archive(records_payloads)
        buffer = io.BytesIO(data)
        with tarfile.open(fileobj=buffer, mode="a") as archive:
            info = tarfile.TarInfo("extra-member.txt")
            info.size = 0
            archive.addfile(info, io.BytesIO(b""))
        archive = self._write_archive(buffer.getvalue())
        destination = self._destination()

        with self.assertRaises(ValueError):
            recovery_restore.validate_archive(archive, destination, make_plan(), policy=FakePolicy())

    def test_non_empty_destination_is_refused(self):
        destination = self._destination()
        (destination / "existing.txt").write_text("occupied")
        archive = self._write_archive(b"")

        with self.assertRaises(ValueError):
            recovery_restore.validate_archive(archive, destination, make_plan(), policy=FakePolicy())

    def test_destination_must_be_owner_private(self):
        destination = self.root / "public-output"
        destination.mkdir(mode=0o755)
        archive = self._write_archive(b"")

        with self.assertRaises(ValueError):
            recovery_restore.validate_archive(archive, destination, make_plan(), policy=FakePolicy())


if __name__ == "__main__":
    unittest.main()
