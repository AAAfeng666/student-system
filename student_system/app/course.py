# app/course.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.db import get_db_connection
from datetime import datetime
from itertools import groupby
from operator import itemgetter

course_bp = Blueprint('course', __name__)


@course_bp.route('/select-course')
def select_course():
    if 'username' not in session or session.get('role') != 'student':
        flash('Please log in first!')
        return redirect(url_for('auth.login'))

    student_id = session['username']
    conn = get_db_connection()

    try:
        # === 1. 获取当前学期及选课时间窗口 ===
        current_semester = conn.execute("""
            SELECT semester_id, semester_name, selection_start, selection_end 
            FROM semester 
            WHERE is_current = 1
        """).fetchone()

        if not current_semester:
            flash('No active semester found. Course selection is unavailable.')
            return redirect(url_for('main.dashboard'))

        now = datetime.now().date()
        selection_start = datetime.strptime(current_semester['selection_start'], '%Y-%m-%d %H:%M:%S').date()
        selection_end = datetime.strptime(current_semester['selection_end'], '%Y-%m-%d %H:%M:%S').date()

        if not (selection_start <= now <= selection_end):
            flash(f'❌ Course selection is not available at this time! Selection period: {selection_start} to {selection_end}')
            return redirect(url_for('main.dashboard'))

        # === 2. 获取学生信息 ===
        student = conn.execute(
            "SELECT college_id, enrollment_year FROM student WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        if not student:
            flash('Student information error!')
            return redirect(url_for('main.dashboard'))

        student_college_id = student['college_id']
        current_year = datetime.now().year
        student_grade = current_year - student['enrollment_year'] + 1

        # === 3. 查询所有本院当前学期课程（包括已选的）===
        all_courses = conn.execute("""
            SELECT oc.offered_id, c.course_name, t.name AS teacher_name, col.college_name,
                   oc.time_slot, oc.classroom, oc.capacity, oc.current_count, 
                   c.college_id AS course_college_id, 
                   c.target_grade,
                   c.credits
            FROM offered_course oc
            JOIN course c ON oc.course_id = c.course_id
            JOIN teacher t ON oc.teacher_id = t.teacher_id
            JOIN college col ON c.college_id = col.college_id
            JOIN semester s ON oc.semester_id = s.semester_id
            WHERE s.is_current = 1
            ORDER BY c.course_name, oc.time_slot
        """).fetchall()

        all_courses = [dict(row) for row in all_courses]
        my_college_list = [c for c in all_courses if c['course_college_id'] == student_college_id]

        # === 4. 查询已选课程（精确到班次）===
        enrolled = conn.execute("""
            SELECT oc.offered_id, c.course_name, t.name AS teacher_name, col.college_name,
                   oc.time_slot, oc.classroom, oc.capacity, oc.current_count, c.credits 
            FROM enrollment e
            JOIN offered_course oc ON e.offered_id = oc.offered_id
            JOIN course c ON oc.course_id = c.course_id
            JOIN teacher t ON oc.teacher_id = t.teacher_id
            JOIN college col ON c.college_id = col.college_id
            JOIN semester s ON oc.semester_id = s.semester_id
            WHERE s.is_current = 1 AND e.student_id = ?
            ORDER BY c.course_name
        """, (student_id,)).fetchall()

        total_credits = sum(course['credits'] for course in enrolled)

        # 🔑 关键：记录已选的 offered_id 和 course_name
        enrolled_offered_ids = {e['offered_id'] for e in enrolled}
        enrolled_course_names = {e['course_name'] for e in enrolled}

        # === 5. 聚合本院课程，并为每个班次标记是否已选 + 排序 ===
        my_college_list_sorted = sorted(my_college_list, key=itemgetter('course_name'))
        my_college_courses_grouped = []

        for course_name, group in groupby(my_college_list_sorted, key=itemgetter('course_name')):
            sections = list(group)
            rep = sections[0]
            credits = rep['credits']
            target_grade = rep['target_grade']

            already_enrolled = course_name in enrolled_course_names

            # 构建增强版班次列表：每个班次带 is_enrolled 标记
            enhanced_sections = []
            selectable_sections = []
            for sec in sections:
                is_enrolled = sec['offered_id'] in enrolled_offered_ids
                enhanced_sec = dict(sec)
                enhanced_sec['is_enrolled'] = is_enrolled
                enhanced_sections.append(enhanced_sec)

                # 判断是否可选（注意：这里逻辑必须和前端一致）
                if (not already_enrolled
                        and sec['target_grade'] == student_grade
                        and sec['current_count'] < sec['capacity']
                        and (total_credits + credits) <= 18):
                    selectable_sections.append(enhanced_sec)

            # ✅【关键】对班次排序：可选的在前，不可选的在后
            def section_sort_key(sec):
                # 如果是可选班次，排前面（0），否则排后面（1）
                is_selectable = (
                        not already_enrolled
                        and sec['target_grade'] == student_grade
                        and sec['current_count'] < sec['capacity']
                        and (total_credits + credits) <= 18
                )
                return (0 if is_selectable else 1, sec['time_slot'])  # 次级按时间排序

            sorted_sections = sorted(enhanced_sections, key=section_sort_key)

            # 判断整个课程是否“有可选项”
            has_selectable = len(selectable_sections) > 0

            my_college_courses_grouped.append({
                'course_name': course_name,
                'credits': credits,
                'college_name': rep['college_name'],
                'target_grade': target_grade,
                'sections': sorted_sections,  # ← 已排序的班次
                'selectable_sections': selectable_sections,
                'already_enrolled': already_enrolled,
                'would_exceed_limit': (total_credits + credits) > 18,
                '_has_selectable': has_selectable  # ← 用于课程排序
            })

        # ✅【关键】对课程整体排序：有可选班次的课程在前，完全不可选的在后
        def course_sort_key(gc):
            if gc['_has_selectable']:
                return (0, gc['course_name'])  # 可选未选 → 第一梯队
            elif gc['already_enrolled']:
                return (1, gc['course_name'])  # 已选 → 第二梯队
            else:
                return (2, gc['course_name'])  # 不可选未选 → 第三梯队

        my_college_courses_grouped.sort(key=course_sort_key)

        # === 6. 聚合其他学院课程（按 course_name + college_name 分组）===
        other_college_list = [c for c in all_courses if c['course_college_id'] != student_college_id]

        # 提取所有其他学院的名称（用于下拉框）
        other_colleges = sorted({c['college_name'] for c in other_college_list})

        # 按 (college_name, course_name) 分组
        other_college_list_sorted = sorted(other_college_list, key=lambda x: (x['college_name'], x['course_name']))
        other_college_grouped = []

        for (college_name, course_name), group in groupby(other_college_list_sorted,
                                                          key=lambda x: (x['college_name'], x['course_name'])):
            sections = list(group)
            rep = sections[0]
            other_college_grouped.append({
                'college_name': college_name,
                'course_name': course_name,
                'credits': rep['credits'],
                'target_grade': rep['target_grade'],
                'sections': sections  # 所有班次
            })

        return render_template('student/select_course.html',
                               username=student_id,
                               current_semester=current_semester,
                               enrolled_courses=enrolled,
                               my_college_courses=my_college_courses_grouped,
                               other_college_courses=other_college_grouped,
                               other_colleges=other_colleges,
                               student_college_id=student_college_id,
                               student_grade=student_grade,
                               total_credits=total_credits)

    except Exception as e:
        flash(f'System error: {str(e)}')
        return redirect(url_for('main.dashboard'))
    finally:
        conn.close()


from datetime import datetime

@course_bp.route('/handle-select-course', methods=['POST'])
def handle_select_course():
    if 'username' not in session or session.get('role') != 'student':
        flash('Please log in first!')
        return redirect(url_for('auth.login'))

    offered_id = request.form.get('offered_id')
    if not offered_id:
        flash('Invalid course ID!')
        return redirect(url_for('course.select_course'))

    student_id = session['username']
    conn = get_db_connection()
    try:
        # === 1. 获取学生信息 ===
        student = conn.execute(
            "SELECT college_id, enrollment_year FROM student WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        if not student:
            flash('Student information error!')
            return redirect(url_for('course.select_course'))
        student_college_id = student['college_id']
        current_year = datetime.now().year
        student_grade = current_year - student['enrollment_year'] + 1

        # === 2. 获取课程详细信息（用于权限、年级、时间等检查）===
        course_info = conn.execute("""
            SELECT 
                c.college_id, 
                oc.capacity, 
                oc.time_slot,
                c.target_grade,
                c.course_name,
                oc.semester_id
            FROM offered_course oc
            JOIN course c ON oc.course_id = c.course_id
            WHERE oc.offered_id = ?
        """, (offered_id,)).fetchone()

        if not course_info:
            flash('Course does not exist!')
            return redirect(url_for('course.select_course'))

        # === 3. 权限检查：本学院 ===
        if course_info['college_id'] != student_college_id:
            flash('❌ You can only select courses offered by your own college!')
            return redirect(url_for('course.select_course'))

        # === 4. 年级检查 ===
        if course_info['target_grade'] != student_grade:
            flash(f'❌ This course is only open to grade {course_info["target_grade"]} students!')
            return redirect(url_for('course.select_course'))

        # === 5. 选课时间窗口检查 ===
        selection_info = conn.execute("""
            SELECT s.selection_start, s.selection_end 
            FROM semester s 
            WHERE s.semester_id = ? AND s.is_current = 1
        """, (course_info['semester_id'],)).fetchone()

        if selection_info:
            print("🔍 DEBUG: selection_start =", repr(selection_info['selection_start']))
            print("🔍 DEBUG: selection_end   =", repr(selection_info['selection_end']))
            now = datetime.now().date()
            selection_start = datetime.strptime(selection_info['selection_start'], '%Y-%m-%d %H:%M:%S').date()
            selection_end = datetime.strptime(selection_info['selection_end'], '%Y-%m-%d %H:%M:%S').date()
            if not (selection_start <= now <= selection_end):
                flash('Course selection is not available outside the designated period!')
                return redirect(url_for('course.select_course'))

        # === 6. 是否已选该班次 ===
        if conn.execute("SELECT 1 FROM enrollment WHERE student_id = ? AND offered_id = ?",
                        (student_id, offered_id)).fetchone():
            flash('❌ You have already enrolled in this course section!')
            return redirect(url_for('course.select_course'))

        # === 7. 检查是否已选同名课程 ===
        same_name_check = conn.execute("""
            SELECT 1
            FROM enrollment e
            JOIN offered_course oc2 ON e.offered_id = oc2.offered_id
            JOIN course c2 ON oc2.course_id = c2.course_id
            WHERE e.student_id = ? AND c2.course_name = ?
        """, (student_id, course_info['course_name'])).fetchone()

        if same_name_check:
            flash(f'❌ You have already enrolled in “{course_info["course_name"]}” — duplicate course names are not allowed!')
            return redirect(url_for('course.select_course'))

        # === 7.5 【新增】检查学分是否超限 ===
        current_total = conn.execute("""
                SELECT COALESCE(SUM(c.credits), 0) AS total
                FROM enrollment e
                JOIN offered_course oc ON e.offered_id = oc.offered_id
                JOIN course c ON oc.course_id = c.course_id
                WHERE e.student_id = ?
            """, (student_id,)).fetchone()['total']

        new_course_credits = conn.execute("""
                SELECT credits 
                FROM course c 
                JOIN offered_course oc ON c.course_id = oc.course_id 
                WHERE oc.offered_id = ?
            """, (offered_id,)).fetchone()['credits']

        if current_total + new_course_credits > 15:
            flash(f'❌ Enrollment failed: total credits would reach {current_total + new_course_credits}, exceeding the 15-credit limit!')
            return redirect(url_for('course.select_course'))

        # === 8. 时间冲突检查 ===
        new_time = course_info['time_slot']
        conflicts = conn.execute("""
            SELECT c.course_name
            FROM enrollment e
            JOIN offered_course oc ON e.offered_id = oc.offered_id
            JOIN course c ON oc.course_id = c.course_id
            WHERE e.student_id = ? AND oc.time_slot = ?
        """, (student_id, new_time)).fetchall()

        if conflicts:
            conflict_names = ', '.join([row['course_name'] for row in conflicts])
            flash(f'❌ Time conflict! Overlaps with enrolled course(s): 「{conflict_names}」.')
            return redirect(url_for('course.select_course'))

        # === 9. 【关键】原子化占位：尝试增加名额（仅当未满时）===
        conn.execute("BEGIN IMMEDIATE")  # SQLite 写锁，避免并发问题

        # 先尝试更新 current_count（只有未满才能成功）
        result = conn.execute("""
            UPDATE offered_course 
            SET current_count = current_count + 1 
            WHERE offered_id = ? AND current_count < capacity
        """, (offered_id,))

        if result.rowcount == 0:
            # 要么已满，要么课程不存在
            flash('❌ Course is full (may have just been taken by another student)')
            conn.rollback()
            return redirect(url_for('course.select_course'))

        # 插入选课记录
        conn.execute(
            "INSERT INTO enrollment (student_id, offered_id, regular_score, exam_score, total_score) VALUES (?, ?, NULL, NULL, NULL)",
            (student_id, offered_id)
        )
        conn.commit()
        flash('✅ Course selected successfully!')

    except Exception as e:
        conn.rollback()
        flash(f'Enrollment failed: {str(e)}')
    finally:
        conn.close()

    # 重定向会触发页面重新加载，模板将显示最新 current_count
    return redirect(url_for('course.select_course'))


@course_bp.route('/drop-course', methods=['POST'])
def drop_course():
    if 'username' not in session or session.get('role') != 'student':
        flash('Please log in as a student!')
        return redirect(url_for('auth.login'))

    offered_id = request.form.get('offered_id')
    if not offered_id:
        flash('Invalid course ID!')
        return redirect(url_for('main.dashboard'))

    student_id = session['username']
    conn = get_db_connection()
    try:
        # 选课时间检查
        selection_info = conn.execute("""
            SELECT s.selection_start, s.selection_end 
            FROM semester s 
            JOIN offered_course oc ON s.semester_id = oc.semester_id 
            WHERE oc.offered_id = ? AND s.is_current = 1
        """, (offered_id,)).fetchone()

        if selection_info:
            now = datetime.now()
            selection_start = datetime.strptime(selection_info['selection_start'], '%Y-%m-%d %H:%M:%S')
            selection_end = datetime.strptime(selection_info['selection_end'], '%Y-%m-%d %H:%M:%S')
            if not (selection_start <= now <= selection_end):
                flash('Drop period has ended. Please act within the allowed timeframe!')
                return redirect(url_for('course.select_course'))

        exists = conn.execute("SELECT 1 FROM enrollment WHERE student_id = ? AND offered_id = ?",
                              (student_id, offered_id)).fetchone()
        if not exists:
            flash('❌ You are not enrolled in this course — cannot drop!')
            return redirect(url_for('course.select_course'))

        # 执行退选 + 减少人数
        conn.execute("DELETE FROM enrollment WHERE student_id = ? AND offered_id = ?", (student_id, offered_id))
        conn.execute("UPDATE offered_course SET current_count = current_count - 1 WHERE offered_id = ?", (offered_id,))
        conn.commit()
        flash('✅ Course dropped successfully!')

    except Exception as e:
        conn.rollback()
        flash(f'Drop failed: {str(e)}')
    finally:
        conn.close()

    return redirect(url_for('course.select_course'))