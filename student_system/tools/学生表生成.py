import sqlite3
import random
from faker import Faker

# 英文 Faker：用于英文名、英文街道
fake_en = Faker('en_US')
# 中文 Faker：仅用于生成中国手机号
fake_cn = Faker('zh_CN')

# 常见中国省市英文名
CHINESE_PROVINCES_EN = [
    "Beijing", "Shanghai", "Guangdong", "Zhejiang", "Jiangsu",
    "Sichuan", "Hubei", "Shaanxi", "Liaoning", "Hebei",
    "Henan", "Shandong", "Fujian", "Hunan", "Anhui"
]

CHINESE_CITIES_EN = {
    "Beijing": ["Beijing"],
    "Shanghai": ["Shanghai"],
    "Guangdong": ["Guangzhou", "Shenzhen", "Dongguan", "Foshan"],
    "Zhejiang": ["Hangzhou", "Ningbo", "Wenzhou"],
    "Jiangsu": ["Nanjing", "Suzhou", "Wuxi"],
    "Sichuan": ["Chengdu", "Mianyang"],
    "Hubei": ["Wuhan", "Xiangyang"],
    "Shaanxi": ["Xi'an", "Baoji"],
    "Liaoning": ["Shenyang", "Dalian"],
    "Hebei": ["Shijiazhuang", "Baoding"],
    "Henan": ["Zhengzhou", "Luoyang"],
    "Shandong": ["Jinan", "Qingdao"],
    "Fujian": ["Fuzhou", "Xiamen"],
    "Hunan": ["Changsha", "Zhuzhou"],
    "Anhui": ["Hefei", "Wuhu"]
}

COLLEGE_IDS = ['CS', 'ENG', 'ARTS', 'MED', 'SCI']


def generate_chinese_phone():
    """生成符合中国规范的11位手机号"""
    prefixes = ['13', '14', '15', '17', '18', '19']
    prefix = random.choice(prefixes)
    suffix = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return prefix + suffix


def generate_fake_id_card(birth_date, gender):
    area_codes = ['110101', '310101', '440301', '330101', '510101']
    area = random.choice(area_codes)
    birth = birth_date.strftime('%Y%m%d')
    seq_prefix = f"{random.randint(10, 99):02d}"
    seq_suffix = random.choice([1, 3, 5, 7, 9]) if gender == 'M' else random.choice([0, 2, 4, 6, 8])
    sequence = seq_prefix + str(seq_suffix)
    check_code = random.choice('0123456789X')
    return area + birth + sequence + check_code


def esc(s):
    return str(s).replace("'", "''")


def generate_students_for_year(year, count=500):
    students_data = []
    for i in range(1, count + 1):
        student_id = f"S{year}{i:06d}"
        name = fake_en.name()  # 英文名
        gender = random.choice(['M', 'F'])

        min_age = 18 + (2025 - year)
        max_age = min_age + 2
        birth_date = fake_en.date_of_birth(minimum_age=min_age, maximum_age=max_age)

        # ✅ 使用自定义函数生成中国手机号
        phone = generate_chinese_phone()

        # 英文版中国地址
        province = random.choice(CHINESE_PROVINCES_EN)
        city = random.choice(CHINESE_CITIES_EN[province])
        street = fake_en.street_address()
        hometown = f"China, {province} {city} {street}"[:48]

        college_id = random.choice(COLLEGE_IDS)
        id_card = generate_fake_id_card(birth_date, gender)

        students_data.append(
            f"('{esc(student_id)}', '{esc(name)}', '{gender}', "
            f"'{birth_date}', '{phone}', '{esc(hometown)}', "
            f"'{college_id}', '{id_card}', {year})"
        )
    return students_data


def main():
    conn = sqlite3.connect('students-ENG.db')
    cursor = conn.cursor()

    all_data = []
    for year in [2023, 2024, 2025]:
        print(f"正在生成 {year} 级 500 名学生...")
        all_data.extend(generate_students_for_year(year, 500))

    insert_query = """
    INSERT INTO "student" (
        "student_id", "name", "gender", "birth_date",
        "phone", "hometown", "college_id", "id_card", "enrollment_year"
    ) VALUES 
    """ + ", ".join(all_data)

    try:
        cursor.execute("BEGIN;")
        cursor.execute(insert_query)
        conn.commit()
        print("✅ 成功插入 1500 名中国籍学生（英文名 + 英文地址 + 中国手机号）")
    except sqlite3.IntegrityError as e:
        print("❌ 主键冲突（学号重复）:", e)
        conn.rollback()
    except Exception as e:
        print("❌ 其他错误:", e)
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    main()