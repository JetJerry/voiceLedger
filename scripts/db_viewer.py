#!/usr/bin/env python3
"""
VoiceLedger Database Viewer CLI.

Inspect tables, schema, and live rows in your Render (or local) PostgreSQL database.

Usage:
    uv run python scripts/db_viewer.py
    uv run python scripts/db_viewer.py --table payments
    uv run python scripts/db_viewer.py --table payment_events
    uv run python scripts/db_viewer.py --table voice_notifications
    uv run python scripts/db_viewer.py --url "postgresql+psycopg://..."
"""
import argparse
import sys
from sqlalchemy import create_engine, inspect, text

DEFAULT_RENDER_URL = "postgresql+psycopg://voiceledger_db_user:VShPgj5k5q9jbt82AqC7PwU3qyt8rQNu@dpg-dad42qf10e5c73d7qpmg-a.oregon-postgres.render.com/voiceledger_db"


def main():
    parser = argparse.ArgumentParser(description="VoiceLedger Database Inspector")
    parser.add_argument(
        "--url",
        default=DEFAULT_RENDER_URL,
        help="PostgreSQL connection string (defaults to your Render external DB)",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Specific table name to view rows from (e.g. payments, payment_events)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max rows to return (default: 20)",
    )
    args = parser.parse_args()

    # Normalize url scheme if passed as postgres:// or postgresql://
    url = args.url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    print("\n=======================================================")
    print(" [*] Connecting to PostgreSQL Database...")
    print("=======================================================\n")

    try:
        engine = create_engine(url)
        insp = inspect(engine)
        tables = insp.get_table_names()

        if not args.table:
            print(f"[OK] Successfully connected! Found {len(tables)} tables:\n")
            with engine.connect() as conn:
                for t in tables:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                    print(f"  - {t:<22} ({count} rows)")
            print("\nTip: To view records from a specific table, run:")
            print("   uv run python scripts/db_viewer.py --table payments")
            print("   uv run python scripts/db_viewer.py --table payment_events")
            print("   uv run python scripts/db_viewer.py --table voice_notifications\n")
            return

        target_table = args.table.strip().lower()
        if target_table not in tables:
            print(f"[ERROR] Table '{target_table}' not found. Available tables:")
            for t in tables:
                print(f"  - {t}")
            sys.exit(1)

        print(f"[TABLE] {target_table} (Limit: {args.limit} rows)\n")
        with engine.connect() as conn:
            columns = [col["name"] for col in insp.get_columns(target_table)]
            print("Columns: " + ", ".join(columns) + "\n")
            rows = conn.execute(text(f"SELECT * FROM {target_table} LIMIT {args.limit}")).fetchall()
            if not rows:
                print("  (Table is currently empty)")
            else:
                for idx, r in enumerate(rows, 1):
                    row_dict = dict(zip(columns, r))
                    print(f"--- [Row {idx}] ---")
                    for k, v in row_dict.items():
                        print(f"  {k}: {v}")
            print()

    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
