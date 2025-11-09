import sqlite3

def normalize_dates():
    conn = sqlite3.connect("astronauts.db")
    cursor = conn.cursor()
    
    print("Normalizing date formats in DB to 'YYYY-MM-DD HH:MM:SS'...")

    # 1. Replace 'T' with space
    cursor.execute("UPDATE missions SET start = REPLACE(start, 'T', ' ') WHERE start LIKE '%T%'")
    cursor.execute("UPDATE missions SET end = REPLACE(end, 'T', ' ') WHERE end LIKE '%T%'")

    # 2. Replace slashes '/' with dashes '-' (common issue in some imports)
    cursor.execute("UPDATE missions SET start = REPLACE(start, '/', '-') WHERE start LIKE '%/%'")
    cursor.execute("UPDATE missions SET end = REPLACE(end, '/', '-') WHERE end LIKE '%/%'")

    conn.commit()
    print(f"Done. Rows affected: {conn.total_changes}")
    conn.close()

if __name__ == "__main__":
    normalize_dates()