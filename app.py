"""
==================================================
SMART MESS MANAGEMENT SYSTEM - MAIN FLASK APP
==================================================
Description: Complete Flask application providing Admin & Student
portals, facial recognition attendance, menu management, notices,
complaints, payment tracking, analytics, and reporting.
==================================================
"""

import os
import sqlite3
from io import BytesIO
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_file
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from werkzeug.security import generate_password_hash, check_password_hash

# Custom project modules
from database import (
    get_db_connection, init_db, seed_demo_data,
    get_next_student_id, get_next_complaint_id
)
from face_utils import (
    register_student_face, register_student_faces,
    recognize_face_from_stream,
    detect_faces, train_model
)

# ==========================================
# FLASK APPLICATION CONFIGURATION - START
# ==========================================
app = Flask(__name__)
app.secret_key = "smart-mess-secret-key-2026-production-exhibition"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max payload
MONTHLY_MESS_FEE = 3200

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACES_DIR = os.path.join(BASE_DIR, "face_data")
app.config['FACE_DATA_FOLDER'] = os.path.join(BASE_DIR, "face_data")
app.config['EXPORTS_FOLDER'] = os.path.join(BASE_DIR, "exports")

# Ensure required directories and DB initialized on startup
os.makedirs(app.config['FACE_DATA_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXPORTS_FOLDER'], exist_ok=True)
init_db()
seed_demo_data()
# ==========================================
# FLASK APPLICATION CONFIGURATION - END
# ==========================================


