"""Ensure inbox tests exercise exactly the pinned production runtime versions."""
from pathlib import Path
import re


def pins(path):
    result = {}
    text = Path(path).read_text()
    for logical in re.sub(r'\\\n\s*', ' ', text).splitlines():
        logical = logical.strip()
        if not logical or logical.startswith('#'):
            continue
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^\s;]+)\s+', logical)
        if not match or '--hash=sha256:' not in logical:
            raise ValueError(f'Unpinned or unhashed requirement in {path}')
        name = re.sub(r'[-_.]+', '-', match[1].lower())
        if name in result:
            raise ValueError(f'Duplicate requirement: {name}')
        result[name] = match[2]
    if not result:
        raise ValueError('Empty dependency lock')
    return result


def check(runtime, tests):
    production, testing = pins(runtime), pins(tests)
    for name, version in production.items():
        if testing.get(name) != version:
            raise ValueError(f'Test/runtime dependency mismatch: {name}')
    return len(production)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1] / 'console-src/inbox'
    print(f'inbox locks: {check(root / "requirements.lock", root / "requirements-test.lock")} runtime pins match test environment')
