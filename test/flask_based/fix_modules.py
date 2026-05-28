import sqlite3

def fix_modules():
    conn = sqlite3.connect("astronauts.db")
    cursor = conn.cursor()

    print("--- Adding Side Ports & Docking Labs ---")

    # 1. Define the Side Ports (Y-Axis)
    # We will use +Y for Left (Port) and -Y for Right (Starboard)
    side_ports = [
        ('Tianhe Core', 'Port Side (Left)',      '+Y', 'Module'),
        ('Tianhe Core', 'Starboard Side (Right)','-Y', 'Module'),
    ]
    
    # Insert ports if they don't exist
    for mod, name, code, type_allowed in side_ports:
        cursor.execute("SELECT id FROM station_ports WHERE axis_code = ?", (code,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO station_ports (module_name, port_name, axis_code, type_allowed) VALUES (?, ?, ?, ?)", 
                           (mod, name, code, type_allowed))
            print(f"Created port: {name}")

    # 2. Define the Lab Modules as Spacecraft
    labs = [
        ("问天实验舱 (Wentian)", "Module", "-Y"), # Right side
        ("梦天实验舱 (Mengtian)", "Module", "+Y")  # Left side
    ]

    for name, s_type, target_axis in labs:
        # Check if ship exists
        cursor.execute("SELECT id FROM spacecrafts WHERE name = ?", (name,))
        row = cursor.fetchone()
        
        if not row:
            cursor.execute("INSERT INTO spacecrafts (name, type) VALUES (?, ?)", (name, s_type))
            ship_id = cursor.lastrowid
            print(f"Created Ship: {name}")
        else:
            ship_id = row[0]

        # Dock them (Delete old logs first to be clean)
        cursor.execute("DELETE FROM docking_log WHERE spacecraft_id = ?", (ship_id,))
        
        # Find the port ID
        cursor.execute("SELECT id FROM station_ports WHERE axis_code = ?", (target_axis,))
        port_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO docking_log (spacecraft_id, port_id, dock_time, undock_time)
            VALUES (?, ?, datetime('now'), NULL)
        """, (ship_id, port_id))
        print(f"Docked {name} to axis {target_axis}")

    conn.commit()
    conn.close()
    print("--- Station T-Shape Configured ---")

if __name__ == "__main__":
    fix_modules()