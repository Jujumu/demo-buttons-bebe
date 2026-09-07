#!/usr/bin/env python3
"""Encrypt consistent local SQLite snapshots to the installed recipient cert.

Only this job's completed encrypted snapshots are subject to retention. Existing
operator backups are untouched. This does not invent an off-host destination.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
from sqlite_backup import backup

CERT = Path('/etc/buttonsbebe-backup-recipient.pem')
DESTINATION = Path('/opt/buttonsbebe/backups/scheduled')
STATUS = Path('/var/lib/buttonsbebe/backup-status.json')
SOURCES = {
    'webhook.sqlite3': Path('/root/Buttonsbebe Agent/webhook/data/webhook.db'),
    'inbox.sqlite3': Path('/var/lib/buttonsbebe-inbox/inbox.sqlite3'),
}
PATTERN = re.compile(r'^scheduled-\d{8}T\d{6}Z\.cms$')


def command(*args):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        raise RuntimeError('Backup encryption command failed')


def write_status(data):
    STATUS.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if STATUS.is_symlink(): raise ValueError('Status cannot be a symlink')
    fd, name = tempfile.mkstemp(prefix='.backup-status-', dir=STATUS.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
            stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, STATUS)
    finally:
        temp.unlink(missing_ok=True)


def prune(directory: Path, now: datetime, retention_days: int = 14):
    # Keep at least three completed snapshots, independent of their age.
    candidates = sorted((p for p in directory.iterdir() if PATTERN.fullmatch(p.name)
                         and p.is_file() and not p.is_symlink()), reverse=True)
    for path in candidates[3:]:
        age = now.timestamp() - path.stat().st_mtime
        receipt = path.with_suffix('.json')
        if age > retention_days * 86400 and receipt.is_file() and not receipt.is_symlink():
            metadata = json.loads(receipt.read_text())
            if metadata.get('ciphertext_sha256') == hashlib.sha256(path.read_bytes()).hexdigest():
                path.unlink(); receipt.unlink()


def snapshot():
    now = datetime.now(timezone.utc)
    state = {'last_attempt': now.isoformat(), 'status': 'failed'}
    try:
        if STATUS.is_file() and not STATUS.is_symlink():
            prior = json.loads(STATUS.read_text())
            state['last_success'] = prior.get('last_success')
        if CERT.is_symlink() or CERT.stat().st_uid != 0 or CERT.stat().st_mode & 0o022:
            raise ValueError('Recipient must be root-owned and protected against replacement')
        command('openssl', 'x509', '-in', str(CERT), '-noout', '-checkend', '86400')
        DESTINATION.mkdir(mode=0o700, parents=True, exist_ok=True)
        if DESTINATION.is_symlink() or DESTINATION.stat().st_mode & 0o077:
            raise ValueError('Encrypted backup destination must be private')
        target = DESTINATION / ('scheduled-' + now.strftime('%Y%m%dT%H%M%SZ') + '.cms')
        if target.exists(): raise ValueError('Snapshot already exists')
        with tempfile.TemporaryDirectory(prefix='.incomplete-', dir=DESTINATION) as temp:
            root = Path(temp)
            manifest = {}
            for name, source in SOURCES.items():
                # Inbox may not have been initialized yet; webhook is required.
                if name == 'inbox.sqlite3' and not source.exists(): continue
                manifest[name] = backup(source, root / name)
            (root / 'manifest.json').write_text(json.dumps(manifest))
            archive = root / 'snapshot.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                for name in [*manifest, 'manifest.json']:
                    tar.add(root / name, arcname=name, recursive=False)
            encrypted = root / 'snapshot.cms'
            command('openssl', 'cms', '-encrypt', '-binary', '-aes-256-gcm', '-outform', 'DER',
                    '-in', str(archive), '-out', str(encrypted), str(CERT))
            if encrypted.stat().st_size == 0: raise RuntimeError('Empty ciphertext')
            metadata = {'created_at': now.isoformat(), 'databases': len(manifest),
                        'ciphertext_sha256': hashlib.sha256(encrypted.read_bytes()).hexdigest()}
            with encrypted.open('rb') as stream: os.fsync(stream.fileno())
            encrypted.rename(target)
            with target.with_suffix('.json').open('x') as stream:
                stream.write(json.dumps(metadata) + '\n')
                stream.flush(); os.fsync(stream.fileno())
            directory = os.open(DESTINATION, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        state.update(status='ok', last_success=now.isoformat(), encrypted_snapshots=len(manifest))
        write_status(state)
        prune(DESTINATION, now)
        print(json.dumps({'backup': 'ok', 'databases': len(manifest)}))
    except Exception as error:
        state['error_type'] = type(error).__name__
        write_status(state)
        raise RuntimeError('Scheduled backup failed; inspect status and protected local state') from None


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    os.umask(0o077)
    if os.geteuid() != 0: raise SystemExit('Run as root on the reviewed VPS')
    try: snapshot()
    except Exception: raise SystemExit('Scheduled backup failed; no data contents printed')
