-- 学院
INSERT OR IGNORE INTO college (college_id, college_name, address, phone)
VALUES 
('CS', '计算机科学与技术学院', '信息楼A座', '010-88889999'),
('EE', '电子工程学院', '实验楼B座', '010-88886666');

-- 教师
INSERT OR IGNORE INTO teacher (teacher_id, name, gender, birth_date, salary, title, college_id)
VALUES 
('T1001', '张伟', 'M', '1980-05-10', 10000.00, '副教授', 'CS'),
('T1002', '李芳', 'F', '1985-12-22', 9500.00, '讲师', 'EE');

-- 学生
INSERT OR IGNORE INTO student (student_id, name, gender, birth_date, phone, hometown, college_id)
VALUES 
('S2025001', '王明', 'M', '2003-03-15', '13800138001', '北京市', 'CS'),
('S2025002', '赵雪', 'F', '2004-07-30', '13800138002', '上海市', 'EE');

