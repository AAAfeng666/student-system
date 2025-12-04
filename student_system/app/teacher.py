# app/teacher.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db_connection

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')


def require_teacher():
    """验证教师身份"""
    return session.get('role') == 'teacher'


# 1.1 查看我的选课情况 - 课程列表
@teacher_bp.route('/my-courses')
def my_courses():
    if not require_teacher():
        flash('请以教师身份登录！')
        return redirect(url_for('auth.login'))

    username = session['username']
    conn = get_db_connection()

    # 获取教师ID
    teacher = conn.execute(
        "SELECT user_id FROM account WHERE username = ?", (username,)
    ).fetchone()

    if not teacher:
        flash('教师信息不存在！')
        conn.close()
        return redirect(url_for('main.dashboard'))

    teacher_id = teacher['user_id']

    # 获取教师所教课程列表
    courses = conn.execute("""
        SELECT 
            oc.offered_id,
            c.course_id,
            c.course_name,
            c.credits,
            c.hours,
            s.semester_name,
            oc.classroom,
            oc.time_slot,
            oc.capacity,
            oc.current_count,
            COUNT(e.student_id) as student_count
        FROM offered_course oc
        JOIN course c ON oc.course_id = c.course_id
        JOIN semester s ON oc.semester_id = s.semester_id
        LEFT JOIN enrollment e ON oc.offered_id = e.offered_id
        WHERE oc.teacher_id = ?
        GROUP BY oc.offered_id
        ORDER BY s.semester_name, c.course_name
    """, (teacher_id,)).fetchall()

    conn.close()
    return render_template('teacher/teacher_courses.html', courses=courses, username=username)


# 1.2 查看课程详情和学生名单
@teacher_bp.route('/course/<int:offered_id>')
def course_detail(offered_id):
    print(f"🔍 进入course_detail函数，offered_id: {offered_id}")

    if not require_teacher():
        flash('请以教师身份登录！')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()

    # 验证教师是否有权访问此课程
    username = session['username']
    teacher = conn.execute(
        "SELECT user_id FROM account WHERE username = ?", (username,)
    ).fetchone()

    if teacher:
        is_authorized = conn.execute("""
            SELECT 1 FROM offered_course 
            WHERE offered_id = ? AND teacher_id = ?
        """, (offered_id, teacher['user_id'])).fetchone()

        if not is_authorized:
            flash('无权访问此课程！')
            conn.close()
            return redirect(url_for('teacher.my_courses'))

    # 获取课程基本信息
    course_info = conn.execute("""
        SELECT 
            oc.offered_id,
            c.course_id,
            c.course_name,
            c.credits,
            c.hours,
            s.semester_name,
            oc.classroom,
            oc.time_slot,
            oc.capacity,
            t.name as teacher_name,
            col.college_name
        FROM offered_course oc
        JOIN course c ON oc.course_id = c.course_id
        JOIN semester s ON oc.semester_id = s.semester_id
        JOIN teacher t ON oc.teacher_id = t.teacher_id
        JOIN college col ON c.college_id = col.college_id
        WHERE oc.offered_id = ?
    """, (offered_id,)).fetchone()

    # 获取学生名单
    students = conn.execute("""
        SELECT 
            s.student_id,
            s.name,
            s.gender,
            s.college_id,
            col.college_name as student_college,
            e.regular_score,
            e.exam_score,
            e.total_score
        FROM enrollment e
        JOIN student s ON e.student_id = s.student_id
        JOIN college col ON s.college_id = col.college_id
        WHERE e.offered_id = ?
        ORDER BY s.student_id
    """, (offered_id,)).fetchall()

    conn.close()

    return render_template('teacher/teacher_course_detail.html',
                           course=course_info,
                           students=students,
                           username=username)


# 2.1 成绩录入页面（带比例调整）
@teacher_bp.route('/grade/<int:offered_id>', methods=['GET', 'POST'])
def grade_input(offered_id):
    if not require_teacher():
        flash('请以教师身份登录！')
        return redirect(url_for('auth.login'))

    conn = get_db_connection()

    try:
        # 验证教师权限
        username = session['username']
        teacher = conn.execute(
            "SELECT user_id FROM account WHERE username = ?", (username,)
        ).fetchone()

        if teacher:
            is_authorized = conn.execute("""
                SELECT 1 FROM offered_course 
                WHERE offered_id = ? AND teacher_id = ?
            """, (offered_id, teacher['user_id'])).fetchone()

            if not is_authorized:
                flash('无权为此课程输入成绩！')
                return redirect(url_for('teacher.my_courses'))

        # 获取课程基本信息
        course_info = conn.execute("""
            SELECT 
                oc.offered_id,
                c.course_name,
                s.semester_name
            FROM offered_course oc
            JOIN course c ON oc.course_id = c.course_id
            JOIN semester s ON oc.semester_id = s.semester_id
            WHERE oc.offered_id = ?
        """, (offered_id,)).fetchone()

        # 获取学生名单（用于成绩输入）
        students = conn.execute("""
            SELECT 
                e.enrollment_id,
                s.student_id,
                s.name,
                s.college_id,
                col.college_name,
                e.regular_score,
                e.exam_score,
                e.total_score
            FROM enrollment e
            JOIN student s ON e.student_id = s.student_id
            JOIN college col ON s.college_id = col.college_id
            WHERE e.offered_id = ?
            ORDER BY s.student_id
        """, (offered_id,)).fetchall()

        if request.method == 'POST':
            # 获取比例设置
            regular_ratio = float(request.form.get('regular_ratio', 40))
            exam_ratio = float(request.form.get('exam_ratio', 60))

            # 验证比例总和为100%
            if regular_ratio + exam_ratio != 100:
                flash('❌ 平时成绩和考试成绩比例之和必须为100%！')
                return render_template('teacher/teacher_grade_input.html',
                                       course=course_info,
                                       students=students,
                                       username=username,
                                       regular_ratio=regular_ratio,
                                       exam_ratio=exam_ratio)

            # 处理成绩提交
            success_count = 0
            for student in students:
                enrollment_id = student['enrollment_id']
                regular_score = request.form.get(f'regular_{enrollment_id}')
                exam_score = request.form.get(f'exam_{enrollment_id}')

                # 计算总评成绩（按设置的比例）
                total_score = None
                if regular_score and exam_score:
                    try:
                        regular = int(regular_score)
                        exam = int(exam_score)
                        total_score = round(regular * (regular_ratio / 100) + exam * (exam_ratio / 100))
                    except ValueError:
                        flash(f'学生 {student["name"]} 的成绩格式错误，已跳过')
                        continue

                # 更新成绩
                try:
                    conn.execute("""
                        UPDATE enrollment 
                        SET regular_score = ?, exam_score = ?, total_score = ?
                        WHERE enrollment_id = ?
                    """, (
                        int(regular_score) if regular_score else None,
                        int(exam_score) if exam_score else None,
                        total_score,
                        enrollment_id
                    ))
                    success_count += 1
                except Exception as e:
                    flash(f'更新学生 {student["name"]} 成绩失败: {str(e)}')

            conn.commit()

            if success_count > 0:
                flash('✅ 已保存修改')
            else:
                flash('❌ 未更新任何成绩，请检查输入格式')

            return redirect(url_for('teacher.course_detail', offered_id=offered_id))

        # GET请求时使用默认比例
        return render_template('teacher/teacher_grade_input.html',
                               course=course_info,
                               students=students,
                               username=username,
                               regular_ratio=40,
                               exam_ratio=60)

    except Exception as e:
        flash(f'成绩录入失败: {str(e)}')
        return redirect(url_for('teacher.my_courses'))
    finally:
        conn.close()


