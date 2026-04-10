"""
Recruiter Routes
All pages and actions available to recruiters.
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
        # Check approval status
        db = get_db()
        user = db.execute("SELECT approved FROM users WHERE id=?", (session['user_id'],)).fetchone()
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
    rec_id = session['user_id']

    total_jobs   = db.execute("SELECT COUNT(*) FROM jobs WHERE recruiter_id=?", (rec_id,)).fetchone()[0]
    active_jobs  = db.execute("SELECT COUNT(*) FROM jobs WHERE recruiter_id=? AND is_active=1", (rec_id,)).fetchone()[0]
    total_apps   = db.execute(
        "SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=?", (rec_id,)
    ).fetchone()[0]
    shortlisted  = db.execute(
        "SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id=j.id WHERE j.recruiter_id=? AND a.status='Shortlisted'",
        (rec_id,)
    ).fetchone()[0]

    # Recent applications across all jobs
    recent_apps = db.execute(
        """SELECT a.id, a.status, a.applied_at, u.name as student_name,
                  j.title as job_title, sp.college, sp.branch, sp.cgpa
           FROM applications a
           JOIN jobs j ON a.job_id = j.id
           JOIN users u ON a.student_id = u.id
           LEFT JOIN student_profiles sp ON sp.user_id = u.id
           WHERE j.recruiter_id = ?
           ORDER BY a.applied_at DESC LIMIT 6""", (rec_id,)
    ).fetchall()

    # My active jobs with applicant count
    my_jobs = db.execute(
        """SELECT j.*, COUNT(a.id) as applicant_count
           FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE j.recruiter_id = ?
           GROUP BY j.id
           ORDER BY j.created_at DESC LIMIT 5""", (rec_id,)
    ).fetchall()

    profile = db.execute(
        "SELECT * FROM recruiter_profiles WHERE user_id=?", (rec_id,)
    ).fetchone()

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
    rec_id = session['user_id']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.execute("UPDATE users SET name=? WHERE id=?", (name, rec_id))
            session['user_name'] = name

        db.execute(
            """UPDATE recruiter_profiles
               SET company=?, designation=?, phone=?, website=?
               WHERE user_id=?""",
            (
                request.form.get('company'),
                request.form.get('designation'),
                request.form.get('phone'),
                request.form.get('website'),
                rec_id
            )
        )
        db.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('recruiter.profile'))

    user    = db.execute("SELECT * FROM users WHERE id=?", (rec_id,)).fetchone()
    profile = db.execute("SELECT * FROM recruiter_profiles WHERE user_id=?", (rec_id,)).fetchone()
    return render_template('recruiter/profile.html', user=user, profile=profile)


# ─────────────────────────────────────────────
# JOB MANAGEMENT
# ─────────────────────────────────────────────
@recruiter_bp.route('/jobs')
@recruiter_required
def jobs():
    db = get_db()
    rec_id = session['user_id']

    my_jobs = db.execute(
        """SELECT j.*, COUNT(a.id) as applicant_count
           FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           WHERE j.recruiter_id = ?
           GROUP BY j.id
           ORDER BY j.created_at DESC""", (rec_id,)
    ).fetchall()

    return render_template('recruiter/jobs.html', jobs=my_jobs)


@recruiter_bp.route('/jobs/create', methods=['GET', 'POST'])
@recruiter_required
def create_job():
    db = get_db()
    rec_id = session['user_id']

    if request.method == 'POST':
        profile = db.execute(
            "SELECT company FROM recruiter_profiles WHERE user_id=?", (rec_id,)
        ).fetchone()
        company = profile['company'] if profile and profile['company'] else request.form.get('company', '')

        db.execute(
            """INSERT INTO jobs
               (recruiter_id, title, company, description, requirements,
                location, job_type, salary, deadline)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                rec_id,
                request.form.get('title'),
                company,
                request.form.get('description'),
                request.form.get('requirements'),
                request.form.get('location'),
                request.form.get('job_type'),
                request.form.get('salary'),
                request.form.get('deadline')
            )
        )
        db.commit()
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter.jobs'))

    profile = db.execute("SELECT * FROM recruiter_profiles WHERE user_id=?", (rec_id,)).fetchone()
    return render_template('recruiter/create_job.html', profile=profile)


@recruiter_bp.route('/jobs/<int:job_id>/toggle', methods=['POST'])
@recruiter_required
def toggle_job(job_id):
    db = get_db()
    rec_id = session['user_id']

    job = db.execute("SELECT * FROM jobs WHERE id=? AND recruiter_id=?", (job_id, rec_id)).fetchone()
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('recruiter.jobs'))

    new_status = 0 if job['is_active'] else 1
    db.execute("UPDATE jobs SET is_active=? WHERE id=?", (new_status, job_id))
    db.commit()
    status_text = 'activated' if new_status else 'deactivated'
    flash(f'Job {status_text}.', 'success')
    return redirect(url_for('recruiter.jobs'))


