from flask import Flask, render_template, request, abort, send_file
from datetime import datetime, timedelta
from dateutil import parser
import sqlite3
from pytz import timezone
import os 
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from flask import redirect, url_for
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.io as pio
from PIL import Image, ImageDraw, ImageOps
import base64

tz_utc8 = timezone("Asia/Shanghai")

# --- Matplotlib Chinese Font Configuration ---
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'PingFang SC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False 

app = Flask(__name__)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("password123")
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

@app.route('/')
def index():
    return render_template("index.html")

# -------------------------------------------------------
# --- MISSING ASTRONAUT ADMIN ROUTES (ADD THESE BACK) ---
# -------------------------------------------------------

@app.route("/admin/astronauts")
@auth.login_required
def admin_astronaut_list():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT uid, name, group_id, status FROM astronauts_cn ORDER BY group_id, name")
    astronauts = cursor.fetchall()
    conn.close()
    return render_template("admin_astronaut_list.html", astronauts=astronauts)

@app.route("/admin/astronaut/new", methods=["GET", "POST"])
@auth.login_required
def add_new_astronaut():
    if request.method == "GET":
        return render_template("admin_astronaut_form.html")
    
    # POST Logic
    uid = request.form.get('uid')
    name = request.form.get('name')
    gender = request.form.get('gender')
    dob = request.form.get('dob')
    group_id = request.form.get('group_id')
    status = request.form.get('status')

    conn = sqlite3.connect("astronauts.db")
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO astronauts_cn (uid, name, gender, DOB, group_id, status) VALUES (?, ?, ?, ?, ?, ?)", 
                       (uid, name, gender, dob, group_id, status))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error adding astronaut: {e}", 500
    finally:
        conn.close()
    return redirect(url_for('admin_astronaut_list'))

@app.route("/admin/astronaut/edit/<uid>", methods=["GET", "POST"])
@auth.login_required
def edit_astronaut(uid):
    if request.method == "POST":
        name = request.form.get('name')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        group_id = request.form.get('group_id')
        status = request.form.get('status')
        
        conn = sqlite3.connect("astronauts.db")
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE astronauts_cn SET name=?, gender=?, DOB=?, group_id=?, status=? WHERE uid=?", 
                           (name, gender, dob, group_id, status, uid))
            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Error updating astronaut: {e}", 500
        finally:
            conn.close()
        return redirect(url_for('admin_astronaut_list'))
        
    # GET Logic
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM astronauts_cn WHERE uid = ?", (uid,))
    astronaut = cursor.fetchone()
    conn.close()
    if not astronaut: abort(404)
    return render_template("admin_astronaut_edit.html", astronaut=astronaut)