# ==========================================
# AUTHENTICATION DECORATORS & HELPERS - START
# ==========================================
def admin_required(f):
    """
    Decorator to restrict route access strictly to authenticated Admins.
    Redirects unauthenticated users or students to the login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_role" not in session or session["user_role"] != "admin":
            flash("Admin access required. Please log in as an administrator.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """
    Decorator to restrict route access strictly to authenticated Students.
    Ensures students cannot view admin tools and can only view their own records.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_role" not in session or session["user_role"] != "student":
            flash("Please log in with your Student ID to access the student portal.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def get_meal_for_time(hour=None):
    """Return the active mess meal using the exact required time windows."""
    if hour is None:
        hour = datetime.now().hour

    if 7 <= hour <= 11:
        return "Breakfast"
    if 12 <= hour <= 16:
        return "Lunch"
    if 19 <= hour <= 22:
        return "Dinner"
    if hour < 7:
        return "Breakfast"
    if 17 <= hour < 19:
        return "Lunch"
    return "Dinner"


@app.context_processor
def inject_global_vars():
    """
    Injects global context variables accessible in all Jinja templates.
    """
    now = datetime.now()
    return {
        "current_year": now.year,
        "current_date": now.strftime("%Y-%m-%d"),
        "current_day": now.strftime("%A"),
        "user_role": session.get("user_role"),
        "user_name": session.get("user_name"),
        "user_id": session.get("user_id"),
        "student_id": session.get("student_id")
    }
# ==========================================
# AUTHENTICATION DECORATORS & HELPERS - END
# ==========================================


# ==========================================
# AUTHENTICATION ROUTES - START
# ==========================================
@app.route("/")
def index():
    """
    Landing redirect based on login session or to login page.
    """
    if "user_role" in session:
        if session["user_role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif session["user_role"] == "student":
            return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Universal Login Portal supporting both Admin and Student authentication.
    """
    if request.method == "POST":
        login_type = request.form.get("login_type", "admin")
        username_or_id = request.form.get("username_or_id", "").strip()
        password = request.form.get("password", "").strip()

        if not username_or_id or not password:
            flash("Please enter both username/ID and password.", "danger")
            return render_template("login.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        if login_type == "admin":
            # Admin Authentication by username or email
            cursor.execute("""
            SELECT id, username, email, password_hash, name
            FROM admins
            WHERE username = ? OR email = ?
            """, (username_or_id, username_or_id))
            admin = cursor.fetchone()
            conn.close()

            if admin and check_password_hash(admin["password_hash"], password):
                session.clear()
                session["user_role"] = "admin"
                session["user_id"] = admin["id"]
                session["user_name"] = admin["name"]
                session["username"] = admin["username"]
                flash(f"Welcome back, {admin['name']}!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid admin username/email or password.", "danger")

        elif login_type == "student":
            # Student Authentication by Student ID
            cursor.execute("""
            SELECT id, student_id, full_name, password_hash, payment_status
            FROM students
            WHERE student_id = ? OR roll_number = ?
            """, (username_or_id.upper(), username_or_id))
            student = cursor.fetchone()
            conn.close()

            if student and check_password_hash(student["password_hash"], password):
                session.clear()
                session["user_role"] = "student"
                session["user_id"] = student["id"]
                session["student_id"] = student["student_id"]
                session["user_name"] = student["full_name"]
                session["payment_status"] = student["payment_status"]
                flash(f"Welcome to Smart Mess, {student['full_name']}!", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash("Invalid Student ID/Roll Number or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """
    Clears active user session and redirects to login.
    """
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))
# ==========================================
# AUTHENTICATION ROUTES - END
# ==========================================


# ==========================================
# ADMIN DASHBOARD & ANALYTICS - START
# ==========================================
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    """Simplified admin dashboard with core counts and menu display."""
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_day = datetime.now().strftime("%A")
    menu_view = request.args.get("menu_view", "today")

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND meal = 'Breakfast'", (today_str,))
    today_breakfast = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND meal = 'Lunch'", (today_str,))
    today_lunch = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND meal = 'Dinner'", (today_str,))
    today_dinner = cursor.fetchone()[0]

    total_meals_today = today_breakfast + today_lunch + today_dinner

    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Paid'")
    paid_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Unpaid'")
    unpaid_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Pending'")
    pending_fee_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'")
    pending_complaints = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'")
    in_progress_complaints = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'")
    resolved_complaints = cursor.fetchone()[0]

    cursor.execute("SELECT id, title, content, priority, created_at FROM notices ORDER BY id DESC LIMIT 3")
    recent_notices = cursor.fetchall()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_menu = {}
    for day in days:
        cursor.execute("SELECT meal_type, items, special_notes, availability_status FROM menu WHERE day_of_week = ?", (day,))
        day_rows = cursor.fetchall()
        weekly_menu[day] = {row["meal_type"]: {"items": row["items"], "special_notes": row["special_notes"], "availability_status": row["availability_status"]} for row in day_rows}

    cursor.execute("SELECT meal_type, items, special_notes, availability_status FROM menu WHERE day_of_week = ?", (current_day,))
    today_menu_rows = cursor.fetchall()
    today_menu = {row["meal_type"]: {"items": row["items"], "special_notes": row["special_notes"], "availability_status": row["availability_status"]} for row in today_menu_rows}

    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_students=total_students,
        today_breakfast=today_breakfast,
        today_lunch=today_lunch,
        today_dinner=today_dinner,
        total_meals_today=total_meals_today,
        paid_students=paid_students,
        unpaid_students=unpaid_students,
        pending_fee_students=pending_fee_students,
        pending_complaints=pending_complaints,
        in_progress_complaints=in_progress_complaints,
        resolved_complaints=resolved_complaints,
        today_menu=today_menu,
        weekly_menu=weekly_menu,
        recent_notices=recent_notices,
        menu_view=menu_view,
        days=days,
        current_day=current_day
    )
# ==========================================
# ADMIN DASHBOARD & ANALYTICS - END
# ==========================================


# ==========================================
# WEEKLY MESS MENU MANAGEMENT - START
# ==========================================
@app.route("/admin/menu", methods=["GET", "POST"])
@admin_required
def admin_menu():
    """View and update individual weekly meal entries for mess administrators."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meal_types = ["Breakfast", "Lunch", "Dinner"]
    statuses = ["Available", "Special Menu", "Not Available"]

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        day = request.form.get("day_of_week", "").strip()
        meal_type = request.form.get("meal_type", "").strip()
        items = request.form.get("items", "").strip()
        special_notes = request.form.get("special_notes", "").strip()
        availability_status = request.form.get("availability_status", "Available").strip()

        if day not in days or meal_type not in meal_types or availability_status not in statuses:
            flash("Invalid menu update request.", "danger")
        elif availability_status != "Not Available" and not items:
            flash("Add menu items before marking a meal available.", "danger")
        else:
            cursor.execute("""
            UPDATE menu
            SET items = ?, special_notes = ?, availability_status = ?, updated_at = ?
            WHERE day_of_week = ? AND meal_type = ?
            """, (items or "Not available", special_notes, availability_status,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"), day, meal_type))
            conn.commit()
            flash(f"{day} {meal_type} updated successfully.", "success")

        conn.close()
        return redirect(url_for("admin_menu"))

    cursor.execute("""
    SELECT day_of_week, meal_type, items, special_notes, availability_status, updated_at
    FROM menu
    ORDER BY CASE day_of_week
      WHEN 'Monday' THEN 1 WHEN 'Tuesday' THEN 2 WHEN 'Wednesday' THEN 3
      WHEN 'Thursday' THEN 4 WHEN 'Friday' THEN 5 WHEN 'Saturday' THEN 6 WHEN 'Sunday' THEN 7
    END, CASE meal_type WHEN 'Breakfast' THEN 1 WHEN 'Lunch' THEN 2 WHEN 'Dinner' THEN 3 END
    """)
    menu_rows = cursor.fetchall()
    conn.close()

    weekly_menu = {day: {} for day in days}
    for row in menu_rows:
        weekly_menu[row["day_of_week"]][row["meal_type"]] = row

    return render_template(
        "admin/menu.html",
        days=days,
        meal_types=meal_types,
        statuses=statuses,
        weekly_menu=weekly_menu
    )
# ==========================================
# WEEKLY MESS MENU MANAGEMENT - END
# ==========================================


# ==========================================
# STUDENT MANAGEMENT (ADMIN) - START
# ==========================================
@app.route("/admin/students")
@admin_required
def admin_students():
    """
    Displays the student directory with real-time search and branch/payment filters.
    """
    search = request.args.get("search", "").strip()
    branch = request.args.get("branch", "").strip()
    payment = request.args.get("payment", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT id, student_id, full_name, roll_number, branch, semester, mobile_number, payment_status, face_registered, face_image_path, registration_date
    FROM students
    WHERE 1=1
    """
    params = []

    if search:
        query += " AND (full_name LIKE ? OR roll_number LIKE ? OR student_id LIKE ? OR mobile_number LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    if branch:
        query += " AND branch = ?"
        params.append(branch)
    if payment:
        query += " AND payment_status = ?"
        params.append(payment)

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    students = cursor.fetchall()

    # Get distinct branches for filter dropdown
    cursor.execute("SELECT DISTINCT branch FROM students ORDER BY branch ASC")
    branches = [row["branch"] for row in cursor.fetchall() if row["branch"]]

    next_id = get_next_student_id()
    conn.close()

    return render_template(
        "admin/students.html",
        students=students,
        branches=branches,
        next_id=next_id,
        search=search,
        selected_branch=branch,
        selected_payment=payment
    )


@app.route("/admin/students/add", methods=["POST"])
@admin_required
def admin_add_student():
    """
    Registers a new student record and optionally processes their initial webcam face photo.
    """
    student_id = request.form.get("student_id", "").strip().upper()
    full_name = request.form.get("full_name", "").strip()
    roll_number = request.form.get("roll_number", "").strip().upper()
    branch = request.form.get("branch", "").strip()
    semester = request.form.get("semester", "").strip()
    mobile_number = request.form.get("mobile_number", "").strip()
    password = request.form.get("password", "").strip()
    payment_status = request.form.get("payment_status", "Unpaid")
    face_image_b64 = request.form.get("face_image_b64", "")

    if not full_name or not roll_number or not branch or not semester or not mobile_number:
        flash("Please fill in all mandatory student details.", "danger")
        return redirect(url_for("admin_students"))

    if not student_id:
        student_id = get_next_student_id()

    if not password:
        password = "student123"  # Default initial password

    password_hash = generate_password_hash(password)
    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO students (student_id, full_name, roll_number, branch, semester, mobile_number, password_hash, payment_status, face_registered, registration_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (student_id, full_name, roll_number, branch, semester, mobile_number, password_hash, payment_status, today_str))
        conn.commit()
        conn.close()

        # If a face snapshot was captured during registration, register it
        if face_image_b64 and len(face_image_b64) > 100:
            face_res = register_student_face(student_id, face_image_b64)
            if face_res["success"]:
                flash(f"Student {student_id} ({full_name}) and Face Model registered successfully!", "success")
            else:
                flash(f"Student saved, but Face Registration warning: {face_res['message']}", "warning")
        else:
            flash(f"Student {student_id} registered successfully! (Face capture pending)", "success")

    except sqlite3.IntegrityError as e:
        conn.close()
        flash(f"Error: A student with ID '{student_id}' or Roll Number '{roll_number}' already exists.", "danger")

    return redirect(url_for("admin_students"))


@app.route("/admin/students/<student_id>/edit", methods=["POST"])
@admin_required
def admin_edit_student(student_id):
    """
    Updates an existing student's demographic details and payment status.
    """
    full_name = request.form.get("full_name", "").strip()
    roll_number = request.form.get("roll_number", "").strip().upper()
    branch = request.form.get("branch", "").strip()
    semester = request.form.get("semester", "").strip()
    mobile_number = request.form.get("mobile_number", "").strip()
    payment_status = request.form.get("payment_status", "Unpaid")
    new_password = request.form.get("new_password", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if new_password:
        pass_hash = generate_password_hash(new_password)
        cursor.execute("""
        UPDATE students
        SET full_name = ?, roll_number = ?, branch = ?, semester = ?, mobile_number = ?, payment_status = ?, password_hash = ?
        WHERE student_id = ?
        """, (full_name, roll_number, branch, semester, mobile_number, payment_status, pass_hash, student_id))
    else:
        cursor.execute("""
        UPDATE students
        SET full_name = ?, roll_number = ?, branch = ?, semester = ?, mobile_number = ?, payment_status = ?
        WHERE student_id = ?
        """, (full_name, roll_number, branch, semester, mobile_number, payment_status, student_id))

    conn.commit()
    conn.close()
    flash(f"Student {student_id} details updated successfully.", "success")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/<student_id>/delete", methods=["POST"])
@admin_required
def admin_delete_student(student_id):
    """
    Deletes a student record and removes any stored facial training images.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted != 1:
        flash(f"Student {student_id} was not found and was not deleted.", "danger")
        return redirect(url_for("admin_students"))

    # Clean up face directory
    student_face_dir = os.path.join(FACES_DIR, student_id)
    if os.path.exists(student_face_dir):
        import shutil
        shutil.rmtree(student_face_dir, ignore_errors=True)
        # Retrain model without this student
        train_model()

    flash(f"Student {student_id} deleted successfully.", "info")
    return redirect(url_for("admin_students"))


@app.route("/admin/students/<student_id>/register-face", methods=["POST"])
@admin_required
def admin_update_student_face(student_id):
    """
    API endpoint for capturing/updating a student's facial training samples via webcam.
    """
    data = request.get_json() or {}
    images_b64 = data.get("images_b64")
    if not images_b64:
        image_b64 = data.get("image_b64") or data.get("image") or data.get("face_image", "")
        images_b64 = [image_b64] if image_b64 else []

    if not images_b64:
        return jsonify({"success": False, "message": "No image data received from webcam."}), 400

    result = register_student_faces(student_id, images_b64)
    return jsonify(result)


@app.route("/admin/students/<student_id>/profile-json")
@admin_required
def admin_student_profile_json(student_id):
    """
    Returns student profile and consumption stats for the quick view modal.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, student_id, full_name, roll_number, branch, semester, mobile_number, payment_status, face_registered, face_image_path, registration_date
    FROM students
    WHERE student_id = ?
    """, (student_id,))
    student = cursor.fetchone()

    if not student:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    # Count meal attendance
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_id,))
    total_meals = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Breakfast'", (student_id,))
    breakfast_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Lunch'", (student_id,))
    lunch_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Dinner'", (student_id,))
    dinner_count = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        "student_id": student["student_id"],
        "full_name": student["full_name"],
        "roll_number": student["roll_number"],
        "branch": student["branch"],
        "semester": student["semester"],
        "mobile_number": student["mobile_number"],
        "payment_status": student["payment_status"],
        "face_registered": student["face_registered"],
        "face_image_path": student["face_image_path"],
        "registration_date": student["registration_date"],
        "total_meals": total_meals,
        "breakfast_count": breakfast_count,
        "lunch_count": lunch_count,
        "dinner_count": dinner_count
    })