@recruiter_bp.route('/jobs/<int:job_id>/delete', methods=['POST'])
@recruiter_required
def delete_job(job_id):
    db = get_db()
    rec_id = session['user_id']

    db.execute("DELETE FROM jobs WHERE id=? AND recruiter_id=?", (job_id, rec_id))
    db.commit()
    flash('Job deleted.', 'success')
    return redirect(url_for('recruiter.jobs'))


# ─────────────────────────────────────────────
# APPLICANTS
# ─────────────────────────────────────────────
@recruiter_bp.route('/jobs/<int:job_id>/applicants')
@recruiter_required
def applicants(job_id):
    db = get_db()
    rec_id = session['user_id']

    job = db.execute(
        "SELECT * FROM jobs WHERE id=? AND recruiter_id=?", (job_id, rec_id)
    ).fetchone()
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('recruiter.jobs'))

    apps = db.execute(
        """SELECT a.*, u.name as student_name, u.email as student_email,
                  sp.college, sp.branch, sp.cgpa, sp.skills, sp.phone, sp.resume_path,
                  i.interview_date, i.interview_time
           FROM applications a
           JOIN users u ON a.student_id = u.id
           LEFT JOIN student_profiles sp ON sp.user_id = u.id
           LEFT JOIN interviews i ON i.application_id = a.id
           WHERE a.job_id = ?
           ORDER BY a.applied_at DESC""", (job_id,)
    ).fetchall()

    return render_template('recruiter/applicants.html', job=job, apps=apps)


@recruiter_bp.route('/applications/<int:app_id>/status', methods=['POST'])
@recruiter_required
def update_status(app_id):
    db = get_db()
    rec_id = session['user_id']
    new_status = request.form.get('status')

    # Validate status
    valid_statuses = ['Applied', 'Shortlisted', 'Rejected', 'Selected']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'error')
        return redirect(request.referrer or url_for('recruiter.dashboard'))

    # Security: ensure this application belongs to one of this recruiter's jobs
    app = db.execute(
        """SELECT a.id, a.job_id FROM applications a
           JOIN jobs j ON a.job_id = j.id
           WHERE a.id=? AND j.recruiter_id=?""",
        (app_id, rec_id)
    ).fetchone()

    if not app:
        flash('Application not found.', 'error')
        return redirect(url_for('recruiter.dashboard'))

    db.execute("UPDATE applications SET status=? WHERE id=?", (new_status, app_id))
    db.commit()
    flash(f'Application status updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('recruiter.applicants', job_id=app['job_id']))


# ─────────────────────────────────────────────
# INTERVIEW SCHEDULING
# ─────────────────────────────────────────────
@recruiter_bp.route('/applications/<int:app_id>/schedule', methods=['GET', 'POST'])
@recruiter_required
def schedule_interview(app_id):
    db = get_db()
    rec_id = session['user_id']

    # Fetch application with student and job info
    app = db.execute(
        """SELECT a.*, u.name as student_name, u.email as student_email,
                  j.title as job_title, j.company
           FROM applications a
           JOIN users u ON a.student_id = u.id
           JOIN jobs j ON a.job_id = j.id
           WHERE a.id=? AND j.recruiter_id=?""",
        (app_id, rec_id)
    ).fetchone()

    if not app:
        flash('Application not found.', 'error')
        return redirect(url_for('recruiter.dashboard'))

    if request.method == 'POST':
        interview_date = request.form.get('interview_date')
        interview_time = request.form.get('interview_time')
        mode           = request.form.get('mode', 'Online')
        location       = request.form.get('location', '')
        notes          = request.form.get('notes', '')

        if not interview_date or not interview_time:
            flash('Date and time are required.', 'error')
            return render_template('recruiter/schedule_interview.html', app=app)

        # Upsert: update if exists, insert if not
        existing = db.execute(
            "SELECT id FROM interviews WHERE application_id=?", (app_id,)
        ).fetchone()

        if existing:
            db.execute(
                """UPDATE interviews
                   SET interview_date=?, interview_time=?, mode=?, location=?, notes=?
                   WHERE application_id=?""",
                (interview_date, interview_time, mode, location, notes, app_id)
            )
        else:
            db.execute(
                """INSERT INTO interviews
                   (application_id, student_id, job_id, recruiter_id,
                    interview_date, interview_time, mode, location, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (app_id, app['student_id'], app['job_id'], rec_id,
                 interview_date, interview_time, mode, location, notes)
            )

        # Auto-shortlist the candidate
        db.execute(
            "UPDATE applications SET status='Shortlisted' WHERE id=?", (app_id,)
        )
        db.commit()
        flash('Interview scheduled successfully!', 'success')
        return redirect(url_for('recruiter.applicants', job_id=app['job_id']))

    # Load existing interview data if any
    existing_interview = db.execute(
        "SELECT * FROM interviews WHERE application_id=?", (app_id,)
    ).fetchone()

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
