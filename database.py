"""
==================================================
SMART MESS MANAGEMENT SYSTEM - DATABASE MODULE
==================================================
Description: SQLite database initialization, table creation,
sample demo data seeding, and query helper functions.
==================================================
"""

import os
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Path to the SQLite database file
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smart_mess.db")


# ==========================================
# DATABASE CONNECTION HELPER - START
# ==========================================
def get_db_connection():
    """
    Establishes and returns a connection to the SQLite database.
    Row factory is set to sqlite3.Row for dictionary-like column access.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable foreign key constraint support in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
# ==========================================
# DATABASE CONNECTION HELPER - END
# ==========================================


# ==========================================
# DATABASE SCHEMA INITIALIZATION - START
# ==========================================
def init_db():
    """
    Creates all necessary database tables with constraints and indexes.
    Includes tables for admins, students, attendance, menu, notices, complaints, and payments.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Admin Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # 2. Student Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        roll_number TEXT UNIQUE NOT NULL,
        branch TEXT NOT NULL,
        semester TEXT NOT NULL,
        mobile_number TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        payment_status TEXT DEFAULT 'Unpaid',
        face_registered INTEGER DEFAULT 0,
        face_image_path TEXT,
        registration_date TEXT NOT NULL
    );
    """)

    # 3. Attendance Table with strict UNIQUE constraint: (student_id + date + meal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        meal TEXT NOT NULL,
        status TEXT DEFAULT 'Present',
        marked_by TEXT DEFAULT 'Admin',
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
        UNIQUE (student_id, date, meal)
    );
    """)

    # 4. Weekly Mess Menu Table (Monday to Sunday, Breakfast/Lunch/Dinner)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week TEXT NOT NULL,
        meal_type TEXT NOT NULL,
        items TEXT NOT NULL,
        special_notes TEXT,
        availability_status TEXT NOT NULL DEFAULT 'Available',
        updated_at TEXT NOT NULL,
        UNIQUE (day_of_week, meal_type)
    );
    """)

    cursor.execute("PRAGMA table_info(menu)")
    menu_columns = {row[1] for row in cursor.fetchall()}
    if "availability_status" not in menu_columns:
        cursor.execute("ALTER TABLE menu ADD COLUMN availability_status TEXT NOT NULL DEFAULT 'Available'")

    # 5. Important Notices Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        priority TEXT DEFAULT 'Normal',
        created_by TEXT DEFAULT 'Mess Admin',
        created_at TEXT NOT NULL
    );
    """)

    # 6. Complaints Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT UNIQUE NOT NULL,
        student_id TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        admin_response TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    """)

    # 7. Payments Table (prepared for online payment expansion)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        amount REAL NOT NULL,
        month_year TEXT NOT NULL,
        status TEXT NOT NULL,
        payment_method TEXT DEFAULT 'Cash/Offline',
        transaction_ref TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
# ==========================================
# DATABASE SCHEMA INITIALIZATION - END
# ==========================================


# ==========================================
# SAMPLE DEMO DATA SEEDING - START
# ==========================================
def seed_demo_data():
    """
    Seeds initial realistic demo data if tables are empty.
    Includes default admin, 6 sample students, complete 7-day menu, sample notices,
    past attendance records, and sample complaints.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute("SELECT COUNT(*) FROM admins")
    admin_count = cursor.fetchone()[0]

    if admin_count == 0:
        # 1. Create Default Admin (admin / admin123)
        admin_pass = generate_password_hash("admin123")
        cursor.execute("""
        INSERT INTO admins (username, email, password_hash, name, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, ("admin", "admin@smartmess.edu", admin_pass, "Chief Mess Warden", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # Check if students exist
    cursor.execute("SELECT COUNT(*) FROM students")
    student_count = cursor.fetchone()[0]

    if student_count == 0:
        # Default student password: student123
        std_pass = generate_password_hash("student123")
        today_str = datetime.now().strftime("%Y-%m-%d")

        sample_students = [
            ("STU001", "Aarav Sharma", "21CS101", "Computer Science", "6th", "9876543210", std_pass, "Paid", 0, None, today_str),
            ("STU002", "Priya Patel", "21EC204", "Electronics & Comm", "6th", "9876543211", std_pass, "Paid", 0, None, today_str),
            ("STU003", "Rohan Verma", "22ME315", "Mechanical Engg", "4th", "9876543212", std_pass, "Unpaid", 0, None, today_str),
            ("STU004", "Sneha Reddy", "22IT402", "Information Tech", "4th", "9876543213", std_pass, "Pending", 0, None, today_str),
            ("STU005", "Vikram Singh", "23EE108", "Electrical Engg", "2nd", "9876543214", std_pass, "Paid", 0, None, today_str),
            ("STU006", "Ananya Joshi", "23CE210", "Civil Engineering", "2nd", "9876543215", std_pass, "Unpaid", 0, None, today_str),
        ]

        cursor.executemany("""
        INSERT INTO students (student_id, full_name, roll_number, branch, semester, mobile_number, password_hash, payment_status, face_registered, face_image_path, registration_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_students)

        # 2. Seed 7-Day Complete Menu
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        menus = {
            "Monday": {
                "Breakfast": ("Puri + Sabzi", ""),
                "Lunch": ("Rice + Dal + Sabzi + Papad + Salad", ""),
                "Dinner": ("Roti + Tarka Bhujiya + Salad", "")
            },
            "Tuesday": {
                "Breakfast": ("Sandwich", ""),
                "Lunch": ("Rice + Kadi + Salad", ""),
                "Dinner": ("Mix Bhujia + Roti + Salad", "")
            },
            "Wednesday": {
                "Breakfast": ("Poha", ""),
                "Lunch": ("Rice + Dal + Sabzi + Chips + Salad", ""),
                "Dinner": ("Roti + Paneer Sabji + Salad + Dal + Chicken + Chawal", "")
            },
            "Thursday": {
                "Breakfast": ("Paratha", ""),
                "Lunch": ("Rice + Rajma + Salad", ""),
                "Dinner": ("Puri + Sabzi + Kheer", "")
            },
            "Friday": {
                "Breakfast": ("Litti", ""),
                "Lunch": ("Rice + Dal + Sabzi + Chips + Salad", ""),
                "Dinner": ("Anda Curry + Roti + Salad", "")
            },
            "Saturday": {
                "Breakfast": ("Idli + Sambhar", ""),
                "Lunch": ("Rice + Chola + Salad + Papad + Achaar", ""),
                "Dinner": ("Roti + Chole Curry + Salad", "")
            },
            "Sunday": {
                "Breakfast": ("Puri + Aloo/Sabzi", ""),
                "Lunch": ("Rice + Fish + Salad", ""),
                "Dinner": ("Puri + Chhola Aalu + Soyabin OR Aalu Chana + Halwa", "")
            }
        }

        for day in days:
            for meal_type, (items, notes) in menus[day].items():
                cursor.execute("""
                INSERT OR REPLACE INTO menu (day_of_week, meal_type, items, special_notes, availability_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (day, meal_type, items, notes, "Available", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        # 3. Seed Important Notices
        sample_notices = [
            ("Mess Timings for Monsoon Season", "Breakfast: 7:30 AM - 9:30 AM | Lunch: 12:30 PM - 2:30 PM | Dinner: 7:30 PM - 9:45 PM. Please arrive on time to maintain food warmth and quality.", "Normal", "Mess Warden", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("Monthly Mess Fee Due Reminder", "All students with pending mess dues are requested to clear their accounts by the 5th of this month to avoid service interruptions.", "High", "Account Office", (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")),
            ("Hostel Feast & Special Sunday Biryani", "Special Hyderabadi Dum Biryani and Sweet Lassi will be served this Sunday. Facial scan registration will be mandatory at the counter entrance.", "Urgent", "Mess Committee", (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")),
        ]

        cursor.executemany("""
        INSERT INTO notices (title, content, priority, created_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, sample_notices)

        # 4. Seed Past Attendance for realistic analytics and demand estimation
        # Generate attendance records for the past 6 days + today
        today = datetime.now()
        for i in range(6, -1, -1):
            record_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            # For each student, generate some realistic attendance
            for std_id in ["STU001", "STU002", "STU003", "STU004", "STU005"]:
                # Past breakfast
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO attendance (student_id, date, time, meal, status, marked_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (std_id, record_date, "08:15:00", "Breakfast", "Present", "Admin Face Scan"))
                except sqlite3.IntegrityError:
                    pass

                # Past lunch
                try:
                    cursor.execute("""
                    INSERT OR IGNORE INTO attendance (student_id, date, time, meal, status, marked_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (std_id, record_date, "13:10:00", "Lunch", "Present", "Admin Face Scan"))
                except sqlite3.IntegrityError:
                    pass

                # Past dinner (for older days, or skip today dinner for live demo)
                if i > 0 or std_id in ["STU001", "STU002"]:
                    try:
                        cursor.execute("""
                        INSERT OR IGNORE INTO attendance (student_id, date, time, meal, status, marked_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (std_id, record_date, "20:05:00", "Dinner", "Present", "Admin Face Scan"))
                    except sqlite3.IntegrityError:
                        pass

        # 5. Seed Sample Complaints
        sample_complaints = [
            ("CMP001", "STU003", "Food Quality", "Chapati is sometimes hard during dinner", "The chapatis served after 9 PM in dinner tend to be dry and hard. Please keep them in thermal containers.", "In Progress", "Noted. We have instructed the catering staff to keep fresh rotis in insulated hotpots.", (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("CMP002", "STU004", "Hygiene", "Water dispenser filter cleaning required", "The water filter in Dining Hall B needs routine filter replacement and cleaning.", "Resolved", "Water cooler serviced and certified by vendor on Tuesday.", (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("CMP003", "STU006", "Food Quantity", "Curd quantity runs out during peak lunch hour", "Curd bowls were exhausted at 1:45 PM today. Kindly ensure sufficient refill buffer.", "Pending", None, (datetime.now() - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"), None)
        ]

        cursor.executemany("""
        INSERT INTO complaints (complaint_id, student_id, category, title, description, status, admin_response, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_complaints)

    conn.commit()
    conn.close()
# ==========================================
# SAMPLE DEMO DATA SEEDING - END
# ==========================================


# ==========================================
# ID GENERATORS & QUERY HELPERS - START
# ==========================================
def get_next_student_id():
    """
    Generates the next sequential unique Student ID in format STU001, STU002, etc.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id FROM students ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row or not row["student_id"]:
        return "STU001"

    last_id = row["student_id"]
    try:
        num = int(last_id.replace("STU", "")) + 1
        return f"STU{num:03d}"
    except ValueError:
        return f"STU{datetime.now().strftime('%M%S')}"


def get_next_complaint_id():
    """
    Generates the next sequential unique Complaint ID in format CMP001, CMP002, etc.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT complaint_id FROM complaints ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row or not row["complaint_id"]:
        return "CMP001"

    last_id = row["complaint_id"]
    try:
        num = int(last_id.replace("CMP", "")) + 1
        return f"CMP{num:03d}"
    except ValueError:
        return f"CMP{datetime.now().strftime('%M%S')}"
# ==========================================
# ID GENERATORS & QUERY HELPERS - END
# ==========================================


# Execute initialization and seeding when database.py is run or imported
if __name__ == "__main__":
    init_db()
    seed_demo_data()
    print("Smart Mess Database initialized and seeded successfully!")
