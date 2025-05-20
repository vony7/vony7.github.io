# create_empty_db.py

import sqlite3

conn = sqlite3.connect("astronauts.db")
cursor = conn.cursor()

# Create astronauts table
cursor.execute('''
CREATE TABLE IF NOT EXISTS astronauts_cn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    uid TEXT UNIQUE,
    gender TEXT,
    DOB TEXT,
    group_id INTEGER,
    status INTEGER
)
''')

# Create missions table
cursor.execute('''
CREATE TABLE IF NOT EXISTS missions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    mid TEXT UNIQUE,
    type TEXT,
    start TEXT,
    end TEXT
)
''')

# Create mission_crew table
cursor.execute('''
CREATE TABLE IF NOT EXISTS mission_crew (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER,
    astronaut_uid TEXT,
    UNIQUE (mission_id, astronaut_uid),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (astronaut_uid) REFERENCES astronauts_cn(uid)
)
''')

conn.commit()
conn.close()

print("✅ Empty DB created: astronauts.db")
