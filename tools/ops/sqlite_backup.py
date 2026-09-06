#!/usr/bin/env python3
"""Create and integrity-check a private, consistent SQLite snapshot.

No table contents or credential configuration are printed. This is a backup
operation, never a restore; deployment rollback must not call it to rewind data.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote


def backup(source: Path, destination: Path) -> dict:
    if not source.is_file() or source.is_symlink():
        raise ValueError('Source must be an existing regular database')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Refusing to overwrite an existing backup')
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.parent.is_symlink() or destination.parent.stat().st_mode & 0o077:
        raise ValueError('Backup parent must be a private real directory')
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    deadline = time.monotonic() + 120
    def progress(_status, _remaining, _total):
        if time.monotonic() > deadline:
            raise TimeoutError('Snapshot deadline exceeded')
    uri = 'file:' + quote(str(source.resolve()), safe='/') + '?mode=ro'
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as reader:
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer, pages=128, progress=progress, sleep=0.05)
                if writer.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise RuntimeError('Snapshot integrity check failed')
        with destination.open('rb') as stream:
            os.fsync(stream.fileno())
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        return {'integrity': 'ok', 'sha256': checksum, 'bytes': destination.stat().st_size}
    except BaseException:
        # An incomplete file is never advertised as a good backup.
        destination.rename(destination.with_name(destination.name + '.incomplete'))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        print(json.dumps(backup(args.source, args.destination)))
    except Exception as error:
        raise SystemExit(f'Backup failed: {type(error).__name__}; no data contents printed') from None


if __name__ == '__main__':
    main()