@app.route("/admin/astronaut/delete/<uid>", methods=["POST"])
@auth.login_required
def delete_astronaut(uid):
    conn = sqlite3.connect("astronauts.db")
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM mission_crew WHERE astronaut_uid = ?", (uid,))
        cursor.execute("DELETE FROM astronauts_cn WHERE uid = ?", (uid,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error deleting astronaut: {e}", 500
    finally:
        conn.close()
    return redirect(url_for('admin_astronaut_list'))

# -------------------- Helpers --------------------

def calculate_mission_duration(start_str, end_str):
    # Default error/empty state
    result = {"seconds": 0, "display": "N/A", "status": "unknown"}

    if not start_str or start_str == "0":
         result["display"] = "未开始 (Not Started)"
         result["status"] = "future"
         return result

    try:
        # 1. Clean up input formats
        start_clean = str(start_str).replace('T', ' ').replace('/', '-')
        start_dt = pd.to_datetime(start_clean).to_pydatetime()
        
        tz_cn = timezone("Asia/Shanghai")
        if start_dt.tzinfo is None: start_dt = tz_cn.localize(start_dt)
        now = datetime.now(tz_cn)

        if start_dt > now:
             result["display"] = "未开始 (Future)"
             result["status"] = "future"
             return result

        # 2. Parse End Date
        if end_str and str(end_str).strip() not in ['', '0', 'None', 'NaT']:
            end_clean = str(end_str).replace('T', ' ').replace('/', '-')
            end_dt = pd.to_datetime(end_clean).to_pydatetime()
            if end_dt.tzinfo is None: end_dt = tz_cn.localize(end_dt)
            
            if end_dt > now:
                end_dt = now
                result["status"] = "ongoing"
            else:
                result["status"] = "completed"
        else:
            end_dt = now
            result["status"] = "ongoing"

        # 3. Calculate Duration
        duration = end_dt - start_dt
        total_seconds = duration.total_seconds()
        days = duration.days
        hours = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)

        if days > 0:
            display = f"{days}天 {hours}小时"
        elif hours > 0:
            display = f"{hours}小时 {minutes}分钟"
        else:
            display = f"{int(total_seconds // 60)}分钟"

        result["seconds"] = total_seconds
        result["display"] = display
        return result

    except Exception as e:
        print(f"Duration Calc Error: {e}")
        result["display"] = "计算错误"
        result["status"] = "error"
        return result

def resolve_astronaut_photo(uid):
    base_dir = os.path.join(app.root_path, "static", "images", "astronauts")
    jpg = os.path.join(base_dir, f"{uid}.jpg")
    png = os.path.join(base_dir, f"{uid}.png")
    if os.path.exists(jpg): return f"/static/images/astronauts/{uid}.jpg"
    elif os.path.exists(png): return f"/static/images/astronauts/{uid}.png"
    else: return "/static/images/astronauts/default.jpg"

def get_circular_photo(uid, active=False):
    base_dir = os.path.join(app.root_path, "static", "images", "astronauts")
    jpg = os.path.join(base_dir, f"{uid}.jpg")
    png = os.path.join(base_dir, f"{uid}.png")
    img_path = jpg if os.path.exists(jpg) else (png if os.path.exists(png) else os.path.join(base_dir, "default.jpg"))

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            size = min(img.size)
            img = ImageOps.fit(img, (size, size), centering=(0.5, 0.5))
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)

            if active:
                draw_img = ImageDraw.Draw(img)
                ring_color = "#00ff00"
                ring_width = int(size * 0.08)
                draw_img.ellipse((0, 0, size, size), outline=ring_color, width=ring_width)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error processing image for {uid}: {e}")
        return ""

# -------------------- Main Routes --------------------

