Test Accounts
Administrator account: admin Password: admin123
Teacher test account: admin2 Password: 123
Student test account: admin3 Password: 123

1. Frontend Templates (templates)
Admin: Administrator module pages
Student: Student module pages
Teacher: Teacher module pages
Base: Base template (defines header, navigation bar, footer, etc.)

2. Backend Code (app)
__init__.py: Imports all modules; new modules must be registered here
auth.py: Login module
main.py: Dashboard pages for administrator, teacher, and student
admin.py: Administrator management functions
teacher.py / student.py: Teacher and student functional modules
course.py: Course selection module
db.py: Database initialization, including administrator data
config.py: Configuration file
All .py files are integrated in __init__.py.

⚙️ Technology Stack
Backend: Python + Flask
Database: SQLite
Frontend: HTML + CSS (Bootstrap) + JavaScript
