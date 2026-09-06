"""Print non-secret installed-version receipt and fail on drift from a hashlock."""
import importlib.metadata
import json
from pathlib import Path
import re
import sys


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def verify(lock, installed):
    expected = {normalized(name): version for name, version in
                re.findall(r'^([A-Za-z0-9_.-]+)==([^\s;]+)', lock, re.M)}
    if not expected:
        raise ValueError('Empty runtime lock')
    actual = {normalized(name): version for name, version in installed.items()
              if normalized(name) not in {'pip', 'setuptools', 'wheel'}}
    if actual != expected:
        raise ValueError(json.dumps({'missing': sorted(set(expected)-set(actual)),
            'extra': sorted(set(actual)-set(expected)),
            'changed': {name: {'expected': expected[name], 'actual': actual[name]}
                        for name in expected.keys() & actual.keys() if expected[name] != actual[name]}}))
    return dict(sorted(actual.items()))


def verify_manifests(path):
    pins = lambda text: {normalized(n): v for n, v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s;]+)', text, re.M)}
    expected = pins(path.read_text())
    constraints = pins(path.with_name('runtime-constraints.txt').read_text())
    direct = pins(path.with_name('requirements.txt').read_text())
    if constraints != expected or not direct or any(expected.get(n) != v for n, v in direct.items()):
        raise ValueError('Runtime lock disagrees with declared requirements or observed constraints')


if __name__ == '__main__':
    verify_manifests(Path(sys.argv[1]))
    receipt = verify(Path(sys.argv[1]).read_text(),
                     {d.metadata['Name']: d.version for d in importlib.metadata.distributions()})
    print(json.dumps({'lock': sys.argv[1], 'packages': receipt}, sort_keys=True))
