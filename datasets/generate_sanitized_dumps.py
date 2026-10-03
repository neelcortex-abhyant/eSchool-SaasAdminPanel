#!/usr/bin/env python3
"""Generate sanitized MySQL dumps for central + two tenants (offline seed).

These dumps are intentional synthetic fixtures for migration contract work.
They contain no production PII. Load with Docker MySQL when available:

  docker compose -f ops/docker-compose.phase0.yml up -d
  ./datasets/load_mysql.sh
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets"


def esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


SCHEMA_CENTRAL = """
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
"""

SCHEMA_TENANT = """
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
"""

# bcrypt hash for password "secret" generated at seed time by Python if needed;
# placeholder replaced by script.
BCRYPT_PLACEHOLDER = "__BCRYPT_SECRET__"


def tenant_seed(school_id: int, code: str) -> str:
    return f"""
INSERT INTO session_years (id, name, `default`, start_date, end_date, school_id, created_at) VALUES
 (1, '2026', 1, '2026-01-01', '2026-12-31', {school_id}, NOW());
INSERT INTO mediums (id, name, school_id, created_at) VALUES (1, 'English', {school_id}, NOW());
INSERT INTO sections (id, name, school_id, created_at) VALUES (1, 'A', {school_id}, NOW());
INSERT INTO classes (id, name, include_semesters, medium_id, school_id, created_at) VALUES
 (1, 'Grade 1', 0, 1, {school_id}, NOW());
INSERT INTO class_sections (id, class_id, section_id, medium_id, school_id, created_at) VALUES
 (1, 1, 1, 1, {school_id}, NOW());
INSERT INTO users (id, first_name, last_name, email, password, status, school_id, country_code, current_address, permanent_address, gender, created_at) VALUES
 (1, 'Ada', 'Student', 'GR001', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', '12 Demo Street', '12 Demo Street', 'female', NOW()),
 (2, 'Sam', 'Student', 'student@school.test', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', NULL, NULL, 'male', NOW()),
 (3, 'Grace', 'Guardian', 'guardian@school.test', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', NULL, NULL, 'female', NOW()),
 (4, 'Tara', 'Teacher', 'teacher@school.test', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', NULL, NULL, 'female', NOW()),
 (5, 'Alice', 'Admin', 'schooladmin@{code.lower()}.test', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', NULL, NULL, 'female', NOW()),
 (6, 'Dan', 'Driver', 'driver@{code.lower()}.test', '{BCRYPT_PLACEHOLDER}', 1, {school_id}, '+91', NULL, NULL, 'male', NOW());
INSERT INTO roles (id, name, guard_name, school_id, created_at) VALUES
 (1, 'Student', 'web', {school_id}, NOW()),
 (2, 'Guardian', 'web', {school_id}, NOW()),
 (3, 'Teacher', 'web', {school_id}, NOW()),
 (4, 'School Admin', 'web', {school_id}, NOW()),
 (5, 'Driver', 'web', {school_id}, NOW());
INSERT INTO model_has_roles (role_id, model_type, model_id) VALUES
 (1, 'App\\\\Models\\\\User', 1),
 (1, 'App\\\\Models\\\\User', 2),
 (2, 'App\\\\Models\\\\User', 3),
 (3, 'App\\\\Models\\\\User', 4),
 (4, 'App\\\\Models\\\\User', 5),
 (5, 'App\\\\Models\\\\User', 6);
INSERT INTO students (id, user_id, class_section_id, admission_no, roll_number, admission_date, school_id, guardian_id, session_year_id, created_at) VALUES
 (1, 1, 1, 'GR001', 1, '2026-04-01', {school_id}, 3, 1, NOW());
"""


def main() -> None:
    import bcrypt

    pwd = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    OUT.mkdir(parents=True, exist_ok=True)

    central = [
        "SET NAMES utf8mb4;",
        "CREATE DATABASE IF NOT EXISTS eschool_central CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        "USE eschool_central;",
        SCHEMA_CENTRAL,
        "INSERT INTO schools (id, name, code, database_name, status, installed, address, support_email, created_at) VALUES",
        " (1, 'Demo School A', 'DEMOA', 'eschool_tenant_a', 1, 1, '100 Demo Ave', 'admin-a@example.test', NOW()),",
        " (2, 'Demo School B', 'DEMOB', 'eschool_tenant_b', 1, 1, '200 Demo Ave', 'admin-b@example.test', NOW());",
        "INSERT INTO system_settings (name, data, type) VALUES ('web_maintenance', '0', 'text');",
        "INSERT INTO packages (name, description, status, created_at) VALUES ('Basic', 'Starter', 1, NOW());",
        f"INSERT INTO users (first_name, last_name, email, password, status, created_at) VALUES ('Super', 'Admin', 'admin@eschool.test', '{pwd}', 1, NOW());",
    ]
    (OUT / "central.schema.sql").write_text(SCHEMA_CENTRAL)
    (OUT / "central.data.sanitized.sql").write_text("\n".join(central) + "\n")

    for school_id, code, dbname in [
        (1, "DEMOA", "eschool_tenant_a"),
        (2, "DEMOB", "eschool_tenant_b"),
    ]:
        body = [
            "SET NAMES utf8mb4;",
            f"CREATE DATABASE IF NOT EXISTS {dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
            f"USE {dbname};",
            SCHEMA_TENANT,
            tenant_seed(school_id, code).replace(BCRYPT_PLACEHOLDER, pwd),
        ]
        (OUT / f"{dbname}.schema.sql").write_text(SCHEMA_TENANT)
        (OUT / f"{dbname}.data.sanitized.sql").write_text("\n".join(body) + "\n")

    (OUT / "MANIFEST.md").write_text(
        f"""# Sanitized dataset manifest

Generated offline for Phase 0/1 gates.

| Database | Files | Purpose |
| --- | --- | --- |
| `eschool_central` | `central.schema.sql`, `central.data.sanitized.sql` | Central schools/settings |
| `eschool_tenant_a` | `eschool_tenant_a.schema.sql`, `eschool_tenant_a.data.sanitized.sql` | Tenant A (`DEMOA`) |
| `eschool_tenant_b` | `eschool_tenant_b.schema.sql`, `eschool_tenant_b.data.sanitized.sql` | Tenant B (`DEMOB`) |

All emails/phones/addresses are synthetic. Password for seeded users: `secret`.

Load: `./datasets/load_mysql.sh` (requires Docker MySQL from `ops/docker-compose.phase0.yml`).
Local SQLite mirror for golden capture: `python3 datasets/seed_sqlite_mirror.py`.
"""
    )
    print("Wrote sanitized dumps to", OUT)


if __name__ == "__main__":
    main()
