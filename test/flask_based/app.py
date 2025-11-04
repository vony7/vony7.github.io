from flask import Flask, render_template, request, abort
from datetime import datetime, timezone, timedelta
from dateutil import parser
import sqlite3
from pytz import timezone
import os 
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for

tz_utc8 = timezone("Asia/Shanghai")

# --- ADD THIS: Basic Auth Setup ---
app = Flask(__name__)  # <-- CREATE THE APP FIRST!

auth = HTTPBasicAuth()

# Hard-code a single admin user.
# In a real app, this would be in the database.
users = {
    "admin": generate_password_hash("password123")  # Change "password123" to your own password
}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username
# --- END Auth Setup ---

@app.route('/')
def index():
    return render_template("index.html")

# -------------------- Helpers --------------------
def calculate_mission_duration(start_str, end_str):
    """Helper function to calculate mission duration with timezone handling"""
    if not start_str or start_str == "0":
        return 0, "未开始", "future"

    try:
        start_dt = parser.parse(start_str)
        if not start_dt.tzinfo:
            start_dt = start_dt.replace(tzinfo=tz_utc8)
        
        now = datetime.now(tz_utc8)
        if start_dt > now:
            return 0, "未开始", "future"

        if end_str and end_str != "0":
            end_dt = parser.parse(end_str)
            if not end_dt.tzinfo:
                end_dt = end_dt.replace(tzinfo=tz_utc8)
            if end_dt > now:
                end_dt = now
                status = "ongoing"
            else:
                status = "completed"
        else:
            end_dt = now
            status = "ongoing"

        duration = end_dt - start_dt
        total_seconds = duration.total_seconds()
        
        # Format duration display
        if duration.days > 0:
            days = duration.days
            hours = int(duration.seconds / 3600)
            display = f"{days}天"
            if hours > 0:
                display += f" {hours}小时"
        else:
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if hours > 0:
                display = f"{hours}小时"
                if minutes > 0:
                    display += f" {minutes}分钟"
            else:
                display = f"{minutes}分钟"
        # print(status)
        return total_seconds, display, status
        
    except Exception as e:
        print(f"Duration calculation error: {e}")
        return 0, "计算错误", "error"
    
def resolve_astronaut_photo(uid):
    base_dir = os.path.join(app.root_path, "static", "images", "astronauts")
    jpg = os.path.join(base_dir, f"{uid}.jpg")
    png = os.path.join(base_dir, f"{uid}.png")
    if os.path.exists(jpg):
        return f"/static/images/astronauts/{uid}.jpg"
    elif os.path.exists(png):
        return f"/static/images/astronauts/{uid}.png"
    else:
        return "/static/images/astronauts/default.jpg"

