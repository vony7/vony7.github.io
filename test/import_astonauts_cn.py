import sqlite3
import csv

# Connect to your database
conn = sqlite3.connect('astronauts.db')
cursor = conn.cursor()

# Create table if not exists
cursor.execute('''
CREATE TABLE IF NOT EXISTS astronauts_cn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    uid TEXT,
    gender TEXT,
    DOB TEXT,
    group_id INTEGER,
    status INTEGER
)
''')

# Read and insert data
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

conn.commit()
conn.close()

print("Database updated with Chinese astronaut data.")
