import sqlite3
from faker import Faker
import random

# 英文 Faker：仅用于生成英文姓名
fake_en = Faker('en_US')
# 中文 Faker：可用于出生日期范围（可选，这里其实用 fake_en 也可以）
# 但为了保持年龄分布合理，我们直接用 date_between，不依赖 locale

COLLEGE_IDS = ['CS', 'ENG', 'ARTS', 'MED', 'SCI']

TITLES = [
    ('Professor', 15000.00),
    ('Associate Professor', 12000.00),
    ('Lecturer', 9000.00),
    ('Assistant Professor', 8000.00),
]


def generate_id_card(birth_date, gender):
    area_codes = ['110101', '310101', '440301', '330101', '510101']
    area = random.choice(area_codes)
    birth = birth_date.strftime('%Y%m%d')
    seq = f"{random.randint(100, 999):03d}"
    if gender == 'M':
        seq = seq[:-1] + str(random.choice([1, 3, 5, 7, 9]))
    else:
        seq = seq[:-1] + str(random.choice([0, 2, 4, 6, 8]))
    check = random.choice('0123456789X')
    return area + birth + seq + check


# 连接数据库
conn = sqlite3.connect('students-ENG.db')
cursor = conn.cursor()

teachers = []
used_ids = set()

for i in range(1, 101):
    tid = f"T{i:04d}"
    name = fake_en.name()  # ← 改为英文名
    gender = random.choice(['M', 'F'])

    # 出生日期：30~60 岁（合理教师年龄）
    from datetime import date, timedelta

    start_date = date.today() - timedelta(days=60 * 365)
    end_date = date.today() - timedelta(days=30 * 365)
    birth = fake_en.date_between(start_date=start_date, end_date=end_date)

    title, base_sal = random.choices(TITLES, weights=[1, 3, 4, 2], k=1)[0]
    salary = round(base_sal + random.uniform(-1000, 1000), 2)
    college = random.choice(COLLEGE_IDS)

    idc = generate_id_card(birth, gender)
    while idc in used_ids:
        idc = generate_id_card(birth, gender)
    used_ids.add(idc)

    teachers.append((tid, name, gender, birth, salary, title, college, idc))

# 安全插入（参数化）
cursor.executemany('''
    INSERT INTO "teacher" (
        "teacher_id", "name", "gender", "birth_date",
        "salary", "title", "college_id", "id_card"
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
''', teachers)

conn.commit()
print(f"✅ 成功插入 {len(teachers)} 名教师（英文名 + 中国身份证）")
conn.close()