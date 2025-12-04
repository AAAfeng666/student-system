# app/db.py
from flask import g
from werkzeug.security import generate_password_hash
import sqlite3
from config import Config

DATABASE = Config.DATABASE

def get_db_connection():
    """使用 flask.g 管理数据库连接，避免多线程锁和泄漏"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            DATABASE,
            timeout=20.0,
            check_same_thread=False
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

def close_db(error):
    """请求结束时关闭数据库连接，出错则回滚"""
    db = g.pop('db', None)
    if db is not None:
        if error:
            db.rollback()
        db.close()

def init_admin():
    """初始化管理员账号"""
    conn = get_db_connection()
    admin = conn.execute("SELECT 1 FROM account WHERE username = 'admin'").fetchone()
    if not admin:
        hashed = generate_password_hash('admin123')
        conn.execute(
            "INSERT INTO account (username, password_hash, role, user_id, is_active) VALUES (?, ?, ?, ?, ?)",
            ('admin', hashed, 'admin', '1', 1)
        )
        conn.commit()
        print("✅ 自动创建管理员账号: admin / admin123")