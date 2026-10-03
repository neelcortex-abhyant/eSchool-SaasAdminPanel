SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS eschool_tenant_b CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eschool_tenant_b;

CREATE TABLE IF NOT EXISTS users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  first_name VARCHAR(128) NOT NULL,
  last_name VARCHAR(128) NOT NULL,
  mobile VARCHAR(255) NULL,
  email VARCHAR(255) NOT NULL,
  password VARCHAR(255) NOT NULL,
  gender VARCHAR(16) NULL,
  image VARCHAR(512) NULL,
  dob DATE NULL,
  country_code VARCHAR(32) NULL,
  current_address VARCHAR(512) NULL,
  permanent_address VARCHAR(512) NULL,
  occupation VARCHAR(255) NULL,
  status INT NOT NULL DEFAULT 1,
  reset_request INT NOT NULL DEFAULT 0,
  fcm_id VARCHAR(1024) NULL,
  school_id INT NULL,
  email_verified_at DATETIME NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS roles (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  guard_name VARCHAR(255) NOT NULL DEFAULT 'web',
  school_id INT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS model_has_roles (
  role_id INT NOT NULL,
  model_type VARCHAR(255) NOT NULL,
  model_id INT NOT NULL,
  PRIMARY KEY (role_id, model_id, model_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS personal_access_tokens (
  id INT PRIMARY KEY AUTO_INCREMENT,
  tokenable_type VARCHAR(255) NOT NULL,
  tokenable_id INT NOT NULL,
  name VARCHAR(255) NOT NULL,
  token VARCHAR(64) NOT NULL UNIQUE,
  abilities TEXT NULL,
  last_used_at DATETIME NULL,
  expires_at DATETIME NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS session_years (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(512) NOT NULL,
  `default` INT NOT NULL DEFAULT 0,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  school_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS mediums (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(512) NOT NULL,
  school_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS sections (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(512) NOT NULL,
  school_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS classes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(512) NOT NULL,
  include_semesters INT NOT NULL DEFAULT 0,
  medium_id INT NOT NULL,
  school_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS class_sections (
  id INT PRIMARY KEY AUTO_INCREMENT,
  class_id INT NOT NULL,
  section_id INT NOT NULL,
  medium_id INT NOT NULL,
  school_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS students (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  class_section_id INT NOT NULL,
  admission_no VARCHAR(512) NOT NULL,
  roll_number INT NULL,
  admission_date DATE NOT NULL,
  school_id INT NOT NULL,
  guardian_id INT NOT NULL,
  session_year_id INT NOT NULL,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


INSERT INTO session_years (id, name, `default`, start_date, end_date, school_id, created_at) VALUES
 (1, '2026', 1, '2026-01-01', '2026-12-31', 2, NOW());
INSERT INTO mediums (id, name, school_id, created_at) VALUES (1, 'English', 2, NOW());
INSERT INTO sections (id, name, school_id, created_at) VALUES (1, 'A', 2, NOW());
INSERT INTO classes (id, name, include_semesters, medium_id, school_id, created_at) VALUES
 (1, 'Grade 1', 0, 1, 2, NOW());
INSERT INTO class_sections (id, class_id, section_id, medium_id, school_id, created_at) VALUES
 (1, 1, 1, 1, 2, NOW());
INSERT INTO users (id, first_name, last_name, email, password, status, school_id, country_code, current_address, permanent_address, gender, created_at) VALUES
 (1, 'Ada', 'Student', 'GR001', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', '12 Demo Street', '12 Demo Street', 'female', NOW()),
 (2, 'Sam', 'Student', 'student@school.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', NULL, NULL, 'male', NOW()),
 (3, 'Grace', 'Guardian', 'guardian@school.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', NULL, NULL, 'female', NOW()),
 (4, 'Tara', 'Teacher', 'teacher@school.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', NULL, NULL, 'female', NOW()),
 (5, 'Alice', 'Admin', 'schooladmin@demob.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', NULL, NULL, 'female', NOW()),
 (6, 'Dan', 'Driver', 'driver@demob.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, 2, '+91', NULL, NULL, 'male', NOW());
INSERT INTO roles (id, name, guard_name, school_id, created_at) VALUES
 (1, 'Student', 'web', 2, NOW()),
 (2, 'Guardian', 'web', 2, NOW()),
 (3, 'Teacher', 'web', 2, NOW()),
 (4, 'School Admin', 'web', 2, NOW()),
 (5, 'Driver', 'web', 2, NOW());
INSERT INTO model_has_roles (role_id, model_type, model_id) VALUES
 (1, 'App\\Models\\User', 1),
 (1, 'App\\Models\\User', 2),
 (2, 'App\\Models\\User', 3),
 (3, 'App\\Models\\User', 4),
 (4, 'App\\Models\\User', 5),
 (5, 'App\\Models\\User', 6);
INSERT INTO students (id, user_id, class_section_id, admission_no, roll_number, admission_date, school_id, guardian_id, session_year_id, created_at) VALUES
 (1, 1, 1, 'GR001', 1, '2026-04-01', 2, 3, 1, NOW());

