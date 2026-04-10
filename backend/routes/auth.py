"""
Authentication Routes
Handles login, signup, and logout for all user roles.
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, g

auth_bp = Blueprint('auth', __name__)

def get_db():
    return current_app.get_db()

# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', '')

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND password = ? AND role = ?",
            (email, password, role)
        ).fetchone()

        if not user:
            flash('Invalid credentials. Please check email, password, and role.', 'error')
            return render_template('auth/login.html')

        # Check recruiter approval
        if role == 'recruiter' and user['approved'] != 1:
            status = 'pending admin approval' if user['approved'] == 0 else 'rejected by admin'
            flash(f'Your recruiter account is {status}.', 'error')
            return render_template('auth/login.html')

        # Store user info in session
        session['user_id']   = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']
        session['user_email']= user['email']

        flash(f'Welcome back, {user["name"]}!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('auth/login.html')


# ─────────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────────
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', '')

        if not all([name, email, password, role]):
            flash('All fields are required.', 'error')
            return render_template('auth/signup.html')

        if role not in ('student', 'recruiter'):
            flash('Invalid role selected.', 'error')
            return render_template('auth/signup.html')

        db = get_db()

        # Check if email already exists
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash('An account with this email already exists.', 'error')
            return render_template('auth/signup.html')

        # Recruiters need admin approval (approved=0), students are auto-approved (approved=1)
        approved = 1 if role == 'student' else 0

        db.execute(
            "INSERT INTO users (name, email, password, role, approved) VALUES (?, ?, ?, ?, ?)",
            (name, email, password, role, approved)
        )
        db.commit()

        # Create empty profile record
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if role == 'student':
            db.execute("INSERT OR IGNORE INTO student_profiles (user_id) VALUES (?)", (user['id'],))
        else:
            db.execute("INSERT OR IGNORE INTO recruiter_profiles (user_id) VALUES (?)", (user['id'],))
        db.commit()

        if role == 'recruiter':
            flash('Account created! Please wait for admin approval before logging in.', 'success')
        else:
            flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/signup.html')


# ─────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


# ─────────────────────────────────────────────
# SMART DASHBOARD REDIRECT
# ─────────────────────────────────────────────
@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    role = session.get('user_role')
    if role == 'student':
        return redirect(url_for('student.dashboard'))
    elif role == 'recruiter':
        return redirect(url_for('recruiter.dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin.dashboard'))
    else:
        session.clear()
        return redirect(url_for('auth.login'))
