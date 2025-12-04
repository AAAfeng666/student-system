-- 创建表
CREATE TABLE "college" (
	"college_id"	VARCHAR(20),
	"college_name"	VARCHAR(50) NOT NULL,
	"address"	TEXT,
	"phone"	VARCHAR(20),
	PRIMARY KEY("college_id"),
	UNIQUE("college_name")
);

CREATE TABLE "teacher" (
	"teacher_id"	VARCHAR(20),
	"name"	VARCHAR(50) NOT NULL,
	"gender"	CHAR(1),
	"birth_date"	DATE,
	"salary"	DECIMAL(10, 2),
	"title"	VARCHAR(20),
	"college_id"	VARCHAR(20),
	"id_card"	CHAR(18) NOT NULL UNIQUE,
	PRIMARY KEY("teacher_id"),
	FOREIGN KEY("college_id") REFERENCES "college"("college_id")
);

CREATE TABLE "student" (
	"student_id"	VARCHAR(20),
	"name"	VARCHAR(50) NOT NULL,
	"gender"	CHAR(1),
	"birth_date"	DATE,
	"phone"	VARCHAR(20),
	"hometown"	VARCHAR(50),
	"college_id"	VARCHAR(20),
	"id_card"	CHAR(18) NOT NULL UNIQUE,
	"enrollment_year"	INT,
	PRIMARY KEY("student_id"),
	FOREIGN KEY("college_id") REFERENCES "college"("college_id")
);

CREATE TABLE "course" (
	"course_id"	VARCHAR(20),
	"course_name"	VARCHAR(100) NOT NULL,
	"credits"	INT,
	"hours"	INT,
	"college_id"	VARCHAR(20),
	"target_grade"	INTEGER CHECK("target_grade" IN (1, 2, 3)),
	PRIMARY KEY("course_id"),
	UNIQUE("course_name"),
	FOREIGN KEY("college_id") REFERENCES "college"("college_id")
);

CREATE TABLE "semester" (
	"semester_id"	VARCHAR(20),
	"semester_name"	VARCHAR(20) NOT NULL,
	"is_current"	BOOLEAN DEFAULT FALSE,
	"selection_start"	DATE,
	"selection_end"	DATE,
	PRIMARY KEY("semester_id"),
	UNIQUE("semester_name")
);

CREATE TABLE "offered_course" (
	"offered_id"	INTEGER,
	"course_id"	VARCHAR(20),
	"teacher_id"	VARCHAR(20),
	"semester_id"	VARCHAR(20),
	"classroom"	VARCHAR(50),
	"time_slot"	VARCHAR(50),
	"capacity"	INT,
	"current_count"	INT DEFAULT 0,
	UNIQUE("course_id","teacher_id","semester_id"),
	PRIMARY KEY("offered_id" AUTOINCREMENT),
	FOREIGN KEY("course_id") REFERENCES "course"("course_id"),
	FOREIGN KEY("semester_id") REFERENCES "semester"("semester_id"),
	FOREIGN KEY("teacher_id") REFERENCES "teacher"("teacher_id")
);

CREATE TABLE "enrollment" (
	"enrollment_id"	INTEGER,
	"student_id"	VARCHAR(20),
	"offered_id"	INTEGER,
	"regular_score"	DECIMAL(5, 2),
	"exam_score"	DECIMAL(5, 2),
	"total_score"	DECIMAL(5, 2),
	PRIMARY KEY("enrollment_id" AUTOINCREMENT),
	UNIQUE("student_id","offered_id"),
	FOREIGN KEY("offered_id") REFERENCES "offered_course"("offered_id"),
	FOREIGN KEY("student_id") REFERENCES "student"("student_id")
);

CREATE TABLE "account" (
	"username"	VARCHAR(50),
	"password_hash"	TEXT NOT NULL,
	"role"	VARCHAR(20) NOT NULL CHECK("role" IN ('student', 'teacher', 'admin')),
	"user_id"	VARCHAR(20),
	"is_active"	BOOLEAN DEFAULT 1,
	PRIMARY KEY("username")
);

CREATE TABLE "messages" (
	"message_id"	INTEGER,
	"student_id"	VARCHAR(20) NOT NULL,
	"student_name"	TEXT NOT NULL,
	"title"	TEXT NOT NULL,
	"content"	TEXT NOT NULL,
	"created_at"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	"status"	TEXT DEFAULT 'open' CHECK("status" IN ('open', 'closed')),
	PRIMARY KEY("message_id" AUTOINCREMENT)
);

CREATE TABLE "replies" (
	"reply_id"	INTEGER,
	"message_id"	INTEGER NOT NULL,
	"sender_role"	TEXT NOT NULL CHECK("sender_role" IN ('student', 'admin')),
	"sender_id"	TEXT NOT NULL,
	"sender_name"	TEXT NOT NULL,
	"content"	TEXT NOT NULL,
	"created_at"	DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("reply_id" AUTOINCREMENT),
	FOREIGN KEY("message_id") REFERENCES "messages"("message_id") ON DELETE CASCADE
);