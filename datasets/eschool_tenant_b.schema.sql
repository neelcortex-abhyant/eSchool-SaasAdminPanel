
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
