import sqlite3
from werkzeug.security import generate_password_hash

# ⚠️ 修改为你的实际数据库路径（如 'instance/school.db'）
DB_PATH = 'students-ENG.db'

def init_accounts():
    conn = sqlite3.connect(DB_PATH)
    try:
        # === 1. 为学生创建账号 ===
        cur = conn.execute("SELECT student_id, id_card FROM student")
        student_count = 0
        for student_id, id_card in cur.fetchall():
            username = student_id
            raw_password = (id_card[-6:] if id_card and len(id_card) >= 6 else '123456')
            hashed = generate_password_hash(raw_password)

            try:
                conn.execute("""
                    INSERT INTO account (username, password_hash, role, user_id, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, hashed, 'student', username, True))
                student_count += 1
            except sqlite3.IntegrityError:
                print(f"⚠️ 学生账号已存在，跳过: {username}")

        # === 2. 为教师创建账号 ===
        cur = conn.execute("SELECT teacher_id, id_card FROM teacher")
        teacher_count = 0
        for teacher_id, id_card in cur.fetchall():
            username = teacher_id
            raw_password = (id_card[-6:] if id_card and len(id_card) >= 6 else '123456')
            hashed = generate_password_hash(raw_password)

            try:
                conn.execute("""
                    INSERT INTO account (username, password_hash, role, user_id, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (username, hashed, 'teacher', username, True))
                teacher_count += 1
            except sqlite3.IntegrityError:
                print(f"⚠️ 教师账号已存在，跳过: {username}")

        conn.commit()
        print(f"✅ 账号初始化完成！新增学生账号: {student_count} 个，教师账号: {teacher_count} 个")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    init_accounts()