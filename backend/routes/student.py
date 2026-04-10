"""
Student Routes - Updated for PostgreSQL/Supabase
"""

import os
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app, send_from_directory)
from werkzeug.utils import secure_filename

student_bp = Blueprint('student', __name__)

ALLOWED_EXTENSIONS = {'pdf'}

def get_db():
    return current_app.get_db()

def login_required(role='student'):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to continue.', 'error')
                return redirect(url_for('auth.login'))
            if session.get('user_role') != role:
                flash('Access denied.', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@student_bp.route('/dashboard')
@login_required('student')
def dashboard():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    cur.execute("SELECT COUNT(*) as cnt FROM jobs WHERE is_active=1")
    total_jobs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM applications WHERE student_id=%s", (student_id,))
    applications = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM applications WHERE student_id=%s AND status='Shortlisted'", (student_id,))
    shortlisted = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM interviews WHERE student_id=%s", (student_id,))
    interviews_count = cur.fetchone()['cnt']

    cur.execute("""
        SELECT a.status, a.applied_at, j.title, j.company, j.location, j.job_type, a.id
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.student_id = %s
        ORDER BY a.applied_at DESC LIMIT 5
    """, (student_id,))
    recent_apps = cur.fetchall()

    cur.execute("""
        SELECT i.interview_date, i.interview_time, i.mode, i.location as venue,
               j.title, j.company, i.notes
        FROM interviews i
        JOIN jobs j ON i.job_id = j.id
        WHERE i.student_id = %s
        ORDER BY i.interview_date ASC LIMIT 3
    """, (student_id,))
    upcoming = cur.fetchall()

    cur.execute("SELECT * FROM student_profiles WHERE user_id=%s", (student_id,))
    profile = cur.fetchone()
    cur.close()

    return render_template('student/dashboard.html',
        total_jobs=total_jobs,
        applications=applications,
        shortlisted=shortlisted,
        interviews_count=interviews_count,
        recent_apps=recent_apps,
        upcoming=upcoming,
        profile=profile
    )


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────
@student_bp.route('/profile', methods=['GET', 'POST'])
@login_required('student')
def profile():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, student_id))
            session['user_name'] = name

        cur.execute("""
            UPDATE student_profiles
            SET college=%s, degree=%s, branch=%s, cgpa=%s, skills=%s, phone=%s
            WHERE user_id=%s
        """, (
            request.form.get('college'),
            request.form.get('degree'),
            request.form.get('branch'),
            request.form.get('cgpa') or None,
            request.form.get('skills'),
            request.form.get('phone'),
            student_id
        ))
        db.commit()
        cur.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.profile'))

    cur.execute("SELECT * FROM users WHERE id=%s", (student_id,))
    user = cur.fetchone()
    cur.execute("SELECT * FROM student_profiles WHERE user_id=%s", (student_id,))
    profile = cur.fetchone()
    cur.close()
    return render_template('student/profile.html', user=user, profile=profile)


# ─────────────────────────────────────────────
# RESUME UPLOAD
# ─────────────────────────────────────────────
@student_bp.route('/upload-resume', methods=['POST'])
@login_required('student')
def upload_resume():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    if 'resume' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('student.profile'))

    file = request.files['resume']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('student.profile'))

    if not allowed_file(file.filename):
        flash('Only PDF files are allowed.', 'error')
        return redirect(url_for('student.profile'))

    filename = f"resume_{student_id}_{secure_filename(file.filename)}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))

    cur.execute("UPDATE student_profiles SET resume_path=%s WHERE user_id=%s", (filename, student_id))
    db.commit()
    cur.close()
    flash('Resume uploaded successfully!', 'success')
    return redirect(url_for('student.profile'))


# ─────────────────────────────────────────────
# JOB LISTINGS
# ─────────────────────────────────────────────
@student_bp.route('/jobs')
@login_required('student')
def jobs():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    search   = request.args.get('search', '')
    job_type = request.args.get('job_type', '')
    location = request.args.get('location', '')

    query = """
        SELECT j.*, u.name as recruiter_name,
               (SELECT id FROM applications WHERE student_id=%s AND job_id=j.id) as applied
        FROM jobs j
        JOIN users u ON j.recruiter_id = u.id
        WHERE j.is_active = 1
    """
    params = [student_id]

    if search:
        query += " AND (j.title ILIKE %s OR j.company ILIKE %s OR j.description ILIKE %s)"
        s = f'%{search}%'
        params += [s, s, s]
    if job_type:
        query += " AND j.job_type = %s"
        params.append(job_type)
    if location:
        query += " AND j.location ILIKE %s"
        params.append(f'%{location}%')

    query += " ORDER BY j.created_at DESC"
    cur.execute(query, params)
    all_jobs = cur.fetchall()
    cur.close()

    return render_template('student/jobs.html',
        jobs=all_jobs, search=search, job_type=job_type, location=location
    )


# ─────────────────────────────────────────────
# JOB DETAIL & APPLY
# ─────────────────────────────────────────────
@student_bp.route('/jobs/<int:job_id>')
@login_required('student')
def job_detail(job_id):
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT j.*, u.name as recruiter_name, rp.company as rec_company
        FROM jobs j JOIN users u ON j.recruiter_id = u.id
        LEFT JOIN recruiter_profiles rp ON rp.user_id = u.id
        WHERE j.id=%s AND j.is_active=1
    """, (job_id,))
    job = cur.fetchone()

    if not job:
        flash('Job not found.', 'error')
        cur.close()
        return redirect(url_for('student.jobs'))

    cur.execute("SELECT * FROM applications WHERE student_id=%s AND job_id=%s", (student_id, job_id))
    applied = cur.fetchone()
    cur.close()

    return render_template('student/job_detail.html', job=job, applied=applied)


@student_bp.route('/apply/<int:job_id>', methods=['POST'])
@login_required('student')
def apply(job_id):
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']
    cover_letter = request.form.get('cover_letter', '')

    cur.execute("SELECT id FROM applications WHERE student_id=%s AND job_id=%s", (student_id, job_id))
    if cur.fetchone():
        flash('You have already applied to this job.', 'error')
        cur.close()
        return redirect(url_for('student.job_detail', job_id=job_id))

    cur.execute(
        "INSERT INTO applications (student_id, job_id, cover_letter) VALUES (%s, %s, %s)",
        (student_id, job_id, cover_letter)
    )
    db.commit()
    cur.close()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student.applications'))


# ─────────────────────────────────────────────
# MY APPLICATIONS
# ─────────────────────────────────────────────
@student_bp.route('/applications')
@login_required('student')
def applications():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT a.*, j.title, j.company, j.location, j.job_type, j.salary,
               i.interview_date, i.interview_time, i.mode as interview_mode, i.location as venue
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        LEFT JOIN interviews i ON i.application_id = a.id
        WHERE a.student_id = %s
        ORDER BY a.applied_at DESC
    """, (student_id,))
    apps = cur.fetchall()
    cur.close()

    return render_template('student/applications.html', apps=apps)


# ─────────────────────────────────────────────
# INTERVIEWS
# ─────────────────────────────────────────────
@student_bp.route('/interviews')
@login_required('student')
def interviews():
    db = get_db()
    cur = db.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT i.*, j.title, j.company, j.location as job_location,
               u.name as recruiter_name
        FROM interviews i
        JOIN jobs j ON i.job_id = j.id
        JOIN users u ON i.recruiter_id = u.id
        WHERE i.student_id = %s
        ORDER BY i.interview_date ASC
    """, (student_id,))
    interviews_list = cur.fetchall()
    cur.close()

    return render_template('student/interviews.html', interviews=interviews_list)
