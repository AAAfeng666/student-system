# -*- coding: utf-8 -*-
import sqlite3

# === 配置 ===
DB_PATH = "students-ENG.db"  # 你的 SQLite 数据库文件

# === 映射字典 ===
weekday_map = {
    "周一": "Monday ",
    "周二": "Tuesday ",
    "周三": "Wednesday ",
    "周四": "Thursday ",
    "周五": "Friday "
}

def translate_time(chinese_time):
    for zh, en in weekday_map.items():
        if chinese_time.startswith(zh):
            return chinese_time.replace(zh, en, 1)
    return chinese_time

def translate_classroom(chinese):
    s = chinese.strip()
    if "信息楼A座" in s:
        room = s.replace("信息楼A座", "").strip()
        return f"Information Building, Block A, Room {room}"
    elif "文理楼" in s:
        room = s.replace("文理楼", "").strip()
        return f"Liberal Arts Building, Room {room}"
    elif "医学楼" in s:
        room = s.replace("医学楼", "").strip()
        return f"Medical Laboratory Building, Room {room}"
    elif "基础楼" in s:
        room = s.replace("基础楼", "").strip()
        return f"Basic Teaching Building, Room {room}"
    elif "艺术中心B" in s:
        room = s.replace("艺术中心", "").strip()
        return f"Art Center, Building B, Room {room}"
    elif "艺术中心" in s:
        room = s.replace("艺术中心", "").strip()
        return f"Art Center, Room {room}"
    else:
        return s

def migrate_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 支持列名访问
    cursor = conn.cursor()

    # 从源表读取数据
    cursor.execute("""
        SELECT offered_id, course_id, teacher_id, semester_id,
               classroom, time_slot, capacity, current_count
        FROM offered_course_raw
    """)
    rows = cursor.fetchall()

    insert_data = []
    for row in rows:
        classroom_en = translate_classroom(row['classroom'])
        time_en = translate_time(row['time_slot'])

        insert_data.append((
            row['offered_id'],
            row['course_id'],
            row['teacher_id'],
            row['semester_id'],
            classroom_en,
            time_en,
            row['capacity'],
            row['current_count']
        ))

    # 批量插入到目标表
    cursor.executemany("""
        INSERT INTO offered_course (
            offered_id, course_id, teacher_id, semester_id,
            classroom, time_slot, capacity, current_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, insert_data)

    conn.commit()
    print(f"✅ 成功迁移 {len(insert_data)} 条记录到 offered_course 表。")
    conn.close()

if __name__ == "__main__":
    migrate_data()