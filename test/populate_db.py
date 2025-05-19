import sqlite3

conn = sqlite3.connect('astronauts.db')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS astronauts (
    id INTEGER PRIMARY KEY,
    name TEXT,
    nationality TEXT,
    mission_count INTEGER,
    first_mission TEXT,
    image_url TEXT
)
''')

cursor.executemany('''
INSERT INTO astronauts (name, nationality, mission_count, first_mission, image_url)
VALUES (?, ?, ?, ?, ?)
''', [
    ('Yuri Gagarin', 'USSR', 1, 'Vostok 1 (1961)', 'static/500px-Chen_Dong.jpg'),
    ('陈冬','中国',2,'神舟十一号 (2016)', 'static/500px-Chen_Dong.jpg'),
])

conn.commit()
conn.close()
