import sqlite3
from config import DATABASE_FILE

def get_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            question TEXT,
            answer TEXT,
            next_review TEXT,
            interval INTEGER,
            ease_factor REAL,
            repetitions INTEGER,
            last_reviewed TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS surveys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            survey_date TEXT,
            topic TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()
