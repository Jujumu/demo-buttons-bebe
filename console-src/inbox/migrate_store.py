"""One-time, explicit legacy JSON import. Originals are never modified.

Run as an operator before the restricted inbox service starts. The target DB
must be absent; an existing DB is refused to avoid replacing newer state.
"""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", type=Path, required=True)
    parser.add_argument("--seen", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    if args.database.exists():
        parser.error("Target database already exists; migration refused")
    if not args.tickets.is_file() and args.seen.is_file():
        parser.error("Seen IDs exist without tickets; reconcile the legacy pair before migration")
    os.environ.update(HELPDESK_PRODUCTION="1", HELPDESK_DB_FILE=str(args.database),
                      HELPDESK_STORE_FILE=str(args.tickets), HELPDESK_SEEN_FILE=str(args.seen))
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "helpdesk-agent"))
    from helpdesk import tickets
    with tickets.transaction():
        pass
    print("Migration committed. Original JSON files retained. Set target directory ownership for the inbox service before startup.")


if __name__ == "__main__":
    main()
