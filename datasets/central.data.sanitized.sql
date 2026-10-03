SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS eschool_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eschool_central;

CREATE TABLE IF NOT EXISTS schools (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  address VARCHAR(255) NOT NULL DEFAULT '',
  support_phone VARCHAR(255) NOT NULL DEFAULT '',
  support_email VARCHAR(255) NOT NULL DEFAULT '',
  tagline VARCHAR(255) NOT NULL DEFAULT '',
  logo VARCHAR(255) NOT NULL DEFAULT '',
  admin_id INT NULL,
  status INT NOT NULL DEFAULT 1,
  code VARCHAR(255) NULL,
  database_name VARCHAR(255) NULL,
  domain VARCHAR(255) NULL,
  installed INT NOT NULL DEFAULT 1,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS system_settings (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL UNIQUE,
  data VARCHAR(255) NOT NULL,
  type VARCHAR(255) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS packages (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NULL,
  description VARCHAR(255) NULL,
  status INT NOT NULL DEFAULT 0,
  created_at DATETIME NULL,
  updated_at DATETIME NULL,
  deleted_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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

INSERT INTO schools (id, name, code, database_name, status, installed, address, support_email, created_at) VALUES
 (1, 'Demo School A', 'DEMOA', 'eschool_tenant_a', 1, 1, '100 Demo Ave', 'admin-a@example.test', NOW()),
 (2, 'Demo School B', 'DEMOB', 'eschool_tenant_b', 1, 1, '200 Demo Ave', 'admin-b@example.test', NOW());
INSERT INTO system_settings (name, data, type) VALUES ('web_maintenance', '0', 'text');
INSERT INTO packages (name, description, status, created_at) VALUES ('Basic', 'Starter', 1, NOW());
INSERT INTO users (first_name, last_name, email, password, status, created_at) VALUES ('Super', 'Admin', 'admin@eschool.test', '$2b$12$xWqCA03i8foiT.vsqJAhkePsyJxhHXq8O1.zb.qeWJ70IY3MHqAiu', 1, NOW());
