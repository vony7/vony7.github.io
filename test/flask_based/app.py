from flask import Flask, render_template, request, abort,send_file
from datetime import datetime, timezone, timedelta
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
from matplotlib.font_manager import FontProperties
import io
import pandas as pd
import numpy as np
import matplotlib.dates as mdates
import plotly.express as px
import plotly.io as pio
from PIL import Image, ImageDraw, ImageOps
import base64

tz_utc8 = timezone("Asia/Shanghai")
# --- Matplotlib Chinese Font Configuration ---
# Try to set a font that supports Chinese. 
# If your chart shows boxes instead of characters, you need to install a CJK font on your server.
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'PingFang SC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False # Fixes minus sign issues

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
@app.route("/css-missions/docking")
def css_docking_status():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tz_cn = timezone("Asia/Shanghai")
    # --- CRITICAL FIX: Use slashes '/' to match your DB format ---
    now_cn = datetime.now(tz_cn).strftime('%Y/%m/%d %H:%M:%S')
    print(f"DEBUG: Server Time (CN): {now_cn}")

    # 1. Fetch ongoing missions with CORRECTED date format comparison
    sql = """
        SELECT name, type, start, end
        FROM missions 
        WHERE start <= ? 
          AND (end IS NULL OR end = '' OR end >= ?)
        ORDER BY start DESC
    """
    cursor.execute(sql, (now_cn, now_cn))
    ongoing_missions = cursor.fetchall()

    print(f"DEBUG: Found {len(ongoing_missions)} ongoing missions:")
    for m in ongoing_missions:
        print(f" - {m['name']} ({m['type']}) Start: {m['start']} End: {m['end']}")

    # --- DEBUG: Check if missing missions even EXIST in the future ---
    # This will help us see if they are just missing from the DB entirely
    cursor.execute("SELECT name, start FROM missions WHERE start > ? ORDER BY start ASC LIMIT 5", (now_cn,))
    future_missions = cursor.fetchall()
    if future_missions:
        print("DEBUG: Future missions found in DB (not active yet):")
        for m in future_missions:
            print(f" - [FUTURE] {m['name']} starts on {m['start']}")
    else:
        print("DEBUG: No future missions found after today in DB.")
    
    conn.close()

    # 2. Separate by type
    manned = [m for m in ongoing_missions if m['type'] == '载人']
    cargo = [m for m in ongoing_missions if m['type'] == '货运']

    # 3. Initialize and Assign Ports
    ports = {
        "core": "天和核心舱 (Tianhe)",
        "left": "梦天实验舱 (Mengtian)",
        "right": "问天实验舱 (Wentian)",
        "forward": None,
        "nadir": None,
        "aft": None
    }

    if len(manned) > 0: ports['forward'] = manned[0]
    if len(manned) > 1: ports['nadir'] = manned[1]
    if len(cargo) > 0: ports['aft'] = cargo[0]

    return render_template("docking_diagram.html", ports=ports)

def get_circular_photo(uid, active=False):
    """
    Helper to create a circular base64 image.
    If active=True, draws a status ring around it.
    """
    base_dir = os.path.join(app.root_path, "static", "images", "astronauts")
    jpg = os.path.join(base_dir, f"{uid}.jpg")
    png = os.path.join(base_dir, f"{uid}.png")
    
    img_path = jpg if os.path.exists(jpg) else (png if os.path.exists(png) else os.path.join(base_dir, "default.jpg"))

    try:
        with Image.open(img_path) as img:
            img = img.convert("RGBA")
            size = min(img.size)
            img = ImageOps.fit(img, (size, size), centering=(0.5, 0.5))

            # Create standard circular mask
            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)

            # --- NEW: Draw Active Ring if currently in orbit ---
            if active:
                draw_img = ImageDraw.Draw(img)
                # Draw a thick, bright colored ring (e.g., Orbit Green or Alert Red)
                # We draw it slightly inside the edge so it doesn't get clipped
                ring_color = "#00ff00" # Bright green for 'Active'
                ring_width = int(size * 0.08) # Dynamic width based on image size (8%)
                
                # Draw multiple circles for anti-aliased thicker look, or just one thick one
                draw_img.ellipse((0, 0, size, size), outline=ring_color, width=ring_width)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
    except Exception as e:
        print(f"Error processing image for {uid}: {e}")
        return ""

