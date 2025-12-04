# app/main.py
from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.db import get_db_connection
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    role = session.get('role', 'student')
    username = session['username']
    conn = get_db_connection()

    if role == 'admin':
        stats = conn.execute("""
            SELECT 
                (SELECT COUNT(*) FROM student) AS student_count,
                (SELECT COUNT(*) FROM teacher) AS teacher_count,
                (SELECT COUNT(*) FROM course) AS course_count
        """).fetchone()
        current_semester = conn.execute(
            "SELECT semester_name FROM semester WHERE is_current = 1"
        ).fetchone()
        return render_template('admin/dashboard_admin.html',
                               username=username,
                               stats=stats,
                               current_semester=current_semester)
    elif role == 'teacher':
        courses = conn.execute("""
            SELECT 
                oc.offered_id,
                c.course_name,
                s.semester_name,
                oc.classroom,
                oc.time_slot,
                oc.capacity,
                COUNT(e.student_id) AS student_count
            FROM offered_course oc
            JOIN course c ON oc.course_id = c.course_id
            JOIN semester s ON oc.semester_id = s.semester_id
            LEFT JOIN enrollment e ON oc.offered_id = e.offered_id
            WHERE oc.teacher_id = (
                SELECT user_id 
                FROM account 
                WHERE username = ?
            )
            GROUP BY oc.offered_id, c.course_name, s.semester_name, oc.classroom, oc.time_slot, oc.capacity
            ORDER BY s.semester_name, c.course_name
        """, (username,)).fetchall()

        # 去重统计：该教师当前学期教的所有课程中，有多少个不同学生
        total_unique_students = conn.execute("""
            SELECT COALESCE(COUNT(DISTINCT e.student_id), 0)
            FROM offered_course oc
            JOIN semester s ON oc.semester_id = s.semester_id
            LEFT JOIN enrollment e ON oc.offered_id = e.offered_id
            WHERE oc.teacher_id = (SELECT user_id FROM account WHERE username = ?)
              AND s.is_current = 1
        """, (username,)).fetchone()[0]

        # 查询当前学期名称
        current_semester_row = conn.execute("""
            SELECT semester_name 
            FROM semester 
            WHERE is_current = 1
        """).fetchone()

        # 查询未完成成绩录入的课程门数
        pending_courses = conn.execute("""
            SELECT COUNT(DISTINCT oc.offered_id)
            FROM offered_course oc
            JOIN enrollment e ON oc.offered_id = e.offered_id
            WHERE oc.teacher_id = (SELECT user_id FROM account WHERE username = ?)
              AND e.total_score IS NULL
        """, (username,)).fetchone()[0]

        current_semester_name = current_semester_row['semester_name'] if current_semester_row else 'Unknown Semester'
        return render_template('teacher/dashboard_teacher.html',
                               username=username,
                               courses=courses,
                               total_students=total_unique_students,
                               pending_courses=pending_courses,
                               current_semester_name=current_semester_name)


    else:  # student
        student_id = conn.execute(
            "SELECT user_id FROM account WHERE username = ?", (username,)
        ).fetchone()['user_id']
        # 获取已选课程（含 time_slot）

        enrollments = conn.execute("""
                SELECT 
                    c.course_name, 
                    t.name AS teacher_name, 
                    e.regular_score, 
                    e.exam_score, 
                    e.total_score, 
                    oc.offered_id,
                    oc.time_slot,
                    oc.classroom

                FROM enrollment e
                JOIN offered_course oc ON e.offered_id = oc.offered_id
                JOIN course c ON oc.course_id = c.course_id
                JOIN teacher t ON oc.teacher_id = t.teacher_id
                JOIN semester s ON oc.semester_id = s.semester_id
                WHERE e.student_id = ? AND s.is_current = 1
            """, (student_id,)).fetchall()

        # === 新增：查询当前学期的选课时间窗口 ===
        selection_window = conn.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:%M:%S', selection_start) AS start_fmt,
                strftime('%Y-%m-%d %H:%M:%S', selection_end) AS end_fmt
            FROM semester 
            WHERE is_current = 1
        """).fetchone()

        # 获取当前时间字符串
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # === 按星期几分组课程（用于课程表）===
        courses_by_day = {}
        weekday_map = {
            '周一': 0,
            '周二': 1,
            '周三': 2,
            '周四': 3,
            '周五': 4,
            '周六': 5,
            '周日': 6
        }

        for row in enrollments:
            slot = row['time_slot']
            if not slot:
                continue

            for day_str, day_index in weekday_map.items():
                if day_str in slot:
                    if day_index not in courses_by_day:
                        courses_by_day[day_index] = []
                    courses_by_day[day_index].append(row)
                    break

        return render_template('student/dashboard_student.html',
                               username=username,
                               enrollments=enrollments,
                               courses_by_day=courses_by_day,
                               selection_window=selection_window,
                               now_str=now_str)

@main_bp.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    username = session['username']
    role = session.get('role', 'student')
    conn = get_db_connection()

    user_info = {'role': role, 'username': username}

    if role == 'student':
        data = conn.execute("""
            SELECT s.student_id, s.name, s.gender, s.birth_date, s.phone, 
                   s.hometown, s.id_card, c.college_name, s.enrollment_year
            FROM student s
            JOIN college c ON s.college_id = c.college_id
            WHERE s.student_id = (SELECT user_id FROM account WHERE username = ?)
        """, (username,)).fetchone()
        if data:
            user_info.update(dict(data))

    elif role == 'teacher':
        data = conn.execute("""
            SELECT t.teacher_id, t.name, t.gender, t.birth_date, t.title,
                   t.id_card, t.salary, c.college_name
            FROM teacher t
            JOIN college c ON t.college_id = c.college_id
            WHERE t.teacher_id = (SELECT user_id FROM account WHERE username = ?)
        """, (username,)).fetchone()
        if data:
            user_info.update(dict(data))

    # 管理员不查额外信息
    conn.close()
    conn.close()

    # 根据角色选择不同的模板
    template = ''
    if role == 'student':
        template = 'student/profile.html'
    elif role == 'teacher':
        template = 'teacher/profile.html'
    else:  # 默认是管理员或其他角色
        template = 'admin/profile.html'

    return render_template(template, user=user_info)