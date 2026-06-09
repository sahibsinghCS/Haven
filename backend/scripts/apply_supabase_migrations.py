#!/usr/bin/env python3
"""Apply supabase/migrations/*.sql to the linked Supabase Postgres database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"


def _project_ref(supabase_url: str) -> str:
    host = supabase_url.strip().rstrip("/").replace("https://", "").replace("http://", "")
    return host.split(".")[0]


def _db_url() -> str:
    direct = (os.environ.get("SUPABASE_DB_URL") or "").strip()
    if direct:
        return direct
    password = (os.environ.get("SUPABASE_DB_PASSWORD") or "").strip()
    supabase_url = (os.environ.get("SUPABASE_URL") or "").strip()
    if not password or not supabase_url:
        raise SystemExit(
            "Missing database credentials.\n"
            "Add SUPABASE_DB_PASSWORD to backend/.env "
            "(Supabase dashboard → Project Settings → Database → Database password),\n"
            "or set SUPABASE_DB_URL to the full postgres connection string."
        )
    ref = _project_ref(supabase_url)
    return f"postgresql://postgres:{password}@db.{ref}.supabase.co:5432/postgres"


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No SQL files in {MIGRATIONS_DIR}", file=sys.stderr)
        return 1

    try:
        import psycopg
    except ImportError:
        print(
            "psycopg is required for migrations. Run:\n"
            "  pip install 'psycopg[binary]>=3.2,<4'",
            file=sys.stderr,
        )
        return 1

    url = _db_url()
    print(f"Applying {len(files)} migration(s) to Supabase…")
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for path in files:
                sql = path.read_text(encoding="utf-8")
                print(f"  → {path.name}")
                cur.execute(sql)
    print("Done. Restart npm run demo if the API is already running.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