@app.route("/astronauts/chart/cumulative")
def astronaut_cumulative_chart():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Identify currently ACTIVE astronauts (UIDs)
    # (Missions that started in the past, but have NO end date yet)
    tz_cn = timezone("Asia/Shanghai")
    now_cn = datetime.now(tz_cn).strftime('%Y/%m/%d %H:%M:%S')
    
    sql_active = """
        SELECT DISTINCT mc.astronaut_uid
        FROM missions m
        JOIN mission_crew mc ON m.id = mc.mission_id
        WHERE m.type = '载人' 
          AND m.start <= ? 
          AND (m.end IS NULL OR m.end = '' OR m.end >= ?)
    """
    cursor.execute(sql_active, (now_cn, now_cn))
    # Create a set for fast lookups: {'jinghaipeng', 'zhu_yangzhu', ...}
    active_uids = {row['astronaut_uid'] for row in cursor.fetchall()}

    # 2. Fetch standard chart data
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

    if not data: return "No mission data found."

    # 3. Process Data
    df = pd.DataFrame([{k: row[k] for k in row.keys()} for row in data])
    df['start_dt'] = pd.to_datetime(df['start'], format='mixed', errors='coerce')
    df['end_dt'] = pd.to_datetime(df['end'], format='mixed', errors='coerce')

    now_dt = datetime.now(tz_cn).replace(tzinfo=None)
    df['end_plot'] = df['end_dt'].fillna(now_dt)
    df['duration_days'] = (df['end_plot'] - df['start_dt']).dt.days

    total_durations = df.groupby('astronaut')['duration_days'].sum().sort_values(ascending=False)
    sorted_names = total_durations.index.tolist()

    # 4. Generate Photos with Active Status
    unique_astronauts = df[['astronaut', 'uid']].drop_duplicates()
    photo_map = {}
    for _, row in unique_astronauts.iterrows():
        # Check if this specific astronaut is in our active set
        is_active = row['uid'] in active_uids
        # Pass the True/False flag to the photo generator
        photo_map[row['astronaut']] = get_circular_photo(row['uid'], active=is_active)

    # 5. Create Chart
    fig = px.bar(
        df,
        x="astronaut",
        y="duration_days",
        color="mission",
        title="中国航天员累计在轨时长",
        labels={"astronaut": "", "duration_days": "在轨时长 (天)", "mission": "执行任务"},
        color_discrete_sequence=px.colors.qualitative.G10,
        custom_data=["mission"]
    )

    fig.update_layout(
        xaxis={'categoryorder':'array', 'categoryarray': sorted_names, 'tickfont': {'size': 14}},
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=14),
        hovermode="closest",
        legend_traceorder="reversed",
        height=800,
        margin=dict(b=130),
        # Add a subtitle to the legend or chart to explain the green ring
        annotations=[dict(
            x=0, y=-0.23, xref='paper', yref='paper',
            text="🟢 绿色光环表示当前在轨",
            showarrow=False, font=dict(size=12, color="#555")
        )]
    )

    for name in sorted_names:
        fig.add_layout_image(
            source=photo_map[name],
            x=name, y=-0.08, xref="x", yref="paper",
            sizex=0.8, sizey=0.13,
            xanchor="center", yanchor="top", layer="above"
        )

    fig.update_traces(hovertemplate="<b>%{x}</b><br>任务: %{customdata[0]}<br>时长: %{y} 天<extra></extra>")

    chart_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return render_template("interactive_chart.html", chart_html=chart_html, page_title="航天员累计时长")


