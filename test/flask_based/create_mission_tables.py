import sqlite3

conn = sqlite3.connect("astronauts.db")
cursor = conn.cursor()

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS mission_crew (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER,
    astronaut_uid TEXT,
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (astronaut_uid) REFERENCES astronauts_cn(uid)
)
''')

conn.commit()
conn.close()

print("✅ Tables 'missions' and 'mission_crew' created.")
