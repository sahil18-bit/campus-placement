"""
Campus Hiring System - Main Application
Updated to use PostgreSQL (Supabase) instead of SQLite
"""

import os
import psycopg2
import psycopg2.extras
from flask import Flask, g
from dotenv import load_dotenv

load_dotenv()

from routes.auth import auth_bp
from routes.student import student_bp
from routes.recruiter import recruiter_bp
from routes.admin import admin_bp

# ─────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────
app = Flask(__name__, template_folder='templates', static_folder='static')

app.secret_key = os.environ.get('SECRET_KEY', 'campus_hiring_secret_key_2024')

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'resumes')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

DATABASE_URL = os.environ.get('DATABASE_URL')

# ─────────────────────────────────────────────
# Database Helpers
# ─────────────────────────────────────────────
def get_db():
    """Get database connection for this request."""
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Create all tables and seed sample data."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL,
            approved    INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS student_profiles (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            college     TEXT,
            degree      TEXT,
            branch      TEXT,
            cgpa        REAL,
            skills      TEXT,
            resume_path TEXT,
            phone       TEXT
        );

        CREATE TABLE IF NOT EXISTS recruiter_profiles (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            company     TEXT,
            designation TEXT,
            phone       TEXT,
            website     TEXT
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id              SERIAL PRIMARY KEY,
            recruiter_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title           TEXT NOT NULL,
            company         TEXT NOT NULL,
            description     TEXT,
            requirements    TEXT,
            location        TEXT,
            job_type        TEXT,
            salary          TEXT,
            deadline        TEXT,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS applications (
            id              SERIAL PRIMARY KEY,
            student_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            status          TEXT DEFAULT 'Applied',
            applied_at      TIMESTAMP DEFAULT NOW(),
            cover_letter    TEXT,
            UNIQUE(student_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS interviews (
            id              SERIAL PRIMARY KEY,
            application_id  INTEGER UNIQUE NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
            student_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            recruiter_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            interview_date  TEXT NOT NULL,
            interview_time  TEXT NOT NULL,
            location        TEXT,
            mode            TEXT DEFAULT 'Online',
            notes           TEXT,
            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)

    # Seed admin
    cur.execute("SELECT id FROM users WHERE email = 'admin@campus.edu'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ('Admin', 'admin@campus.edu', 'admin123', 'admin')
        )

    # Seed recruiter
    cur.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (%s, %s, %s, %s, %s)",
            ('Priya Sharma', 'recruiter@techcorp.com', 'recruiter123', 'recruiter', 1)
        )
        cur.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'")
        rec = cur.fetchone()
        cur.execute(
            "INSERT INTO recruiter_profiles (user_id, company, designation, phone) VALUES (%s, %s, %s, %s)",
            (rec['id'], 'TechCorp India', 'HR Manager', '9876543210')
        )

    # Seed student
    cur.execute("SELECT id FROM users WHERE email = 'student@college.edu'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
            ('Rahul Verma', 'student@college.edu', 'student123', 'student')
        )
        cur.execute("SELECT id FROM users WHERE email = 'student@college.edu'")
        stu = cur.fetchone()
        cur.execute(
            """INSERT INTO student_profiles (user_id, college, degree, branch, cgpa, skills, phone)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (stu['id'], 'IIT Mumbai', 'B.Tech', 'Computer Science', 8.5,
             'Python, Flask, Machine Learning, SQL', '9123456789')
        )

    # Seed jobs
    cur.execute("SELECT id FROM users WHERE email = 'recruiter@techcorp.com'")
    rec = cur.fetchone()
    if rec:
        cur.execute("SELECT COUNT(*) as cnt FROM jobs WHERE recruiter_id = %s", (rec['id'],))
        count = cur.fetchone()['cnt']
        if count == 0:
            jobs_data = [
                (rec['id'], 'Software Engineer', 'TechCorp India',
                 'Work on scalable backend systems using Python and Go.',
                 'B.Tech/M.Tech CS/IT, 7+ CGPA, Python, SQL',
                 'Bangalore', 'Full-time', '12-18 LPA', '2025-12-31'),
                (rec['id'], 'Data Science Intern', 'TechCorp India',
                 'Help our data team build ML models and dashboards.',
                 'B.Tech CS/IT, 7+ CGPA, Python, pandas, scikit-learn',
                 'Remote', 'Internship', '25,000/month', '2025-11-30'),
                (rec['id'], 'Frontend Developer', 'TechCorp India',
                 'Build beautiful user interfaces with React and TypeScript.',
                 'B.Tech any branch, HTML, CSS, JavaScript, React',
                 'Hyderabad', 'Full-time', '8-14 LPA', '2025-12-15'),
            ]
            for j in jobs_data:
                cur.execute(
                    """INSERT INTO jobs (recruiter_id, title, company, description, requirements,
                       location, job_type, salary, deadline) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", j
                )

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database initialized with sample data.")

# ─────────────────────────────────────────────
# Register Blueprints
# ─────────────────────────────────────────────
app.teardown_appcontext(close_db)
app.get_db = get_db

app.register_blueprint(auth_bp)
app.register_blueprint(student_bp, url_prefix='/student')
app.register_blueprint(recruiter_bp, url_prefix='/recruiter')
app.register_blueprint(admin_bp, url_prefix='/admin')

from flask import redirect, url_for
@app.route('/')
def index():
    return redirect(url_for('auth.login'))

# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
init_db()

if __name__ == '__main__':
    print("🚀 Campus Hiring System running at http://localhost:5000")
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
