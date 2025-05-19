import sqlite3
import csv

# Connect to DB
conn = sqlite3.connect("astronauts.db")
cursor = conn.cursor()

# Create tables if not exist
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

# Load and insert data
with open("data/missions_cn.csv", newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Normalize end date
        end_date = row["end"] if row["end"] != "0" else None

        # Insert mission
        cursor.execute('''
        INSERT OR IGNORE INTO missions (name, mid, type, start, end)
        VALUES (?, ?, ?, ?, ?)
        ''', (row["name"], row["mid"], row["type"], row["start"], end_date))

        # Get inserted mission ID
        cursor.execute("SELECT id FROM missions WHERE mid = ?", (row["mid"],))
        mission_id = cursor.fetchone()[0]

        # Insert crew members if applicable
        if row["crews"] != "NA":
            for uid in row["crews"].split():
                cursor.execute('''
                INSERT INTO mission_crew (mission_id, astronaut_uid)
                VALUES (?, ?)
                ''', (mission_id, uid))

conn.commit()
conn.close()
print("✅ Mission data and crew links imported successfully.")