@app.route("/css-missions/interactive")
def css_interactive_chart():
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch CSS missions
    cursor.execute("SELECT name, type, start, end FROM missions WHERE start >= '2021-04-29' ORDER BY start ASC")
    data = cursor.fetchall()
    conn.close()

    if not data:
        return "No data found for CSS missions."

    # 2. Process Data
    df = pd.DataFrame([{k: row[k] for k in row.keys()} for row in data])
    
    # Save raw strings for hover display
    df['start_str'] = df['start'].astype(str)
    df['end_str'] = df['end'].fillna('进行中 (Ongoing)').astype(str)

    # Convert for plotting
    df['start_plot'] = pd.to_datetime(df['start'], format='mixed', errors='coerce')
    df['end_plot'] = pd.to_datetime(df['end'], format='mixed', errors='coerce')
    df = df.dropna(subset=['start_plot'])

    # Handle ongoing missions
    tz_cn = timezone("Asia/Shanghai")
    now_cn = datetime.now(tz_cn).replace(tzinfo=None)
    df['end_plot'] = df['end_plot'].fillna(now_cn)

    # Calculate duration
    df['duration_days'] = (df['end_plot'] - df['start_plot']).dt.days

    # 3. Create Plotly Timeline
    color_map = {'载人': '#e74c3c', '舱段': '#3498db', '货运': '#f1c40f'}

    fig = px.timeline(
        df, 
        x_start="start_plot", 
        x_end="end_plot", 
        y="name",
        color="type",
        title="中国空间站任务交互进度图 (China Space Station Interactive Timeline)",
        color_discrete_map=color_map,
        custom_data=["type", "start_str", "end_str", "duration_days"]
    )

    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="日期 (Date)", rangeslider_visible=True, tickformat="%Y-%m-%d")

    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>类型: %{customdata[0]}<br>发射: %{customdata[1]}<br>结束: %{customdata[2]}<br>时长: %{customdata[3]} 天<extra></extra>"
    )

    fig.update_layout(
        height=max(600, len(df) * 40),
        font=dict(family="Microsoft YaHei, SimHei, sans-serif", size=14),
        hovermode="closest",
        legend_title_text='任务类型'
    )

    # --- FIX IS HERE ---
    # Convert 'now_cn' to milliseconds timestamp for Plotly
    now_ts = pd.Timestamp(now_cn).timestamp() * 1000
    fig.add_vline(x=now_ts, line_width=2, line_dash="dash", line_color="red", annotation_text="今天 (Today)")

    chart_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    return render_template("interactive_chart.html", chart_html=chart_html)

# Route 2: The viewer page
@app.route("/css-missions/gantt")
def css_gantt_view():
    return render_template("gantt_view.html")

@app.route("/chart/css-gantt.png")
def css_gantt_chart():
    # --- Optional: Configure Chinese Fonts if you haven't already ---
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'PingFang SC', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False 

    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Fetch only CSS missions (after Tianhe launch 2021-04-29)
    cursor.execute("SELECT name, type, start, end FROM missions WHERE start >= '2021-04-29' ORDER BY start ASC")
    data = cursor.fetchall()
    conn.close()

    if not data:
        # Handle case with no data
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No CSS Data Found", ha='center')
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close(fig)
        return send_file(img, mimetype='image/png')

    # 2. Process Data with Pandas
    df = pd.DataFrame([{k: row[k] for k in row.keys()} for row in data])
    
    # Convert to datetime
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])
    
    # Fill ongoing missions with current time for visualization
    now = datetime.now()
    df['end'] = df['end'].fillna(now)

    # Calculate duration
    df['start_num'] = mdates.date2num(df['start'])
    df['end_num'] = mdates.date2num(df['end'])
    df['duration'] = df['end_num'] - df['start_num']

    # 3. Create Plot
    fig_height = max(6, len(df) * 0.5)
    fig, ax = plt.subplots(figsize=(14, fig_height))

    colors = {'载人': '#e74c3c', '舱段': '#3498db', '货运': '#f1c40f'}
    default_c = '#95a5a6'

    for i, row in df.iterrows():
        c = colors.get(row['type'], default_c)
        ax.barh(row['name'], row['duration'], left=row['start_num'], 
                color=c, edgecolor='black', height=0.6, alpha=0.9)

    # 4. Format Chart
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate()

    ax.grid(True, axis='x', linestyle='--', alpha=0.5)
    ax.set_xlabel('日期 (Date)')
    ax.set_title('中国空间站任务进度 (China Space Station Timeline)', fontsize=14, pad=20)

    # Add 'Today' line
    ax.axvline(mdates.date2num(now), color='red', linestyle='--', alpha=0.5)

    # 5. Save to memory buffer
    img = io.BytesIO()
    plt.tight_layout()
    plt.savefig(img, format='png', dpi=100)
    img.seek(0)
    plt.close(fig)

    return send_file(img, mimetype='image/png')

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
        m_dict["end_raw"]=m["end"]
        
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
        
