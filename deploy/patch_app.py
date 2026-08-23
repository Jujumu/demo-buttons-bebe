#!/usr/bin/env python3
"""Retired deployment helper.

The old script edited a live ``app.py`` by matching literal route text and
inserting a ``sys.path`` shim. The webhook is now deployed as a composed
application with explicit routers, so mutating it in place would be unsafe.
The file remains as a harmless compatibility command for old runbooks.
"""

from __future__ import annotations


def main() -> int:
    print("patch_app.py is retired; deploy the versioned webhook package instead")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
