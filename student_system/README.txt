管理员账号：admin      密码：admin123
老师测试账号： admin2    密码：123
学生测试账号： admin3    密码：123

run.py 运行文件

templates 文件是html前端模板：Admin是管理员模块，student是学生模块，teacher是老师模块，base是基础模板（定义头部、导航栏、页脚等）

app文件是py文件：

_init_.py      分别导入不同的py模块，写了的新模块记得在这里加上
auth.py       登录模块
main.py      增加管理员，老师，学生的仪表盘页面
admin.py     增加管理员管理功能模块
teacher.py，student.py     分别是老师和学生的功能模块
course.py       选课功能模块
db.py      初始化数据库，管理员数据
config.py     配置文件

所有的.py文件都集成在_init_.py


