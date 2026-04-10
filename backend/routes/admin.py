"""
Admin Routes - Updated for PostgreSQL/Supabase
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, current_app)
from functools import wraps

admin_bp = Blueprint('admin', __name__)

def get_db():
    return current_app.get_db()

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='student'")
    total_students = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='recruiter'")
    total_recruiters = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='recruiter' AND approved=0")
    pending_recs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM jobs")
    total_jobs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM jobs WHERE is_active=1")
    active_jobs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM applications")
    total_apps = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM interviews")
    total_interviews = cur.fetchone()['cnt']

    cur.execute("SELECT status, COUNT(*) as cnt FROM applications GROUP BY status")
    status_counts = cur.fetchall()

    cur.execute("""
        SELECT u.*, rp.company, rp.designation
        FROM users u
        LEFT JOIN recruiter_profiles rp ON rp.user_id = u.id
        WHERE u.role='recruiter' AND u.approved=0
        ORDER BY u.created_at DESC
    """)
    pending_recruiters = cur.fetchall()

    cur.execute("""
        SELECT a.applied_at, a.status, u.name as student_name, j.title, j.company
        FROM applications a
        JOIN users u ON a.student_id = u.id
        JOIN jobs j ON a.job_id = j.id
        ORDER BY a.applied_at DESC LIMIT 8
    """)
    recent_apps = cur.fetchall()
    cur.close()

    return render_template('admin/dashboard.html',
        total_students=total_students,
        total_recruiters=total_recruiters,
        pending_recs=pending_recs,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_apps=total_apps,
        total_interviews=total_interviews,
        status_counts=status_counts,
        pending_recruiters=pending_recruiters,
        recent_apps=recent_apps
    )


# ─────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────
@admin_bp.route('/users')
@admin_required
def users():
    db = get_db()
    cur = db.cursor()
    role_filter = request.args.get('role', '')

    query = "SELECT u.*, rp.company FROM users u LEFT JOIN recruiter_profiles rp ON rp.user_id=u.id WHERE u.role != 'admin'"
    params = []
    if role_filter in ('student', 'recruiter'):
        query += " AND u.role=%s"
        params.append(role_filter)
    query += " ORDER BY u.created_at DESC"

    cur.execute(query, params)
    all_users = cur.fetchall()
    cur.close()
    return render_template('admin/users.html', users=all_users, role_filter=role_filter)


@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_recruiter(user_id):
    db = get_db()
    cur = db.cursor()
    action = request.form.get('action')

    if action == 'approve':
        cur.execute("UPDATE users SET approved=1 WHERE id=%s AND role='recruiter'", (user_id,))
        flash('Recruiter approved.', 'success')
    elif action == 'reject':
        cur.execute("UPDATE users SET approved=2 WHERE id=%s AND role='recruiter'", (user_id,))
        flash('Recruiter rejected.', 'success')

    db.commit()
    cur.close()
    return redirect(url_for('admin.users', role='recruiter'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM users WHERE id=%s AND role != 'admin'", (user_id,))
    db.commit()
    cur.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin.users'))


# ─────────────────────────────────────────────
# JOB MONITORING
# ─────────────────────────────────────────────
@admin_bp.route('/jobs')
@admin_required
def jobs():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        SELECT j.*, u.name as recruiter_name, rp.company,
               COUNT(a.id) as applicant_count
        FROM jobs j
        JOIN users u ON j.recruiter_id = u.id
        LEFT JOIN recruiter_profiles rp ON rp.user_id = u.id
        LEFT JOIN applications a ON a.job_id = j.id
        GROUP BY j.id, u.name, rp.company
        ORDER BY j.created_at DESC
    """)
    all_jobs = cur.fetchall()
    cur.close()

    return render_template('admin/jobs.html', jobs=all_jobs)


@admin_bp.route('/jobs/<int:job_id>/toggle', methods=['POST'])
@admin_required
def toggle_job(job_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT is_active FROM jobs WHERE id=%s", (job_id,))
    job = cur.fetchone()
    if job:
        cur.execute("UPDATE jobs SET is_active=%s WHERE id=%s", (1 - job['is_active'], job_id))
        db.commit()
        flash('Job status updated.', 'success')
    cur.close()
    return redirect(url_for('admin.jobs'))
