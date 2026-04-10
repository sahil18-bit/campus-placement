"""
Recruiter Routes - Updated for PostgreSQL/Supabase
"""

import os
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app, send_from_directory)
from functools import wraps

recruiter_bp = Blueprint('recruiter', __name__)

def get_db():
    return current_app.get_db()

def recruiter_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'recruiter':
            flash('Access denied.', 'error')
            return redirect(url_for('auth.login'))
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT approved FROM users WHERE id=%s", (session['user_id'],))
        user = cur.fetchone()
        cur.close()
        if not user or user['approved'] != 1:
            flash('Your account is pending admin approval.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@recruiter_bp.route('/dashboard')
@recruiter_required
def dashboard():
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("SELECT COUNT(*) as cnt FROM jobs WHERE recruiter_id=%s", (rec_id,))
    total_jobs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM jobs WHERE recruiter_id=%s AND is_active=1", (rec_id,))
    active_jobs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=%s", (rec_id,))
    total_apps = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=%s AND a.status='Shortlisted'", (rec_id,))
    shortlisted = cur.fetchone()['cnt']

    cur.execute("""
        SELECT a.id, a.status, a.applied_at, u.name as student_name,
               j.title as job_title, sp.college, sp.branch, sp.cgpa
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN users u ON a.student_id = u.id
        LEFT JOIN student_profiles sp ON sp.user_id = u.id
        WHERE j.recruiter_id = %s
        ORDER BY a.applied_at DESC LIMIT 6
    """, (rec_id,))
    recent_apps = cur.fetchall()

    cur.execute("""
        SELECT j.*, COUNT(a.id) as applicant_count
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.recruiter_id = %s
        GROUP BY j.id
        ORDER BY j.created_at DESC LIMIT 5
    """, (rec_id,))
    my_jobs = cur.fetchall()

    cur.execute("SELECT * FROM recruiter_profiles WHERE user_id=%s", (rec_id,))
    profile = cur.fetchone()
    cur.close()

    return render_template('recruiter/dashboard.html',
        total_jobs=total_jobs, active_jobs=active_jobs,
        total_apps=total_apps, shortlisted=shortlisted,
        recent_apps=recent_apps, my_jobs=my_jobs, profile=profile
    )


# ─────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────
@recruiter_bp.route('/profile', methods=['GET', 'POST'])
@recruiter_required
def profile():
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            cur.execute("UPDATE users SET name=%s WHERE id=%s", (name, rec_id))
            session['user_name'] = name

        cur.execute("""
            UPDATE recruiter_profiles
            SET company=%s, designation=%s, phone=%s, website=%s
            WHERE user_id=%s
        """, (
            request.form.get('company'),
            request.form.get('designation'),
            request.form.get('phone'),
            request.form.get('website'),
            rec_id
        ))
        db.commit()
        cur.close()
        flash('Profile updated!', 'success')
        return redirect(url_for('recruiter.profile'))

    cur.execute("SELECT * FROM users WHERE id=%s", (rec_id,))
    user = cur.fetchone()
    cur.execute("SELECT * FROM recruiter_profiles WHERE user_id=%s", (rec_id,))
    profile = cur.fetchone()
    cur.close()
    return render_template('recruiter/profile.html', user=user, profile=profile)


# ─────────────────────────────────────────────
# JOB MANAGEMENT
# ─────────────────────────────────────────────
@recruiter_bp.route('/jobs')
@recruiter_required
def jobs():
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("""
        SELECT j.*, COUNT(a.id) as applicant_count
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.recruiter_id = %s
        GROUP BY j.id
        ORDER BY j.created_at DESC
    """, (rec_id,))
    my_jobs = cur.fetchall()
    cur.close()

    return render_template('recruiter/jobs.html', jobs=my_jobs)


@recruiter_bp.route('/jobs/create', methods=['GET', 'POST'])
@recruiter_required
def create_job():
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    if request.method == 'POST':
        cur.execute("SELECT company FROM recruiter_profiles WHERE user_id=%s", (rec_id,))
        profile = cur.fetchone()
        company = profile['company'] if profile and profile['company'] else request.form.get('company', '')

        cur.execute("""
            INSERT INTO jobs (recruiter_id, title, company, description, requirements,
                location, job_type, salary, deadline)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            rec_id,
            request.form.get('title'),
            company,
            request.form.get('description'),
            request.form.get('requirements'),
            request.form.get('location'),
            request.form.get('job_type'),
            request.form.get('salary'),
            request.form.get('deadline')
        ))
        db.commit()
        cur.close()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter.jobs'))

    cur.execute("SELECT * FROM recruiter_profiles WHERE user_id=%s", (rec_id,))
    profile = cur.fetchone()
    cur.close()
    return render_template('recruiter/create_job.html', profile=profile)


@recruiter_bp.route('/jobs/<int:job_id>/toggle', methods=['POST'])
@recruiter_required
def toggle_job(job_id):
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("SELECT * FROM jobs WHERE id=%s AND recruiter_id=%s", (job_id, rec_id))
    job = cur.fetchone()
    if not job:
        flash('Job not found.', 'error')
        cur.close()
        return redirect(url_for('recruiter.jobs'))

    new_status = 0 if job['is_active'] else 1
    cur.execute("UPDATE jobs SET is_active=%s WHERE id=%s", (new_status, job_id))
    db.commit()
    cur.close()
    status_text = 'activated' if new_status else 'deactivated'
    flash(f'Job {status_text}.', 'success')
    return redirect(url_for('recruiter.jobs'))


@recruiter_bp.route('/jobs/<int:job_id>/delete', methods=['POST'])
@recruiter_required
def delete_job(job_id):
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("DELETE FROM jobs WHERE id=%s AND recruiter_id=%s", (job_id, rec_id))
    db.commit()
    cur.close()
    flash('Job deleted.', 'success')
    return redirect(url_for('recruiter.jobs'))


# ─────────────────────────────────────────────
# APPLICANTS
# ─────────────────────────────────────────────
@recruiter_bp.route('/jobs/<int:job_id>/applicants')
@recruiter_required
def applicants(job_id):
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("SELECT * FROM jobs WHERE id=%s AND recruiter_id=%s", (job_id, rec_id))
    job = cur.fetchone()
    if not job:
        flash('Job not found.', 'error')
        cur.close()
        return redirect(url_for('recruiter.jobs'))

    cur.execute("""
        SELECT a.*, u.name as student_name, u.email as student_email,
               sp.college, sp.branch, sp.cgpa, sp.skills, sp.phone, sp.resume_path,
               i.interview_date, i.interview_time
        FROM applications a
        JOIN users u ON a.student_id = u.id
        LEFT JOIN student_profiles sp ON sp.user_id = u.id
        LEFT JOIN interviews i ON i.application_id = a.id
        WHERE a.job_id = %s
        ORDER BY a.applied_at DESC
    """, (job_id,))
    apps = cur.fetchall()
    cur.close()

    return render_template('recruiter/applicants.html', job=job, apps=apps)


@recruiter_bp.route('/applications/<int:app_id>/status', methods=['POST'])
@recruiter_required
def update_status(app_id):
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']
    new_status = request.form.get('status')

    valid_statuses = ['Applied', 'Shortlisted', 'Rejected', 'Selected']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'error')
        cur.close()
        return redirect(request.referrer or url_for('recruiter.dashboard'))

    cur.execute("""
        SELECT a.id, a.job_id FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.id=%s AND j.recruiter_id=%s
    """, (app_id, rec_id))
    app = cur.fetchone()

    if not app:
        flash('Application not found.', 'error')
        cur.close()
        return redirect(url_for('recruiter.dashboard'))

    cur.execute("UPDATE applications SET status=%s WHERE id=%s", (new_status, app_id))
    db.commit()
    cur.close()
    flash(f'Application status updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('recruiter.applicants', job_id=app['job_id']))


# ─────────────────────────────────────────────
# INTERVIEW SCHEDULING
# ─────────────────────────────────────────────
@recruiter_bp.route('/applications/<int:app_id>/schedule', methods=['GET', 'POST'])
@recruiter_required
def schedule_interview(app_id):
    db = get_db()
    cur = db.cursor()
    rec_id = session['user_id']

    cur.execute("""
        SELECT a.*, u.name as student_name, u.email as student_email,
               j.title as job_title, j.company
        FROM applications a
        JOIN users u ON a.student_id = u.id
        JOIN jobs j ON a.job_id = j.id
        WHERE a.id=%s AND j.recruiter_id=%s
    """, (app_id, rec_id))
    app = cur.fetchone()

    if not app:
        flash('Application not found.', 'error')
        cur.close()
        return redirect(url_for('recruiter.dashboard'))

    if request.method == 'POST':
        interview_date = request.form.get('interview_date')
        interview_time = request.form.get('interview_time')
        mode           = request.form.get('mode', 'Online')
        location       = request.form.get('location', '')
        notes          = request.form.get('notes', '')

        if not interview_date or not interview_time:
            flash('Date and time are required.', 'error')
            cur.close()
            return render_template('recruiter/schedule_interview.html', app=app)

        cur.execute("SELECT id FROM interviews WHERE application_id=%s", (app_id,))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE interviews
                SET interview_date=%s, interview_time=%s, mode=%s, location=%s, notes=%s
                WHERE application_id=%s
            """, (interview_date, interview_time, mode, location, notes, app_id))
        else:
            cur.execute("""
                INSERT INTO interviews
                (application_id, student_id, job_id, recruiter_id,
                 interview_date, interview_time, mode, location, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (app_id, app['student_id'], app['job_id'], rec_id,
                  interview_date, interview_time, mode, location, notes))

        cur.execute("UPDATE applications SET status='Shortlisted' WHERE id=%s", (app_id,))
        db.commit()
        cur.close()
        flash('Interview scheduled successfully!', 'success')
        return redirect(url_for('recruiter.applicants', job_id=app['job_id']))

    cur.execute("SELECT * FROM interviews WHERE application_id=%s", (app_id,))
    existing_interview = cur.fetchone()
    cur.close()

    return render_template('recruiter/schedule_interview.html',
        app=app, existing=existing_interview
    )


# ─────────────────────────────────────────────
# RESUME DOWNLOAD
# ─────────────────────────────────────────────
@recruiter_bp.route('/resume/<path:filename>')
@recruiter_required
def download_resume(filename):
    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(upload_folder, filename, as_attachment=True)