# ==========================================
# STUDENT MANAGEMENT (ADMIN) - END
# ==========================================


# ==========================================
# FACE ATTENDANCE SCANNER (ADMIN ONLY) - START
# ==========================================
@app.route("/admin/attendance")
@admin_required
def admin_attendance():
    """
    Admin-only Live Facial Attendance Scanner view.
    Includes meal selector (Breakfast, Lunch, Dinner), live webcam feed,
    recognition alerts, and today's instant scan logs.
    """
    default_meal = get_meal_for_time()

    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.id, a.student_id, s.full_name, s.roll_number, s.branch, a.time, a.meal, a.marked_by
    FROM attendance a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.date = ?
    ORDER BY a.id DESC
    LIMIT 10
    """, (today_str,))
    today_scans = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/attendance.html",
        default_meal=default_meal,
        today_scans=today_scans
    )


@app.route("/admin/attendance/scan", methods=["POST"])
@app.route("/admin/attendance/recognize", methods=["POST"])
@admin_required
def admin_attendance_scan():
    """
    Processes a live webcam frame during face attendance scanning.
    Checks:
      1. Single face detected (or returns 'No face detected.' / 'Please ensure only one student is visible.')
      2. Student recognized by LBPH recognizer (or returns 'Student not recognized.')
      3. Check duplicate attendance for (student_id, date, meal) via logic and DB constraint
      4. Saves attendance with timestamp
    """
    data = request.get_json() or {}
    image_b64 = data.get("image_b64") or data.get("image") or data.get("frame", "")
    meal = data.get("meal", "Lunch")

    if not image_b64:
        return jsonify({"success": False, "status": "no_face", "message": "No face image received from webcam."}), 400

    # 1. Perform Face Recognition on Frame
    rec_result = recognize_face_from_stream(image_b64)

    if not rec_result["success"]:
        return jsonify(rec_result)

    student_id = rec_result["student_id"]
    student_info = rec_result["student"]
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_time_str = datetime.now().strftime("%H:%M:%S")

    # 2. Duplicate Attendance Check
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, time FROM attendance
    WHERE student_id = ? AND date = ? AND meal = ?
    """, (student_id, today_str, meal))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return jsonify({
            "success": False,
            "status": "already_marked",
            "student_id": student_id,
            "student_name": student_info["full_name"],
            "meal": meal,
            "marked_at": existing["time"],
            "message": f"Attendance already marked for {student_info['full_name']} ({student_id}) for {meal} today at {existing['time']}."
        })

    # 3. Save Attendance Record into Database
    try:
        cursor.execute("""
        INSERT INTO attendance (student_id, date, time, meal, status, marked_by)
        VALUES (?, ?, ?, ?, 'Present', 'Admin Face Scan')
        """, (student_id, today_str, now_time_str, meal))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()

        return jsonify({
            "success": True,
            "status": "marked",
            "record_id": record_id,
            "student_id": student_id,
            "student_name": student_info["full_name"],
            "roll_number": student_info["roll_number"],
            "branch": student_info["branch"],
            "meal": meal,
            "time": now_time_str,
            "confidence": rec_result.get("confidence", 95.0),
            "payment_status": student_info.get("payment_status", "Unpaid"),
            "message": f"Attendance marked successfully for {student_info['full_name']} ({meal})."
        })

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({
            "success": False,
            "status": "already_marked",
            "student_id": student_id,
            "student_name": student_info["full_name"],
            "message": f"Attendance already marked for {meal} today."
        })


