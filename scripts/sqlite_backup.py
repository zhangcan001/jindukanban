"""SQLite online backup with integrity check.

Used by backup.ps1 to safely copy a live SQLite database without stopping the
service. Uses sqlite3.Connection.backup() (Python 3.7+), which is safe to call
while the source database is being written to.

Usage:
    python sqlite_backup.py <source.db> <target.db>

Exit codes:
    0 - backup succeeded and integrity_check returned "ok"
    1 - source missing, backup failed, or integrity_check failed
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <source.db> <target.db>", file=sys.stderr)
        return 1

    source = Path(argv[1])
    target = Path(argv[2])

    if not source.exists():
        print(f"[error] source database not found: {source}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    check = sqlite3.connect(str(target))
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
    finally:
        check.close()

    if not row or row[0] != "ok":
        print(f"[error] integrity_check failed: {row}", file=sys.stderr)
        return 1

    print(f"[ok] backup verified: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
