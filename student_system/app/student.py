# app/student.py
from flask import Blueprint, render_template, redirect, url_for, session, flash, request
from app.db import get_db_connection
import re
from datetime import datetime, timedelta

student_bp = Blueprint('student', __name__, url_prefix='/student')


def time_to_period(time_str):
    """将 '8:00' 或 '14:30' 转为节次编号"""
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M").time()

        # 预定义每节课的 [开始, 结束) 时间（结束 = 开始 + 45分钟）
        periods = [
            (1, "8:00", "8:45"),
            (2, "8:55", "9:40"),
            (3, "10:00", "10:45"),
            (4, "10:55", "11:40"),
            (5, "14:00", "14:45"),
            (6, "14:55", "15:40"),
            (7, "16:00", "16:45"),
            (8, "16:55", "17:40"),
            (9, "19:00", "19:45"),
            (10, "19:55", "20:40")
        ]

        for period_num, start_str, end_str in periods:
            start = datetime.strptime(start_str, "%H:%M").time()
            end = datetime.strptime(end_str, "%H:%M").time()
            if start <= t <= end:  # 允许等于 end（因为 end 是实际下课时间）
                return period_num

    except Exception:
        pass
    return None


def parse_time_slot_to_periods(slot):
    """
    输入: "周一8:00-10:00"
    输出: (weekday_int, [period_start, period_end]) → (1, [1, 2])
    """
    day_map = {
        'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4,
        'Friday': 5, 'Saturday': 6, 'Sunday': 7
    }

    slot = slot.strip()
    for day_str, wd in day_map.items():
        if slot.startswith(day_str):
            time_part = slot[len(day_str):]  # 如 "8:00-10:00"
            if '-' in time_part:
                start_time, end_time = time_part.split('-', 1)
                p1 = time_to_period(start_time)
                p2 = time_to_period(end_time)
                if p1 and p2:
                    # 返回连续节次范围
                    return wd, list(range(p1, p2 + 1))
            break
    return None, []

@student_bp.before_request
def require_student_login():
    """确保只有已登录的学生才能访问此蓝图"""
    if 'username' not in session:
        flash('Please log in first.')
        return redirect(url_for('auth.login'))
    if session.get('role') != 'student':
        flash('You do not have permission to access student features.')
        return redirect(url_for('main.dashboard'))

@student_bp.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    username = session['username']
    conn = get_db_connection()

    # 获取学生信息
    student = conn.execute("""
        SELECT student_id, name, gender, birth_date, phone, hometown, id_card
        FROM student
        WHERE student_id = ?
    """, (username,)).fetchone()

    if not student:
        conn.close()
        flash('Student information not found.')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        gender = request.form.get('gender')
        birth_date = request.form.get('birth_date') or None
        phone = request.form.get('phone', '').strip()
        hometown = request.form.get('hometown', '').strip()
        id_card = request.form.get('id_card', '').strip()

        # 验证
        errors = []
        if not name:
            errors.append("Name cannot be empty")
        if not id_card:
            errors.append("ID card number is required")
        elif len(id_card) != 18:
            errors.append("ID card number must be 18 digits")
        elif not re.match(r'^\d{17}[\dXx]$', id_card):
            errors.append("Invalid ID card number format")
        if phone and not re.match(r'^1[3-9]\d{9}$', phone):
            errors.append("Invalid phone number format")

        if errors:
            for err in errors:
                flash(err)
            conn.close()
            return render_template('student/edit_profile.html', student=student)

        # 更新数据库
        try:
            conn.execute("""
                UPDATE student
                SET name = ?, gender = ?, birth_date = ?, phone = ?, hometown = ?, id_card = ?
                WHERE student_id = ?
            """, (name, gender, birth_date, phone, hometown, id_card, student['student_id']))
            conn.commit()
            flash('Personal information updated successfully!')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            conn.rollback()
            flash('Failed to save. Please try again later.')
            print("DB Error:", e)
        finally:
            conn.close()

    conn.close()
    return render_template('student/edit_profile.html', student=student)

import re
from collections import defaultdict