# -------------------- Chinese Astronaut List --------------------
@app.route("/astronauts/")
def chinese_astronauts():
    # Get filter and sort parameters
    gender = request.args.get("gender")
    search = request.args.get("search")
    group = request.args.get("group")
    sort_by = request.args.get("sort_by", "name")
    order = request.args.get("order", "asc")

    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fixed JOIN condition (id instead of mid)
    sql = """
        SELECT a.*, m.name AS mission_name, m.mid, m.start, m.end
        FROM astronauts_cn a
        LEFT JOIN mission_crew mc ON a.uid = mc.astronaut_uid
        LEFT JOIN missions m ON mc.mission_id = m.id
        WHERE 1=1
    """
    
    params = []

    if gender:
        sql += " AND a.gender = ?"
        params.append(gender)
    if search:
        sql += " AND (a.name LIKE ? OR a.uid LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if group:
        sql += " AND a.group_id = ?"
        params.append(group)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    # Group missions by astronaut
    astronauts_map = {}
    for row in rows:
        uid = row["uid"]
        if uid not in astronauts_map:
            astronauts_map[uid] = {
                "uid": uid,
                "name": row["name"],
                "gender": row["gender"],
                "DOB": row["DOB"],
                "group_id": row["group_id"],
                "missions": [],
                "total_seconds": 0,
                "status":row["status"],
                "photo_url": resolve_astronaut_photo(uid),

            }
        
        if row["mid"]:  # Only add if mission exists
            total_seconds, duration_display, status = calculate_mission_duration(
                row["start"], row["end"]
            )
            
            # Only accumulate completed/ongoing missions
            if status in ["completed", "ongoing"]:
                astronauts_map[uid]["total_seconds"] += total_seconds
            
            astronauts_map[uid]["missions"].append({
                "mid": row["mid"],
                "name": row["mission_name"],
                "duration_display": duration_display,
                "duration_seconds": total_seconds,
                "status": status,
            })

    # Convert to list and calculate total display
    enhanced_astronauts = []
    for astronaut in astronauts_map.values():
        total_seconds = astronaut["total_seconds"]
        
        # Format total display
        if total_seconds > 0:
            total_days = int(total_seconds // 86400)
            remaining_seconds = total_seconds % 86400
            hours = int(remaining_seconds // 3600)

            if total_days >= 1:
                total_display = f"{total_days}天"
                if hours > 0:
                    total_display += f" {hours}小时"
            else:
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                if hours > 0:
                    total_display = f"{hours}小时"
                else:
                    total_display = f"{minutes}分钟"
        else:
            total_display = "0天"
            
        astronaut["total_mission_time"] = total_display
        enhanced_astronauts.append(astronaut)

    # Sorting
    reverse = order == "desc"
    if sort_by == "total":
        enhanced_astronauts.sort(key=lambda x: x["total_seconds"], reverse=reverse)
    elif sort_by == "name":
        enhanced_astronauts.sort(key=lambda x: x["name"], reverse=reverse)
    elif sort_by == "group":
        enhanced_astronauts.sort(key=lambda x: x["group_id"], reverse=reverse)

    conn.close()

    return render_template(
        "astronaut_cn.html",
        astronauts=enhanced_astronauts,
        selected_gender=gender,
        search=search,
        selected_group=group,
        sort_by=sort_by,
        order=order,
    )

# -----------------------------------------------------
# --- NEW ASTRONAUT ADMIN ROUTES (Add this) ---
# -----------------------------------------------------

# This page will show a form to add a new astronaut
@app.route("/admin/astronaut/new", methods=["GET"])
@auth.login_required  # <-- Protected!
def new_astronaut_form():
    return render_template("admin_astronaut_form.html")


# This route will *handle* the data from the form
@app.route("/admin/astronaut/new", methods=["POST"])
@auth.login_required  # <-- Protected!
def add_new_astronaut():
    # 1. Get all the fields from the form
    uid = request.form.get('uid')
    name = request.form.get('name')
    gender = request.form.get('gender')
    dob = request.form.get('dob')
    group_id = request.form.get('group_id')
    status = request.form.get('status') # This will be '1' or '0' as a string

    # 2. Validation
    if not uid or not name or not gender or not dob or not group_id or not status:
        return "Error: All fields are required.", 400

    try:
        # Convert numbers to integers
        group_id_int = int(group_id)
        status_int = int(status)
    except ValueError:
        return "Error: Group ID and Status must be numbers.", 400

    # 3. SQL Query
    try:
        conn = sqlite3.connect("astronauts.db")
        cursor = conn.cursor()
        
        # The table is 'astronauts_cn'
        sql = """
            INSERT INTO astronauts_cn (uid, name, gender, DOB, group_id, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        """
        # The parameters must be in the same order
        cursor.execute(sql, (uid, name, gender, dob, group_id_int, status_int))
        
        conn.commit()
    except sqlite3.IntegrityError:
        # This happens if the UID (primary key) already exists
        conn.rollback()
        return f"Error: Astronaut UID '{uid}' already exists. Please go back and choose a different one.", 409
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return f"An error occurred while adding the astronaut: {e}", 500
    finally:
        conn.close()

    # 4. Success! Redirect to the main astronaut list.
    return redirect(url_for('chinese_astronauts'))

# -------------------- Astronaut Profile --------------------
@app.route("/astronauts/<uid>")
def astronaut_profile(uid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Astronaut basic info
    cursor.execute("SELECT * FROM astronauts_cn WHERE uid = ?", (uid,))
    astronaut = cursor.fetchone()
    if not astronaut:
        return "Astronaut not found", 404

    # Missions - Fixed JOIN condition (id instead of mid)
    cursor.execute(
        """
        SELECT m.name, m.mid, m.start, m.end
        FROM missions m
        JOIN mission_crew mc ON m.id = mc.mission_id
        WHERE mc.astronaut_uid = ?
        ORDER BY m.start DESC
        """,
        (uid,),
    )
    all_missions = cursor.fetchall()

    past_missions, future_missions = [], []
    total_cumulative_seconds = 0
    for m in all_missions:
        total_seconds, duration_display, status = calculate_mission_duration(
            m["start"], m["end"]
        )
        m_dict = dict(m)
        m_dict["duration"] = duration_display
        m_dict["status"] = status
        
        if status == "future":
            future_missions.append(m_dict)
        else:
            past_missions.append(m_dict)
            # Only add completed or ongoing missions to the total
            if status in ["completed", "ongoing"]:
                total_cumulative_seconds += total_seconds
    if total_cumulative_seconds > 0:
                total_days = int(total_cumulative_seconds // 86400)
                remaining_seconds = total_cumulative_seconds % 86400
                hours = int(remaining_seconds // 3600)

                if total_days >= 1:
                    total_display = f"{total_days}天"
                    if hours > 0:
                            total_display += f" {hours}小时"
                else:
                    hours = int(total_cumulative_seconds // 3600)
                    minutes = int((total_cumulative_seconds % 3600) // 60)
                    if hours > 0:
                            total_display = f"{hours}小时"
                    else:
                            total_display = f"{minutes}分钟"
    else:
        total_display = "0天"
    conn.close()
    return render_template(
        "astronaut.html",
        astronaut=astronaut,
        past_missions=past_missions,
        future_missions=future_missions,
        total_mission_time=total_display  # <-- Add this new variable
    )


# -------------------- Missions Viewer --------------------
@app.route("/missions/")
def mission_list():
    sort_by = request.args.get("sort_by", "start")  # default
    order = request.args.get("order", "desc")
    mission_type = request.args.get("type")
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT * FROM missions WHERE 1=1"
    params = []
    if mission_type:
        query += " AND type = ?"
        params.append(mission_type)

    cursor.execute(query, params)
    missions = cursor.fetchall()

    mission_data = []
    for m in missions:
        # Get crew
        cursor.execute(
            """
            SELECT a.name, a.uid
            FROM mission_crew mc
            JOIN astronauts_cn a ON mc.astronaut_uid = a.uid
            WHERE mc.mission_id = ?
            """,
            (m["id"],),
        )
        crew = cursor.fetchall()

        # Use helper for duration calculation
        total_seconds, duration_display, status = calculate_mission_duration(
            m["start"], m["end"]
        )
        
        end_date = m["end"] or "进行中"
        mission_data.append(
            {
                "name": m["name"],
                "mid": m["mid"],
                "type": m["type"],
                "start": m["start"],
                "end": end_date,
                "duration_display": duration_display,
                "duration_seconds": total_seconds,
                "crew": crew,
                "status": status
            }
        )

    # Sorting
    reverse = order == "desc"
    if sort_by == "duration":
        mission_data.sort(key=lambda m: m["duration_seconds"], reverse=reverse)
    elif sort_by in ("start", "end"):
        # Handle empty values by sorting them last
        mission_data.sort(
            key=lambda m: (
                m[sort_by] if m[sort_by] and m[sort_by] != "0" 
                else "9999-12-31" if sort_by == "start" else ""
            ), 
            reverse=reverse
        )

    conn.close()
    return render_template(
        "missions.html",
        missions=mission_data,
        selected_type=mission_type,
        sort_by=sort_by,
        order=order,
    )


@app.route("/missions/<mid>")
def mission_detail(mid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get mission details
    cursor.execute("SELECT * FROM missions WHERE mid = ?", (mid,))
    mission = cursor.fetchone()

    if not mission:
        conn.close()
        abort(404)
    mission_id = mission["id"]

    # Get crew members
    cursor.execute(
        """
        SELECT a.* 
        FROM astronauts_cn a
        JOIN mission_crew mc ON a.uid = mc.astronaut_uid
        WHERE mc.mission_id = ?
        """,
        (mission_id,),
    )
    crew_rows = cursor.fetchall()
    crew = []
    for row in crew_rows:
        row = dict(row)
        row["photo_url"] = resolve_astronaut_photo(row["uid"])
        crew.append(row)

        
    
    # Enhanced duration calculation using helper
    total_seconds, duration_display, status = calculate_mission_duration(
        mission["start"], mission["end"]
    )
    
    duration_info = {
        "display": duration_display,
        "status": status
    }

    conn.close()

    return render_template(
        "mission_detail.html", 
        mission=mission, 
        crew=crew, 
        duration=duration_info
    )
# -------------------------------------------------
# --- ADMIN EDIT/DELETE ROUTES (Add this) ---
# -------------------------------------------------

# 1. THE MISSION "ADMIN HUB" PAGE
@app.route("/admin/missions")
@auth.login_required
def admin_mission_list():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all missions, a simple list
    cursor.execute("SELECT id, mid, name, start FROM missions ORDER BY start DESC")
    missions = cursor.fetchall()
    conn.close()
    
    return render_template("admin_mission_list.html", missions=missions)


# 2. THE "EDIT MISSION" PAGE (HANDLES BOTH GET AND POST)
@app.route("/admin/mission/edit/<mid>", methods=["GET", "POST"])
@auth.login_required
def edit_mission(mid):
    if request.method == "POST":
        # --- This is the UPDATE (POST) logic ---
        # Get data from the submitted form
        name = request.form.get('name')
        type = request.form.get('type')
        start = request.form.get('start')
        end = request.form.get('end')

        # Handle optional end date
        if end == "":
            end = None # Store as NULL in the database
        
        try:
            conn = sqlite3.connect("astronauts.db")
            cursor = conn.cursor()
            
            sql = """
                UPDATE missions 
                SET name = ?, type = ?, start = ?, end = ?
                WHERE mid = ?
            """
            cursor.execute(sql, (name, type, start, end, mid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            return "An error occurred while updating the mission.", 500
        finally:
            conn.close()

        # Success! Redirect back to the admin list
        return redirect(url_for('admin_mission_list'))
        
    else:
        # --- This is the LOAD (GET) logic ---
        # Fetch the mission's current data
        conn = sqlite3.connect("astronauts.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM missions WHERE mid = ?", (mid,))
        mission = cursor.fetchone()
        conn.close()
        
        if not mission:
            abort(404)
        
        # Show the edit form, pre-filled with 'mission' data
        return render_template("admin_mission_edit.html", mission=mission)


# 3. THE "DELETE MISSION" ROUTE (HANDLES POST ONLY)
@app.route("/admin/mission/delete/<mid>", methods=["POST"])
@auth.login_required
def delete_mission(mid):
    try:
        conn = sqlite3.connect("astronauts.db")
        cursor = conn.cursor()

        # IMPORTANT: We must delete the 'child' records first.
        # 1. Get the mission's primary ID (the integer 'id', not 'mid')
        cursor.execute("SELECT id FROM missions WHERE mid = ?", (mid,))
        mission_row = cursor.fetchone()
        
        if mission_row:
            mission_id = mission_row['id']
            
            # 2. Delete all links from mission_crew
            cursor.execute("DELETE FROM mission_crew WHERE mission_id = ?", (mission_id,))
            
            # 3. Now delete the 'parent' mission
            cursor.execute("DELETE FROM missions WHERE mid = ?", (mid,))
            
            conn.commit()
        else:
            return "Mission not found.", 404
            
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return "An error occurred while deleting the mission.", 500
    finally:
        conn.close()

    # Success! Redirect back to the admin list
    return redirect(url_for('admin_mission_list'))

# -------------------------------------------------
# --- NEW ADMIN ROUTES (Add this at the bottom) ---
# -------------------------------------------------

# This page will show a form to add a new mission
@app.route("/admin/mission/new", methods=["GET"])
@auth.login_required  # <-- This magic line protects the page!
def new_mission_form():
    # It just shows the HTML form
    return render_template("admin_mission_form.html")


# This route will *handle* the data from the form
@app.route("/admin/mission/new", methods=["POST"])
@auth.login_required  # <-- Also protected!
def add_new_mission():
    # 1. Get data from the form
    name = request.form.get('name')
    mid = request.form.get('mid')
    type = request.form.get('type')
    start = request.form.get('start')
    end = request.form.get('end')

    # Simple validation
    if not name or not mid or not type:
        return "Error: Name, MID, and Type are required.", 400

    # Handle optional end date
    if end == "":
        end = None # Store as NULL in the database
        
    try:
        # 2. Insert data into the database
        conn = sqlite3.connect("astronauts.db")
        cursor = conn.cursor()
        
        # IMPORTANT: Use ? to prevent SQL injection
        sql = "INSERT INTO missions (name, mid, type, start, end) VALUES (?, ?, ?, ?, ?)"
        cursor.execute(sql, (name, mid, type, start, end))
        
        conn.commit()  # <-- Don't forget to commit the change!
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback() # Roll back changes on error
        return "An error occurred while adding the mission.", 500
    finally:
        conn.close()

    # 3. Redirect back to the main mission list
    return redirect(url_for('mission_list'))

# -----------------------------------------------------
# --- ADMIN ASTRONAUT EDIT/DELETE ROUTES (Add this) ---
# -----------------------------------------------------

# 1. THE ASTRONAUT "ADMIN HUB" PAGE
@app.route("/admin/astronauts")
@auth.login_required
def admin_astronaut_list():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all astronauts, a simple list
    cursor.execute("SELECT uid, name, group_id, status FROM astronauts_cn ORDER BY group_id, name")
    astronauts = cursor.fetchall()
    conn.close()
    
    return render_template("admin_astronaut_list.html", astronauts=astronauts)


# 2. THE "EDIT ASTRONAUT" PAGE (HANDLES BOTH GET AND POST)
@app.route("/admin/astronaut/edit/<uid>", methods=["GET", "POST"])
@auth.login_required
def edit_astronaut(uid):
    if request.method == "POST":
        # --- This is the UPDATE (POST) logic ---
        # Get data from the submitted form
        name = request.form.get('name')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        group_id = request.form.get('group_id')
        status = request.form.get('status') # This will be '1' or '0' as a string
        
        try:
            # Convert numbers to integers
            group_id_int = int(group_id)
            status_int = int(status)
        except ValueError:
            return "Error: Group ID and Status must be numbers.", 400

        try:
            conn = sqlite3.connect("astronauts.db")
            cursor = conn.cursor()
            
            sql = """
                UPDATE astronauts_cn 
                SET name = ?, gender = ?, DOB = ?, group_id = ?, status = ?
                WHERE uid = ?
            """
            cursor.execute(sql, (name, gender, dob, group_id_int, status_int, uid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            return "An error occurred while updating the astronaut.", 500
        finally:
            conn.close()

        # Success! Redirect back to the admin list
        return redirect(url_for('admin_astronaut_list'))
        
    else:
        # --- This is the LOAD (GET) logic ---
        # Fetch the astronaut's current data
        conn = sqlite3.connect("astronauts.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM astronauts_cn WHERE uid = ?", (uid,))
        astronaut = cursor.fetchone()
        conn.close()
        
        if not astronaut:
            abort(404)
        
        # Show the edit form, pre-filled with 'astronaut' data
        return render_template("admin_astronaut_edit.html", astronaut=astronaut)


# 3. THE "DELETE ASTRONAUT" ROUTE (HANDLES POST ONLY)
@app.route("/admin/astronaut/delete/<uid>", methods=["POST"])
@auth.login_required
def delete_astronaut(uid):
    try:
        conn = sqlite3.connect("astronauts.db")
        cursor = conn.cursor()

        # IMPORTANT: We must delete the 'child' records first.
        # 1. Delete all links from mission_crew
        cursor.execute("DELETE FROM mission_crew WHERE astronaut_uid = ?", (uid,))
            
        # 2. Now delete the 'parent' astronaut
        cursor.execute("DELETE FROM astronauts_cn WHERE uid = ?", (uid,))
            
        conn.commit()
            
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return "An error occurred while deleting the astronaut.", 500
    finally:
        conn.close()

    # Success! Redirect back to the admin list
    return redirect(url_for('admin_astronaut_list'))

# -------------------- Run App --------------------
if __name__ == "__main__":
    app.run(debug=True)