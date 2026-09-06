#!/usr/bin/env python3
"""Guarded two-field Hermes MCP2 compatibility repair; dry-run by default."""
import argparse
import ast
import hashlib
import os
from pathlib import Path
import tempfile

REPLACEMENTS = (
    ('hint = getattr(annotations, "readOnlyHint", None)',
     'hint = mcp_field(annotations, "read_only_hint", "readOnlyHint")'),
    ('schema_obj = getattr(mcp_tool, "inputSchema", None)',
     'schema_obj = mcp_field(mcp_tool, "input_schema", "inputSchema")'),
)


def patched(source):
    for old, new in REPLACEMENTS:
        if source.count(new) == 1 and old not in source:
            continue
        if source.count(old) != 1 or new in source:
            raise ValueError('Unsupported Hermes source; manual review required')
        source = source.replace(old, new)
    ast.parse(source)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--expected-sha256', help='Reviewed pre-patch source digest; required for apply')
    args = parser.parse_args()
    if args.source.is_symlink() or not args.source.is_file():
        parser.error('Source must be a regular non-symlink file')
    original = args.source.read_bytes()
    desired = patched(original.decode()).encode()
    print('before_sha256=' + hashlib.sha256(original).hexdigest())
    print('after_sha256=' + hashlib.sha256(desired).hexdigest())
    if not args.apply or original == desired:
        return
    if args.expected_sha256 != hashlib.sha256(original).hexdigest():
        parser.error('--apply requires the matching reviewed --expected-sha256')
    if args.backup is None:
        parser.error('--apply requires a new explicit backup path')
    with args.backup.open('xb') as backup:
        os.chmod(args.backup, 0o600)
        backup.write(original); backup.flush(); os.fsync(backup.fileno())
    fd, name = tempfile.mkstemp(prefix='.mcp-compat-', dir=args.source.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(desired); out.flush(); os.fsync(out.fileno())
        os.chmod(name, args.source.stat().st_mode & 0o777)
        if args.source.read_bytes() != original:
            raise ValueError('Source changed during review; refusing replacement')
        os.replace(name, args.source)
        directory = os.open(args.source.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(name): os.unlink(name)


if __name__ == '__main__':
    main()
