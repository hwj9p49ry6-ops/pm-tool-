import sqlite3
from flask import g

DATABASE = 'tools/pm/pm.db'


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db(app):
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#4A90E2',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT 'New Task',
                owner TEXT DEFAULT '',
                status TEXT DEFAULT 'Not Started',
                priority TEXT DEFAULT 'Medium',
                start_date TEXT DEFAULT '',
                end_date TEXT DEFAULT '',
                pct_complete INTEGER DEFAULT 0,
                depends_on TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                duration INTEGER DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.commit()

        # Seed a default project on first run
        count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if count == 0:
            db.execute(
                "INSERT INTO projects (name, color) VALUES (?, ?)",
                ("My First Project", "#4A90E2")
            )
            db.commit()
        db.close()
