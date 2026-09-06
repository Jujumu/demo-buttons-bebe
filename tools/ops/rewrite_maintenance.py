#!/usr/bin/env python3
"""Manual, hash-guarded temporary rewrite gate. Never stops producer services."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ANCHOR = 'srv1766050.hstgr.cloud, support.buttonsbebe.com {\n'
BLOCK = '''\t# BEGIN BB REWRITE MAINTENANCE
\t@bb_rewrite_maintenance path_regexp bb_rewrite_maintenance ^/console/api/ticket/[^/]+/rewrite/?$
\thandle @bb_rewrite_maintenance {
\t\theader Retry-After 120
\t\trespond "Draft editing is temporarily unavailable. Please try again shortly." 503
\t}
\t# END BB REWRITE MAINTENANCE
'''
IMPORTS = ('support', 'exchange', 'warehouse', 'receiving')


def digest(data): return hashlib.sha256(data).hexdigest()


def transform(source, mode):
    if source.count(ANCHOR) != 1 or source.count('@consoleapi path /console/api/*') != 1:
        raise ValueError('Supported route anchors changed')
    if mode == 'install':
        if 'BB REWRITE MAINTENANCE' in source or 'bb_rewrite_maintenance' in source:
            raise ValueError('Maintenance marker already present or changed')
        return source.replace(ANCHOR, ANCHOR + BLOCK)
    if mode != 'remove' or source.count(BLOCK) != 1:
        raise ValueError('Exact installed gate not found')
    return source.replace(BLOCK, '', 1)


def run(args):
    result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if result.returncode:
        raise RuntimeError('Caddy validation or reload failed; raw diagnostics suppressed')


def atomic(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.rewrite-maintenance-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data); output.flush(); os.fsync(output.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def apply(mode, expected_sha, entry, backup_parent, command=run):
    """Caller must hold the maintenance lock; all validation precedes live writes."""
    entry = entry.resolve(strict=True)
    root = entry.parent
    expected_entry = '\n'.join('import sites/' + name + '.caddy' for name in IMPORTS)
    actual_lines = '\n'.join(l.strip() for l in entry.read_text().splitlines()
                             if l.strip() and not l.lstrip().startswith('#'))
    if actual_lines != expected_entry:
        raise ValueError('Caddy import layout changed')
    files = {name: (root / 'sites' / (name + '.caddy')).resolve(strict=True) for name in IMPORTS}
    if len(set(files.values())) != len(files): raise ValueError('Duplicate fragment targets')
    before = {name: path.read_bytes() for name, path in files.items()}
    entry_before = entry.read_bytes()
    target = files['support']
    if digest(before['support']) != expected_sha:
        raise ValueError('Support source changed since review')
    rewritten = transform(before['support'].decode(), mode).encode()
    backup_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if backup_parent.is_symlink(): raise ValueError('Backup directory cannot be a symlink')
    backup = Path(tempfile.mkdtemp(prefix='rewrite-' + mode + '-', dir=backup_parent))
    backup.chmod(0o700)
    atomic(backup / 'support.before.caddy', before['support'], 0o600)
    with tempfile.TemporaryDirectory(prefix='.rewrite-stage-', dir=root) as temp:
        stage = Path(temp); stage.chmod(0o700)
        (stage / 'sites').mkdir(mode=0o700)
        atomic(stage / 'Caddyfile', entry_before, 0o600)
        for name in IMPORTS:
            atomic(stage / 'sites' / (name + '.caddy'), rewritten if name == 'support' else before[name], 0o600)
        candidate = stage / 'Caddyfile'
        command(['caddy', 'validate', '--config', str(candidate), '--adapter', 'caddyfile'])
        # Validate the actual rollback candidate too, before accepting an outage.
        atomic(stage / 'sites/support.caddy', before['support'], 0o600)
        command(['caddy', 'validate', '--config', str(candidate), '--adapter', 'caddyfile'])
        if entry.read_bytes() != entry_before or any(files[n].read_bytes() != before[n] for n in IMPORTS):
            raise ValueError('Concurrent Caddy change; live files untouched')
        file_mode = target.stat().st_mode & 0o777
        atomic(target, rewritten, file_mode)
        try:
            command(['caddy', 'reload', '--config', str(entry), '--adapter', 'caddyfile'])
        except Exception:
            if target.read_bytes() != rewritten:
                raise RuntimeError('Reload failed and source changed; manual recovery required') from None
            # The staged original was validated; revalidate before rollback apply.
            command(['caddy', 'validate', '--config', str(candidate), '--adapter', 'caddyfile'])
            atomic(target, before['support'], file_mode)
            command(['caddy', 'reload', '--config', str(entry), '--adapter', 'caddyfile'])
            raise RuntimeError('Reload failed; previous validated configuration restored') from None
    receipt = {'mode': mode, 'before_sha256': expected_sha, 'after_sha256': digest(rewritten),
               'backup': str(backup)}
    atomic(backup / 'receipt.json', (json.dumps(receipt) + '\n').encode(), 0o600)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['install', 'remove'])
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0: raise SystemExit('Root required')
    os.umask(0o077)
    with open('/run/buttonsbebe-rewrite-maintenance.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            print(json.dumps(apply(args.mode, args.expected_sha256, Path('/etc/caddy/Caddyfile'),
                                   Path('/opt/buttonsbebe/backups'))))
        except Exception as error:
            print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
            raise SystemExit(1) from None


if __name__ == '__main__': main()