# -------------------- ADD THIS NEW LOGIC --------------------
    time_since_last_display = None
    if astronaut['status'] == 1:  # 1 means 'Active'
        if past_missions:
            # past_missions is already sorted by start date, DESC
            most_recent_past_mission = past_missions[0] 
            
            if most_recent_past_mission['status'] == 'ongoing':
                time_since_last_display = "目前在轨"
            
            elif most_recent_past_mission['status'] == 'completed':
                try:
                    # Use the 'end_raw' date we saved
                    last_end_dt = parser.parse(most_recent_past_mission['end_raw'])
                    if not last_end_dt.tzinfo:
                        last_end_dt = last_end_dt.replace(tzinfo=tz_utc8)
                    
                    now = datetime.now(tz_utc8)
                    time_since = now - last_end_dt
                    days_since = time_since.days

                    if days_since < 0:
                        time_since_last_display = "N/A"
                    elif days_since > 365:
                        years = days_since // 365
                        months = (days_since % 365) // 30
                        time_since_last_display = f"约 {years}年 {months}月"
                    elif days_since > 30:
                        months = days_since // 30
                        days = days_since % 30
                        time_since_last_display = f"约 {months}月 {days}天"
                    elif days_since > 0:
                         time_since_last_display = f"{days_since}天"
                    else:
                        time_since_last_display = "今天" # Landed today
                except Exception as e:
                    print(f"Error parsing last mission end date: {e}")
                    time_since_last_display = "日期错误"
        
        else: # Active, but no past missions
            time_since_last_display = "未执行任务"
    else:
        time_since_last_display = "已退役"
    # ------------------ END OF NEW LOGIC ------------------

    conn.close()
    return render_template(
        "astronaut.html",
        astronaut=astronaut,
        past_missions=past_missions,
        future_missions=future_missions,
        total_mission_time=total_display,
        time_since_last_mission=time_since_last_display
    )


# -------------------- Missions Viewer --------------------
# REPLACE this function
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
        # --- UPDATED SQL: Added ORDER BY mc.crew_order ASC ---
        cursor.execute(
            """
            SELECT a.name, a.uid
            FROM mission_crew mc
            JOIN astronauts_cn a ON mc.astronaut_uid = a.uid
            WHERE mc.mission_id = ?
            ORDER BY mc.crew_order ASC
            """,
            (m["id"],),
        )
        crew = cursor.fetchall()

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

    # ... (rest of your sorting logic) ...
    reverse = order == "desc"
    if sort_by == "duration":
        mission_data.sort(key=lambda m: m["duration_seconds"], reverse=reverse)
    elif sort_by in ("start", "end"):
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

# REPLACE this function
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
    mission_id = mission["id"]

    # --- UPDATED SQL: Added ORDER BY mc.crew_order ASC ---
    cursor.execute(
        """
        SELECT a.* FROM astronauts_cn a
        JOIN mission_crew mc ON a.uid = mc.astronaut_uid
        WHERE mc.mission_id = ?
        ORDER BY mc.crew_order ASC
        """,
        (mission_id,),
    )
    crew_rows = cursor.fetchall()
    crew = []
    for row in crew_rows:
        row = dict(row)
        row["photo_url"] = resolve_astronaut_photo(row["uid"])
        crew.append(row)

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


# 在 app.py 中添加

