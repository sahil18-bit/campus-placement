"""
Campus Hiring System - Main Application
A full-stack web application connecting students with recruiters.
"""

import os
import sqlite3
from flask import Flask, g
from routes.auth import auth_bp
from routes.student import student_bp
from routes.recruiter import recruiter_bp
from routes.admin import admin_bp

# ─────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────
app = Flask(__name__, template_folder='templates', static_folder='static')

# Secret key for session management (change in production!)
app.secret_key = 'campus_hiring_secret_key_2024'

# File upload settings
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'resumes')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max file size
app.config['DATABASE'] = os.path.join(os.path.dirname(__file__), 'campus_hiring.db')

# ─────────────────────────────────────────────
# Database Helpers
# ─────────────────────────────────────────────
def get_db():
    """Get database connection, creating one if needed for this request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row  # Rows behave like dicts
    return g.db

def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Create all database tables if they don't exist."""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row

    db.executescript('''
        -- USERS table: stores all user accounts
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,           -- stored as plain text (use hashing in production!)
            role        TEXT NOT NULL,           -- 'student', 'recruiter', 'admin'
            approved    INTEGER DEFAULT 1,       -- recruiters need admin approval (0=pending, 1=approved, 2=rejected)
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- STUDENT PROFILES: extra info for students
        CREATE TABLE IF NOT EXISTS student_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE NOT NULL,
            college     TEXT,
            degree      TEXT,
            branch      TEXT,
            cgpa        REAL,
            skills      TEXT,                   -- comma-separated skills
            resume_path TEXT,                   -- path to uploaded PDF
            phone       TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- RECRUITER PROFILES: extra info for recruiters
        CREATE TABLE IF NOT EXISTS recruiter_profiles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE NOT NULL,
            company     TEXT,
            designation TEXT,
            phone       TEXT,
            website     TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- JOBS table: job postings by recruiters
        CREATE TABLE IF NOT EXISTS jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            recruiter_id    INTEGER NOT NULL,
            title           TEXT NOT NULL,
            company         TEXT NOT NULL,
            description     TEXT,
            requirements    TEXT,
            location        TEXT,
            job_type        TEXT,               -- Full-time, Internship, etc.
            salary          TEXT,
            deadline        TEXT,
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (recruiter_id) REFERENCES users(id)
        );

        -- APPLICATIONS table: student job applications
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      INTEGER NOT NULL,
            job_id          INTEGER NOT NULL,
            status          TEXT DEFAULT 'Applied',  -- Applied, Shortlisted, Rejected, Selected
            applied_at      TEXT DEFAULT (datetime('now')),
            cover_letter    TEXT,
            UNIQUE(student_id, job_id),
            FOREIGN KEY (student_id) REFERENCES users(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        );

        -- INTERVIEWS table: scheduled interviews
        CREATE TABLE IF NOT EXISTS interviews (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id  INTEGER UNIQUE NOT NULL,
            student_id      INTEGER NOT NULL,
            job_id          INTEGER NOT NULL,
            recruiter_id    INTEGER NOT NULL,
            interview_date  TEXT NOT NULL,
            interview_time  TEXT NOT NULL,
            location        TEXT,
            mode            TEXT DEFAULT 'Online',   -- Online, In-person
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (application_id) REFERENCES applications(id)
        );
    ''')

    # ─── Seed admin account ───
    existing = db.execute("SELECT id FROM users WHERE email = 'admin@campus.edu'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@campus.edu', 'admin123', 'admin')
        )

    # ─── Seed sample recruiter ───
    existing = db.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (?, ?, ?, ?, ?)",
            ('Priya Sharma', 'recruiter@techcorp.com', 'recruiter123', 'recruiter', 1)
        )
        rec = db.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'").fetchone()
        db.execute(
            "INSERT INTO recruiter_profiles (user_id, company, designation, phone) VALUES (?, ?, ?, ?)",
            (rec['id'], 'TechCorp India', 'HR Manager', '9876543210')
        )

    # ─── Seed sample student ───
    existing = db.execute("SELECT id FROM users WHERE email = 'student@college.edu'").fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ('Rahul Verma', 'student@college.edu', 'student123', 'student')
        )
        stu = db.execute("SELECT id FROM users WHERE email = 'student@college.edu'").fetchone()
        db.execute(
            """INSERT INTO student_profiles (user_id, college, degree, branch, cgpa, skills, phone)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (stu['id'], 'IIT Mumbai', 'B.Tech', 'Computer Science', 8.5,
             'Python, Flask, Machine Learning, SQL', '9123456789')
        )

    # ─── Seed sample jobs ───
    rec = db.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'").fetchone()
    if rec:
        count = db.execute("SELECT COUNT(*) FROM jobs WHERE recruiter_id = ?", (rec['id'],)).fetchone()[0]
        if count == 0:
            jobs_data = [
                (rec['id'], 'Software Engineer', 'TechCorp India',
                 'Work on scalable backend systems using Python and Go.',
                 'B.Tech/M.Tech CS/IT, 7+ CGPA, Python, SQL',
                 'Bangalore', 'Full-time', '12-18 LPA', '2024-12-31'),
                (rec['id'], 'Data Science Intern', 'TechCorp India',
                 'Help our data team build ML models and dashboards.',
                 'B.Tech CS/IT, 7+ CGPA, Python, pandas, scikit-learn',
                 'Remote', 'Internship', '25,000/month', '2024-11-30'),
                (rec['id'], 'Frontend Developer', 'TechCorp India',
                 'Build beautiful user interfaces with React and TypeScript.',
                 'B.Tech any branch, HTML, CSS, JavaScript, React',
                 'Hyderabad', 'Full-time', '8-14 LPA', '2024-12-15'),
            ]
            for j in jobs_data:
                db.execute(
                    """INSERT INTO jobs (recruiter_id, title, company, description, requirements,
                       location, job_type, salary, deadline) VALUES (?,?,?,?,?,?,?,?,?)""", j
                )

    db.commit()
    db.close()
    print("✅ Database initialized with sample data.")

# ─────────────────────────────────────────────
# Register Blueprints (route groups)
# ─────────────────────────────────────────────
app.teardown_appcontext(close_db)

# Make get_db available to blueprints via app context
app.get_db = get_db

app.register_blueprint(auth_bp)
app.register_blueprint(student_bp, url_prefix='/student')
app.register_blueprint(recruiter_bp, url_prefix='/recruiter')
app.register_blueprint(admin_bp, url_prefix='/admin')

# ─────────────────────────────────────────────
# Root redirect
# ─────────────────────────────────────────────
from flask import redirect, url_for
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    print("🚀 Campus Hiring System running at http://localhost:5000")
    app.run(debug=True, port=5000)
