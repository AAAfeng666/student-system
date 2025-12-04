# app/admin.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash
from app.db import get_db_connection
from datetime import date
from datetime import datetime
from math import ceil

admin_bp = Blueprint('admin', __name__)

def require_admin():
    return session.get('role') == 'admin'

# --- College Management ---
@admin_bp.route('/colleges')
def colleges():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college ORDER BY college_id").fetchall()
    conn.close()
    return render_template('admin/admin_colleges.html', colleges=colleges)

@admin_bp.route('/colleges/add', methods=['GET', 'POST'])
def add_college():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name:
            flash('College name cannot be empty!')
            return render_template('admin/admin_college_form.html', form={'college_name': name, 'address': address, 'phone': phone}, is_edit=False)
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO college (college_name, address, phone) VALUES (?, ?, ?)", (name, address, phone))
            conn.commit()
            flash('✅ College added successfully!')
        except sqlite3.IntegrityError as e:
            flash(f'❌ Failed to add: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.colleges'))
    return render_template('admin/admin_college_form.html', form={'college_name': '', 'address': '', 'phone': ''}, is_edit=False)

@admin_bp.route('/colleges/edit/<college_id>', methods=['GET', 'POST'])
def edit_college(college_id):
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    college = conn.execute("SELECT * FROM college WHERE college_id = ?", (college_id,)).fetchone()
    if not college:
        conn.close()
        flash('College does not exist!')
        return redirect(url_for('admin.colleges'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        if not name:
            conn.close()
            flash('College name cannot be empty!')
            return render_template('admin/admin_college_form.html', form={'college_id': college_id, 'college_name': name, 'address': address, 'phone': phone}, is_edit=True)
        try:
            conn.execute("UPDATE college SET college_name = ?, address = ?, phone = ? WHERE college_id = ?", (name, address, phone, college_id))
            conn.commit()
            flash('✅ College information updated successfully!')
        except sqlite3.Error as e:
            flash(f'❌ Update failed: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.colleges'))
    conn.close()
    return render_template('admin/admin_college_form.html', form=dict(college), is_edit=True)

# --- Teacher Management ---
@admin_bp.route('/teachers')
def teachers():
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    search_query = request.args.get('q', '').strip()
    college_filter = request.args.get('college_id', '')
    title_filter = request.args.get('title', '').strip()
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    ITEMS_PER_PAGE = 20

    conn = get_db_connection()

    colleges = conn.execute("SELECT * FROM college ORDER BY college_name").fetchall()

    titles = conn.execute("""
        SELECT DISTINCT title FROM teacher 
        WHERE title IS NOT NULL AND title != '' 
        ORDER BY title
    """).fetchall()

    where_clauses = []
    params = []

    if search_query:
        base_like = f'%{search_query}%'
        where_clauses.append("(t.teacher_id LIKE ? OR t.name LIKE ? OR t.title LIKE ? OR c.college_name LIKE ?)")
        params.extend([base_like] * 4)

    if college_filter:
        where_clauses.append("t.college_id = ?")
        params.append(college_filter)

    if title_filter:
        where_clauses.append("t.title = ?")
        params.append(title_filter)

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_query = """
        SELECT COUNT(*) 
        FROM teacher t 
        LEFT JOIN college c ON t.college_id = c.college_id
    """ + where_sql
    total_count = conn.execute(count_query, params).fetchone()[0]
    total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if total_pages > 0 and page > total_pages:
        page = total_pages

    offset = (page - 1) * ITEMS_PER_PAGE
    data_query = """
        SELECT t.*, c.college_name 
        FROM teacher t 
        LEFT JOIN college c ON t.college_id = c.college_id
    """ + where_sql + " ORDER BY t.teacher_id LIMIT ? OFFSET ?"

    teachers = conn.execute(data_query, params + [ITEMS_PER_PAGE, offset]).fetchall()
    conn.close()

    return render_template(
        'admin/admin_teachers.html',
        teachers=teachers,
        colleges=colleges,
        titles=[row['title'] for row in titles],
        selected_college=college_filter,
        selected_title=title_filter,
        search_query=search_query,
        current_page=page,
        total_pages=total_pages,
        total_count=total_count
    )

@admin_bp.route('/teachers/add', methods=['GET', 'POST'])
def add_teacher():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college ORDER BY college_id").fetchall()
    if request.method == 'POST':
        tid = request.form.get('teacher_id', '').strip().upper()
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender')
        birth = request.form.get('birth_date') or None
        title = request.form.get('title', '').strip()
        cid = request.form.get('college_id')
        if not all([tid, name, cid]):
            flash('Teacher ID, name, and affiliated college cannot be empty!')
            return render_template('admin/admin_teacher_form.html', form=request.form, colleges=colleges, is_edit=False)
        try:
            conn.execute("INSERT INTO teacher (teacher_id, name, gender, birth_date, title, college_id) VALUES (?, ?, ?, ?, ?, ?)",
                         (tid, name, gender, birth, title, cid))
            conn.commit()
            flash(f'✅ Teacher {name} ({tid}) added successfully!')
        except sqlite3.IntegrityError as e:
            flash(f'❌ Failed to add: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.teachers'))
    conn.close()
    return render_template('admin/admin_teacher_form.html', form={'teacher_id': '', 'name': '', 'gender': '', 'birth_date': '', 'title': '', 'college_id': ''}, colleges=colleges, is_edit=False)

