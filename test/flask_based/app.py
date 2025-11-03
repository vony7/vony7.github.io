from flask import Flask, render_template, request, abort
from datetime import datetime, timezone, timedelta
from dateutil import parser
import sqlite3
from pytz import timezone
import os 

tz_utc8 = timezone("Asia/Shanghai")

app = Flask(__name__)

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


# -------------------- Run App --------------------
if __name__ == "__main__":
    app.run(debug=True)