@app.route("/admin/attendance/manual", methods=["POST"])
@app.route("/admin/attendance/manual-mark", methods=["POST"])
@admin_required
def admin_manual_attendance():
    """
    Allows Admin to manually mark attendance in case of student card/camera issues.
    """
    student_id = request.form.get("student_id", "").strip().upper()
    meal = request.form.get("meal", "Lunch")
    date_str = request.form.get("date", datetime.now().strftime("%Y-%m-%d"))
    time_str = datetime.now().strftime("%H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check student exists
    cursor.execute("SELECT full_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        flash(f"Student ID '{student_id}' does not exist.", "danger")
        return redirect(url_for("admin_attendance_records"))

    try:
        cursor.execute("""
        INSERT INTO attendance (student_id, date, time, meal, status, marked_by)
        VALUES (?, ?, ?, ?, 'Present', 'Admin Manual Override')
        """, (student_id, date_str, time_str, meal))
        conn.commit()
        conn.close()
        flash(f"Manual attendance marked for {student['full_name']} ({student_id}) - {meal}.", "success")
    except sqlite3.IntegrityError:
        conn.close()
        flash(f"Attendance for {student_id} on {date_str} ({meal}) has already been recorded.", "warning")

    return redirect(url_for("admin_attendance_records"))


@app.route("/admin/attendance/records")
@admin_required
def admin_attendance_records():
    """
    Complete filterable attendance log history for the Admin.
    """
    date_filter = request.args.get("date", "")
    meal_filter = request.args.get("meal", "")
    student_filter = request.args.get("student", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT a.id, a.student_id, s.full_name, s.roll_number, s.branch, a.date, a.time, a.meal, a.status, a.marked_by
    FROM attendance a
    JOIN students s ON a.student_id = s.student_id
    WHERE 1=1
    """
    params = []

    if date_filter:
        query += " AND a.date = ?"
        params.append(date_filter)
    if meal_filter:
        query += " AND a.meal = ?"
        params.append(meal_filter)
    if student_filter:
        query += " AND (a.student_id LIKE ? OR s.full_name LIKE ? OR s.roll_number LIKE ?)"
        params.extend([f"%{student_filter}%", f"%{student_filter}%", f"%{student_filter}%"])

    query += " ORDER BY a.date DESC, a.time DESC LIMIT 200"
    cursor.execute(query, params)
    records = cursor.fetchall()

    # Get student list for manual attendance modal dropdown
    cursor.execute("SELECT student_id, full_name, roll_number FROM students ORDER BY student_id ASC")
    students_list = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/attendance_records.html",
        records=records,
        students_list=students_list,
        selected_date=date_filter,
        selected_meal=meal_filter,
        search_student=student_filter
    )


@app.route("/admin/attendance/<int:attendance_id>/delete", methods=["POST"])
@admin_required
def admin_delete_attendance(attendance_id):
    """Deletes exactly one attendance log identified by its primary key."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE id = ?", (attendance_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 1:
        flash(f"Attendance log #{attendance_id} deleted successfully.", "success")
    else:
        flash(f"Attendance log #{attendance_id} was not found and was not deleted.", "danger")
    return redirect(url_for("admin_attendance_records"))
# ==========================================
# FACE ATTENDANCE SCANNER (ADMIN ONLY) - END
# ==========================================


# ==========================================
# DAILY MESS MENU MANAGEMENT - START
# ==========================================
# ==========================================
# DAILY MESS MENU MANAGEMENT - REMOVED
# Dashboard-only menu is kept in the dashboard UI.
# ==========================================


# ==========================================
# IMPORTANT NOTICES MANAGEMENT - START
# ==========================================
@app.route("/admin/notices", methods=["GET", "POST"])
@admin_required
def admin_notices():
    """
    Admin notice board manager: create, edit, delete, and prioritize notices.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action", "create")

        if action == "create":
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            priority = request.form.get("priority", "Normal")

            if title and content:
                cursor.execute("""
                INSERT INTO notices (title, content, priority, created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                """, (title, content, priority, session.get("user_name", "Admin"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
                flash("Notice posted successfully.", "success")
            else:
                flash("Title and content are required for posting a notice.", "danger")

        elif action == "edit":
            notice_id = request.form.get("notice_id")
            title = request.form.get("title", "").strip()
            content = request.form.get("content", "").strip()
            priority = request.form.get("priority", "Normal")

            if notice_id and title and content:
                cursor.execute("""
                UPDATE notices
                SET title = ?, content = ?, priority = ?
                WHERE id = ?
                """, (title, content, priority, notice_id))
                conn.commit()
                flash("Notice updated successfully.", "success")

    cursor.execute("SELECT id, title, content, priority, created_by, created_at FROM notices ORDER BY id DESC")
    notices = cursor.fetchall()
    conn.close()

    return render_template("admin/notices.html", notices=notices)


@app.route("/admin/notices/<int:notice_id>/delete", methods=["POST"])
@admin_required
def admin_delete_notice(notice_id):
    """
    Deletes an existing notice.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted == 1:
        flash("Notice deleted successfully.", "success")
    else:
        flash("The selected notice was not found and was not deleted.", "danger")
    return redirect(url_for("admin_notices"))
# ==========================================
# IMPORTANT NOTICES MANAGEMENT - END
# ==========================================


# ==========================================
# COMPLAINTS MANAGEMENT (ADMIN) - START
# ==========================================
@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    """
    Admin complaints portal: view student grievances, filter by status/category, and submit resolution replies.
    """
    status_filter = request.args.get("status", "")
    category_filter = request.args.get("category", "")

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
    SELECT c.id, c.complaint_id, c.student_id, s.full_name, s.roll_number, s.branch,
           c.category, c.title, c.description, c.status, c.admin_response, c.created_at, c.updated_at
    FROM complaints c
    JOIN students s ON c.student_id = s.student_id
    WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND c.status = ?"
        params.append(status_filter)
    if category_filter:
        query += " AND c.category = ?"
        params.append(category_filter)

    query += " ORDER BY c.id DESC"
    cursor.execute(query, params)
    complaints = cursor.fetchall()
    conn.close()

    categories = ["Food Quality", "Food Quantity", "Hygiene", "Timing", "Staff Behaviour", "Other"]

    return render_template(
        "admin/complaints.html",
        complaints=complaints,
        categories=categories,
        selected_status=status_filter,
        selected_category=category_filter
    )


@app.route("/admin/complaints/<complaint_id>/respond", methods=["POST"])
@app.route("/admin/complaints/<complaint_id>/status", methods=["POST"])
@admin_required
def admin_respond_complaint(complaint_id):
    """
    Updates the resolution status of a student complaint and attaches official admin comments.
    """
    status = request.form.get("status", "In Progress")
    admin_response = request.form.get("admin_response", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE complaints
    SET status = ?, admin_response = ?, updated_at = ?
    WHERE complaint_id = ? OR id = ?
    """, (status, admin_response, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(complaint_id), str(complaint_id)))
    conn.commit()
    conn.close()

    flash(f"Complaint status updated to '{status}'.", "success")
    return redirect(url_for("admin_complaints"))
# ==========================================
# COMPLAINTS MANAGEMENT (ADMIN) - END
# ==========================================


# ==========================================
# PAYMENT MANAGEMENT (ADMIN) - START
# ==========================================
@app.route("/admin/payments", methods=["GET", "POST"])
@admin_required
def admin_payments():
    """
    Admin Payment Status manager: toggle student fee statuses (Paid, Unpaid, Pending)
    and view historical payment records.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        student_id = request.form.get("student_id")
        new_status = request.form.get("payment_status") or request.form.get("status")

        if student_id and new_status:
            cursor.execute("""
            UPDATE students
            SET payment_status = ?
            WHERE student_id = ?
            """, (new_status, student_id))
            conn.commit()
            flash(f"Payment status for {student_id} updated to '{new_status}'.", "success")

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()

    # Calculate overall stats
    cursor.execute("SELECT COUNT(*) FROM students")
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Paid'")
    paid_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Unpaid'")
    unpaid_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM students WHERE payment_status = 'Pending'")
    pending_count = cursor.fetchone()[0]

    stats = {
        "total": total_count,
        "paid": paid_count,
        "unpaid": unpaid_count,
        "pending": pending_count
    }

    query = """
    SELECT id, student_id, full_name, roll_number, branch, semester, mobile_number, payment_status, registration_date
    FROM students
    WHERE 1=1
    """
    params = []

    if search:
        query += " AND (full_name LIKE ? OR student_id LIKE ? OR roll_number LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if status_filter:
        query += " AND payment_status = ?"
        params.append(status_filter)

    query += " ORDER BY student_id ASC"
    cursor.execute(query, params)
    students = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/payments.html",
        students=students,
        stats=stats,
        search=search,
        selected_status=status_filter,
        monthly_fee=MONTHLY_MESS_FEE
    )


@app.route("/admin/payments/<student_id>/status", methods=["POST"])
@app.route("/admin/payments/<student_id>/update", methods=["POST"])
@admin_required
def admin_update_payment_status(student_id):
    """
    Updates the payment status of a student via route parameter.
    """
    new_status = request.form.get("status") or request.form.get("payment_status")
    if student_id and new_status:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET payment_status = ? WHERE student_id = ?", (new_status, student_id))
        conn.commit()
        conn.close()
        flash(f"Payment status for {student_id} updated to '{new_status}'.", "success")

    return redirect(url_for("admin_payments"))
# ==========================================
# PAYMENT MANAGEMENT (ADMIN) - END
# ==========================================


def _xlsx_response(filename, title, headers, rows):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Smart Mess"
    worksheet.append([title])
    worksheet.append([])
    worksheet.append(headers)
    for row in rows:
        worksheet.append(list(row))

    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    worksheet["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    worksheet["A1"].fill = PatternFill("solid", fgColor="176B87")
    worksheet["A1"].alignment = Alignment(horizontal="center")
    for cell in worksheet[3]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="24434D")
        cell.alignment = Alignment(horizontal="center")
    for column_index in range(1, len(headers) + 1):
        column_values = [worksheet.cell(row=row_index, column=column_index).value for row_index in range(3, worksheet.max_row + 1)]
        width = min(max(len(str(value or "")) for value in column_values) + 2, 32)
        worksheet.column_dimensions[worksheet.cell(row=3, column=column_index).column_letter].width = width
    worksheet.freeze_panes = "A4"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _pdf_response(filename, title, headers, rows):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(title, styles["Title"]),
        Spacer(1, 6 * mm)
    ]
    table_data = [headers] + [[str(value or "") for value in row] for row in rows]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176B87")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    document.build(elements)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype="application/pdf")


def _attendance_export_rows():
    date_filter = request.args.get("date", "")
    meal_filter = request.args.get("meal", "")
    student_filter = request.args.get("student", "").strip()
    query = """
    SELECT a.id, a.student_id, s.full_name, a.date, a.time, a.meal, a.status, a.marked_by
    FROM attendance a
    JOIN students s ON a.student_id = s.student_id
    WHERE 1=1
    """
    params = []
    if date_filter:
        query += " AND a.date = ?"
        params.append(date_filter)
    if meal_filter:
        query += " AND a.meal = ?"
        params.append(meal_filter)
    if student_filter:
        query += " AND (a.student_id LIKE ? OR s.full_name LIKE ? OR s.roll_number LIKE ?)"
        params.extend([f"%{student_filter}%"] * 3)
    query += " ORDER BY a.date DESC, a.time DESC LIMIT 200"
    conn = get_db_connection()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


@app.route("/admin/attendance/export/<export_format>")
@admin_required
def admin_export_attendance(export_format):
    """Exports the currently filtered attendance logs as Excel or PDF."""
    if export_format not in {"xlsx", "pdf"}:
        return "Unsupported export format", 404
    rows = _attendance_export_rows()
    headers = ["Log ID", "Student ID", "Student Name", "Date", "Time", "Meal", "Status", "Marked By"]
    data = [[row["id"], row["student_id"], row["full_name"], row["date"], row["time"], row["meal"], row["status"], row["marked_by"]] for row in rows]
    title = "Smart Mess Attendance Logs"
    if export_format == "xlsx":
        return _xlsx_response("attendance_logs.xlsx", title, headers, data)
    return _pdf_response("attendance_logs.pdf", title, headers, data)


@app.route("/admin/students/export/<export_format>")
@admin_required
def admin_export_student_day_counts(export_format):
    """Exports student-wise distinct attendance day counts and fee status."""
    if export_format not in {"xlsx", "pdf"}:
        return "Unsupported export format", 404
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT s.student_id, s.full_name, COUNT(DISTINCT a.date) AS day_count,
           s.payment_status
    FROM students s
    LEFT JOIN attendance a ON a.student_id = s.student_id
    GROUP BY s.id, s.student_id, s.full_name, s.payment_status
    ORDER BY s.student_id ASC
    """).fetchall()
    conn.close()
    headers = ["Student ID", "Student Name", "Total Days", "Monthly Mess Fee", "Payment Status"]
    data = [[row["student_id"], row["full_name"], row["day_count"], f"₹{MONTHLY_MESS_FEE}", row["payment_status"]] for row in rows]
    title = "Smart Mess Student Day Count and Fee Status"
    if export_format == "xlsx":
        return _xlsx_response("student_day_counts.xlsx", title, headers, data)
    return _pdf_response("student_day_counts.pdf", title, headers, data)


# ==========================================
# STUDENT PORTAL ROUTES - START
# ==========================================
@app.route("/student/dashboard")
@student_required
def student_dashboard():
    """Student dashboard with the required simplified menu and personal details."""
    student_id = session.get("student_id")
    current_day = datetime.now().strftime("%A")
    menu_view = request.args.get("menu_view", "today")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT student_id, full_name, roll_number, branch, semester, mobile_number, payment_status, face_registered, registration_date
    FROM students
    WHERE student_id = ?
    """, (student_id,))
    student = cursor.fetchone()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_menu = {}
    for day in days:
        cursor.execute("SELECT meal_type, items, special_notes, availability_status FROM menu WHERE day_of_week = ?", (day,))
        day_rows = cursor.fetchall()
        weekly_menu[day] = {row["meal_type"]: {"items": row["items"], "special_notes": row["special_notes"], "availability_status": row["availability_status"]} for row in day_rows}

    cursor.execute("SELECT meal_type, items, special_notes, availability_status FROM menu WHERE day_of_week = ?", (current_day,))
    menu_rows = cursor.fetchall()
    today_menu = {row["meal_type"]: {"items": row["items"], "special_notes": row["special_notes"], "availability_status": row["availability_status"]} for row in menu_rows}

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ?", (student_id,))
    total_meals = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Breakfast'", (student_id,))
    breakfast_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Lunch'", (student_id,))
    lunch_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance WHERE student_id = ? AND meal = 'Dinner'", (student_id,))
    dinner_count = cursor.fetchone()[0]

    cursor.execute("""
    SELECT id, date, time, meal, status, marked_by
    FROM attendance
    WHERE student_id = ?
    ORDER BY date DESC, time DESC
    LIMIT 6
    """, (student_id,))
    recent_logs = cursor.fetchall()

    cursor.execute("SELECT id, title, content, priority, created_by, created_at FROM notices ORDER BY id DESC LIMIT 5")
    notices = cursor.fetchall()

    cursor.execute("""
    SELECT complaint_id, category, title, status, admin_response, created_at
    FROM complaints
    WHERE student_id = ?
    ORDER BY id DESC LIMIT 3
    """, (student_id,))
    my_complaints = cursor.fetchall()

    conn.close()

    return render_template(
        "student/dashboard.html",
        student=student,
        today_menu=today_menu,
        weekly_menu=weekly_menu,
        days=days,
        menu_view=menu_view,
        current_day=current_day,
        total_meals=total_meals,
        breakfast_count=breakfast_count,
        lunch_count=lunch_count,
        dinner_count=dinner_count,
        recent_attendance=recent_logs,
        recent_logs=recent_logs,
        notices=notices,
        my_complaints=my_complaints
    )


@app.route("/student/complaints", methods=["GET", "POST"])
@student_required
def student_complaints():
    """
    Student complaint portal: submit new grievances and track resolution feedback.
    """
    student_id = session.get("student_id")
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "Other")
        description = request.form.get("description", "").strip()

        if title and description:
            complaint_id = get_next_complaint_id()
            cursor.execute("""
            INSERT INTO complaints (complaint_id, student_id, category, title, description, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'Pending', ?)
            """, (complaint_id, student_id, category, title, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash(f"Complaint {complaint_id} submitted successfully. The mess administration will review it.", "success")
            return redirect(url_for("student_complaints"))
        else:
            flash("Please fill in both title and description.", "danger")

    cursor.execute("""
    SELECT complaint_id, category, title, description, status, admin_response, created_at, updated_at
    FROM complaints
    WHERE student_id = ?
    ORDER BY id DESC
    """, (student_id,))
    complaints = cursor.fetchall()
    conn.close()

    categories = ["Food Quality", "Cleanliness", "Mess Timings", "Staff Behavior", "Food Quantity", "Other"]

    return render_template(
        "student/complaints.html",
        complaints=complaints,
        categories=categories
    )


@app.route("/student/complaints/add", methods=["POST"])
@student_required
def student_add_complaint():
    """
    Direct endpoint for student complaint submission form.
    """
    return student_complaints()


# ==========================================
# STUDENT PORTAL ROUTES - END
# ==========================================


# ==========================================
# STATIC ASSET & HEALTH ROUTES - START
# ==========================================
@app.route("/api/health")
def health_check():
    """
    API endpoint for container health probes and uptime verification.
    """
    return jsonify({
        "status": "healthy",
        "system": "Smart Mess Management System",
        "timestamp": datetime.now().isoformat()
    })
# ==========================================
# STATIC ASSET & HEALTH ROUTES - END
# ==========================================


# ==========================================
# SERVER BOOTSTRAP - START
# ==========================================
if __name__ == "__main__":
    # Bind to host 0.0.0.0 and port 3000 as strictly required by AI Studio environment
    port = 3000
    print(f"==================================================")
    print(f" SMART MESS MANAGEMENT SYSTEM SERVER STARTING")
    print(f" URL: http://0.0.0.0:{port}")
    print(f" Role Default Credentials:")
    print(f"   Admin:   Username: admin    Password: admin123")
    print(f"   Student: ID: STU001         Password: student123")
    print(f"==================================================")
    app.run(host="0.0.0.0", port=port, debug=False)
# ==========================================
# SERVER BOOTSTRAP - END
# ==========================================
