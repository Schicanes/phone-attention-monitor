import sqlite3
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY, task TEXT, started TEXT, ended TEXT,
            planned_seconds REAL, elapsed REAL DEFAULT 0, focus REAL DEFAULT 0,
            phone REAL DEFAULT 0, pickups INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0,
            longest_focus REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS attention_events (
            id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
            timestamp TEXT, state TEXT, confidence REAL, duration REAL);
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
            timestamp TEXT, type TEXT, phone_duration REAL, response_time REAL);
        CREATE TABLE IF NOT EXISTS email_events (
            id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
            timestamp TEXT, status TEXT);
        """)
        self.connection.commit()

    def execute(self, sql, values=()):
        cursor = self.connection.execute(sql, values)
        self.connection.commit()
        return cursor

    def rows(self, sql, values=()):
        return self.connection.execute(sql, values).fetchall()

    def close(self):
        self.connection.close()
