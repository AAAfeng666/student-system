# app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM account WHERE username = ?", (username,)).fetchone()

        if user:
            is_active = bool(user['is_active']) if 'is_active' in user.keys() else True
            if is_active and check_password_hash(user['password_hash'], password):
                session['username'] = username
                session['role'] = user['role']
                flash('Login successful!', 'success')
                return redirect(url_for('main.dashboard'))
            elif not is_active:
                flash('This account has been disabled. Please contact the administrator.', 'error')
            else:
                flash('Invalid username or password.', 'error')
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        id_card = request.form.get('id_card', '').strip()
        if not username or not id_card:
            flash('Please enter both username and ID number.')
            return render_template('forgot_password.html')

        conn = get_db_connection()
        user = conn.execute("SELECT role, user_id FROM account WHERE username = ? AND is_active = 1", (username,)).fetchone()
        if not user:
            flash('Username does not exist or the account is disabled.')
            return render_template('forgot_password.html')

        role, user_id = user['role'], user['user_id']
        id_in_db = None
        if role == 'student':
            row = conn.execute("SELECT id_card FROM student WHERE student_id = ?", (user_id,)).fetchone()
            id_in_db = row['id_card'] if row else None
        elif role == 'teacher':
            row = conn.execute("SELECT id_card FROM teacher WHERE teacher_id = ?", (user_id,)).fetchone()
            id_in_db = row['id_card'] if row else None
        else:
            flash('System administrators cannot reset passwords via this method.')
            return render_template('forgot_password.html')

        if not id_in_db or id_in_db != id_card:
            flash('ID number does not match. Please double-check and try again.')
            return render_template('forgot_password.html')

        new_password = id_card[-6:]
        hashed_pw = generate_password_hash(new_password)
        conn.execute("UPDATE account SET password_hash = ? WHERE username = ?", (hashed_pw, username))
        conn.commit()
        flash(f'✅ Password has been reset to the last 6 digits of your ID: {new_password}. Please log in immediately and change your password.')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    role = session.get('role', 'student')  # default to student

    if request.method == 'POST':
        old = request.form.get('old_password', '').strip()
        new = request.form.get('new_password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        if not all([old, new, confirm]):
            flash('All fields are required.', 'error')
            return render_template(get_password_template(role))

        if new != confirm:
            flash('New password and confirmation do not match.', 'error')
            return render_template(get_password_template(role))

        conn = get_db_connection()
        user = conn.execute(
            "SELECT password_hash FROM account WHERE username = ?",
            (session['username'],)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user['password_hash'], old):
            flash('Current password is incorrect.', 'error')
            return render_template(get_password_template(role))

        # Update password
        conn = get_db_connection()
        conn.execute(
            "UPDATE account SET password_hash = ? WHERE username = ?",
            (generate_password_hash(new), session['username'])
        )
        conn.commit()
        conn.close()

        # Clear session and redirect to login
        session.clear()
        flash('Password updated successfully! Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    # GET request: render role-specific template
    return render_template(get_password_template(role))


def get_password_template(role: str) -> str:
    """Return the appropriate change-password template based on user role."""
    mapping = {
        'admin': 'admin/change_password.html',
        'teacher': 'teacher/change_password.html',
        'student': 'student/change_password.html'
    }
    return mapping.get(role, 'student/change_password.html')  # default to student

@auth_bp.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))