@admin_bp.route('/teachers/edit/<teacher_id>', methods=['GET', 'POST'])
def edit_teacher(teacher_id):
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college").fetchall()
    teacher = conn.execute("SELECT * FROM teacher WHERE teacher_id = ?", (teacher_id,)).fetchone()
    if not teacher:
        conn.close()
        flash('Teacher does not exist!')
        return redirect(url_for('admin.teachers'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender')
        birth = request.form.get('birth_date') or None
        title = request.form.get('title', '').strip()
        cid = request.form.get('college_id')
        if not all([name, cid]):
            flash('Name and affiliated college cannot be empty!')
            return render_template('admin/admin_teacher_form.html', form=dict(teacher) | request.form, colleges=colleges, is_edit=True)
        try:
            conn.execute("UPDATE teacher SET name = ?, gender = ?, birth_date = ?, title = ?, college_id = ? WHERE teacher_id = ?",
                         (name, gender, birth, title, cid, teacher_id))
            conn.commit()
            flash(f'✅ Teacher {name} information updated successfully!')
        except sqlite3.Error as e:
            flash(f'❌ Update failed: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.teachers'))
    conn.close()
    return render_template('admin/admin_teacher_form.html', form=dict(teacher), colleges=colleges, is_edit=True)


# --- Student Management ---
ITEMS_PER_PAGE = 20

@admin_bp.route('/students')
def students():
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    search_query = request.args.get('q', '').strip()
    selected_year = request.args.get('year', '').strip()
    sort_by = request.args.get('sort_by', 'student_id')
    order = request.args.get('order', 'asc')
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    allowed_sort_fields = {'student_id', 'birth_date', 'enrollment_year'}
    if sort_by not in allowed_sort_fields:
        sort_by = 'student_id'
    if order not in ('asc', 'desc'):
        order = 'asc'

    conn = get_db_connection()

    where_clauses = []
    params = []

    if search_query:
        clean_q = search_query.strip().rstrip('Cohort').strip()
        year_value = None
        if clean_q.isdigit() and len(clean_q) == 4:
            try:
                y = int(clean_q)
                if 2000 <= y <= 2030:
                    year_value = y
            except ValueError:
                pass

        if year_value is not None:
            where_clauses.append("s.enrollment_year = ?")
            params.append(year_value)
        else:
            text_fields = ['s.student_id', 's.name', 's.phone', 's.hometown', 'c.college_name', 's.birth_date', 's.id_card']
            text_clause = " OR ".join([f"{field} LIKE ?" for field in text_fields])
            where_clauses.append(f"({text_clause})")
            params.extend([f'%{search_query}%'] * len(text_fields))

    if selected_year and selected_year.isdigit():
        where_clauses.append("s.enrollment_year = ?")
        params.append(int(selected_year))

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_query = "SELECT COUNT(*) FROM student s LEFT JOIN college c ON s.college_id = c.college_id" + where_sql
    total_count = conn.execute(count_query, params).fetchone()[0]
    total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page > total_pages and total_pages > 0:
        page = total_pages

    base_query = """
        SELECT s.*, c.college_name
        FROM student s
        LEFT JOIN college c ON s.college_id = c.college_id
    """ + where_sql + f" ORDER BY {sort_by} {order.upper()} LIMIT ? OFFSET ?"

    offset = (page - 1) * ITEMS_PER_PAGE
    students = conn.execute(base_query, params + [ITEMS_PER_PAGE, offset]).fetchall()

    year_stats = conn.execute("""
        SELECT enrollment_year, COUNT(*) as count
        FROM student
        GROUP BY enrollment_year
        ORDER BY enrollment_year DESC
    """).fetchall()

    conn.close()

    return render_template(
        'admin/admin_students.html',
        students=students,
        q=search_query,
        selected_year=selected_year,
        year_stats=year_stats,
        sort_by=sort_by,
        order=order,
        total_count=total_count,
        current_page=page,
        total_pages=total_pages
    )

@admin_bp.route('/students/add', methods=['GET', 'POST'])
def add_student():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college").fetchall()
    if request.method == 'POST':
        sid = request.form.get('student_id', '').strip().upper()
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender')
        birth = request.form.get('birth_date') or None
        phone = request.form.get('phone', '').strip()
        hometown = request.form.get('hometown', '').strip()
        cid = request.form.get('college_id')
        if not all([sid, name, cid]):
            flash('Student ID, name, and affiliated college cannot be empty!')
            return render_template('admin/admin_student_form.html', form=request.form, colleges=colleges, is_edit=False)
        try:
            conn.execute("INSERT INTO student (student_id, name, gender, birth_date, phone, hometown, college_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (sid, name, gender, birth, phone, hometown, cid))
            conn.commit()
            flash(f'✅ Student {name} ({sid}) added successfully!')
        except sqlite3.IntegrityError as e:
            flash(f'❌ Failed to add: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.students'))
    conn.close()
    return render_template('admin/admin_student_form.html', form={'student_id': '', 'name': '', 'gender': '', 'birth_date': '', 'phone': '', 'hometown': '', 'college_id': ''}, colleges=colleges, is_edit=False)

@admin_bp.route('/students/edit/<student_id>', methods=['GET', 'POST'])
def edit_student(student_id):
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college").fetchall()
    student = conn.execute("SELECT * FROM student WHERE student_id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash('Student does not exist!')
        return redirect(url_for('admin.students'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender')
        birth = request.form.get('birth_date') or None
        phone = request.form.get('phone', '').strip()
        hometown = request.form.get('hometown', '').strip()
        cid = request.form.get('college_id')
        if not all([name, cid]):
            flash('Name and affiliated college cannot be empty!')
            return render_template('admin/admin_student_form.html', form=dict(student) | request.form, colleges=colleges, is_edit=True)
        try:
            conn.execute("UPDATE student SET name = ?, gender = ?, birth_date = ?, phone = ?, hometown = ?, college_id = ? WHERE student_id = ?",
                         (name, gender, birth, phone, hometown, cid, student_id))
            conn.commit()
            flash(f'✅ Student {name} information updated successfully!')
        except sqlite3.Error as e:
            flash(f'❌ Update failed: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.students'))
    conn.close()
    return render_template('admin/admin_student_form.html', form=dict(student), colleges=colleges, is_edit=True)


# --- Course Management ---
@admin_bp.route('/courses')
def courses():
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    per_page = ITEMS_PER_PAGE
    offset = (page - 1) * per_page

    college_id = request.args.get('college_id', '').strip()
    conn = get_db_connection()

    count_query = "SELECT COUNT(*) FROM course co"
    data_query = """
        SELECT co.*, c.college_name 
        FROM course co 
        LEFT JOIN college c ON co.college_id = c.college_id
    """
    params = []

    if college_id:
        count_query += " WHERE co.college_id = ?"
        data_query += " WHERE co.college_id = ?"
        params.append(college_id)

    total = conn.execute(count_query, params).fetchone()[0]

    data_query += " ORDER BY co.course_id LIMIT ? OFFSET ?"
    paginated_params = params + [per_page, offset]
    courses = conn.execute(data_query, paginated_params).fetchall()

    colleges = conn.execute("SELECT * FROM college ORDER BY college_name").fetchall()

    college_counts = conn.execute("""
        SELECT college_id, COUNT(*) as count 
        FROM course 
        GROUP BY college_id
    """).fetchall()
    college_count_dict = {row['college_id']: row['count'] for row in college_counts}

    conn.close()

    pagination = {
        'total': total,
        'per_page': per_page,
        'page': page,
        'pages': (total + per_page - 1) // per_page
    }

    return render_template(
        'admin/admin_courses.html',
        courses=courses,
        colleges=colleges,
        selected_college_id=college_id or None,
        college_count_dict=college_count_dict,
        pagination=pagination
    )

@admin_bp.route('/courses/add', methods=['GET', 'POST'])
def add_course():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college").fetchall()
    if request.method == 'POST':
        cid = request.form.get('course_id', '').strip().upper()
        name = request.form.get('course_name', '').strip()
        credits = request.form.get('credits')
        hours = request.form.get('hours')
        college_id = request.form.get('college_id')
        if not all([cid, name, college_id]):
            flash('Course ID, course name, and affiliated college cannot be empty!')
            return render_template('admin/admin_course_form.html', form=request.form, colleges=colleges, is_edit=False)
        try:
            credits = int(credits) if credits else None
            hours = int(hours) if hours else None
            conn.execute("INSERT INTO course (course_id, course_name, credits, hours, college_id) VALUES (?, ?, ?, ?, ?)",
                         (cid, name, credits, hours, college_id))
            conn.commit()
            flash(f'✅ Course {name} ({cid}) added successfully!')
        except ValueError:
            flash('❌ Credits or hours must be integers.')
        except sqlite3.IntegrityError:
            flash('❌ Course ID already exists. Please use a different ID.')
        finally:
            conn.close()
        return redirect(url_for('admin.courses'))
    conn.close()
    return render_template('admin/admin_course_form.html', form={'course_id': '', 'course_name': '', 'credits': '', 'hours': '', 'college_id': ''}, colleges=colleges, is_edit=False)

@admin_bp.route('/courses/edit/<course_id>', methods=['GET', 'POST'])
def edit_course(course_id):
    if not require_admin(): return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    colleges = conn.execute("SELECT * FROM college").fetchall()
    course = conn.execute("SELECT * FROM course WHERE course_id = ?", (course_id,)).fetchone()
    if not course:
        conn.close()
        flash('Course does not exist!')
        return redirect(url_for('admin.courses'))
    if request.method == 'POST':
        name = request.form.get('course_name', '').strip()
        credits = request.form.get('credits')
        hours = request.form.get('hours')
        college_id = request.form.get('college_id')
        if not all([name, college_id]):
            flash('Course name and affiliated college cannot be empty!')
            return render_template('admin/admin_course_form.html', form=dict(course) | request.form, colleges=colleges, is_edit=True)
        try:
            credits = int(credits) if credits else None
            hours = int(hours) if hours else None
            conn.execute("UPDATE course SET course_name = ?, credits = ?, hours = ?, college_id = ? WHERE course_id = ?",
                         (name, credits, hours, college_id, course_id))
            conn.commit()
            flash('✅ Course information updated successfully!')
        except ValueError:
            flash('❌ Credits or hours must be integers.')
        except sqlite3.Error as e:
            flash(f'❌ Update failed: {str(e)}')
        finally:
            conn.close()
        return redirect(url_for('admin.courses'))
    conn.close()
    return render_template('admin/admin_course_form.html', form=dict(course), colleges=colleges, is_edit=True)



# --- Account Management ---
ITEMS_PER_PAGE = 20

@admin_bp.route('/accounts')
def accounts():
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    q = request.args.get('q', '').strip()
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db_connection()

    count_base = "SELECT COUNT(*) FROM account"
    count_params = []

    select_clause = """
        SELECT username, role, user_id, is_active,
        CASE 
            WHEN role = 'student' THEN (SELECT name FROM student WHERE student_id = user_id)
            WHEN role = 'teacher' THEN (SELECT name FROM teacher WHERE teacher_id = user_id)
            ELSE 'System Administrator'
        END AS real_name
    """
    from_clause = " FROM account"
    where_clauses = []
    query_params = []

    if q:
        like_pattern = f'%{q}%'
        where_clauses.append("""
            (username LIKE ? 
             OR (role = 'student' AND EXISTS (
                 SELECT 1 FROM student 
                 WHERE student_id = account.user_id AND name LIKE ?
             )) 
             OR (role = 'teacher' AND EXISTS (
                 SELECT 1 FROM teacher 
                 WHERE teacher_id = account.user_id AND name LIKE ?
             ))
            )
        """)
        count_params = [like_pattern, like_pattern, like_pattern]
        query_params = [like_pattern, like_pattern, like_pattern]

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    order_limit_sql = " ORDER BY role, username LIMIT ? OFFSET ?"

    total = conn.execute(count_base + where_sql, count_params).fetchone()[0]

    accounts = conn.execute(
        select_clause + from_clause + where_sql + order_limit_sql,
        query_params + [per_page, offset]
    ).fetchall()

    conn.close()

    total_pages = ceil(total / per_page) if total > 0 else 1
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages

    return render_template(
        'admin/admin_accounts.html',
        accounts=accounts,
        current_page=page,
        total_pages=total_pages,
        total=total,
        current_query=q
    )

@admin_bp.route('/accounts/add', methods=['GET', 'POST'])
def add_account():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = request.form['role']
        user_id = request.form.get('user_id', '').strip() or None

        if not username or not password:
            flash('Username and password cannot be empty', 'error')
            return redirect(request.url)

        conn = get_db_connection()
        if conn.execute("SELECT 1 FROM account WHERE username = ?", (username,)).fetchone():
            flash('Username already exists', 'error')
            conn.close()
            return redirect(request.url)

        if role in ('student', 'teacher'):
            table = 'student' if role == 'student' else 'teacher'
            id_field = 'student_id' if role == 'student' else 'teacher_id'
            if not user_id or not conn.execute(f"SELECT 1 FROM {table} WHERE {id_field} = ?", (user_id,)).fetchone():
                flash(f'The associated {"student" if role == "student" else "teacher"} ID does not exist', 'error')
                conn.close()
                return redirect(request.url)

        hashed = generate_password_hash(password)
        conn.execute("INSERT INTO account (username, password_hash, role, user_id, is_active) VALUES (?, ?, ?, ?, ?)",
                     (username, hashed, role, user_id, 1))
        conn.commit()
        conn.close()
        flash(f'✅ Account {username} created successfully!', 'success')
        return redirect(url_for('admin.accounts'))
    return render_template('admin/admin_account_form.html')

@admin_bp.route('/toggle-account', methods=['POST'])
def toggle_account_status():
    if not require_admin(): return redirect(url_for('main.dashboard'))
    username = request.form.get('username')
    conn = get_db_connection()
    current = conn.execute("SELECT is_active FROM account WHERE username = ?", (username,)).fetchone()
    if current:
        new_status = 0 if current['is_active'] else 1
        conn.execute("UPDATE account SET is_active = ? WHERE username = ?", (new_status, username))
        conn.commit()
        flash(f'✅ Account {username} has been {"enabled" if new_status else "disabled"}', 'success')
    conn.close()
    return redirect(url_for('admin.accounts'))

@admin_bp.route('/reset-password', methods=['POST'])
def reset_password():
    if not require_admin(): return redirect(url_for('admin.accounts'))
    username = request.form.get('username')
    if not username:
        flash('Invalid username', 'error')
        return redirect(url_for('admin.accounts'))
    conn = get_db_connection()
    if not conn.execute("SELECT 1 FROM account WHERE username = ?", (username,)).fetchone():
        flash('User does not exist', 'error')
        conn.close()
        return redirect(url_for('admin.accounts'))
    hashed_pw = generate_password_hash('123456')
    conn.execute("UPDATE account SET password_hash = ? WHERE username = ?", (hashed_pw, username))
    conn.commit()
    conn.close()
    flash(f'✅ Password for user {username} has been reset to: 123456', 'success')
    return redirect(url_for('admin.accounts'))


# --- Semester Course Selection Period Management ---
@admin_bp.route('/manage-semesters', methods=['GET'])
def manage_semesters():
    conn = get_db_connection()
    semesters = conn.execute('''
        SELECT semester_id, semester_name, is_current, selection_start, selection_end
        FROM semester ORDER BY semester_id DESC
    ''').fetchall()
    return render_template('admin/manage_semesters.html', semesters=semesters)

@admin_bp.route('/manage-semesters/add', methods=['GET', 'POST'])
def add_semester():
    if request.method == 'POST':
        sid = request.form['semester_id'].strip()
        name = request.form['semester_name'].strip()
        start = request.form.get('selection_start')
        end = request.form.get('selection_end')

        def format_for_db(dt_local_str):
            if dt_local_str:
                return dt_local_str.replace('T', ' ') + ':00'
            return None

        db_start = format_for_db(start)
        db_end = format_for_db(end)

        if not sid or not name:
            flash('❌ Semester ID and name cannot be empty!', 'danger')
        elif db_start and db_end and db_start > db_end:
            flash('❌ Start time cannot be later than end time!', 'danger')
        else:
            try:
                conn = get_db_connection()
                conn.execute('''
                    INSERT INTO semester (semester_id, semester_name, selection_start, selection_end)
                    VALUES (?, ?, ?, ?)
                ''', (sid, name, db_start, db_end))
                conn.commit()
                conn.close()
                flash(f'✅ Semester {name} added successfully!', 'success')
                return redirect(url_for('admin.manage_semesters'))
            except sqlite3.IntegrityError as e:
                if 'UNIQUE constraint failed' in str(e):
                    flash('❌ Semester ID or name already exists. Please avoid duplicates!', 'danger')
                else:
                    flash('❌ Database error: ' + str(e), 'danger')
    return render_template('admin/edit_semester.html', semester=None)

from datetime import datetime
from flask import request, flash, redirect, url_for, render_template
# ... 其他导入

@admin_bp.route('/manage-semesters/edit/<semester_id>', methods=['GET', 'POST'])
def edit_semester(semester_id):
    conn = get_db_connection()
    semester_row = conn.execute('SELECT * FROM semester WHERE semester_id = ?', (semester_id,)).fetchone()
    if not semester_row:
        flash('❌ Semester not found!', 'danger')
        return redirect(url_for('admin.manage_semesters'))

    # Helper: parse DB datetime string (e.g., "2025-02-10 00:00:00")
    def parse_db_datetime(s):
        if s:
            try:
                return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return None

    semester = {
        'semester_id': semester_row['semester_id'],
        'semester_name': semester_row['semester_name'],
        'is_current': bool(semester_row['is_current']),
        'selection_start': parse_db_datetime(semester_row['selection_start']),
        'selection_end': parse_db_datetime(semester_row['selection_end']),
    }

    if request.method == 'POST':
        name = request.form['semester_name'].strip()
        start_input = request.form.get('selection_start', '').strip()  # from <input type="datetime-local">
        end_input = request.form.get('selection_end', '').strip()
        is_current = bool(request.form.get('is_current'))

        if not name:
            flash('❌ Semester name cannot be empty!', 'danger')
            return render_template('admin/edit_semester.html', semester=semester)

        # Parse frontend datetime-local strings → datetime objects
        start_dt = None
        end_dt = None
        try:
            if start_input:
                start_dt = datetime.fromisoformat(start_input.replace('T', ' '))
            if end_input:
                end_dt = datetime.fromisoformat(end_input.replace('T', ' '))
        except ValueError:
            flash('❌ Invalid date/time format!', 'danger')
            return render_template('admin/edit_semester.html', semester=semester)

        # Validate time order
        if start_dt and end_dt and start_dt > end_dt:
            flash('❌ Course selection start time cannot be later than end time!', 'danger')
            return render_template('admin/edit_semester.html', semester=semester)

        # Convert datetime objects back to DB string format, or None
        db_start = start_dt.strftime('%Y-%m-%d %H:%M:%S') if start_dt else None
        db_end = end_dt.strftime('%Y-%m-%d %H:%M:%S') if end_dt else None

        # Save to DB
        conn = get_db_connection()
        if is_current:
            conn.execute("UPDATE semester SET is_current = 0")  # unset others
        conn.execute('''
            UPDATE semester 
            SET semester_name = ?, selection_start = ?, selection_end = ?, is_current = ? 
            WHERE semester_id = ?
        ''', (name, db_start, db_end, is_current, semester_id))
        conn.commit()
        conn.close()

        flash(f'✅ Semester "{name}" updated successfully!', 'success')
        return redirect(url_for('admin.manage_semesters'))

    return render_template('admin/edit_semester.html', semester=semester)

@admin_bp.route('/manage-semesters/delete/<semester_id>', methods=['POST'])
def delete_semester(semester_id):
    conn = get_db_connection()
    cur = conn.execute("SELECT is_current FROM semester WHERE semester_id = ?", (semester_id,)).fetchone()
    if cur and cur['is_current']:
        flash('❌ Cannot delete the current semester! Please switch first.', 'danger')
    else:
        conn.execute("DELETE FROM semester WHERE semester_id = ?", (semester_id,))
        conn.commit()
        flash('🗑️ Semester deleted.', 'info')
    return redirect(url_for('admin.manage_semesters'))

# Global Search Redirect
@admin_bp.route('/search')
def global_search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('main.dashboard'))

    # 统一转为小写，便于匹配
    query_lower = query.lower()

    # 定义关键词别名列表：每个 endpoint 对应多个可能的搜索词（单数、复数、常见变体）
    keyword_to_endpoint = {
        'admin.students': ['student', 'students'],
        'admin.teachers': ['teacher', 'teachers'],
        'admin.courses': ['course', 'courses'],
        'admin.colleges': ['college', 'colleges'],
        'admin.manage_semesters': ['semester', 'semesters'],
        'admin.accounts': ['account', 'accounts'],
    }

    # 遍历所有 endpoint 和其对应的关键词列表
    for endpoint, keywords in keyword_to_endpoint.items():
        for kw in keywords:
            if kw in query_lower:
                return redirect(url_for(endpoint))

    flash(f'No feature found related to "{query}"', 'warning')
    return redirect(url_for('main.dashboard'))


# Message Center
@admin_bp.route('/messages')
def messages():
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    page = request.args.get('page', 1, type=int)
    ITEMS_PER_PAGE = 15
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()

    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    main_messages = conn.execute("""
        SELECT m.*,
               (SELECT MAX(created_at) FROM replies r WHERE r.message_id = m.message_id) AS last_activity
        FROM messages m
        ORDER BY COALESCE(last_activity, m.created_at) DESC
        LIMIT ? OFFSET ?
    """, (ITEMS_PER_PAGE, offset)).fetchall()

    threads = []
    for msg in main_messages:
        replies = conn.execute("""
            SELECT * FROM replies
            WHERE message_id = ?
            ORDER BY created_at ASC
        """, (msg['message_id'],)).fetchall()
        threads.append({
            'main': msg,
            'replies': replies
        })

    conn.close()
    return render_template(
        'admin/admin_messages.html',
        threads=threads,
        current_page=page,
        total_pages=total_pages
    )

@admin_bp.route('/messages/<int:message_id>/read', methods=['POST'])
def mark_message_read(message_id):
    if not require_admin():
        return redirect(url_for('main.dashboard'))
    conn = get_db_connection()
    try:
        conn.execute("UPDATE message SET is_read = 1 WHERE message_id = ?", (message_id,))
        conn.commit()
        flash('Message marked as read.', 'success')
    except Exception as e:
        conn.rollback()
        flash('Operation failed. Please try again.', 'error')
    finally:
        conn.close()
    page = request.args.get('page', 1, type=int)
    return redirect(url_for('admin.messages', page=page))


@admin_bp.route('/messages/<int:message_id>/reply', methods=['POST'])
def reply_to_message(message_id):
    if not require_admin():
        return redirect(url_for('main.dashboard'))

    content = request.form.get('content', '').strip()
    if not content:
        flash('Reply content cannot be empty.', 'error')
        return redirect(url_for('admin.messages', page=request.args.get('page', 1)))

    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO replies (message_id, sender_role, sender_id, sender_name, content)
            VALUES (?, 'admin', 'admin', 'System Administrator', ?)
        """, (message_id, content))
        conn.commit()
        flash('✅ Reply sent.', 'success')
    except Exception as e:
        conn.rollback()
        flash('❌ Failed to send reply. Please try again.', 'error')
        print("Admin reply error:", e)
    finally:
        conn.close()

    return redirect(url_for('admin.messages', page=request.args.get('page', 1)))