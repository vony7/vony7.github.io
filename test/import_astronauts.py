import sqlite3
import csv

# Connect to your database
conn = sqlite3.connect('astronauts.db')
cursor = conn.cursor()

# Ensure table exists before checking
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

# Check if data already exists
cursor.execute("SELECT COUNT(*) FROM astronauts_cn")
count = cursor.fetchone()[0]

if count == 0:
    print("Importing astronauts...")

    with open('data/astronauts_cn.csv', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        data = [
            (row['name'], row['uid'], row['gender'], row['DOB'], int(row['group']), int(row['status']))
            for row in reader
        ]

    cursor.executemany('''
    INSERT INTO astronauts_cn (name, uid, gender, DOB, group_id, status)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', data)
else:
    print(f"Skipped import: {count} astronauts already exist.")

conn.commit()
conn.close()

print("Done.")
