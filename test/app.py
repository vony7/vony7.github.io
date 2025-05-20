from flask import Flask, render_template, request, abort
from datetime import datetime, timezone, timedelta
from dateutil import parser
import sqlite3

tz_utc8 = timezone(timedelta(hours=8))

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, Flask is running on Render!"

# -------------------- Helpers --------------------
def query_chinese_astronauts(gender=None, group=None):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = "SELECT * FROM astronauts_cn WHERE 1=1"
    params = []

    if gender:
        sql += " AND gender = ?"
        params.append(gender)
    if group:
        sql += " AND group_id = ?"
        params.append(group)

    cursor.execute(sql, params)
    results = cursor.fetchall()
    conn.close()
    return results

# -------------------- Chinese Astronaut List --------------------
@app.route("/chinese")
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

    # Base query
    sql = "SELECT * FROM astronauts_cn WHERE 1=1"
    params = []

    if gender:
        sql += " AND gender = ?"
        params.append(gender)
    if search:
        sql += " AND (name LIKE ? OR uid LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if group:
        sql += " AND group_id = ?"
        params.append(group)

    cursor.execute(sql, params)
    astronauts = cursor.fetchall()

    enhanced_astronauts = []
    for astronaut in astronauts:
        # Get missions for this astronaut
        cursor.execute(
            """
            SELECT m.id, m.name, m.start, m.end 
            FROM missions m
            JOIN mission_crew mc ON m.id = mc.mission_id
            WHERE mc.astronaut_uid = ?
        """,
            (astronaut["uid"],),
        )
        missions = cursor.fetchall()

        total_seconds = 0
        mission_list = []

        for mission in missions:
            mission_seconds = 0
            duration_display = "-"

            try:
                if mission["start"] and mission["start"] != "0":
                    # Parse dates with timezone awareness
                    start_dt = parser.parse(mission["start"])
                    if not start_dt.tzinfo:
                        start_dt = start_dt.replace(tzinfo=tz_utc8).replace(tzinfo=None)

                    if mission["end"] and mission["end"] != "0":
                        end_dt = parser.parse(mission["end"])
                        if not end_dt.tzinfo:
                            end_dt = end_dt.replace(tzinfo=tz_utc8).replace(tzinfo=None)
                    else:
                        end_dt = datetime.now(tz_utc8).replace(tzinfo=None)

                    if start_dt and end_dt:
                        duration = end_dt - start_dt
                        mission_seconds = duration.total_seconds()
                        total_seconds += mission_seconds  # Accumulate total

                        # Format display
                        if mission_seconds > 0:
                            if duration.days >= 1:
                                duration_display = f"{duration.days}天"
                            else:
                                hours = int(mission_seconds // 3600)
                                minutes = int((mission_seconds % 3600) // 60)
                                if hours > 0:
                                    duration_display = f"{hours}小时"
                                else:
                                    duration_display = f"{minutes}分钟"
            except Exception as e:
                mission_id = mission["id"] if "id" in mission else "unknown"
                print(f"Date error for mission {mission_id}: {e}")
                duration_display = "计算中"

            mission_list.append(
                {
                    "id": mission["id"],
                    "name": mission["name"],
                    "duration_display": duration_display,
                    "duration_seconds": mission_seconds,
                }
            )

        # Calculate total time display
        total_display = "0天"
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

        enhanced_astronaut = dict(astronaut)
        enhanced_astronaut["missions"] = mission_list
        enhanced_astronaut["total_mission_time"] = total_display
        enhanced_astronaut["total_seconds"] = total_seconds

        enhanced_astronauts.append(enhanced_astronaut)

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
@app.route("/astronaut/<uid>")
def astronaut_profile(uid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Astronaut basic info
    cursor.execute("SELECT * FROM astronauts_cn WHERE uid = ?", (uid,))
    astronaut = cursor.fetchone()
    if not astronaut:
        return "Astronaut not found", 404

    # Missions
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
    for m in all_missions:
        m_dict = dict(m)
        is_future = not m["start"] or m["start"] == "0"

        if m["start"] and m["start"] != "0":
            try:
                start_dt = parser.parse(m["start"])
                if m["end"] and m["end"] != "0":
                    end_dt = parser.parse(m["end"])
                else:
                    end_dt = datetime.now(tz_utc8).replace(tzinfo=None)
                m_dict["duration"] = (end_dt - start_dt).days
            except Exception:
                m_dict["duration"] = None

        if is_future:
            future_missions.append(m_dict)
        else:
            past_missions.append(m_dict)

    conn.close()
    return render_template(
        "astronaut.html",
        astronaut=astronaut,
        past_missions=past_missions,
        future_missions=future_missions,
    )


# -------------------- Missions Viewer --------------------
@app.route("/missions")
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
        # Crew query remains the same
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

        # Duration calculation
        duration_seconds = 0
        duration_display = "-"
        end_date = m["end"] or "进行中"

        try:
            if m["start"] and m["start"] != "0":
                start_dt = parser.parse(m["start"])
                if m["end"] and m["end"] != "0":
                    end_dt = parser.parse(m["end"])
                else:
                    end_dt = datetime.now(tz_utc8).replace(tzinfo=None)

                if start_dt and end_dt:
                    duration = end_dt - start_dt
                    duration_seconds = duration.total_seconds()
                    if duration_seconds > 0:
                        if duration.days >= 1:
                            duration_display = f"{duration.days}天"
                        else:
                            hours = int(duration_seconds // 3600)
                            minutes = int((duration_seconds % 3600) // 60)
                            if hours > 0:
                                duration_display = f"{hours}小时"
                            else:
                                duration_display = f"{minutes}分钟"
        except Exception as e:
            print(f"Date parsing error: {e}")

        mission_data.append(
            {
                "name": m["name"],
                "mid": m["mid"],
                "type": m["type"],
                "start": m["start"],
                "end": end_date,
                "duration_display": duration_display,
                "duration_seconds": duration_seconds,  # For sorting
                "crew": crew,
            }
        )

    # Update sorting to use duration_seconds
    reverse = order == "desc"
    if sort_by == "duration":
        mission_data.sort(key=lambda m: m["duration_seconds"], reverse=reverse)
    elif sort_by in ("start", "end"):
        mission_data.sort(key=lambda m: m[sort_by] or "", reverse=reverse)

    conn.close()
    return render_template(
        "missions.html",
        missions=mission_data,
        selected_type=mission_type,
        sort_by=sort_by,
        order=order,
    )


@app.route("/mission/<mission_id>")
def mission_detail(mission_id):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get mission details
    cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
    mission = cursor.fetchone()

    if not mission:
        conn.close()
        abort(404)

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
    crew = cursor.fetchall()
    # Enhanced duration calculation
    duration_info = {
        "days": 0,
        "hours": 0,
        "minutes": 0,
        "seconds": 0,
        "is_ongoing": False,
        "display": "待计算",
    }

    try:
        if mission["start"] and mission["start"] != "0":
            start_dt = parser.parse(mission["start"])
            if not start_dt.tzinfo:
                start_dt = start_dt.replace(tzinfo=tz_utc8)

            # Determine end time (current time if ongoing)
            if mission["end"] and mission["end"] != "0":
                end_dt = parser.parse(mission["end"])
                if not end_dt.tzinfo:
                    end_dt = end_dt.replace(tzinfo=tz_utc8)
            else:
                end_dt = datetime.now(tz_utc8)
                duration_info["is_ongoing"] = True

            if start_dt and end_dt:
                delta = end_dt - start_dt
                total_seconds = delta.total_seconds()

                # Calculate breakdown
                duration_info["days"] = int(total_seconds // 86400)
                remaining_seconds = total_seconds % 86400
                duration_info["hours"] = int(remaining_seconds // 3600)
                remaining_seconds %= 3600
                duration_info["minutes"] = int(remaining_seconds // 60)
                duration_info["seconds"] = int(remaining_seconds % 60)

                # Format display
                if duration_info["days"] > 0:
                    duration_info["display"] = (
                        f"{duration_info['days']}天 {duration_info['hours']}小时"
                    )
                elif duration_info["hours"] > 0:
                    duration_info["display"] = (
                        f"{duration_info['hours']}小时 {duration_info['minutes']}分钟"
                    )
                else:
                    duration_info["display"] = f"{duration_info['minutes']}分钟"

                if duration_info["is_ongoing"]:
                    duration_info["display"] += " (进行中)"

    except Exception as e:
        print(f"Duration calculation error: {e}")

    conn.close()

    return render_template(
        "mission_detail.html", mission=mission, crew=crew, duration=duration_info
    )


# -------------------- Run App --------------------
if __name__ == "__main__":
    app.run(debug=True)
