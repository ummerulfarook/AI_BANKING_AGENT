"""
database.py — Database initialization helper.

Run this file directly to create/migrate the database:
    python database.py

The app.py also calls init_db() on startup automatically.
"""

import sqlite3

DB = "database.db"


def init_db():
    """Create tables and apply any missing column migrations."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Conversations table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT DEFAULT 'New Chat',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Messages table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender          TEXT NOT NULL,
            message         TEXT NOT NULL,
            intent          TEXT,
            sentiment       TEXT,
            language        TEXT,
            is_fraud        INTEGER DEFAULT 0,
            timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        )
    """)

    # Migration: add columns if upgrading from older schema
    migrations = [
        ("intent",    "ALTER TABLE messages ADD COLUMN intent TEXT"),
        ("sentiment", "ALTER TABLE messages ADD COLUMN sentiment TEXT"),
        ("language",  "ALTER TABLE messages ADD COLUMN language TEXT"),
        ("is_fraud",  "ALTER TABLE messages ADD COLUMN is_fraud INTEGER DEFAULT 0"),
    ]
    cur.execute("PRAGMA table_info(messages)")
    existing_cols = {row[1] for row in cur.fetchall()}
    for col_name, sql in migrations:
        if col_name not in existing_cols:
            try:
                cur.execute(sql)
                print(f"Migration applied: added column '{col_name}' to messages")
            except Exception as e:
                print(f"Migration skipped for '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()