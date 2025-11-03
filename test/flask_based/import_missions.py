import sqlite3
import csv

# Connect to DB
conn = sqlite3.connect("astronauts.db")
cursor = conn.cursor()

# Ensure tables exist
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
    UNIQUE (mission_id, astronaut_uid),
    FOREIGN KEY (mission_id) REFERENCES missions(id),
    FOREIGN KEY (astronaut_uid) REFERENCES astronauts_cn(uid)
)
''')

# Load and insert data
with open("data/missions_cn.csv", newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        end_date = row["end"] if row["end"] != "0" else None

        # Check if mission already exists by mid
        cursor.execute("SELECT id FROM missions WHERE mid = ?", (row["mid"],))
        mission_result = cursor.fetchone()

        if mission_result:
            mission_id = mission_result[0]
            print(f"Skipped mission '{row['name']}' (mid={row['mid']}) — already exists.")
        else:
            # Insert new mission
            cursor.execute('''
            INSERT INTO missions (name, mid, type, start, end)
            VALUES (?, ?, ?, ?, ?)
            ''', (row["name"], row["mid"], row["type"], row["start"], end_date))
            mission_id = cursor.lastrowid
            print(f"Inserted mission '{row['name']}'")

        # Insert crew members (only if mission_id is valid and crew listed)
        if mission_id and row["crews"] != "NA":
            for uid in row["crews"].split():
                cursor.execute('''
                SELECT 1 FROM mission_crew WHERE mission_id = ? AND astronaut_uid = ?
                ''', (mission_id, uid))
                crew_exists = cursor.fetchone()

                if not crew_exists:
                    cursor.execute('''
                    INSERT INTO mission_crew (mission_id, astronaut_uid)
                    VALUES (?, ?)
                    ''', (mission_id, uid))
                    print(f" → Linked astronaut {uid} to mission {row['mid']}")
                else:
                    print(f" → Skipped existing crew link: {uid} in mission {row['mid']}")

conn.commit()
conn.close()
print("✅ Mission import completed with duplicate checks.")
