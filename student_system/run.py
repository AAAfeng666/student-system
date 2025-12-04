from app import create_app
from app.db import init_admin
import os

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        init_admin()

    if not os.path.exists(app.config['DATABASE']):
        print(f"⚠️ 警告：数据库 {app.config['DATABASE']} 不存在！")

    app.run(debug=True, threaded=False)