@app.route("/css-missions/")
def css_mission_list():
    # 1. 基本设置
    sort_by = request.args.get("sort_by", "start")
    order = request.args.get("order", "desc")
    # 这里我们不需要 'type' 过滤器，因为这是专门的 CSS 视图，
    # 但如果你想在 CSS 任务中再过滤载人/货运，可以保留它。
    mission_type = request.args.get("type") 

    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 2. 核心修改：强制过滤 2021-04-29 之后的任务 (天和核心舱发射日期)
    query = "SELECT * FROM missions WHERE start >= '2021-04-29'"
    params = []

    # 可选：如果还想支持在 CSS 任务中进一步筛选类型
    if mission_type:
        query += " AND type = ?"
        params.append(mission_type)

    cursor.execute(query, params)
    missions = cursor.fetchall()

    # 3. 数据处理 (与标准任务列表相同)
    mission_data = []
    for m in missions:
        cursor.execute(
            "SELECT a.name, a.uid FROM mission_crew mc JOIN astronauts_cn a ON mc.astronaut_uid = a.uid WHERE mc.mission_id = ? ORDER BY mc.crew_order ASC",
            (m["id"],)
        )
        crew = cursor.fetchall()
        total_seconds, duration_display, status = calculate_mission_duration(m["start"], m["end"])
        
        mission_data.append({
            "name": m["name"],
            "mid": m["mid"],
            "type": m["type"],
            "start": m["start"],
            "end": m["end"] or "进行中",
            "duration_display": duration_display,
            "duration_seconds": total_seconds,
            "crew": crew,
            "status": status
        })

    conn.close()

    # 4. 排序逻辑 (与标准任务列表相同)
    reverse = order == "desc"
    if sort_by == "duration":
        mission_data.sort(key=lambda m: m["duration_seconds"], reverse=reverse)
    elif sort_by in ("start", "end"):
         mission_data.sort(key=lambda m: (m[sort_by] if m[sort_by] and m[sort_by] != "0" else "9999-12-31"), reverse=reverse)

    # 5. 复用 missions.html 模板，但传入一个特殊的 title
    return render_template(
        "missions.html",
        missions=mission_data,
        selected_type=mission_type,
        sort_by=sort_by,
        order=order,
        page_title="中国空间站任务 (China Space Station)" # 传递一个新变量用于显示标题
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

# -------------------------------------------------
# --- REPLACE YOUR "EDIT MISSION" FUNCTION WITH THIS ---
# -------------------------------------------------
# REPLACE THIS FUNCTION in app.py
# REPLACE this function
@app.route("/admin/mission/edit/<mid>", methods=["GET", "POST"])
@auth.login_required
def edit_mission(mid):
    if request.method == "POST":
        # --- This is the UPDATE (POST) logic ---
        name = request.form.get('name')
        type = request.form.get('type')
        start = request.form.get('start')
        end = request.form.get('end')
        
        crew_01 = request.form.get('crew_01')
        crew_02 = request.form.get('crew_02')
        crew_03 = request.form.get('crew_03')

        # --- UPDATED: Create a list of tuples with the order ---
        crew_list = []
        if crew_01: crew_list.append((crew_01, 1))
        if crew_02: crew_list.append((crew_02, 2))
        if crew_03: crew_list.append((crew_03, 3))
        
        if type != '载人':
            crew_list = []
            
        if end == "": end = None
        
        conn = sqlite3.connect("astronauts.db")
        try:
            cursor = conn.cursor()
            
            # 1. Update the main 'missions' table
            sql_update_mission = "UPDATE missions SET name = ?, type = ?, start = ?, end = ? WHERE mid = ?"
            cursor.execute(sql_update_mission, (name, type, start, end, mid))
            
            # 2. Get the mission's integer ID
            cursor.execute("SELECT id FROM missions WHERE mid = ?", (mid,))
            mission_row = cursor.fetchone()
            mission_id = mission_row[0]

            # 3. --- UPDATED: Sync the 'mission_crew' table ---
            # "Scorched Earth": Delete all old crew, insert new crew. Safest way.
            cursor.execute("DELETE FROM mission_crew WHERE mission_id = ?", (mission_id,))
            
            if crew_list:
                crew_data_to_insert = [
                    (mission_id, uid, order) for (uid, order) in crew_list
                ]
                sql_crew = "INSERT INTO mission_crew (mission_id, astronaut_uid, crew_order) VALUES (?, ?, ?)"
                cursor.executemany(sql_crew, crew_data_to_insert)

            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"Database error: {e}")
            return "An error occurred while updating the mission.", 500
        finally:
            conn.close()

        return redirect(url_for('admin_mission_list'))
        
    else:
        # --- This is the LOAD (GET) logic ---
        conn = sqlite3.connect("astronauts.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM missions WHERE mid = ?", (mid,))
        mission = cursor.fetchone()
        
        if not mission:
            conn.close()
            abort(404)
        
        cursor.execute("SELECT uid, name FROM astronauts_cn WHERE status = 1 ORDER BY name")
        all_astronauts = cursor.fetchall()
        
        # --- UPDATED: Get current crew *in the correct order* ---
        cursor.execute(
            "SELECT astronaut_uid FROM mission_crew WHERE mission_id = ? ORDER BY crew_order ASC", 
            (mission['id'],)
        )
        current_crew_rows = cursor.fetchall()
        
        current_crew_list = [row['astronaut_uid'] for row in current_crew_rows]
        # Pad the list to 3 elements with empty strings
        current_crew = (current_crew_list + ["", "", ""])[:3]
        
        conn.close()
        
        return render_template(
            "admin_mission_edit.html", 
            mission=mission,
            all_astronauts=all_astronauts,
            current_crew=current_crew
        )