@student_bp.route('/timetable')
def timetable():
    username = session['username']
    conn = get_db_connection()

    student = conn.execute("""
        SELECT student_id
        FROM student
        WHERE student_id = ?
    """, (username,)).fetchone()

    if not student:
        flash('Student information not found.')
        return redirect(url_for('main.dashboard'))

    student_id = student['student_id']

    # ✅ 动态获取当前学期 ID
    current_sem_row = conn.execute("""
        SELECT semester_id, semester_name FROM semester WHERE is_current = 1
    """).fetchone()

    if not current_sem_row:
        flash('Current semester is not set. Please contact the administrator.')
        return redirect(url_for('main.dashboard'))

    current_semester = current_sem_row['semester_id']  # 得到 'S2025A'
    current_semester_name = current_sem_row['semester_name']

    # 查询已选课程的开课信息（关键：从 offered_course 获取 time_slot）
    courses = conn.execute("""
        SELECT 
            c.course_name,
            t.name AS teacher_name,
            oc.classroom,
            oc.time_slot
        FROM enrollment e
        JOIN offered_course oc ON e.offered_id = oc.offered_id
        JOIN course c ON oc.course_id = c.course_id
        JOIN teacher t ON oc.teacher_id = t.teacher_id
        WHERE e.student_id = ?
          AND oc.semester_id = ?
    """, (student_id, current_semester)).fetchall()

    # 构建空课表（周一到周五，1-10节）
    time_table = {day: {period: None for period in range(1, 11)} for day in range(1, 6)}
    for course in courses:
        weekday, periods = parse_time_slot_to_periods(course['time_slot'])
        if weekday is None or weekday > 5 or not periods:
            continue  # 跳过周末或无法解析的课程

        periods = [p for p in periods if 1 <= p <= 10]
        if not periods:
            continue

        start_p = min(periods)
        end_p = max(periods)

        for p in range(start_p, end_p + 1):
            time_table[weekday][p] = {
                'name': course['course_name'],
                'teacher': course['teacher_name'],
                'classroom': course['classroom'],
                'span_start': start_p,
                'span_end': end_p
            }

    weekdays = {1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday'}
    periods = list(range(1, 11))
    period_times = {
        1: "8:00–8:45",
        2: "8:55–9:40",
        3: "10:00–10:45",
        4: "10:55–11:40",
        5: "14:00–14:45",
        6: "14:55–15:40",
        7: "16:00–16:45",
        8: "16:55–17:40",
        9: "19:00–19:45",
        10: "19:55–20:40"
    }

    return render_template(
        'student/student_timetable.html',
        time_table=time_table,
        weekdays=weekdays,
        periods=periods,
        period_times=period_times,
        current_semester_name = current_semester_name
    )


@student_bp.route('/my-grades')
def my_grades():
    username = session['username']
    conn = get_db_connection()

    # 获取学生ID
    student_row = conn.execute(
        "SELECT user_id FROM account WHERE username = ?", (username,)
    ).fetchone()
    if not student_row:
        flash("Account information is invalid. Please contact the administrator.", "error")
        return redirect(url_for('main.dashboard'))
    student_id = student_row['user_id']

    # 查询所有已选课程的成绩情况（包括未录入的）
    grades = conn.execute("""
        SELECT 
            c.course_name,
            t.name AS teacher_name,
            s.semester_name,
            e.regular_score,
            e.exam_score,
            e.total_score,
            oc.offered_id
        FROM enrollment e
        JOIN offered_course oc ON e.offered_id = oc.offered_id
        JOIN course c ON oc.course_id = c.course_id
        JOIN teacher t ON oc.teacher_id = t.teacher_id
        JOIN semester s ON oc.semester_id = s.semester_id
        WHERE e.student_id = ?
        ORDER BY s.semester_name DESC, c.course_name
    """, (student_id,)).fetchall()

    conn.close()

    # 可选：分离“已出成绩”和“未出成绩”
    published = [g for g in grades if g['total_score'] is not None]
    pending = [g for g in grades if g['total_score'] is None]

    return render_template(
        'student/my_grades.html',
        published=published,
        pending=pending
    )


@student_bp.route('/school-mailbox', methods=['GET', 'POST'])
def school_mailbox():
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    # 获取学生信息
    user = conn.execute("""
        SELECT a.user_id, s.name 
        FROM account a 
        JOIN student s ON a.user_id = s.student_id 
        WHERE a.username = ?
    """, (username,)).fetchone()

    if request.method == 'POST':
        title = request.form['title'].strip()
        content = request.form['content'].strip()
        if title and content:
            cur = conn.execute("""
                INSERT INTO messages (student_id, student_name, title, content)
                VALUES (?, ?, ?, ?)
            """, (user['user_id'], user['name'], title, content))
            conn.commit()
            flash('✅ Message sent successfully!', 'success')
            return redirect(url_for('student.school_mailbox'))

    # 查询所有主消息 + 最新回复时间（用于排序）
    messages = conn.execute("""
        SELECT m.*, 
               (SELECT MAX(created_at) FROM replies r WHERE r.message_id = m.message_id) AS last_reply_at
        FROM messages m
        WHERE m.student_id = ?
        ORDER BY COALESCE(last_reply_at, m.created_at) DESC
    """, (user['user_id'],)).fetchall()

    # 为每条主消息加载完整对话
    full_threads = []
    for msg in messages:
        replies = conn.execute("""
            SELECT * FROM replies 
            WHERE message_id = ? 
            ORDER BY created_at ASC
        """, (msg['message_id'],)).fetchall()
        full_threads.append({
            'main': msg,
            'replies': replies
        })

    conn.close()
    return render_template('student/school_mailbox.html', threads=full_threads)


@student_bp.route('/school-mailbox/<int:message_id>/reply', methods=['POST'])
def reply_to_thread(message_id):
    username = session.get('username')
    if not username:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT user_id, name FROM account a JOIN student s ON a.user_id = s.student_id WHERE username = ?",
        (username,)).fetchone()

    content = request.form.get('content', '').strip()
    if content and user:
        conn.execute("""
            INSERT INTO replies (message_id, sender_role, sender_id, sender_name, content)
            VALUES (?, 'student', ?, ?, ?)
        """, (message_id, user['user_id'], user['name'], content))
        conn.commit()

    conn.close()
    return redirect(url_for('student.school_mailbox'))