# 2.2 快速成绩提交（单名学生）
@teacher_bp.route('/update-single-grade', methods=['POST'])
def update_single_grade():
    if not require_teacher():
        return redirect(url_for('auth.login'))

    enrollment_id = request.form.get('enrollment_id')
    regular_score = request.form.get('regular_score')
    exam_score = request.form.get('exam_score')
    offered_id = request.form.get('offered_id')

    if not enrollment_id or not offered_id:
        flash('参数错误！')
        return redirect(url_for('teacher.my_courses'))

    conn = get_db_connection()

    try:
        # 验证权限
        username = session['username']
        teacher = conn.execute(
            "SELECT user_id FROM account WHERE username = ?", (username,)
        ).fetchone()

        if teacher:
            is_authorized = conn.execute("""
                SELECT 1 FROM offered_course oc
                JOIN enrollment e ON oc.offered_id = e.offered_id
                WHERE e.enrollment_id = ? AND oc.teacher_id = ?
            """, (enrollment_id, teacher['user_id'])).fetchone()

            if not is_authorized:
                flash('无权修改此成绩！')
                return redirect(url_for('teacher.my_courses'))

        # 计算总评成绩
        total_score = None
        if regular_score and exam_score:
            try:
                regular = float(regular_score)
                exam = float(exam_score)
                total_score = round(regular * 0.4 + exam * 0.6, 2)
            except ValueError:
                flash('成绩格式错误！')
                return redirect(url_for('teacher.grade_input', offered_id=offered_id))

        # 更新成绩
        conn.execute("""
            UPDATE enrollment 
            SET regular_score = ?, exam_score = ?, total_score = ?
            WHERE enrollment_id = ?
        """, (
            float(regular_score) if regular_score else None,
            float(exam_score) if exam_score else None,
            total_score,
            enrollment_id
        ))
        conn.commit()
        flash('✅ 已保存修改')

    except Exception as e:
        flash(f'❌ 成绩更新失败: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('teacher.grade_input', offered_id=offered_id))


@teacher_bp.route('/reset-grade', methods=['POST'])
def reset_grade():
    if not require_teacher():
        print(">>> 未登录或非教师")
        flash('请以教师身份登录！')
        return redirect(url_for('auth.login'))

    enrollment_id = request.form.get('enrollment_id')
    offered_id = request.form.get('offered_id')

    if not enrollment_id or not offered_id:
        print(">>> 参数缺失！")
        flash('参数错误！')
        return redirect(url_for('teacher.my_courses'))


    conn = get_db_connection()
    try:
        username = session['username']
        teacher = conn.execute("SELECT user_id FROM account WHERE username = ?", (username,)).fetchone()
        if not teacher:
            flash('教师账户异常！')
            return redirect(url_for('auth.login'))

        is_authorized = conn.execute("""
            SELECT 1 FROM offered_course oc
            JOIN enrollment e ON oc.offered_id = e.offered_id
            WHERE e.enrollment_id = ? AND oc.teacher_id = ?
        """, (enrollment_id, teacher['user_id'])).fetchone()

        if not is_authorized:
            flash('无权重置此学生成绩！')
            return redirect(url_for('teacher.my_courses'))

        # 使用 None 显式表示 NULL（推荐）
        conn.execute("""
            UPDATE enrollment
            SET regular_score = ?,
                exam_score = ?,
                total_score = ?
            WHERE enrollment_id = ?
        """, (None, None, None, enrollment_id))

        conn.commit()
        flash('✅ 成绩已重置为空')
    except Exception as e:
        flash(f'❌ 重置成绩失败: {str(e)}')
        # 可选：记录日志 print(e)
    finally:
        conn.close()

    return redirect(url_for('teacher.grade_input', offered_id=offered_id))
