#!/usr/bin/env python3
"""Remove only the three Buttons Bebe schema-cache entries after reviewed repair.

Dry-run by default. Stop all Hermes producers first; no service is changed here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

SERVERS = frozenset({'buttonsbebe_kb', 'buttonsbebe_redo', 'buttonsbebe_gorgias'})


def invalidate(raw):
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Unsupported MCP cache schema')
    retained = {key: value for key, value in data.items() if key not in SERVERS}
    removed = sorted(SERVERS.intersection(data))
    if not removed:
        return raw, removed
    return (json.dumps(retained, indent=2, ensure_ascii=False) + '\n').encode(), removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    if args.cache.is_symlink() or not args.cache.is_file():
        parser.error('Cache must be a regular non-symlink file')
    if args.cache.stat().st_size > 16 * 1024 * 1024:
        parser.error('Oversized cache requires manual review')
    raw = args.cache.read_bytes()
    desired, removed = invalidate(raw)
    before = hashlib.sha256(raw).hexdigest()
    print(json.dumps({'before_sha256':before, 'after_sha256':hashlib.sha256(desired).hexdigest(),
                      'removed_server_names':removed}))
    if not args.apply or desired == raw:
        return
    if args.expected_sha256 != before or args.backup is None:
        parser.error('Apply requires matching reviewed --expected-sha256 and a new --backup path')
    with args.backup.open('xb') as backup:
        os.chmod(args.backup, 0o600)
        backup.write(raw); backup.flush(); os.fsync(backup.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.mcp-cache-', dir=args.cache.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(desired); out.flush(); os.fsync(out.fileno())
        os.chmod(temporary, args.cache.stat().st_mode & 0o777)
        if args.cache.read_bytes() != raw:
            raise ValueError('Cache changed; stop producers and review the new digest')
        os.replace(temporary, args.cache)
        directory = os.open(args.cache.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


if __name__ == '__main__':
    main()
