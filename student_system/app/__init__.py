# app/__init__.py
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from config import Config
import os

def create_app():
    # 获取项目根目录（即 run.py 所在目录）
    # 方法：当前文件 (app/__init__.py) 的上级目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(project_root, 'templates')
    static_dir = os.path.join(project_root, 'static')

    app = Flask(__name__, template_folder=template_dir,
                static_folder=static_dir,      # 显式指定静态文件夹
                static_url_path='/static')  # 显式指定
    csrf = CSRFProtect()
    csrf.init_app(app)
    app.config['WTF_CSRF_ENABLED'] = False
    app.config.from_object(Config)

    # 注册蓝图
    from app.main import main_bp # 登录不同身份的仪表盘页面
    from app.auth import auth_bp # 登录界面、忘记密码、修改密码
    from app.admin import admin_bp # 仪表盘功能管理
    from app.course import course_bp # 选课功能
    from app.student import student_bp # 学生修改个人信息
    from app.teacher import teacher_bp  # 老师功能:查看课程信息，登记课程

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(teacher_bp)

    # 数据库连接关闭钩子
    from app.db import close_db # 初始化
    app.teardown_appcontext(close_db)

    return app