@app.route("/astronauts/")
def chinese_astronauts():
    gender = request.args.get("gender")
    search = request.args.get("search")
    group = request.args.get("group")
    sort_by = request.args.get("sort_by", "name")
    order = request.args.get("order", "asc")

    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

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

    astronauts_map = {}
    for row in rows:
        uid = row["uid"]
        if uid not in astronauts_map:
            astronauts_map[uid] = {
                "uid": uid, "name": row["name"], "gender": row["gender"],
                "DOB": row["DOB"], "group_id": row["group_id"],
                "missions": [], "total_seconds": 0, "status":row["status"],
                "photo_url": resolve_astronaut_photo(uid),
            }
        
        if row["mid"]:
            total_seconds, duration_display, status = calculate_mission_duration(row["start"], row["end"])
            if status in ["completed", "ongoing"]:
                astronauts_map[uid]["total_seconds"] += total_seconds
            astronauts_map[uid]["missions"].append({
                "mid": row["mid"], "name": row["mission_name"],
                "duration_display": duration_display, "status": status
            })

    enhanced_astronauts = []
    for astronaut in astronauts_map.values():
        total_seconds = astronaut["total_seconds"]
        if total_seconds > 0:
            days = int(total_seconds // 86400)
            hours = int((total_seconds % 86400) // 3600)
            astronaut["total_mission_time"] = f"{days}天 {hours}小时"
        else:
            astronaut["total_mission_time"] = "0天"
        enhanced_astronauts.append(astronaut)

    reverse = order == "desc"
    if sort_by == "total": enhanced_astronauts.sort(key=lambda x: x["total_seconds"], reverse=reverse)
    elif sort_by == "name": enhanced_astronauts.sort(key=lambda x: x["name"], reverse=reverse)
    elif sort_by == "group": enhanced_astronauts.sort(key=lambda x: x["group_id"], reverse=reverse)

    conn.close()
    return render_template("astronaut_cn.html", astronauts=enhanced_astronauts, 
                         selected_gender=gender, search=search, selected_group=group, 
                         sort_by=sort_by, order=order)

@app.route("/astronauts/<uid>")
def astronaut_profile(uid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM astronauts_cn WHERE uid = ?", (uid,))
    astronaut = cursor.fetchone()
    if not astronaut: return "Astronaut not found", 404

    cursor.execute("""
        SELECT m.name, m.mid, m.start, m.end
        FROM missions m
        JOIN mission_crew mc ON m.id = mc.mission_id
        WHERE mc.astronaut_uid = ?
        ORDER BY m.start DESC
    """, (uid,))
    all_missions = cursor.fetchall()

    past_missions, future_missions = [], []
    total_cumulative_seconds = 0
    for m in all_missions:
        total_seconds, duration_display, status = calculate_mission_duration(m["start"], m["end"])
        m_dict = dict(m)
        m_dict["duration"] = duration_display
        m_dict["status"] = status
        m_dict["end_raw"] = m["end"]
        
        if status == "future": future_missions.append(m_dict)
        else:
            past_missions.append(m_dict)
            if status in ["completed", "ongoing"]: total_cumulative_seconds += total_seconds

    if total_cumulative_seconds > 0:
        days = int(total_cumulative_seconds // 86400)
        hours = int((total_cumulative_seconds % 86400) // 3600)
        total_display = f"{days}天 {hours}小时"
    else:
        total_display = "0天"

    time_since_last_display = None
    if astronaut['status'] == 1:
        if past_missions:
            most_recent = past_missions[0]
            if most_recent['status'] == 'ongoing':
                time_since_last_display = "目前在轨"
            elif most_recent['status'] == 'completed':
                try:
                    last_end = pd.to_datetime(most_recent['end_raw'].replace('T', ' ').replace('/', '-')).to_pydatetime()
                    tz_cn = timezone("Asia/Shanghai")
                    if last_end.tzinfo is None: last_end = tz_cn.localize(last_end)
                    days_since = (datetime.now(tz_cn) - last_end).days
                    if days_since < 0: time_since_last_display = "N/A"
                    elif days_since == 0: time_since_last_display = "今天"
                    else: time_since_last_display = f"{days_since}天"
                except: time_since_last_display = "日期错误"
        else: time_since_last_display = "未执行任务"
    else: time_since_last_display = "已退役"

    conn.close()
    return render_template("astronaut.html", astronaut=astronaut, past_missions=past_missions,
                         future_missions=future_missions, total_mission_time=total_display,
                         time_since_last_mission=time_since_last_display)

@app.route("/missions/")
def mission_list():
    sort_by = request.args.get("sort_by", "start")
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
        cursor.execute("SELECT a.name, a.uid FROM mission_crew mc JOIN astronauts_cn a ON mc.astronaut_uid = a.uid WHERE mc.mission_id = ? ORDER BY mc.crew_order ASC", (m["id"],))
        crew = cursor.fetchall()
        duration_info = calculate_mission_duration(m["start"], m["end"])
        mission_data.append({
            "name": m["name"], "mid": m["mid"], "type": m["type"],
            "start": m["start"], "end": m["end"] or "进行中",
            "duration_display": duration_info["display"],
            "duration_seconds": duration_info["seconds"],
            "status": duration_info["status"],
            "crew": crew
        })

    reverse = order == "desc"
    if sort_by == "duration": mission_data.sort(key=lambda m: m["duration_seconds"], reverse=reverse)
    elif sort_by in ("start", "end"):
        mission_data.sort(key=lambda m: (m[sort_by] if m[sort_by] and m[sort_by] != "0" else "9999-12-31"), reverse=reverse)

    conn.close()
    return render_template("missions.html", missions=mission_data, selected_type=mission_type,
                         sort_by=sort_by, order=order)

@app.route("/missions/<mid>")
def mission_detail(mid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM missions WHERE mid = ?", (mid,))
    mission = cursor.fetchone()
    if not mission:
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT a.*, mc.role, mc.crew_order
        FROM astronauts_cn a
        JOIN mission_crew mc ON a.uid = mc.astronaut_uid
        WHERE mc.mission_id = ?
        ORDER BY mc.crew_order ASC
    """, (mission['id'],))
    crew_rows = cursor.fetchall()
    conn.close()

    launch_crew, landing_crew = [], []
    def process_crew(row):
        c = dict(row)
        c["photo_url"] = resolve_astronaut_photo(row["uid"])
        return c

    for row in crew_rows:
        role = row['role']
        if not role or role == 'both':
            launch_crew.append(process_crew(row))
            landing_crew.append(process_crew(row))
        elif role == 'launch':
            launch_crew.append(process_crew(row))
        elif role == 'landing':
            landing_crew.append(process_crew(row))

    launch_uids = [c['uid'] for c in launch_crew]
    landing_uids = [c['uid'] for c in landing_crew]
    same_crew = (launch_uids == landing_uids)
    duration_info = calculate_mission_duration(mission["start"], mission["end"])

    return render_template("mission_detail.html", mission=mission, launch_crew=launch_crew,
                         landing_crew=landing_crew, same_crew=same_crew, duration=duration_info,
                         crew=launch_crew if same_crew else [])

@app.route("/css-missions/")
def css_mission_list():
    return mission_list() # Re-use generic list but could filter if needed

# -------------------- Charts & Visualizations --------------------

@app.route("/css-missions/docking")
def css_docking_status():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tz_cn = timezone("Asia/Shanghai")
    now_cn = datetime.now(tz_cn).strftime('%Y-%m-%d %H:%M:%S')

    # Fetch ONGOING missions (Standardized date format for comparison)
    sql = """
        SELECT name, type, start, end
        FROM missions 
        WHERE REPLACE(start, 'T', ' ') <= ? 
          AND (end IS NULL OR end = '' OR REPLACE(end, 'T', ' ') >= ?)
        ORDER BY start DESC
    """
    cursor.execute(sql, (now_cn, now_cn))
    ongoing_missions = cursor.fetchall()
    conn.close()

    manned = [m for m in ongoing_missions if m['type'] == '载人']
    cargo = [m for m in ongoing_missions if m['type'] == '货运']

    ports = {
        "core": "天和核心舱 (Tianhe)", "left": "梦天实验舱 (Mengtian)", "right": "问天实验舱 (Wentian)",
        "forward": None, "nadir": None, "aft": None
    }

    if len(manned) > 0: ports['forward'] = manned[0]
    if len(manned) > 1: ports['nadir'] = manned[1]
    if len(cargo) > 0: ports['aft'] = cargo[0]

    return render_template("docking_diagram.html", ports=ports)

@app.route("/astronauts/chart/cumulative")
def astronaut_cumulative_chart():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tz_cn = timezone("Asia/Shanghai")
    now_cn = datetime.now(tz_cn).strftime('%Y-%m-%d %H:%M:%S')
    
    # Identify active astronauts
    sql_active = """
        SELECT DISTINCT mc.astronaut_uid FROM missions m
        JOIN mission_crew mc ON m.id = mc.mission_id
        WHERE m.type = '载人' AND REPLACE(m.start,'T',' ') <= ? AND (m.end IS NULL OR m.end = '' OR REPLACE(m.end,'T',' ') >= ?)
    """
    cursor.execute(sql_active, (now_cn, now_cn))
    active_uids = {row['astronaut_uid'] for row in cursor.fetchall()}

    sql = """
        SELECT a.name as astronaut, a.uid, m.name as mission, m.start, m.end
        FROM mission_crew mc
        JOIN astronauts_cn a ON mc.astronaut_uid = a.uid
        JOIN missions m ON mc.mission_id = m.id
        ORDER BY m.start ASC
    """
    cursor.execute(sql)
    data = cursor.fetchall()
    conn.close()

    if not data: return "No data found."

    df = pd.DataFrame([{k: row[k] for k in row.keys()} for row in data])
    df['start'] = df['start'].astype(str).str.replace('T', ' ').str.replace('/', '-')
    df['end'] = df['end'].astype(str).str.replace('T', ' ').str.replace('/', '-')
    
    df['start_dt'] = pd.to_datetime(df['start'], errors='coerce')
    df['end_dt'] = pd.to_datetime(df['end'], errors='coerce')
    
    now_dt = datetime.now(tz_cn).replace(tzinfo=None)
    df['end_plot'] = df['end_dt'].fillna(now_dt)
    df['duration_days'] = (df['end_plot'] - df['start_dt']).dt.days

    total_durations = df.groupby('astronaut')['duration_days'].sum().sort_values(ascending=False)
    sorted_names = total_durations.index.tolist()

    photo_map = {}
    for _, row in df[['astronaut', 'uid']].drop_duplicates().iterrows():
        photo_map[row['astronaut']] = get_circular_photo(row['uid'], active=(row['uid'] in active_uids))

    fig = px.bar(df, x="astronaut", y="duration_days", color="mission",
                 title="中国航天员累计在轨时长",
                 labels={"astronaut": "", "duration_days": "在轨时长 (天)", "mission": "执行任务"},
                 color_discrete_sequence=px.colors.qualitative.G10, custom_data=["mission"])

    fig.update_layout(xaxis={'categoryorder':'array', 'categoryarray': sorted_names, 'tickfont': {'size': 14}},
                      font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=14),
                      hovermode="closest", legend_traceorder="reversed", height=800, margin=dict(b=130))

    for name in sorted_names:
        fig.add_layout_image(source=photo_map[name], x=name, y=-0.08, xref="x", yref="paper",
                             sizex=0.8, sizey=0.13, xanchor="center", yanchor="top", layer="above")

    fig.update_traces(hovertemplate="<b>%{x}</b><br>任务: %{customdata[0]}<br>时长: %{y} 天<extra></extra>")
    return render_template("interactive_chart.html", chart_html=pio.to_html(fig, full_html=False, include_plotlyjs='cdn'), page_title="航天员累计时长")

@app.route("/css-missions/interactive")
def css_interactive_chart():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, type, start, end FROM missions WHERE start >= '2021-04-29' ORDER BY start ASC")
    data = cursor.fetchall()
    conn.close()
    if not data: return "No data found."

    df = pd.DataFrame([{k: row[k] for k in row.keys()} for row in data])
    df['start'] = df['start'].astype(str).str.replace('T', ' ').str.replace('/', '-')
    df['end'] = df['end'].astype(str).str.replace('T', ' ').str.replace('/', '-')
    
    df['start_plot'] = pd.to_datetime(df['start'], errors='coerce')
    df['end_plot'] = pd.to_datetime(df['end'], errors='coerce')
    df = df.dropna(subset=['start_plot'])
    
    tz_cn = timezone("Asia/Shanghai")
    now_cn = datetime.now(tz_cn).replace(tzinfo=None)
    df['end_plot'] = df['end_plot'].fillna(now_cn)
    df['duration_days'] = (df['end_plot'] - df['start_plot']).dt.days

    fig = px.timeline(df, x_start="start_plot", x_end="end_plot", y="name", color="type",
                      title="中国空间站任务交互进度图",
                      color_discrete_map={'载人': '#e74c3c', '舱段': '#3498db', '货运': '#f1c40f'},
                      custom_data=["type", "start", "end", "duration_days"])
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="日期", rangeslider_visible=True, tickformat="%Y-%m-%d")
    fig.update_traces(hovertemplate="<b>%{y}</b><br>类型: %{customdata[0]}<br>发射: %{customdata[1]}<br>结束: %{customdata[2]}<br>时长: %{customdata[3]} 天<extra></extra>")
    fig.add_vline(x=pd.Timestamp(now_cn).timestamp() * 1000, line_width=2, line_dash="dash", line_color="red")

    return render_template("interactive_chart.html", chart_html=pio.to_html(fig, full_html=False, include_plotlyjs='cdn'))

# -------------------- Admin Routes --------------------

@app.route("/admin/missions")
@auth.login_required
def admin_mission_list():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, mid, name, start FROM missions ORDER BY start DESC")
    missions = cursor.fetchall()
    conn.close()
    return render_template("admin_mission_list.html", missions=missions)

@app.route("/admin/mission/new", methods=["GET", "POST"])
@auth.login_required
def add_new_mission():
    if request.method == "GET":
        conn = sqlite3.connect("astronauts.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT uid, name FROM astronauts_cn WHERE status = 1 ORDER BY name")
        astronauts = cursor.fetchall()
        conn.close()
        return render_template("admin_mission_form.html", astronauts=astronauts)

    # POST Logic
    name = request.form.get('name')
    mid = request.form.get('mid')
    type = request.form.get('type')
    start = request.form.get('start').replace('T', ' ')
    end = request.form.get('end')
    end = end.replace('T', ' ') if end else None
    same_crew = request.form.get('same_crew') == 'on'

    conn = sqlite3.connect("astronauts.db")
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO missions (name, mid, type, start, end) VALUES (?, ?, ?, ?, ?)", 
                       (name, mid, type, start, end))
        new_mission_id = cursor.lastrowid

        if type == '载人':
            crew_to_insert = []
            # Launch Crew
            for i in range(1, 4):
                uid = request.form.get(f"launch_0{i}")
                if uid:
                    role = 'both' if same_crew else 'launch'
                    crew_to_insert.append((new_mission_id, uid, i, role))
            # Landing Crew
            if not same_crew:
                for i in range(1, 4):
                    uid = request.form.get(f"land_0{i}")
                    if uid: crew_to_insert.append((new_mission_id, uid, i, 'landing'))
            
            if crew_to_insert:
                cursor.executemany("INSERT INTO mission_crew (mission_id, astronaut_uid, crew_order, role) VALUES (?, ?, ?, ?)", crew_to_insert)

        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error adding mission: {e}", 500
    finally:
        conn.close()
    return redirect(url_for('admin_mission_list'))

@app.route("/admin/mission/edit/<mid>", methods=["GET", "POST"])
@auth.login_required
def edit_mission(mid):
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM missions WHERE mid = ?", (mid,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        abort(404)
    mission_id = row['id']

    if request.method == "POST":
        name = request.form.get('name')
        type = request.form.get('type')
        start = request.form.get('start').replace('T', ' ')
        end = request.form.get('end')
        end = end.replace('T', ' ') if (end and end.strip() != '') else None
        same_crew = request.form.get('same_crew') == 'on'

        try:
            cursor.execute("UPDATE missions SET name=?, type=?, start=?, end=? WHERE id=?", 
                           (name, type, start, end, mission_id))
            cursor.execute("DELETE FROM mission_crew WHERE mission_id = ?", (mission_id,))
            
            if type == '载人':
                crew_to_insert = []
                for i in range(1, 4):
                    uid = request.form.get(f"launch_0{i}")
                    if uid:
                        role = 'both' if same_crew else 'launch'
                        crew_to_insert.append((mission_id, uid, i, role))
                if not same_crew:
                    for i in range(1, 4):
                        uid = request.form.get(f"land_0{i}")
                        if uid: crew_to_insert.append((mission_id, uid, i, 'landing'))
                if crew_to_insert:
                    cursor.executemany("INSERT INTO mission_crew (mission_id, astronaut_uid, crew_order, role) VALUES (?, ?, ?, ?)", crew_to_insert)
            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Error updating mission: {e}", 500
        finally:
            conn.close()
        return redirect(url_for('mission_detail', mid=mid))

    # GET Logic
    cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
    mission = cursor.fetchone()
    cursor.execute("SELECT uid, name FROM astronauts_cn WHERE status = 1 ORDER BY name")
    all_astronauts = cursor.fetchall()
    cursor.execute("SELECT astronaut_uid, crew_order, role FROM mission_crew WHERE mission_id = ? ORDER BY crew_order", (mission_id,))
    crew_rows = cursor.fetchall()

    launch_crew = ['', '', '']
    land_crew = ['', '', '']
    is_same_crew = True
    if crew_rows:
        roles = {row['role'] for row in crew_rows}
        if 'launch' in roles or 'landing' in roles: is_same_crew = False
        for row in crew_rows:
            if row['crew_order'] is None: continue
            idx = row['crew_order'] - 1
            if 0 <= idx < 3:
                if row['role'] == 'both':
                    launch_crew[idx] = row['astronaut_uid']
                    land_crew[idx] = row['astronaut_uid']
                elif row['role'] == 'launch': launch_crew[idx] = row['astronaut_uid']
                elif row['role'] == 'landing': land_crew[idx] = row['astronaut_uid']

    conn.close()
    return render_template("admin_mission_edit.html", mission=mission, all_astronauts=all_astronauts,
                         launch_crew=launch_crew, land_crew=land_crew, is_same_crew=is_same_crew)

if __name__ == "__main__":
    app.run(debug=True)