# 3. THE "DELETE MISSION" ROUTE (HANDLES POST ONLY)
# REPLACE this function in app.py
@app.route("/admin/mission/delete/<mid>", methods=["POST"])
@auth.login_required
def delete_mission(mid):
    try:
        conn = sqlite3.connect("astronauts.db")
        
        # --- ADD THIS LINE ---
        # This tells sqlite to return dictionaries (like {'id': 12})
        # instead of tuples (like (12,)).
        conn.row_factory = sqlite3.Row
        # ---------------------

        cursor = conn.cursor()

        # 1. Get the mission's primary ID (the integer 'id', not 'mid')
        cursor.execute("SELECT id FROM missions WHERE mid = ?", (mid,))
        mission_row = cursor.fetchone()
        
        if mission_row:
            # This line will now work correctly
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
        print(f"Database error: {e}") # This is where your error was printed
        return "An error occurred while deleting the mission.", 500
    finally:
        conn.close()

    # Success! Redirect back to the admin list
    return redirect(url_for('admin_mission_list'))

# -------------------------------------------------
# --- NEW ADMIN ROUTES (Add this at the bottom) ---
# -------------------------------------------------
# -------------------------------------------------
# --- ADMIN "CREATE" ROUTES (REPLACE THESE) ---
# -------------------------------------------------

# This page will show a form to add a new mission
@app.route("/admin/mission/new", methods=["GET"])
@auth.login_required  # <-- This magic line protects the page!
def new_mission_form():
    # --- NEW ---
    # We need to fetch all active astronauts to list them in the form
    conn = sqlite3.connect("astronauts.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all active astronauts
    cursor.execute("SELECT uid, name FROM astronauts_cn WHERE status = 1 ORDER BY name")
    astronauts = cursor.fetchall()
    conn.close()
    
    # Pass the astronauts to the template
    return render_template("admin_mission_form.html", astronauts=astronauts)

# REPLACE THIS FUNCTION in app.py
# REPLACE this function
@app.route("/admin/mission/new", methods=["POST"])
@auth.login_required
def add_new_mission():
    # 1. Get data from the form
    name = request.form.get('name')
    mid = request.form.get('mid')
    type = request.form.get('type')
    start = request.form.get('start')
    end = request.form.get('end')
    
    crew_01 = request.form.get('crew_01')
    crew_02 = request.form.get('crew_02')
    crew_03 = request.form.get('crew_03')
    
    # --- UPDATED: Create a list of tuples with the order ---
    # (uid, order)
    crew_list = []
    if crew_01: crew_list.append((crew_01, 1))
    if crew_02: crew_list.append((crew_02, 2))
    if crew_03: crew_list.append((crew_03, 3))
    
    # If the type is not 'Manned', force the crew list to be empty
    if type != 'Manned':
        crew_list = []

    if not name or not mid or not type:
        return "Error: Name, MID, and Type are required.", 400

    if end == "": end = None
        
    conn = sqlite3.connect("astronauts.db")
    try:
        cursor = conn.cursor()
        
        # 2. Insert into 'missions'
        sql = "INSERT INTO missions (name, mid, type, start, end) VALUES (?, ?, ?, ?, ?)"
        cursor.execute(sql, (name, mid, type, start, end))
        
        new_mission_id = cursor.lastrowid
        
        # 3. --- UPDATED: Insert into 'mission_crew' with order ---
        if crew_list:
            # Prepare data: (mission_id, astronaut_uid, crew_order)
            crew_data_to_insert = [
                (new_mission_id, uid, order) for (uid, order) in crew_list
            ]
            
            # Note the 3 columns in the SQL
            sql_crew = "INSERT INTO mission_crew (mission_id, astronaut_uid, crew_order) VALUES (?, ?, ?)"
            cursor.executemany(sql_crew, crew_data_to_insert)
        
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return "An error occurred while adding the mission.", 500
    finally:
        conn.close()

    return redirect(url_for('admin_mission_list'))

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